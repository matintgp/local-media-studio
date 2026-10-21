import os
import subprocess
from pathlib import Path

import pytest
from studio.core import Store
from studio.media import render_composition, probe, MediaError

def sample(path,size,fps,tone=False):
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i',f'testsrc2=size={size}:rate={fps}','-t','1.6']
    if tone:cmd+=['-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-c:a','aac']
    cmd+=['-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p','-y',str(path)]
    subprocess.run(cmd,check=True)

def test_two_unequal_shots_and_no_audio(tmp_path):
    s=Store(tmp_path)
    with s.tx() as db:db.execute("INSERT INTO projects(id,name) VALUES('p','demo')")
    a=tmp_path/'assets'/'a.mp4';b=tmp_path/'assets'/'b.mp4'
    sample(a,'320x240',15);sample(b,'480x270',30)
    x=s.insert_asset('p','video','import',a);y=s.insert_asset('p','video','import',b)
    out,meta=render_composition(s,{'shots':[{'asset_id':x,'start':.2,'end':1.2},{'asset_id':y,'start':0,'end':1}], 'tracks':[], 'fps':24,'width':640,'height':360})
    assert out.is_file() and meta['audio'] and meta['width']==640 and meta['height']==360
    assert 1.9<=meta['duration']<=2.2

def test_invalid_timing_and_no_source_deletion(tmp_path):
    s=Store(tmp_path)
    with s.tx() as db:db.execute("INSERT INTO projects(id,name) VALUES('p','demo')")
    a=tmp_path/'assets'/'source.mp4';sample(a,'320x240',24)
    x=s.insert_asset('p','video','import',a)
    with pytest.raises(MediaError):render_composition(s,{'shots':[{'asset_id':x,'start':1.0,'end':.5}]})
    assert a.is_file()
    with pytest.raises(MediaError):render_composition(s,{'shots':[{'asset_id':x,'start':float('nan')}]})

def test_embedded_srt_subtitles(tmp_path):
    s=Store(tmp_path)
    with s.tx() as db:db.execute("INSERT INTO projects(id,name) VALUES('p','demo')")
    a=tmp_path/'assets'/'source.mp4';sample(a,'320x240',24)
    x=s.insert_asset('p','video','import',a)
    captions=tmp_path/'assets'/'captions.srt'
    captions.write_text('1\n00:00:00,000 --> 00:00:01,000\nDemo subtitle\n',encoding='utf-8')
    sub=s.insert_asset('p','subtitle','import',captions)
    output,meta=render_composition(s,{'shots':[{'asset_id':x}],'subtitle_asset_id':sub})
    assert output.is_file() and meta['width']==640
    import json
    streams=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(output)]))['streams']
    assert any(st.get('codec_name')=='mov_text' for st in streams)
