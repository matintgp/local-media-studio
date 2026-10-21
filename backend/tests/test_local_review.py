"""Regressions discovered during the Windows/local engine review."""
import importlib
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from studio.core import Store, secure_path
from studio.engines import EngineError, Wan
from studio.runtime import single_instance


def test_native_path_and_worker_exclusion(tmp_path):
    child=tmp_path/'asset.wav';child.write_bytes(b'x')
    assert secure_path(tmp_path,child)==child.resolve()
    with single_instance(tmp_path):
        with pytest.raises(RuntimeError):
            with single_instance(tmp_path):pass


@pytest.mark.asyncio
async def test_wan_global_queue_includes_ui_tasks(monkeypatch):
    w=Wan('http://127.0.0.1:7866/mcp');w.context='test'
    async def tool(name,args):
        assert name=='wangp_session' and args['action']=='list_queue' and args['arguments']=={}
        return {'total_count':1,'running_count':1,'tasks':[{'source':'ui'}]}
    monkeypatch.setattr(w,'tool',tool)
    assert await w.conflict()


@pytest.mark.asyncio
async def test_upload_same_origin_and_real_reference(tmp_path,monkeypatch):
    source=tmp_path/'input.png';source.write_bytes(b'1234')
    w=Wan('http://127.0.0.1:7866/mcp');w.context='test'
    async def tool(name,args):
        assert args['action']=='create_file_upload'
        return {'upload_url':'/wangp_api/files/upload/test','chunk_bytes':2,'max_bytes':100}
    def handler(req):
        assert req.url.host=='127.0.0.1'
        offset=int(req.headers['upload-offset'])
        return httpx.Response(200,json={'status':'done' if offset==2 else 'uploading','path':'@documents/input.png' if offset==2 else None})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda *a,**k:original(*a,transport=httpx.MockTransport(handler),**k))
    monkeypatch.setattr(w,'tool',tool)
    assert (await w.upload(source))['path']=='@documents/input.png'
    async def evil(name,args):return {'upload_url':'http://example.com/leak'}
    monkeypatch.setattr(w,'tool',evil)
    with pytest.raises(EngineError):await w.upload(source)


@pytest.mark.asyncio
async def test_dependent_workflow_reuses_outputs_without_duplicate_jobs(tmp_path,monkeypatch):
    monkeypatch.setenv('STUDIO_DATA_ROOT',str(tmp_path));monkeypatch.setenv('STUDIO_MODE','mock')
    from studio import app as mod
    importlib.reload(mod)
    async def settle(j,payload):
        return mod.STORE.insert_asset(j['project_id'],j['kind'],'mock',job_id=j['id'])
    monkeypatch.setattr(mod,'settle_output',settle)
    c=TestClient(mod.app)
    pid=c.post('/api/projects',json={'name':'Pipeline'}).json()['id']
    steps=[{'kind':k,'settings':{'prompt':'test'},**({'input_from':i-1} if i else {})} for i,k in enumerate(('image','video','ambience'))]
    wid=c.post('/api/workflows',json={'name':'chain','project_id':pid,'steps':steps}).json()['id']
    assert c.post(f'/api/workflows/{wid}/run').status_code==200
    for _ in range(5):await mod.scheduler_once()
    jobs=c.get('/api/jobs').json();assert len(jobs)==3 and all(j['state']=='succeeded' for j in jobs)
    video=next(j for j in jobs if j['kind']=='video')
    image=next(a for a in c.get('/api/assets').json() if a['kind']=='image')
    assert json.loads(video['settings'])['start_asset_id']==image['id']
    c.post(f'/api/workflows/{wid}/run')
    await mod.scheduler_once()
    assert len(c.get('/api/jobs').json())==3
    assert all('context' not in j for j in c.get('/api/jobs').json())


def test_external_asset_reference_without_copy(tmp_path,monkeypatch):
    root=tmp_path/'app';root.mkdir();external=tmp_path/'engine';external.mkdir()
    f=external/'image.png';f.write_bytes(b'example')
    store=Store(root)
    with store.tx() as db:db.execute("INSERT INTO projects(id,name) VALUES('p','example')")
    monkeypatch.setenv('STUDIO_COMFY_OUTPUT_ROOT',str(external))
    aid=store.insert_asset('p','image','comfy',f)
    a=store.row('SELECT * FROM assets WHERE id=?',(aid,))
    assert store.asset_path(a)==f.resolve()
    assert list((root/'assets').iterdir())==[]
    with pytest.raises(Exception):store.asset_path(dict(a,path=str(tmp_path/'private')))


@pytest.mark.asyncio
async def test_native_validation_does_not_receive_app_fields(monkeypatch):
    w=Wan('http://127.0.0.1:7866/mcp');w.context='test'
    async def tool(name,args):
        assert name=='wangp_validate'
        assert 'kind' not in args['settings']
        return {'valid':True,'tasks':[{'availability':{'available':True}}]}
    monkeypatch.setattr(w,'tool',tool)
    assert await w.validate({'kind':'speech','model_type':'omnivoice','prompt':'Hello'})=='test'
