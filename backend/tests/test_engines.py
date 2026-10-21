import json
import pytest
from studio.engines import parse_mcp,require_success,EngineError,Wan

def test_mcp_sse_and_tool_success():
    s='event: message\ndata: '+json.dumps({'jsonrpc':'2.0','id':1,'result':{'structuredContent':{'valid':True,'success':True}}})+'\n\n'
    assert require_success(parse_mcp(s,'text/event-stream'))['valid']
    for x in ({'isError':True},{'structuredContent':{'success':False}},{'error':{'code':-1}}):
        with pytest.raises(EngineError):require_success(x)

def test_mcp_protocol_error():
    with pytest.raises(EngineError):parse_mcp('{"error":{"code":-32000}}','application/json')

@pytest.mark.asyncio
async def test_wan_request_id_persisted(monkeypatch):
    w=Wan('http://127.0.0.1:7866/mcp')
    calls=[]
    async def tool(name,args):
        calls.append((name,args))
        if name=='wangp_generate':return {'job_id':'job-one'}
        return {'available':True,'valid':True}
    monkeypatch.setattr(w,'tool',tool)
    async def workspace():return 'sandbox-context'
    monkeypatch.setattr(w,'workspace',workspace)
    row={'kind':'speech','id':'local-job','request_id':'stable-request','settings':json.dumps({'kind':'speech','model_type':'omnivoice','prompt':'Hello'})}
    eid,ctx=await w.submit(row)
    assert eid=='job-one' and ctx=='sandbox-context'
    assert calls[-1][1]['request_id']=='stable-request' and calls[-1][1]['wait'] is False

@pytest.mark.asyncio
async def test_expired_session_does_not_replay_tool_call(monkeypatch):
    import httpx
    from studio.engines import UnknownSubmission
    sent=[]
    def handler(req):
        sent.append(json.loads(req.content))
        return httpx.Response(404,json={'error':'session expired'})
    transport=httpx.MockTransport(handler)
    original=httpx.AsyncClient
    def fake_client(*args,**kwargs):
        kwargs['transport']=transport
        return original(*args,**kwargs)
    monkeypatch.setattr(httpx,'AsyncClient',fake_client)
    w=Wan('http://127.0.0.1:7866/mcp')
    w.session='expired-session'
    with pytest.raises(UnknownSubmission):
        await w.rpc('tools/call',{'name':'wangp_generate','arguments':{'request_id':'stable'}})
    assert len(sent)==1
    assert sent[0]['params']['arguments']['request_id']=='stable'
    assert w.session is None
