"""HTTP API and crash-conservative single GPU scheduler."""
import asyncio
import json
import mimetypes
import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .core import KINDS, Store, canonical_json, config, ensure_space, secure_path, uid
from .engines import Comfy, Wan, EngineError, UnknownSubmission
from .media import MediaError, generate_demo, probe, render_composition

CONFIG=config()
STORE=Store(CONFIG['root'])
TEMPLATE=Path(__file__).resolve().parents[2]/'examples'/'recipes'/'z-image-comfy-api.json'
COMFY=Comfy(CONFIG['comfy'],json.loads(TEMPLATE.read_text(encoding='utf-8'))) if TEMPLATE.exists() else None
WAN=Wan(CONFIG['wan'],STORE.root/'wan-session.json')

MODELS={
    'image':{'engine':'comfy','model':'z-image-turbo-nunchaku'},
    'video':{'engine':'wan','model_type':'ti2v_2_2_fastwan','resolution':'640x640','video_length':121,'force_fps':24,'num_inference_steps':3,'guidance_scale':1,'flow_shift':3,'image_prompt_type':'S'},
    'speech':{'engine':'wan','model_type':'omnivoice','model_mode':'persian','num_inference_steps':32,'duration_seconds':0},
    'music':{'engine':'wan','model_type':'ace_step_v1_5_turbo_lm_0_6b','num_inference_steps':8,'duration_seconds':24,'prompt':'[Instrumental]'},
    'ambience':{'engine':'wan','model_type':'mmaudio'}
}

class ProjectIn(BaseModel):
    name:str=Field(min_length=1,max_length=100)
    brief:str=Field(default='',max_length=3000)
    aspect:str='1:1'
    language:str='fa'
    archived:bool=False
class GenerateIn(BaseModel):
    project_id:str
    kind:str
    settings:dict=Field(default_factory=dict)
class WorkflowIn(BaseModel):
    project_id:str
    name:str=Field(min_length=1,max_length=100)
    steps:list[dict]
class ExportIn(BaseModel):
    project_id:str
    shots:list[dict]
    tracks:list[dict]=Field(default_factory=list)
    width:int=640
    height:int=640
    fps:int=24
    duck:bool=True
    subtitle_asset_id:str|None=None
    wait:bool=False


def project(pid): return STORE.row('SELECT * FROM projects WHERE id=?',(pid,))
def asset(aid): return STORE.row('SELECT * FROM assets WHERE id=?',(aid,))
def job(jid): return STORE.row('SELECT * FROM jobs WHERE id=?',(jid,))
def public_job(row): return {k:v for k,v in row.items() if k!='context'}
def public_asset(row): return {k:v for k,v in row.items() if k not in ('path','external_ref')}

def normalize_settings(kind,s):
    if kind not in KINDS:raise HTTPException(422,'Unsupported modality')
    if not isinstance(s,dict):raise HTTPException(422,'Settings must be an object')
    prompt=str(s.get('prompt','')).strip()
    if not prompt:raise HTTPException(422,'Enter a prompt or speech text')
    if len(prompt)>4000:raise HTTPException(422,'Prompt too long')
    def number(key,default):
        try:
            value=s.get(key,default)
            if isinstance(value,bool) or float(value)!=int(value):raise ValueError()
            return int(value)
        except (TypeError,ValueError,OverflowError):raise HTTPException(422,f'{key} must be an integer')
    seed=number('seed',20261021)
    if not 0<=seed<2**53: raise HTTPException(422,'Seed outside supported range')
    out={'kind':kind,'seed':seed,'prompt':prompt}
    if kind=='image':
        w=number('width',1024);h=number('height',1024)
        if not 256<=w<=1536 or not 256<=h<=1536 or w%64 or h%64:raise HTTPException(422,'Image dimensions must be multiples of 64')
        out.update(width=w,height=h)
    elif kind=='video':
        a=asset(s.get('start_asset_id',''))
        if a['kind']!='image':raise HTTPException(422,'Start asset must be an image')
        out.update({k:v for k,v in MODELS['video'].items() if k!='engine'})
        resolution=s.get('resolution','640x640'); frames=number('video_length',121)
        if resolution not in ('640x640','640x384','384x640') or frames not in (81,121):raise HTTPException(422,'Use an installed 8GB video preset: 81 or 121 frames at a supported 640px canvas')
        out.update(resolution=resolution,video_length=frames)
        out['start_asset_id']=a['id']
    elif kind=='speech':
        lang=s.get('language','fa')
        if lang not in ('fa','en'):raise HTTPException(422,'Select Persian or English')
        out.update({'model_type':'omnivoice','model_mode':'persian' if lang=='fa' else 'english','num_inference_steps':32,'duration_seconds':0,'repeat_generation':1})
    elif kind=='music':
        instrumental=bool(s.get('instrumental',True))
        duration=number('duration_seconds',24)
        if not 5<=duration<=120:raise HTTPException(422,'Music duration 5–120 seconds')
        out.update({'model_type':'ace_step_v1_5_turbo_lm_0_6b','num_inference_steps':8,'duration_seconds':duration,'repeat_generation':1,'alt_prompt':prompt,'prompt':'[Instrumental]' if instrumental else str(s.get('lyrics',''))[:4000]})
    elif kind=='ambience':
        a=asset(s.get('video_asset_id',''))
        if a['kind']!='video' and a['kind']!='ambience':raise HTTPException(422,'Ambience input must be a video')
        out.update(media_id=a.get('external_ref'),video_asset_id=a['id'],negative_prompt=str(s.get('negative_prompt',''))[:2000])
    return out

async def settle_output(jobrow, payload):
    existing=STORE.rows('SELECT id FROM assets WHERE job_id=?',(jobrow['id'],))
    if existing: return existing[0]['id']
    kind=jobrow['kind']
    if jobrow['mode']=='mock':
        f=await asyncio.to_thread(generate_demo,STORE.root,kind,CONFIG['ffmpeg'])
        meta=await asyncio.to_thread(probe,f,CONFIG['ffprobe']) if kind!='image' else {'width':640,'height':640}
        return STORE.insert_asset(jobrow['project_id'],kind,'mock',f,jobrow['id'],meta|{'demo':True,'settings':json.loads(jobrow['settings'])})
    if jobrow['engine']=='comfy':
        history=payload or {}
        outputs=history.get('outputs',{})
        refs=[r for o in outputs.values() for r in (o.get('images',[])+o.get('videos',[])+o.get('audio',[]))]
        if not refs:raise EngineError('ComfyUI finished without supported media outputs')
        ref=refs[0]
        # Never expose arbitrary path/view URLs to browser. Requires authorized output root.
        source_root=os.getenv('STUDIO_COMFY_OUTPUT_ROOT')
        if not source_root:raise EngineError('Configure STUDIO_COMFY_OUTPUT_ROOT to register ComfyUI result safely')
        p=secure_path(Path(source_root),Path(source_root)/ref.get('subfolder','')/ref['filename'])
        if not p.is_file(): raise EngineError('Comfy output is missing from its approved root')
        meta=await asyncio.to_thread(probe,p,CONFIG['ffprobe'])
        return STORE.insert_asset(jobrow['project_id'],kind,'comfy',p,jobrow['id'],meta|{'settings':json.loads(jobrow['settings'])},external_ref=canonical_json(ref))
    items=(payload or {}).get('result',{}).get('gallery_items',[])
    if not items:raise EngineError('WanGP success has no gallery items; media reference not guessed')
    item=items[0];media_id=item.get('media_id')
    if not media_id:raise EngineError('WanGP gallery item missing media_id')
    root=os.getenv('STUDIO_WAN_OUTPUT_ROOT')
    if not root: raise EngineError('Configure STUDIO_WAN_OUTPUT_ROOT')
    ref=item.get('path','')
    if not ref.startswith('@outputs/'): raise EngineError('Wan output outside configured output grant')
    p=secure_path(Path(root),Path(root)/ref[len('@outputs/'):])
    if not p.is_file(): raise EngineError('Wan output missing from configured output root')
    meta=await asyncio.to_thread(probe,p,CONFIG['ffprobe'])
    return STORE.insert_asset(jobrow['project_id'],kind,'wan',p,jobrow['id'],meta|{'settings':json.loads(jobrow['settings']),'engine_meta':item},external_ref=media_id)

async def scheduler_once():
    await advance_workflows()
    active=STORE.admission()
    if active:
        j=job(active)
        if j['state']=='unknown' and not j['external_id']:return
        if j['state'] in ('running','cancel_requested','unknown'):
            if j['mode']=='mock':
                STORE.update_job(active,'unknown','reconciling','Mock worker interrupted; manual reconciliation required');return
            adapter=COMFY if j['engine']=='comfy' else WAN
            try:state,data=await adapter.status(j)
            except EngineError as e: STORE.update_job(active,'unknown','reconciling',str(e));return
            if state=='running':
                progress=(data or {}).get('progress') or {}
                if isinstance(progress,dict):
                    pct=progress.get('progress')
                    STORE.update_job(active,'running' if j['state']=='unknown' else j['state'],progress.get('phase','running'),str(progress.get('status',''))[:300],float(pct)/100 if isinstance(pct,(int,float)) else None)
                return
            if state=='unknown':STORE.update_job(active,'unknown','reconciling','External state unconfirmed');return
            if state=='succeeded':
                try:await settle_output(j,data)
                except Exception as e:STORE.update_job(active,'unknown','output-recovery',str(e));return
            STORE.update_job(active,state,detail='Confirmed by engine');STORE.release(active)
        return
    rows=STORE.rows("SELECT * FROM jobs WHERE state='waiting' ORDER BY created,id LIMIT 1")
    if not rows:return
    j=rows[0]
    if not STORE.acquire(j['id']):return
    if j['mode']=='mock':
        STORE.update_job(j['id'],'running','rendering','CPU-only synthetic demonstration',0.1)
        try:
            await settle_output(j,None)
            STORE.update_job(j['id'],'succeeded','complete','DEMO / MOCK — not generated by AI',1)
        except Exception as e:STORE.update_job(j['id'],'failed','failed',str(e))
        finally:STORE.release(j['id'])
        return
    try:
        if not COMFY:raise EngineError('ComfyUI template unavailable')
        try: conflict=await COMFY.conflict() or await WAN.conflict()
        except EngineError as e:
            STORE.update_job(j['id'],'waiting','engine-offline',str(e));STORE.release(j['id']);return
        if conflict:
            STORE.update_job(j['id'],'waiting','external-busy','An external engine is busy; admission paused');STORE.release(j['id']);return
        adapter=COMFY if j['engine']=='comfy' else WAN
        if j['engine']=='wan':
            # Both queues were checked idle above. Release idle Comfy weights
            # before using the shared 8GB device; no files or graphs are removed.
            await COMFY.request('POST','/free',json={'unload_models':True,'free_memory':True})
            await asyncio.sleep(1)
        settings=json.loads(j['settings'])
        source=settings.get('start_asset_id') or settings.get('video_asset_id')
        if source:
            path=STORE.asset_path(asset(source))
            if j['kind']=='video': j['_image_path']=str(path)
            elif not settings.get('media_id'): j['_video_path']=str(path)
        ensure_space(STORE.root,16*1024**2,CONFIG['reserve'])
        # Set running BEFORE dispatch. Crash or lost reply cannot duplicate inference.
        STORE.update_job(j['id'],'running','submitting','External request in flight')
        external,context=await adapter.submit(j)
        with STORE.tx() as db:
            db.execute('UPDATE jobs SET external_id=?,context=?,stage=? WHERE id=?',(external,context,'loading',j['id']))
            STORE.event(db,'job',j['id'])
    except UnknownSubmission as e:
        STORE.update_job(j['id'],'unknown','reconciling',str(e))
    except Exception as e:
        STORE.update_job(j['id'],'failed','failed',str(e));STORE.release(j['id'])

async def scheduler():
    while True:
        try:await scheduler_once()
        except asyncio.CancelledError:raise
        except Exception as e:print('scheduler error:',type(e).__name__)
        await asyncio.sleep(1)

@asynccontextmanager
async def lifespan(app):
    # A prior active lease remains active. Running external jobs reattach by external ID.
    from .runtime import single_instance
    with single_instance(STORE.root):
        with STORE.tx() as db:
            db.execute("UPDATE exports SET state='failed',error='App stopped during export; sources preserved. Retry explicitly.' WHERE state='running'")
        t=asyncio.create_task(scheduler())
        e=asyncio.create_task(export_scheduler())
        try: yield
        finally:
            t.cancel();e.cancel()
            await asyncio.gather(t,e,return_exceptions=True)

app=FastAPI(title='Local Media Studio',lifespan=lifespan)

@app.middleware('http')
async def boundaries(request:Request, call_next):
    host=request.headers.get('host','').split(':')[0].lower()
    if host not in ('127.0.0.1','localhost','testserver'):return __import__('fastapi').responses.JSONResponse({'detail':'Host rejected'},400)
    if request.method not in ('GET','HEAD','OPTIONS'):
        origin=request.headers.get('origin')
        valid={'http://127.0.0.1:8787','http://localhost:8787','http://127.0.0.1:5173','http://localhost:5173'}
        valid.add('http://'+request.headers.get('host',''))
        if origin and origin not in valid:return __import__('fastapi').responses.JSONResponse({'detail':'Cross-origin write rejected'},403)
        if request.headers.get('sec-fetch-site')=='cross-site':return __import__('fastapi').responses.JSONResponse({'detail':'Cross-site write rejected'},403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='no-referrer'
    return response

@app.get('/api/status')
async def status():
    return {'mode':CONFIG['mode'],'locale':CONFIG['locale'],'admission':STORE.admission(),'free_bytes':shutil.disk_usage(STORE.root).free,'reserve_bytes':CONFIG['reserve'],'ffmpeg':shutil.which(CONFIG['ffmpeg']) is not None}

@app.get('/api/health')
async def health():
    if CONFIG['mode']=='mock':return {'comfy':{'state':'mock'},'wan':{'state':'mock'}}
    out={}
    for name,fn in [('comfy',COMFY.health if COMFY else None),('wan',WAN.health)]:
        try:
            if not fn:raise EngineError('Template missing')
            await fn();out[name]={'state':'online'}
        except Exception as e:out[name]={'state':'offline','detail':str(e)[:150]}
    return out

@app.get('/api/projects')
async def projects():return STORE.rows('SELECT * FROM projects ORDER BY created DESC')
@app.post('/api/projects')
async def create_project(p:ProjectIn):
    ident=uid()
    with STORE.tx() as db:
        db.execute('INSERT INTO projects(id,name,brief,aspect,language) VALUES(?,?,?,?,?)',(ident,p.name,p.brief,p.aspect,p.language))
        STORE.event(db,'project',ident)
    return project(ident)
@app.patch('/api/projects/{pid}')
async def patch_project(pid:str,p:ProjectIn):
    project(pid)
    with STORE.tx() as db:
        db.execute('UPDATE projects SET name=?,brief=?,aspect=?,language=?,archived=? WHERE id=?',(p.name,p.brief,p.aspect,p.language,int(p.archived),pid))
        STORE.event(db,'project',pid)
    return project(pid)

@app.get('/api/jobs')
async def jobs(project_id:str|None=None,limit:int=50):
    limit=max(1,min(100,limit))
    return [{k:v for k,v in row.items() if k!='context'} for row in STORE.rows('SELECT * FROM jobs WHERE (? IS NULL OR project_id=?) ORDER BY created DESC,id DESC LIMIT ?',(project_id,project_id,limit))]
@app.post('/api/jobs')
async def generate(inp:GenerateIn):
    project(inp.project_id)
    if len(STORE.rows("SELECT id FROM jobs WHERE state='waiting'"))>=30:raise HTTPException(429,'Queue limit reached')
    settings=normalize_settings(inp.kind,inp.settings)
    for field in ('start_asset_id','video_asset_id'):
        if settings.get(field) and asset(settings[field])['project_id']!=inp.project_id:raise HTTPException(403,'Source is not in this project')
    return public_job(enqueue(inp.project_id,inp.kind,settings))

def enqueue(pid,kind,settings,workflow=None,index=None):
    engine=MODELS[kind]['engine'];ident=uid()
    import hashlib
    payload=canonical_json(settings)
    with STORE.tx() as db:
        db.execute('INSERT INTO jobs(id,project_id,kind,mode,engine,state,settings,payload_hash,request_id) VALUES(?,?,?,?,?,?,?,?,?)',
                   (ident,pid,kind,CONFIG['mode'],engine,'waiting',payload,hashlib.sha256(payload.encode()).hexdigest(),ident))
        if workflow is not None:db.execute('INSERT INTO workflow_jobs(workflow_id,step_index,job_id) VALUES(?,?,?)',(workflow,index,ident))
        STORE.event(db,'job',ident)
    return job(ident)
@app.post('/api/jobs/{jid}/cancel')
async def cancel(jid:str):
    j=job(jid)
    if j['state']=='waiting':STORE.update_job(jid,'cancelled');return public_job(job(jid))
    if j['state']=='running':
        if j['mode']=='mock':raise HTTPException(409,'CPU demo is finishing; wait for completion')
        adapter=COMFY if j['engine']=='comfy' else WAN
        try: removed=await adapter.cancel(j)
        except EngineError as e:raise HTTPException(409,str(e))
        STORE.update_job(jid,'cancelled' if removed else 'cancel_requested','waiting-for-engine','Awaiting engine confirmation')
        if removed: STORE.release(jid)
        return public_job(job(jid))
    raise HTTPException(409,'Only waiting/running jobs can request cancellation')
@app.post('/api/jobs/{jid}/resolve')
async def resolve(jid:str):
    j=job(jid)
    if j['state']!='unknown':raise HTTPException(409,'Only unknown jobs can be reconciled')
    if not j['external_id']:raise HTTPException(409,'Submission status ambiguous; inspect external engine UI before releasing slot')
    adapter=COMFY if j['engine']=='comfy' else WAN
    try:s,payload=await adapter.reconcile(j)
    except Exception as e:raise HTTPException(503,str(e))
    if s not in ('succeeded','failed','cancelled'):raise HTTPException(409,'Engine still unconfirmed')
    if s=='succeeded':await settle_output(j,payload)
    STORE.update_job(jid,s,detail='Reconciled');STORE.release(jid)
    return public_job(job(jid))

@app.post('/api/jobs/{jid}/abandon')
async def abandon(jid:str,confirmation:dict):
    j=job(jid)
    if j['state']!='unknown' or confirmation.get('checked_engine') is not True:raise HTTPException(409,'Inspect the external engine and explicitly acknowledge unknown outcome first')
    try:
        if await COMFY.conflict() or await WAN.conflict():raise HTTPException(409,'An engine is still active; slot remains held')
    except EngineError:raise HTTPException(409,'Both engine queues must be verifiably idle')
    STORE.update_job(jid,'failed','operator-abandoned','Outcome remained unknown; operator explicitly abandoned tracking. No external task was cancelled or resubmitted.')
    STORE.release(jid)
    return {'id':jid,'state':'failed'}

@app.get('/api/assets')
async def assets(project_id:str|None=None,kind:str|None=None,limit:int=100):
    return [{k:v for k,v in row.items() if k not in ('path','external_ref')} for row in STORE.rows('SELECT * FROM assets WHERE (? IS NULL OR project_id=?) AND (? IS NULL OR kind=?) ORDER BY created DESC,id DESC LIMIT ?', (project_id,project_id,kind,kind,min(100,max(1,limit))))]
@app.get('/api/assets/{aid}/media')
async def media(aid:str):
    a=asset(aid)
    if a['path']:return FileResponse(STORE.asset_path(a))
    if a['origin']=='comfy' and a['external_ref']:
        ref=json.loads(a['external_ref'])
        root=os.getenv('STUDIO_COMFY_OUTPUT_ROOT')
        if not root:raise HTTPException(409,'Configure STUDIO_COMFY_OUTPUT_ROOT')
        try:p=secure_path(Path(root),Path(root)/ref['subfolder']/ref['filename'])
        except ValueError:raise HTTPException(403,'Unauthorized path')
        if not p.is_file():raise HTTPException(404,'Engine output missing')
        return FileResponse(p)
    raise HTTPException(409,'WanGP virtual media needs authorized workspace materialization; not a public OS path')

@app.post('/api/assets/import')
async def import_file(project_id:str,file:UploadFile):
    project(project_id)
    ext=Path(file.filename or '').suffix.lower()
    allowed={'.png':'image','.jpg':'image','.jpeg':'image','.webp':'image','.mp4':'video','.mov':'video','.wav':'audio','.mp3':'audio','.srt':'subtitle','.vtt':'subtitle'}
    if ext not in allowed:raise HTTPException(415,'Unsupported media extension')
    ident=uid();target=STORE.root/'assets'/(ident+ext);tmp=STORE.root/'staging'/(ident+'.part')
    size=0
    try:
        with tmp.open('wb') as f:
            while chunk:=await file.read(1024*1024):
                size+=len(chunk)
                if size>256*1024*1024:raise HTTPException(413,'Import exceeds 256 MiB')
                ensure_space(STORE.root,len(chunk),CONFIG['reserve'])
                f.write(chunk)
        if ext in ('.srt','.vtt'):
            try:text=tmp.read_text('utf-8')
            except UnicodeDecodeError:raise HTTPException(422,'Subtitle must be UTF-8 text')
            if len(text)>1024*1024 or '\x00' in text:raise HTTPException(422,'Malformed subtitle')
            meta={}
        else:
            try:meta=await asyncio.to_thread(probe,tmp,CONFIG['ffprobe'])
            except MediaError:meta={}
            if not meta.get('audio') and not meta.get('width'):raise HTTPException(415,'Invalid or unsupported media content')
            if allowed[ext] in ('image','video') and not meta.get('width'):raise HTTPException(415,'File does not contain the declared visual media')
            if allowed[ext]=='audio' and not meta.get('audio'):raise HTTPException(415,'File does not contain audio')
        os.replace(tmp,target)
        aid=STORE.insert_asset(project_id,allowed[ext],'import',target,meta=meta)
        return public_asset(asset(aid))
    finally:tmp.unlink(missing_ok=True)

@app.get('/api/presets')
async def presets():return STORE.rows('SELECT * FROM presets ORDER BY kind,name')
@app.post('/api/presets')
async def save_preset(data:dict):
    kind=data.get('kind');name=str(data.get('name',''))[:80]
    if kind not in KINDS or not name:raise HTTPException(422,'Valid preset kind/name required')
    normalize_settings(kind,data.get('settings',{}));s=data['settings'];ident=uid()
    with STORE.tx() as db:db.execute('INSERT INTO presets(id,name,kind,settings) VALUES(?,?,?,?)',(ident,name,kind,canonical_json(s)))
    return {'id':ident}

@app.get('/api/workflows')
async def workflows(project_id:str|None=None):
    return STORE.rows('SELECT * FROM workflows WHERE (? IS NULL OR project_id=?) ORDER BY created DESC',(project_id,project_id))
@app.post('/api/workflows')
async def create_workflow(w:WorkflowIn):
    project(w.project_id)
    if not 1<=len(w.steps)<=12 or any(step.get('kind') not in KINDS for step in w.steps):raise HTTPException(422,'Workflow requires 1–12 typed steps')
    for i,step in enumerate(w.steps):
        if step.get('input_from') is not None and (not isinstance(step['input_from'],int) or not 0<=step['input_from']<i):raise HTTPException(422,'Workflow bindings must reference an earlier step')
    ident=uid()
    with STORE.tx() as db:db.execute('INSERT INTO workflows(id,project_id,name,steps) VALUES(?,?,?,?)',(ident,w.project_id,w.name,canonical_json(w.steps)))
    return {'id':ident,'state':'draft'}
@app.post('/api/workflows/{wid}/run')
async def run_workflow(wid:str):
    w=STORE.row('SELECT * FROM workflows WHERE id=?',(wid,))
    with STORE.tx() as db:
        db.execute("DELETE FROM workflow_jobs WHERE workflow_id=? AND job_id IN (SELECT id FROM jobs WHERE state IN ('failed','cancelled'))",(wid,))
        db.execute("UPDATE workflows SET state='running' WHERE id=?",(wid,))
    return {'id':wid,'state':'running'}

async def advance_workflows():
    for w in STORE.rows("SELECT * FROM workflows WHERE state='running'"):
        steps=json.loads(w['steps']); complete=0
        for index,step in enumerate(steps):
            links=STORE.rows('SELECT j.* FROM workflow_jobs w JOIN jobs j ON j.id=w.job_id WHERE w.workflow_id=? AND w.step_index=?',(w['id'],index))
            if links:
                if links[0]['state']=='succeeded': complete+=1;continue
                if links[0]['state'] in ('failed','cancelled'):
                    with STORE.tx() as db:db.execute("UPDATE workflows SET state='failed' WHERE id=?",(w['id'],))
                break
            settings=dict(step.get('settings',{})); parent=step.get('input_from')
            key='start_asset_id' if step['kind']=='video' else 'video_asset_id' if step['kind']=='ambience' else None
            if key and parent is None and not settings.get(key):
                wanted=('image',) if key=='start_asset_id' else ('video','ambience')
                parent=next((i for i in reversed(range(index)) if steps[i]['kind'] in wanted),None)
            if parent is not None:
                outputs=STORE.rows('SELECT a.* FROM workflow_jobs w JOIN assets a ON a.job_id=w.job_id JOIN jobs j ON j.id=w.job_id WHERE w.workflow_id=? AND w.step_index=? AND j.state=?',(w['id'],parent,'succeeded'))
                if not outputs:break
                if key:settings[key]=outputs[0]['id']
            try:
                resolved=normalize_settings(step['kind'],settings)
                for k in ('start_asset_id','video_asset_id'):
                    if resolved.get(k) and asset(resolved[k])['project_id']!=w['project_id']:raise HTTPException(403,'Workflow source is not in project')
                enqueue(w['project_id'],step['kind'],resolved,w['id'],index)
            except (HTTPException,ValueError,TypeError):
                with STORE.tx() as db:db.execute("UPDATE workflows SET state='failed' WHERE id=?",(w['id'],))
            break
        if complete==len(steps):
            with STORE.tx() as db:db.execute("UPDATE workflows SET state='succeeded' WHERE id=?",(w['id'],))

@app.post('/api/exports')
async def export(inp:ExportIn):
    project(inp.project_id)
    if not shutil.which(CONFIG['ffmpeg']) or not shutil.which(CONFIG['ffprobe']):raise HTTPException(503,'Install FFmpeg and FFprobe and configure STUDIO_FFMPEG/STUDIO_FFPROBE')
    spec=inp.model_dump();ident=uid()
    for source in [x.get('asset_id') for x in inp.shots+inp.tracks]+([inp.subtitle_asset_id] if inp.subtitle_asset_id else []):
        if asset(source)['project_id']!=inp.project_id: raise HTTPException(403,'Export source is not in this project')
    with STORE.tx() as db:db.execute('INSERT INTO exports(id,project_id,state,spec) VALUES(?,?,?,?)',(ident,inp.project_id,'running' if inp.wait else 'waiting',canonical_json(spec)))
    if not inp.wait:return {'id':ident,'state':'waiting'}
    return await execute_export(ident,inp.project_id,spec)

EXPORT_LOCK=asyncio.Lock()

async def execute_export(ident,pid,spec):
    async with EXPORT_LOCK:
        return await render_export(ident,pid,spec)

async def render_export(ident,pid,spec):
    try:
        p,meta=await asyncio.to_thread(render_composition,STORE,spec,CONFIG['ffmpeg'],CONFIG['ffprobe'],CONFIG['reserve'])
        aid=STORE.insert_asset(pid,'video','composition',p,meta=meta|{'spec':spec})
        with STORE.tx() as db:db.execute("UPDATE exports SET state='succeeded',asset_id=? WHERE id=?",(aid,ident))
        return {'id':ident,'asset_id':aid,'meta':meta}
    except Exception as e:
        with STORE.tx() as db:db.execute("UPDATE exports SET state='failed',error=? WHERE id=?",(str(e),ident))
        raise HTTPException(422,detail=str(e))

async def export_scheduler():
    while True:
        rows=STORE.rows("SELECT * FROM exports WHERE state='waiting' ORDER BY created,id LIMIT 1")
        if rows:
            row=rows[0]
            with STORE.tx() as db:db.execute("UPDATE exports SET state='running' WHERE id=?",(row['id'],))
            try:await execute_export(row['id'],row['project_id'],json.loads(row['spec']))
            except HTTPException:pass
        await asyncio.sleep(1)

@app.get('/api/exports')
async def exports(project_id:str|None=None):return STORE.rows('SELECT * FROM exports WHERE (? IS NULL OR project_id=?) ORDER BY created DESC',(project_id,project_id))
@app.get('/api/events')
async def events(after:int=0):
    async def stream():
        cursor=max(0,after)
        while True:
            rows=STORE.rows('SELECT seq,event FROM events WHERE seq>? ORDER BY seq LIMIT 50',(cursor,))
            for r in rows:
                cursor=r['seq'];yield f'id: {cursor}\ndata: {r["event"]}\n\n'
            await asyncio.sleep(1)
    return StreamingResponse(stream(),media_type='text/event-stream')

FRONT=Path(__file__).resolve().parents[2]/'frontend'/'dist'
if FRONT.is_dir():
    app.mount('/',StaticFiles(directory=FRONT,html=True),name='frontend')
