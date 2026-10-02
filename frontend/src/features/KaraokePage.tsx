import { useEffect, useRef, useState } from "react";
import type { ApiPort, LyricsRecord } from "../ports/api";
import type { Song } from "../domain/types";
import { SyncedStems, activeLine } from "./syncedAudio";

export function KaraokePage({api,songs,isHost,refresh}: {api:ApiPort;songs:Song[];isHost:boolean;refresh:()=>void}) {
  const [id,setId]=useState("");
  const eligible=songs.filter(s=>s.status==="CONCLUIDA" && s.library?.ready && s.library.lyrics_status==="LETRA_SINCRONIZADA");
  const song=eligible.find(s=>s.id===id);
  return <section><h2>Cantar</h2>
    <label>Música <select aria-label="Música para cantar" value={id} onChange={e=>setId(e.target.value)}>
      <option value="">Selecione uma música com letra sincronizada</option>
      {eligible.map(s=><option key={s.id} value={s.id}>{s.title} — {s.artist}</option>)}
    </select></label>
    {song ? <Player key={song.id} song={song} api={api} isHost={isHost} refresh={refresh} /> :
      <p>Escolha uma música concluída, com stems válidos e letra sincronizada.</p>}
  </section>;
}

function Player({song,api,isHost,refresh}: {song:Song;api:ApiPort;isHost:boolean;refresh:()=>void}) {
  const player=useRef<SyncedStems | null>(null);
  const stage=useRef<HTMLDivElement>(null);
  const [lyrics,setLyrics]=useState<LyricsRecord | null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(true);
  const [ready,setReady]=useState(false);
  const [playing,setPlaying]=useState(false);
  const [time,setTime]=useState(0);
  const [duration,setDuration]=useState(0);
  const [offset,setOffset]=useState(song.lyrics_offset_ms || 0);
  const [inst,setInst]=useState(.85);
  const [voice,setVoice]=useState(0);
  const [backing,setBacking]=useState(0);
  const [fullscreen,setFullscreen]=useState(false);
  const [background,setBackground]=useState(() => localStorage.getItem(`karaoke.bg.${song.id}`) || "");
  const lines=lyrics?.lines || [];
  const current=activeLine(lines,time,offset);

  useEffect(() => {
    let alive=true;
    const p=new SyncedStems();player.current=p;
    Promise.all([api.selectedLyrics(song.id),p.load(api,song.id)]).then(([r])=>{
      if(!alive)return;
      if(r.status!=="LETRA_SINCRONIZADA" || !r.lines.length)throw new Error("A letra não possui timestamps.");
      setLyrics(r);setDuration(p.duration);setReady(true);
    }).catch(e=>{if(alive)setError(e instanceof Error?e.message:"Falha ao carregar mídia.");})
      .finally(()=>{if(alive)setLoading(false);});
    return ()=>{alive=false;player.current=null;void p.close();};
  },[api,song.id]);

  useEffect(()=>{
    let frame=0;
    const tick=()=>{const p=player.current;if(p){const t=p.position();setTime(t);
      if(p.isPlaying && t>=p.duration-.02){p.pause();setPlaying(false);}}
      frame=requestAnimationFrame(tick);};
    frame=requestAnimationFrame(tick);return ()=>cancelAnimationFrame(frame);
  },[]);
  useEffect(()=>{
    const change=()=>setFullscreen(document.fullscreenElement===stage.current);
    document.addEventListener("fullscreenchange",change);return ()=>document.removeEventListener("fullscreenchange",change);
  },[]);

  async function toggle(){const p=player.current;if(!p)return;
    try {if(p.isPlaying){p.pause();setPlaying(false);}else{await p.play();setPlaying(true);}}
    catch(e){setError(e instanceof Error?e.message:"Reprodução bloqueada; toque em play.");}
  }
  async function seek(n:number){try{await player.current?.seek(n);setTime(n);}catch(e){setError(String(e));}}
  async function saveOffset(){try{await api.updateLyricsOffset(song.id,offset);refresh();}
    catch(e){setError(e instanceof Error?e.message:"Não foi possível salvar o offset.");}}
  async function full(){try{if(!document.fullscreenElement)await stage.current?.requestFullscreen();else await document.exitFullscreen();}
    catch{setError("Tela cheia indisponível neste navegador.");}}
  function pickImage(f?:File){if(!f)return;
    if(!["image/png","image/jpeg","image/webp"].includes(f.type)||f.size>2*1024*1024){setError("Use PNG, JPEG ou WebP até 2 MB.");return;}
    const reader=new FileReader();reader.onload=()=>{
      const data=reader.result;if(typeof data!=="string")return;
      try{localStorage.setItem(`karaoke.bg.${song.id}`,data);setBackground(data);}
      catch{setError("Sem espaço para salvar a imagem neste navegador.");}
    };reader.readAsDataURL(f);
  }
  function gain(which:"instrumental"|"vocals",n:number){player.current?.setGain(which,n);if(which==="instrumental")setInst(n);else setVoice(n);}
  return <div className="col">
    <h3>{song.title} — {song.artist}</h3>
    {loading&&<p role="status">Carregando e decodificando os dois stems locais…</p>}
    {error&&<p role="alert" className="error">{error}</p>}
    {ready&&<>
      <div className="row"><button onClick={()=>void toggle()}>{playing?"Pausar":"Play"}</button>
        <span>{time.toFixed(1)} / {duration.toFixed(1)} s</span>
        <button onClick={()=>void full()}>{fullscreen?"Sair da tela cheia":"Tela cheia"}</button></div>
      <label>Progresso <input type="range" min="0" max={duration||1} step="0.1" value={time}
        onChange={e=>void seek(Number(e.target.value))} /></label>
      <label>Instrumental: {Math.round(inst*100)}% <input type="range" min="0" max="1" step="0.01" value={inst}
        onChange={e=>gain("instrumental",Number(e.target.value))}/><button onClick={()=>gain("instrumental",inst?0:.85)}>Silenciar/reativar instrumental</button></label>
      <label>Vocal principal (stem de vocais): {Math.round(voice*100)}% <input type="range" min="0" max="1" step="0.01" value={voice}
        onChange={e=>gain("vocals",Number(e.target.value))}/><button onClick={()=>gain("vocals",voice?0:.65)}>Silenciar/reativar vocal</button></label>
      <label>Backing vocals (indisponível): {Math.round(backing*100)}% <input type="range" min="0" max="1" step="0.01"
        value={backing} disabled onChange={e=>setBacking(Number(e.target.value))}/><button disabled>Silenciar backing</button></label>
      <div className="row"><span>Deslocamento da letra: {offset} ms (positivo = letra antecipada)</span>
        {[-500,-50,50,500].map(n=><button key={n} onClick={()=>setOffset(v=>Math.max(-10000,Math.min(10000,v+n)))}>{n>0?"+":""}{n} ms</button>)}
        {isHost&&<button onClick={()=>void saveOffset()}>Salvar deslocamento</button>}</div>
      <label>Imagem de fundo local (opcional) <input type="file" accept="image/png,image/jpeg,image/webp"
        onChange={e=>pickImage(e.target.files?.[0])} /></label>
      <div ref={stage} className="karaoke-stage" style={{backgroundImage:background?`linear-gradient(#0008,#0009),url(${JSON.stringify(background)})`:"linear-gradient(135deg,#111,#282856)"}}>
        <div className="karaoke-lines" aria-live="off">{lines.map(([ms,text],i)=><p key={`${ms}-${i}`} className={i===current?"karaoke-active":""}>{text||"♪"}</p>)}</div>
        {fullscreen&&<button className="karaoke-exit" onClick={()=>void full()}>Sair da tela cheia</button>}
      </div>
      <p className="hint">Dois stems usam o mesmo relógio Web Audio; lead/backing independente ainda não está disponível. Saia da tela cheia com Esc.</p>
    </>}
  </div>;
}
