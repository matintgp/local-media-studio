"""External inference transports. No model runtime is installed or launched here."""
import asyncio
import copy
import json
import uuid
from pathlib import Path

import httpx

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
    def __init__(self, url, template): self.url=url; self.template=template
    async def request(self, method, path, **kwargs):
        try:
            async with httpx.AsyncClient(base_url=self.url, timeout=12, follow_redirects=False) as client:
                r=await client.request(method,path,**kwargs); r.raise_for_status();return r.json()
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
            if state=='error': return 'failed',item
            if item.get('status',{}).get('completed') or item.get('outputs'): return 'succeeded',item
        queue=await self.request('GET','/queue')
        for label in ('queue_running','queue_pending'):
            if any(isinstance(entry,list) and len(entry)>1 and entry[1]==job['external_id'] for entry in queue.get(label,[])):
                return 'running',None
        return 'unknown',None
    async def reconcile(self,job): return await self.status(job)
    async def cancel(self,job):
        # Never issue global /interrupt or /queue clear. This adapter is deliberately conservative.
        raise EngineError('ComfyUI running cancellation is not ownership-safe; reconcile and wait')


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
    def __init__(self,url): self.url=url;self.session=None;self.context=None;self.seq=0
    async def rpc(self,method,params=None, notification=False, refresh=True):
        self.seq+=1
        body={'jsonrpc':'2.0','method':method}
        if not notification:body['id']=self.seq
        if params is not None:body['params']=params
        headers={'Accept':'application/json, text/event-stream','Content-Type':'application/json','MCP-Protocol-Version':'2025-03-26'}
        if self.session: headers['Mcp-Session-Id']=self.session
        try:
            async with httpx.AsyncClient(timeout=30,follow_redirects=False) as client:
                r=await client.post(self.url,json=body,headers=headers)
            if r.status_code==404 and self.session and refresh and method!='initialize':
                self.session=None;self.context=None
                # Tool calls may have performed a side effect before the session expired.
                # Never replay an ambiguous generate/postprocess/upload request automatically.
                if method=='tools/call':
                    raise UnknownSubmission('WanGP MCP session expired during a tool call; job not replayed')
                await self.connect()
                return await self.rpc(method,params,notification,False)
            r.raise_for_status()
            self.session=r.headers.get('Mcp-Session-Id',self.session)
            return {} if notification else parse_mcp(r.text,r.headers.get('content-type','application/json'))
        except httpx.HTTPError as e: raise EngineError('WanGP MCP connection failed: '+type(e).__name__) from e
    async def connect(self):
        self.session=None;self.context=None
        result=await self.rpc('initialize',{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'local-media-studio','version':'0.1.0'}})
        if not result.get('protocolVersion'): raise EngineError('WanGP MCP initialization failed')
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
        self.context=ctx; return ctx
    async def conflict(self):
        # Engine activity cannot reliably be inferred without a supported global status tool.
        # Fail closed if discovery does not explicitly expose one.
        tools=await self.health()
        names={x.get('name') for x in tools.get('tools',[])}
        if 'wangp_session' not in names: raise EngineError('Cannot inspect WanGP session/queue')
        try:
            data=await self.tool('wangp_session',{'action':'list_jobs','agent_context':await self.workspace()})
        except EngineError as e:
            raise EngineError('WanGP external activity could not be verified; dispatch blocked') from e
        return any(j.get('status') not in ('done','failed','cancelled') for j in data.get('jobs',[]))
    async def validate(self,settings):
        ctx=await self.workspace()
        if settings.get('kind')=='ambience': return ctx
        model=settings.get('model_type')
        availability=await self.tool('wangp_model',{'model_type':model,'action':'availability'})
        if availability.get('available') is False:raise EngineError('WanGP model unavailable: '+str(model))
        validation=await self.tool('wangp_validate',{'settings':settings,'agent_context':ctx})
        if validation.get('valid') is not True: raise EngineError('WanGP rejected settings: '+str(validation)[:250])
        return ctx
    async def submit(self,job):
        settings=json.loads(job['settings']);ctx=await self.validate(settings)
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
            return ('succeeded' if result.get('success') is True and not result.get('errors') else 'failed'),data
        return 'running',data
    async def reconcile(self,job): return await self.status(job)
    async def cancel(self,job):
        raise EngineError('Cancellation requires confirmed ownership-specific WanGP contract')
