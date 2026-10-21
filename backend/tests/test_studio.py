import importlib
import io
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def ctx(tmp_path,monkeypatch):
    monkeypatch.setenv('STUDIO_DATA_ROOT',str(tmp_path))
    monkeypatch.setenv('STUDIO_MODE','mock')
    from studio import app as module
    importlib.reload(module)
    with TestClient(module.app) as client:
        yield module, client

def project(client):return client.post('/api/projects',json={'name':'نمونه فارسی'}).json()['id']

def test_project_persistence_mock_pipeline_and_compose(ctx):
    mod,c=ctx;pid=project(c)
    for kind,settings in [('image',{'prompt':'نمونه تصویر'}),('video',{'prompt':'Motion','start_asset_id':None}),('speech',{'prompt':'سلام','language':'fa'}),('music',{'prompt':'ambient instrumental'}),('ambience',{'prompt':'Wind','video_asset_id':None})]:
        if kind=='video':settings['start_asset_id']=c.get('/api/assets').json()[0]['id']
        if kind=='ambience':settings['video_asset_id']=next(a['id'] for a in c.get('/api/assets').json() if a['kind']=='video')
        j=c.post('/api/jobs',json={'project_id':pid,'kind':kind,'settings':settings});assert j.status_code==200,j.text
        import time
        for _ in range(60):
            result=c.get('/api/jobs').json()[0]
            if result['state'] in ['succeeded','failed']:break
            time.sleep(.15)
        assert result['state']=='succeeded',result
    a=c.get('/api/assets').json()
    assert len(a)==5 and all(x['origin']=='mock' for x in a)
    shot=next(x for x in a if x['kind']=='video');narr=next(x for x in a if x['kind']=='speech');music=next(x for x in a if x['kind']=='music')
    exported=c.post('/api/exports',json={'project_id':pid,'shots':[{'asset_id':shot['id'],'start':.25,'end':2.25}],'tracks':[{'asset_id':narr['id'],'role':'narration','gain':1,'offset':0},{'asset_id':music['id'],'role':'music','gain':.5,'offset':.5}]})
    assert exported.status_code==200,exported.text
    assert exported.json()['meta']['audio'] is True
    assert 1.9<exported.json()['meta']['duration']<2.2
    assert c.get('/api/assets/'+exported.json()['asset_id']+'/media').status_code==200
    assert mod.STORE.row('SELECT * FROM projects WHERE id=?',(pid,))['name']=='نمونه فارسی'

def test_cross_origin_and_media_boundary(ctx,tmp_path):
    mod,c=ctx;pid=project(c)
    assert c.post('/api/projects',json={'name':'x'},headers={'Origin':'https://attacker.test'}).status_code==403
    assert c.get('/api/assets/bogus/media').status_code==404
    from studio.core import secure_path
    with pytest.raises(ValueError):secure_path(tmp_path,tmp_path/'..'/'outside')
    with pytest.raises(ValueError):secure_path(tmp_path,Path('C:/Windows/system.ini'))
    (tmp_path/'escape').symlink_to(tmp_path.parent,target_is_directory=True)
    with pytest.raises(ValueError):secure_path(tmp_path,tmp_path/'escape'/'secret')
    assert c.post('/api/jobs',json={'project_id':pid,'kind':'image','settings':{'prompt':''}}).status_code==422

def test_unknown_keeps_admission(ctx):
    mod,c=ctx;pid=project(c)
    j=c.post('/api/jobs',json={'project_id':pid,'kind':'image','settings':{'prompt':'Test'}}).json()
    # model ambiguous real submit with persisted slot: explicit recovery needed.
    mod.STORE.acquire('unknown-external');assert mod.STORE.admission()=='unknown-external'
    assert not mod.STORE.acquire(j['id'])
    mod.STORE.release('unknown-external')

def test_import_limits_and_subtitles(ctx):
    mod,c=ctx;pid=project(c)
    bad=c.post('/api/assets/import',params={'project_id':pid},files={'file':('evil.py',b'print(1)')})
    assert bad.status_code==415
    good=c.post('/api/assets/import',params={'project_id':pid},files={'file':('captions.srt',b'1\n00:00:00,000 --> 00:00:01,000\nHello\n')})
    assert good.status_code==200,good.text
    assert good.json()['kind']=='subtitle'

@pytest.mark.asyncio
async def test_unknown_real_job_blocks_future_dispatch(ctx, monkeypatch):
    mod,c=ctx;pid=project(c)
    j=c.post('/api/jobs',json={'project_id':pid,'kind':'image','settings':{'prompt':'a demo'}}).json()
    mod.STORE.update_job(j['id'],'unknown','reconciling','Ambiguous external submit')
    assert mod.STORE.acquire(j['id'])
    later=c.post('/api/jobs',json={'project_id':pid,'kind':'speech','settings':{'prompt':'سلام'}}).json()
    await mod.scheduler_once()
    assert mod.job(later['id'])['state']=='waiting'
    assert mod.STORE.admission()==j['id']
    mod.STORE.release(j['id'])
