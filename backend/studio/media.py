"""CPU-only synthetic demo media and safe FFmpeg composition."""
import asyncio
import json
import math
import os
import shutil
import subprocess
from pathlib import Path
from .core import ensure_space, secure_path, uid

class MediaError(Exception):pass

def run(args):
    try:
        p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180,check=False)
    except (OSError,subprocess.TimeoutExpired) as e: raise MediaError(str(e)) from e
    if p.returncode: raise MediaError(p.stderr.decode(errors='replace')[-750:])
    return p.stdout

def probe(path,ffprobe='ffprobe'):
    doc=json.loads(run([ffprobe,'-v','error','-show_format','-show_streams','-of','json',str(path)]))
    vs=next((s for s in doc.get('streams',[]) if s.get('codec_type')=='video'),None)
    return {'duration':float(doc.get('format',{}).get('duration',0)),'width':vs.get('width') if vs else None,'height':vs.get('height') if vs else None,'format':doc.get('format',{}).get('format_name'),'audio':any(s.get('codec_type')=='audio' for s in doc.get('streams',[]))}

def generate_demo(root,kind,ffmpeg='ffmpeg'):
    """Synthetic, labelled demonstration only. No model inference."""
    out=root/'assets'/(uid()+('.png' if kind=='image' else '.mp4' if kind in ('video','ambience') else '.wav'))
    if kind=='image':
        run([ffmpeg,'-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=0x246d70:s=640x640','-frames:v','1','-update','1','-y',str(out)])
    elif kind in ('video','ambience'):
        args=[ffmpeg,'-hide_banner','-loglevel','error','-f','lavfi','-i','testsrc2=size=640x640:rate=24','-t','3']
        if kind=='ambience': args+=['-f','lavfi','-i','sine=frequency=220:sample_rate=48000','-shortest','-c:a','aac']
        args+=['-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p','-y',str(out)]
        run(args)
    else:
        freq='440' if kind=='speech' else '262'
        run([ffmpeg,'-hide_banner','-loglevel','error','-f','lavfi','-i',f'sine=frequency={freq}:sample_rate=48000','-t','3','-c:a','pcm_s16le','-y',str(out)])
    return out

def finite(value,lower=0,upper=7200):
    if isinstance(value,bool): raise MediaError('Invalid numeric value')
    try:f=float(value)
    except (TypeError,ValueError):raise MediaError('Expected numeric value')
    if not math.isfinite(f) or not lower<=f<=upper: raise MediaError('Timing or gain outside supported range')
    return f

def render_composition(store,spec,ffmpeg='ffmpeg',ffprobe='ffprobe',reserve=0):
    """Validated filter graph; video duration always wins, tracks padded/trimmed accordingly."""
    shots=spec.get('shots',[])
    if not isinstance(shots,list) or not 1<=len(shots)<=16: raise MediaError('1–16 shots required')
    tracks=spec.get('tracks',[])
    if not isinstance(tracks,list) or len(tracks)>12:raise MediaError('Maximum 12 audio tracks')
    width=int(spec.get('width',640));height=int(spec.get('height',640));fps=int(spec.get('fps',24))
    if not (160<=width<=1920 and 160<=height<=1080 and width%2==0 and height%2==0 and 12<=fps<=60):
        raise MediaError('Unsupported export dimensions or FPS')
    inputs=[]; graph=[]; shot_labels=[];offset=0;total=0
    def source(aid):
        a=store.row('SELECT * FROM assets WHERE id=?',(aid,))
        p=store.asset_path(a)
        return p
    for i,shot in enumerate(shots):
        p=source(shot['asset_id']);meta=probe(p,ffprobe)
        if not meta['width']:raise MediaError('A shot must contain video')
        start=finite(shot.get('start',0));end=finite(shot.get('end',meta['duration']))
        if end<=start or end>meta['duration']+0.1:raise MediaError('Invalid shot in/out points')
        inputs+=['-i',str(p)];duration=end-start;total+=duration
        graph.append(f'[{offset}:v]trim=start={start}:end={end},setpts=PTS-STARTPTS,scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p[v{i}]')
        shot_labels.append(f'[v{i}]');offset+=1
    if total>900:raise MediaError('Export duration exceeds 15 minutes')
    graph.append(''.join(shot_labels)+f'concat=n={len(shots)}:v=1:a=0[vcat]')
    narr=[];others=[]
    for j,track in enumerate(tracks):
        role=track.get('role')
        if role not in ('narration','music','ambience'):raise MediaError('Unsupported track lane')
        p=source(track['asset_id']);meta=probe(p,ffprobe)
        if not meta['audio']: raise MediaError('Track has no audio stream')
        start=finite(track.get('start',0));end=finite(track.get('end',meta['duration']))
        at=finite(track.get('offset',0),0,900);gain=finite(track.get('gain',1),0,4)
        fadein=finite(track.get('fade_in',0),0,60);fadeout=finite(track.get('fade_out',0),0,60)
        if end<=start or end>meta['duration']+0.1 or at>=total:raise MediaError('Invalid audio trim or offset')
        duration=min(end-start,total-at)
        if fadein>duration or fadeout>duration:raise MediaError('Fade exceeds track duration')
        inputs+=['-i',str(p)]
        chain=f'[{offset}:a]atrim=start={start}:end={start+duration},asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume={gain}'
        if fadein:chain+=f',afade=t=in:st=0:d={fadein}'
        if fadeout:chain+=f',afade=t=out:st={max(0,duration-fadeout)}:d={fadeout}'
        chain+=f',adelay={round(at*1000)}|{round(at*1000)},apad=whole_dur={total},atrim=duration={total}[a{j}]'
        graph.append(chain);(narr if role=='narration' else others).append(f'[a{j}]');offset+=1
    def mix(labels,name):
        if not labels:return None
        if len(labels)==1:return labels[0]
        graph.append(''.join(labels)+f'amix=inputs={len(labels)}:duration=longest:normalize=0[{name}]')
        return f'[{name}]'
    n=mix(narr,'speech');o=mix(others,'bed')
    if n and o and spec.get('duck',True):
        graph.append(f'{n}asplit=2[nside][nvoice]')
        graph.append(f'{o}[nside]sidechaincompress=threshold=0.035:ratio=6:attack=35:release=300[ducked]')
        graph.append('[ducked][nvoice]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95[amix]')
        audio='[amix]'
    elif n and o:
        graph.append(f'{o}{n}amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95[amix]');audio='[amix]'
    else:audio=n or o
    if not audio:
        inputs+=['-f','lavfi','-t',str(total),'-i','anullsrc=r=48000:cl=stereo'];audio=f'{offset}:a';offset+=1
    subtitle_index=None
    if spec.get('subtitle_asset_id'):
        sub=source(spec['subtitle_asset_id'])
        if sub.suffix.lower() != '.srt' or sub.stat().st_size>1024*1024 or b'\x00' in sub.read_bytes():
            raise MediaError('Subtitles must be a valid SRT text asset under 1 MiB')
        subtitle_index=offset
        inputs+=['-i',str(sub)]
    staging=store.root/'staging'/(uid()+'.mp4')
    dest=store.root/'exports'/(uid()+'.mp4')
    ensure_space(store.root,int(max(total*2*1024*1024,1024*1024)),reserve)
    args=[ffmpeg,'-nostdin','-hide_banner','-loglevel','error','-y',*inputs,'-filter_complex',';'.join(graph),'-map','[vcat]','-map',audio,'-c:v','libx264','-preset','veryfast','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-t',str(total),'-movflags','+faststart']
    if subtitle_index is not None:
        args+=['-map',f'{subtitle_index}:0','-c:s','mov_text']
    args+=[str(staging)]
    try:
        run(args)
        result=probe(staging,ffprobe)
        if not result['width'] or not result['audio'] or abs(result['duration']-total)>0.4:raise MediaError('Output probe failed timing or audio verification')
        os.replace(staging,dest)
        return dest,result
    finally:staging.unlink(missing_ok=True)
