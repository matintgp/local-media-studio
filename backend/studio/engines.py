"""External inference transports. No model runtime is installed or launched here."""
import asyncio
import copy
import json
import uuid
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
import websockets

class EngineError(Exception): pass
class UnknownSubmission(EngineError): pass

def require_success(payload):
    if not isinstance(payload,dict) or payload.get('error') or payload.get('isError'):
        raise EngineError('Engine returned an error: '+str(payload)[:300])
    content=payload.get('structuredContent')
    if content is not None:
        if not isinstance(content,dict) or content.get('success') is False or content.get('valid') is False or content.get('error'):
            raise EngineError('Engine tool failed: '+str(content)[:300])
        return content
    # MCP text content may include JSON result
    for item in payload.get('content',[]):
        if item.get('type')=='text':
            try:
                doc=json.loads(item['text'])
                if isinstance(doc,dict):
                    if doc.get('success') is False or doc.get('valid') is False or doc.get('error'):
                        raise EngineError('Engine returned task failure: '+str(doc)[:300])
                    return doc
            except json.JSONDecodeError: pass
    return payload

class Comfy:
    def __init__(self, url, template):
        self.url=url; self.template=template; self._listeners={};self._progress={}
    async def listen(self,client_id):
        try:
            url=self.url.replace('http://','ws://',1)+'/ws?clientId='+client_id
            async with websockets.connect(url,open_timeout=5,max_size=8*1024**2) as ws:
                async for raw in ws:
                    if not isinstance(raw,str):continue
                    message=json.loads(raw);data=message.get('data',{});kind=message.get('type')
                    if kind=='progress' and data.get('max',0)>0:
                        self._progress[client_id]={'progress':{'phase':'sampling','status':f"{data.get('value')}/{data['max']}",'progress':100*data.get('value',0)/data['max']}}
                    elif kind in ('executing','execution_start'):
                        self._progress[client_id]={'progress':{'phase':'executing','status':str(data.get('node',''))}}
                    if kind in ('execution_success','execution_error','execution_interrupted'):break
        except (OSError,ValueError,websockets.WebSocketException):pass
        finally:self._listeners.pop(client_id,None)
    async def request(self, method, path, **kwargs):
        try:
            async with httpx.AsyncClient(base_url=self.url, timeout=12, follow_redirects=False) as client:
                r=await client.request(method,path,**kwargs); r.raise_for_status()
                return r.json() if r.content else {}
        except (httpx.HTTPError,ValueError) as e: raise EngineError(f'ComfyUI unreachable or invalid: {type(e).__name__}') from e
    async def health(self):
        return await self.request('GET','/system_stats')
    async def conflict(self):
        q=await self.request('GET','/queue')
        return bool(q.get('queue_running') or q.get('queue_pending'))
    async def validate(self, settings):
        info=await self.request('GET','/object_info')
        graph=copy.deepcopy(self.template)
        for node in graph.values():
            schema=info.get(node['class_type'])
            if not schema: raise EngineError('Missing ComfyUI node: '+node['class_type'])
            required=schema.get('input',{}).get('required',{})
            for key,value in node['inputs'].items():
                options=required.get(key)
                if options and isinstance(options[0],list) and isinstance(value,str) and value not in options[0]:
                    raise EngineError('Missing installed model/choice: '+value)
        return graph
    async def submit(self, job):
        settings=json.loads(job['settings']); graph=await self.validate(settings)
        graph['45']['inputs']['text']=settings['prompt']
        graph['41']['inputs'].update(width=int(settings.get('width',1024)),height=int(settings.get('height',1024)))
        graph['44']['inputs']['seed']=int(settings.get('seed',0))
        body={'prompt':graph,'client_id':job['id'],'extra_data':{'studio_job_id':job['id']}}
        self._listeners[job['id']]=asyncio.create_task(self.listen(job['id']))
        try: out=await self.request('POST','/prompt',json=body)
        except EngineError as e: raise UnknownSubmission(str(e)) from e
        if out.get('node_errors'): raise EngineError('ComfyUI validation errors: '+str(out['node_errors'])[:300])
        if not out.get('prompt_id'): raise UnknownSubmission('ComfyUI returned no prompt_id; do not resubmit without history/queue reconciliation')
        return out['prompt_id'],None
    async def status(self,job):
        if not job['external_id']: return 'unknown',None
        hist=await self.request('GET','/history/'+job['external_id'])
        item=hist.get(job['external_id'])
        if item:
            state=item.get('status',{}).get('status_str','')
            if state=='error':
                interrupted=any(m[0]=='execution_interrupted' for m in item.get('status',{}).get('messages',[]))
                return ('cancelled' if interrupted else 'failed'),item
            if state=='success' and item.get('status',{}).get('completed'): return 'succeeded',item
        queue=await self.request('GET','/queue')
        for label in ('queue_running','queue_pending'):
            if any(isinstance(entry,list) and len(entry)>1 and entry[1]==job['external_id'] for entry in queue.get(label,[])):
                return 'running',self._progress.get(job['id'])
        return 'unknown',None
    async def reconcile(self,job):
        if job['external_id']: return await self.status(job)
        # Correlation metadata survives an app restart even if the POST reply did not.
        history=await self.request('GET','/history?max_items=100')
        for external,item in history.items():
            prompt=item.get('prompt',[])
            if len(prompt)>3 and prompt[3].get('studio_job_id')==job['id']:
                return await self.status(dict(job,external_id=external))
        return 'unknown',None
    async def cancel(self,job):
        if not job.get('external_id'): raise EngineError('Cannot cancel an unconfirmed submission')
        q=await self.request('GET','/queue')
        if any(e[1]==job['external_id'] for e in q.get('queue_pending',[])):
            await self.request('POST','/queue',json={'delete':[job['external_id']]})
            return True
        # Targeted interrupt is supported by the installed engine. Never send a
        # blanket interrupt: the engine verifies the prompt_id again server-side.
        if any(e[1]==job['external_id'] for e in q.get('queue_running',[])):
            await self.request('POST','/interrupt',json={'prompt_id':job['external_id']})
        return False


def parse_mcp(body, content_type):
    if 'text/event-stream' in content_type:
        events=[]; frame=[]
        for line in body.splitlines()+['']:
            if line.startswith('data:'): frame.append(line[5:].strip())
            elif not line and frame:
                events.append('\n'.join(frame));frame=[]
        if not events: raise EngineError('Empty MCP SSE response')
        body=events[-1]
    try: doc=json.loads(body)
    except (ValueError,TypeError) as e: raise EngineError('Malformed MCP JSON-RPC') from e
    if not isinstance(doc,dict) or doc.get('error'): raise EngineError('MCP protocol error: '+str(doc)[:300])
    return doc.get('result',{})

class Wan:
    """Constrained MCP Streamable HTTP client with session/context recovery.

    A lost generate reply stays unknown: it is NEVER automatically replayed.
    """
    def __init__(self,url,state_path=None):
        self.url=url;self.session=None;self.context=None;self.seq=0
        self.protocol='2025-03-26'; self.state_path=state_path
        self._connect_lock=asyncio.Lock()
        if state_path and state_path.is_file():
            try: self.context=json.loads(state_path.read_text('utf-8')).get('context')
            except (ValueError,OSError): pass
    async def rpc(self,method,params=None, notification=False, refresh=True):
        self.seq+=1
        body={'jsonrpc':'2.0','method':method}
        if not notification:body['id']=self.seq
        if params is not None:body['params']=params
        headers={'Accept':'application/json, text/event-stream','Content-Type':'application/json','MCP-Protocol-Version':self.protocol}
        if self.session: headers['Mcp-Session-Id']=self.session
        try:
            async with httpx.AsyncClient(timeout=30,follow_redirects=False) as client:
                r=await client.post(self.url,json=body,headers=headers)
            if r.status_code==404 and self.session and refresh and method!='initialize':
                self.session=None
                # Tool calls may have performed a side effect before the session expired.
                # Never replay an ambiguous generate/postprocess/upload request automatically.
                action=(params or {}).get('arguments',{}).get('action')
                safe_tool=(params or {}).get('name') in ('wangp_workspace','wangp_model','wangp_validate') or ((params or {}).get('name')=='wangp_session' and action in ('get_job','list_queue','get_upload'))
                if method=='tools/call' and not safe_tool:
                    self.context=None
                    raise UnknownSubmission('WanGP MCP session expired during a tool call; job not replayed')
                await self.connect()
                return await self.rpc(method,params,notification,False)
            r.raise_for_status()
            self.session=r.headers.get('Mcp-Session-Id',self.session)
            return {} if notification else parse_mcp(r.text,r.headers.get('content-type','application/json'))
        except httpx.HTTPError as e: raise EngineError('WanGP MCP connection failed: '+type(e).__name__) from e
    async def connect(self):
        async with self._connect_lock:
            if self.session: return {'protocolVersion':self.protocol}
            result=await self.rpc('initialize',{'protocolVersion':self.protocol,'capabilities':{},'clientInfo':{'name':'local-media-studio','version':'0.2.0'}})
            if not result.get('protocolVersion'): raise EngineError('WanGP MCP initialization failed')
            self.protocol=result['protocolVersion']
            await self.rpc('notifications/initialized',notification=True)
            return result
    async def tool(self,name,args):
        if not self.session: await self.connect()
        return require_success(await self.rpc('tools/call',{'name':name,'arguments':args}))
    async def health(self):
        if not self.session: await self.connect()
        return await self.rpc('tools/list',{})
    async def workspace(self):
        if self.context: return self.context
        data=await self.tool('wangp_workspace',{'action':'current'})
        ctx=data.get('agent_context') or data.get('workspace',{}).get('agent_context')
        if not ctx: raise EngineError('WanGP did not return agent_context')
        self.context=ctx
        if self.state_path:
            tmp=self.state_path.with_suffix('.tmp')
            tmp.write_text(json.dumps({'context':ctx}),encoding='utf-8')
            tmp.replace(self.state_path)
        return ctx
    async def conflict(self):
        data=await self.tool('wangp_session',{'action':'list_queue','arguments':{},'agent_context':await self.workspace()})
        if 'total_count' not in data: raise EngineError('WanGP queue activity is unconfirmed')
        return int(data['total_count']) > 0

    async def upload(self,path,gallery=False):
        """Upload only an app-authorized file; ticket destinations stay on MCP origin."""
        ctx=await self.workspace()
        action='create_gallery_upload' if gallery else 'create_file_upload'
        args={'filename':path.name}
        if not gallery: args['size_bytes']=path.stat().st_size
        ticket=await self.tool('wangp_session',{'action':action,'arguments':args,'agent_context':ctx})
        target=urljoin(self.url,ticket.get('upload_url',''))
        base=urlparse(self.url); parsed=urlparse(target)
        if (parsed.scheme,parsed.netloc)!=(base.scheme,base.netloc) or not parsed.path.startswith('/wangp_api/'):
            raise EngineError('Upload destination outside configured engine')
        if path.stat().st_size>min(ticket.get('max_bytes',256*1024**2),256*1024**2):
            raise EngineError('Input exceeds engine upload limit')
        chunk_size=min(ticket.get('chunk_bytes',4*1024**2),4*1024**2)
        result={}; offset=0
        async with httpx.AsyncClient(timeout=60,follow_redirects=False) as client:
            with path.open('rb') as reader:
                while chunk:=reader.read(chunk_size):
                    r=await client.put(target,content=chunk,headers={'Upload-Offset':str(offset),'Content-Type':'application/octet-stream'})
                    r.raise_for_status(); result=r.json(); offset+=len(chunk)
        if result.get('status') not in ('uploaded','done','complete') or not (result.get('path') or result.get('media_id')):
            raise EngineError('Upload did not publish a usable engine reference')
        return result
    async def validate(self,settings):
        ctx=await self.workspace()
        if settings.get('kind')=='ambience': return ctx
        native={k:v for k,v in settings.items() if k!='kind'}
        validation=await self.tool('wangp_validate',{'settings':native,'agent_context':ctx})
        if validation.get('valid') is not True: raise EngineError('WanGP rejected settings: '+str(validation)[:250])
        if any(t.get('availability',{}).get('available') is False for t in validation.get('tasks',[])):
            raise EngineError('WanGP model is not installed; no downloads are attempted')
        return ctx
    async def submit(self,job):
        settings=json.loads(job['settings'])
        for local in ('_image_path','_video_path','start_asset_id','video_asset_id'):
            settings.pop(local,None)
        if job.get('_image_path'):
            uploaded=await self.upload(Path(job['_image_path']))
            settings['image_start']=uploaded['path']
        if job.get('_video_path'):
            uploaded=await self.upload(Path(job['_video_path']),gallery=True)
            settings['media_id']=uploaded['media_id']
        if job['kind']!='ambience':
            defaults=await self.tool('wangp_model',{'model_type':settings['model_type'],'action':'defaults'})
            # Runtime defaults may be exposed directly or nested by engine version.
            baseline=defaults.get('settings',defaults)
            if isinstance(baseline,dict): settings={**baseline,**settings}
        ctx=await self.validate(settings)
        if job['kind']=='ambience':
            args={'media':settings['media_id'],'action':'mmaudio','arguments':{'prompt':settings['prompt'],'negative_prompt':settings.get('negative_prompt',''),'seed':settings.get('seed',0)},'agent_context':ctx,'wait':False,'request_id':job['request_id']}
            name='wangp_postprocess'
        else:
            args={'settings':{k:v for k,v in settings.items() if k!='kind'},'agent_context':ctx,'wait':False,'request_id':job['request_id']}
            name='wangp_generate'
        try:result=await self.tool(name,args)
        except EngineError as e: raise UnknownSubmission('WanGP submit outcome ambiguous: '+str(e)) from e
        job_id=result.get('job_id') or result.get('job',{}).get('id')
        if not job_id: raise UnknownSubmission('WanGP returned no job_id; requires reconciliation')
        return job_id,ctx
    async def status(self,job):
        if not job['external_id']: return 'unknown',None
        ctx=job.get('context') or await self.workspace()
        data=await self.tool('wangp_session',{'action':'get_job','arguments':{'job_id':job['external_id'],'wait_s':0,'event_limit':3},'agent_context':ctx})
        if data.get('done'):
            result=data.get('result',{})
            return ('cancelled' if result.get('cancelled') else 'succeeded' if result.get('success') is True and not result.get('errors') else 'failed'),data
        return 'running',data
    async def reconcile(self,job): return await self.status(job)
    async def cancel(self,job):
        if not job.get('external_id') or not job.get('context'): raise EngineError('Cancellation ownership unconfirmed')
        await self.tool('wangp_session',{'action':'cancel_job','arguments':{'job_id':job['external_id']},'agent_context':job['context']})
        return False
