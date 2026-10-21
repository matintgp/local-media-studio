import importlib
import json
import httpx
import pytest
from fastapi.testclient import TestClient
from studio.providers import Assistant, ChatIn, ProviderConfig


def test_config_rejects_proxy_targets_and_never_persists_key(tmp_path):
    for url in ('http://192.168.1.1','http://169.254.169.254','https://example.org','http://user:pass@localhost','http://localhost/evil'):
        with pytest.raises(ValueError):ProviderConfig(base_url=url)
    a=Assistant(tmp_path)
    cfg=ProviderConfig(provider='openai',base_url='https://api.openai.com/v1',model='configured-model',api_key='test-secret')
    assert a.configure(cfg)['has_key']
    assert 'test-secret' not in a.path.read_text() and 'api_key' not in a.public()
    a.configure(ProviderConfig())
    assert not a.public()['has_key']


@pytest.mark.asyncio
async def test_no_network_without_enablement_or_consent(tmp_path,monkeypatch):
    def denied(*args,**kwargs):raise AssertionError('Network must not run')
    monkeypatch.setattr(httpx,'AsyncClient',denied)
    a=Assistant(tmp_path);req=ChatIn(project_id='p',messages=[{'role':'user','content':'hello'}])
    with pytest.raises(ValueError):await a.suggest(req)
    a.configure(ProviderConfig(provider='openai',base_url='https://api.openai.com/v1',model='configured-model',api_key='test'))
    with pytest.raises(ValueError):await a.suggest(req)


@pytest.mark.asyncio
async def test_cpu_local_request_plan_validation_and_no_actions(tmp_path,monkeypatch):
    response={'reply':'Draft','name':'Courtyard','steps':[{'kind':'image','prompt':'Courtyard'},{'kind':'video','prompt':'Slow pan'}]}
    def handler(req):
        assert req.url==httpx.URL('http://127.0.0.1:11434/api/chat')
        body=json.loads(req.content)
        assert body['options']['num_gpu']==0 and body['keep_alive']==0 and body['stream'] is False
        assert 'Authorization' not in req.headers
        return httpx.Response(200,json={'message':{'content':json.dumps(response)}})
    client=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:client(transport=httpx.MockTransport(handler),**kw))
    a=Assistant(tmp_path);a.configure(ProviderConfig(provider='ollama',model='installed-model'))
    req=ChatIn(project_id='p',messages=[{'role':'user','content':'plan a scene'}])
    assert len((await a.suggest(req))['steps'])==2
    response['steps']=[{'kind':'video','prompt':'No image'}]
    with pytest.raises(ValueError):await a.suggest(req)
    response['steps']=[{'kind':'image','prompt':'x','command':'bad'}]
    with pytest.raises(ValueError):await a.suggest(req)


def test_assistant_api_does_not_enqueue_and_redacts_invalid_config(tmp_path,monkeypatch):
    monkeypatch.setenv('STUDIO_DATA_ROOT',str(tmp_path));monkeypatch.setenv('STUDIO_MODE','mock')
    from studio import app as mod
    importlib.reload(mod)
    c=TestClient(mod.app)
    pid=c.post('/api/projects',json={'name':'Assistant demo'}).json()['id']
    assert c.post('/api/assistant/chat',json={'project_id':pid,'messages':[{'role':'user','content':'hello'}]}).status_code==422
    assert c.get('/api/jobs').json()==[]
    r=c.put('/api/assistant/config',json={'provider':'openai','base_url':'http://evil','api_key':'secret-never-echo'})
    assert r.status_code==422 and 'secret-never-echo' not in r.text


@pytest.mark.asyncio
async def test_remote_consent_and_exact_endpoint(tmp_path,monkeypatch):
    def handler(req):
        assert str(req.url)=='https://api.openai.com/v1/chat/completions'
        assert req.headers['Authorization']=='Bearer test-key'
        assert json.loads(req.content)['response_format']=={'type':'json_object'}
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'reply':'Ideas only','steps':[]})}}]})
    client=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:client(transport=httpx.MockTransport(handler),**kw))
    a=Assistant(tmp_path);a.configure(ProviderConfig(provider='openai',base_url='https://api.openai.com/v1',model='configured-model',api_key='test-key'))
    result=await a.suggest(ChatIn(project_id='p',allow_remote=True,messages=[{'role':'user','content':'Suggest an idea'}]))
    assert result['steps']==[]
