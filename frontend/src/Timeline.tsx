import {useEffect,useRef,useState} from 'react';

export type Shot={asset_id:string;start:number;end?:number};
export type Track={asset_id:string;role:string;offset:number;gain:number;start:number;end?:number;fade_in:number;fade_out:number};
type Asset={id:string;kind?:string;meta?:string;[key:string]:unknown};
type Props={assets:Asset[];shots:Shot[];tracks:Track[];setShots:(s:Shot[])=>void;setTracks:(s:Track[])=>void;lang:'fa'|'en'};
function duration(a:Asset|undefined){try{return Number(JSON.parse(a?.meta||'{}').duration)||0}catch{return 0}}
const clamp=(n:number,a:number,b:number)=>Math.min(b,Math.max(a,n));

/** Preview is an editing aid; the exported FFmpeg mix is authoritative. */
export function Timeline({assets,shots,tracks,setShots,setTracks,lang}:Props){
 const fa=lang==='fa';const [time,setTime]=useState(0);const [playing,setPlaying]=useState(false);const [zoom,setZoom]=useState(90);const [selected,setSelected]=useState(-1);
 const video=useRef<HTMLVideoElement>(null);const audio=useRef<(HTMLAudioElement|null)[]>([]);const drag=useRef<number|null>(null);
 const find=(id:string)=>assets.find(a=>a.id===id);
 let cursor=0;const clips=shots.map((s,i)=>{const d=Math.max(0,(s.end??duration(find(s.asset_id)))-s.start);const clip={...s,i,at:cursor,d};cursor+=d;return clip});const total=cursor;
 const current=clips.find(c=>time>=c.at&&time<c.at+c.d)||clips.at(-1);
 useEffect(()=>{setPlaying(false);setTime(0)},[shots,tracks]);
 useEffect(()=>{if(!playing)return;let raf=0;let last=performance.now();const tick=(now:number)=>{const dt=(now-last)/1000;last=now;setTime(t=>{if(t+dt>=total){setPlaying(false);return total}return t+dt});raf=requestAnimationFrame(tick)};raf=requestAnimationFrame(tick);return()=>cancelAnimationFrame(raf)},[playing,total]);
 useEffect(()=>{
  const v=video.current;if(v&&current){const target=current.start+Math.max(0,time-current.at);if(Math.abs(v.currentTime-target)>.25)v.currentTime=target;if(playing)v.play().catch(()=>setPlaying(false));else v.pause()}
  tracks.forEach((t,i)=>{const a=audio.current[i];if(!a)return;const end=t.end??duration(find(t.asset_id));const d=Math.min(end-t.start,total-t.offset);const local=time-t.offset;const active=local>=0&&local<d;
   let gain=t.gain; if(t.fade_in)gain*=clamp(local/t.fade_in,0,1);if(t.fade_out)gain*=clamp((d-local)/t.fade_out,0,1);
   a.volume=clamp(gain,0,1);if(active){const target=t.start+local;if(Math.abs(a.currentTime-target)>.25)a.currentTime=target;if(playing)a.play().catch(()=>{});else a.pause()}else a.pause();
  });
 },[time,playing,current,tracks,total]);
 useEffect(()=>()=>{audio.current.forEach(a=>a?.pause())},[]);
 const reorder=(from:number,to:number)=>{if(from===to)return;const next=[...shots];next.splice(to,0,next.splice(from,1)[0]);setShots(next);setSelected(to)};
 const trim=(i:number,edge:'start'|'end',delta:number)=>{const s=shots[i];const max=duration(find(s.asset_id));if(!max)return;const end=s.end??max;const v=edge==='start'?clamp(s.start+delta,0,end-.1):clamp(end+delta,s.start+.1,max);setShots(shots.map((x,k)=>k===i?{...x,[edge]:Math.round(v*100)/100}:x))};
 function pointerDrag(e:React.PointerEvent,move:(delta:number)=>void){e.preventDefault();e.stopPropagation();setPlaying(false);const target=e.currentTarget as HTMLElement;const initial=e.clientX;target.setPointerCapture(e.pointerId);const up=(ev:PointerEvent)=>{target.removeEventListener('pointerup',up);target.removeEventListener('pointercancel',cancel);move((ev.clientX-initial)/zoom)};const cancel=()=>{target.removeEventListener('pointerup',up);target.removeEventListener('pointercancel',cancel)};target.addEventListener('pointerup',up,{once:true});target.addEventListener('pointercancel',cancel,{once:true})}
 return <section className="panel timeline" aria-label={fa?'تایم‌لاین تعاملی':'Interactive timeline'}>
  <div className="sectionTitle"><span>{fa?'تایم‌لاین':'TIMELINE'}</span><label className="zoom">{fa?'بزرگ‌نمایی':'Zoom'} <input aria-label="Timeline zoom" type="range" min="30" max="180" value={zoom} onChange={e=>setZoom(Number(e.target.value))}/></label></div>
  <div className="timelineMonitor">{current?.asset_id?<video ref={video} key={current.asset_id} src={`/api/assets/${current.asset_id}/media`} muted playsInline preload="metadata" onLoadedMetadata={()=>{if(video.current)video.current.currentTime=current.start+Math.max(0,time-current.at)}}/>:<p>{fa?'یک نما اضافه کنید':'Add a shot to begin'}</p>}</div>
  {tracks.map((t,i)=><audio key={i+':'+t.asset_id} ref={el=>{audio.current[i]=el}} src={t.asset_id?`/api/assets/${t.asset_id}/media`:undefined} preload="metadata"/>)}
  <div className="transport" dir="ltr"><button aria-label={playing?'Pause timeline':'Play timeline'} disabled={!total} onClick={()=>{if(time>=total)setTime(0);setPlaying(!playing)}}>{playing?'Ⅱ':'▶'}</button><button aria-label="Rewind timeline" onClick={()=>{setPlaying(false);setTime(0)}}>↤</button><output>{time.toFixed(2)} / {total.toFixed(2)} s</output><input aria-label="Timeline playhead" type="range" min="0" max={total||1} step="0.01" value={Math.min(time,total)} onChange={e=>{setPlaying(false);setTime(Number(e.target.value))}}/></div>
  <p className="muted tiny">{fa?'نماها را بکشید تا مرتب شوند؛ لبه‌ها برای برش و بلوک صدا برای جابه‌جایی است. پیکان‌های صفحه‌کلید هم فعال‌اند. پیش‌نمایش تقریبی است؛ میکس دقیق، کاهش موسیقی و زیرنویس در MP4 خروجی اعمال می‌شوند.':'Drag shots to reorder, edges to trim, audio blocks to offset. Arrow keys also work. Editing preview is approximate; MP4 export applies the exact mix, ducking and subtitles.'}</p>
  <div className="timelineScroll" dir="ltr"><div className="timelineCanvas" style={{width:Math.max(600,total*zoom)}}>
   <div className="timeRuler" onClick={e=>{const r=e.currentTarget.getBoundingClientRect();setPlaying(false);setTime(clamp((e.clientX-r.left)/zoom,0,total))}}>{Array.from({length:Math.min(901,Math.ceil(total)+1)},(_,i)=><span key={i} style={{left:i*zoom}}>{i}s</span>)}</div>
   <div className="videoLane">{clips.map(c=><div className={'timelineClip '+(selected===c.i?'chosen':'')} key={c.i} style={{left:c.at*zoom,width:Math.max(12,c.d*zoom)}} draggable onDragStart={()=>{drag.current=c.i;setPlaying(false)}} onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();if(drag.current!==null)reorder(drag.current,c.i);drag.current=null}} onClick={()=>setSelected(c.i)}>
    <button className="trimHandle" draggable={false} aria-label={`Trim start ${c.i+1}`} onPointerDown={e=>pointerDrag(e,d=>trim(c.i,'start',d))} onKeyDown={e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();trim(c.i,'start',e.key==='ArrowRight'?.1:-.1)}}}>[</button>
    <button className="clipTitle" aria-label={`Shot ${c.i+1}`} onKeyDown={e=>{if(e.key==='ArrowLeft'&&c.i>0){e.preventDefault();reorder(c.i,c.i-1)}if(e.key==='ArrowRight'&&c.i<shots.length-1){e.preventDefault();reorder(c.i,c.i+1)}}}>{c.i+1} · {c.d.toFixed(1)}s</button>
    <button className="trimHandle" draggable={false} aria-label={`Trim end ${c.i+1}`} onPointerDown={e=>pointerDrag(e,d=>trim(c.i,'end',d))} onKeyDown={e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();trim(c.i,'end',e.key==='ArrowRight'?.1:-.1)}}}>]</button>
   </div>)}</div>
   {tracks.map((t,i)=>{const d=Math.max(0,Math.min((t.end??duration(find(t.asset_id)))-t.start,total-t.offset));const offset=(v:number)=>setTracks(tracks.map((x,k)=>k===i?{...x,offset:Math.round(clamp(v,0,Math.max(0,total-.1))*100)/100}:x));return <div className="audioLane" key={i}><button aria-label={`Move audio ${i+1}`} className={'audioClip '+t.role} style={{left:t.offset*zoom,width:Math.max(30,d*zoom)}} onPointerDown={e=>pointerDrag(e,delta=>offset(t.offset+delta))} onKeyDown={e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();offset(t.offset+(e.key==='ArrowRight'?.1:-.1))}}}>{t.role} · {t.offset.toFixed(1)}s</button></div>})}
   <div className="playhead" style={{left:time*zoom}}/>
  </div></div>
 </section>
}
