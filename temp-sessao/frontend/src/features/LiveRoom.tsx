import {useEffect,useRef,useState} from "react";
import type {ApiPort,LyricsRecord} from "../ports/api";
import type {Song} from "../domain/types";
import {SyncedStems} from "./syncedAudio";
import {lineIndex,newer,positionMs,type SessionState} from "./liveClock";

export function LiveRoom({api,songs,isHost}: {api:ApiPort;songs:Song[];isHost:boolean}) {
  const [state,setState]=useState<SessionState|null>(null);
  const latest=useRef<SessionState|null>(null);
  const ws=useRef<WebSocket|null>(null);
  const player=useRef<SyncedStems|null>(null);
  const [lyrics,setLyrics]=useState<LyricsRecord|null>(null);
  const [status,setStatus]=useState("Conectando à sessão…");
  const [error,setError]=useState("");
  const [prepared,setPrepared]=useState(false);
  const [time,setTime]=useState(0);
  const [skew,setSkew]=useState(0);
  const skewRef=useRef(0);
  const stage=useRef<HTMLDivElement>(null);
  const [fullscreen,setFullscreen]=useState(false);
  const [pickOffset,setPickOffset]=useState(0);
  const reconnect=useRef<ReturnType<typeof setTimeout>|null>(null);
  const report=useRef<ReturnType<typeof setInterval>|null>(null);
  const [selection,setSelection]=useState("");
  const current=songs.find(x=>x.id===state?.song_id);
  const valid=songs.filter(x=>x.status==="CONCLUIDA"&&x.library?.ready&&x.library?.lyrics_status==="LETRA_SINCRONIZADA");
  const lines=lyrics?.lines || [];
  const index=lineIndex(lines,time,state?.offset_ms||0);
  function send(kind:string,value?:unknown){
    if(ws.current?.readyState!==WebSocket.OPEN){setError("Sessão desconectada; tente novamente quando reconectar.");return;}
    ws.current.send(JSON.stringify({type:"command",kind,value}));
  }
  useEffect(()=>{
    let mounted=true;
    function connect(){
      if(!mounted)return;
      const socket=new WebSocket(`${location.protocol==="https:"?"wss":"ws"}://${location.host}/api/ws/live`);
      ws.current=socket;
      socket.onopen=()=>{
        const token=sessionStorage.getItem("karaoke.token");
        if(!token){setError("Token ausente; entre pelo QR code novamente.");socket.close();return;}
        socket.send(JSON.stringify({type:"auth",token}));setStatus("Autenticando…");
      };
      socket.onmessage=event=>{
        try {
          const data=JSON.parse(event.data);
          if(data.type==="snapshot"){
            const incoming=data.state as SessionState;
            if(newer(latest.current,incoming)){
              latest.current=incoming;setState(incoming);setPickOffset(incoming.offset_ms);
              // Estimativa imediata, refinada por mensagens de clock com RTT.
              if(!skewRef.current)skewRef.current=incoming.server_ms-Date.now();
              setStatus(incoming.host_online?"Conectado":"Aguardando host");
            }
          } else if(data.type==="clock"){
            const rtt=Date.now()-Number(data.nonce);
            if(rtt>=0&&rtt<2000){skewRef.current=Number(data.server_ms)-(Number(data.nonce)+rtt/2);setSkew(skewRef.current);}
          } else if(data.type==="error")setError(data.message);
        }catch{setError("Mensagem inválida do servidor.");}
      };
      socket.onclose=()=>{
        if(isHost){player.current?.pause();setPrepared(false);}
        if(ws.current===socket)ws.current=null;
        if(mounted){setStatus("Reconectando…");reconnect.current=setTimeout(connect,1500);}
      };
      socket.onerror=()=>setStatus("Conexão interrompida");
    }
    connect();
    const sync=setInterval(()=>{if(ws.current?.readyState===WebSocket.OPEN)ws.current.send(JSON.stringify({type:"sync",nonce:Date.now()}));},5000);
    return ()=>{mounted=false;clearInterval(sync);if(reconnect.current)clearTimeout(reconnect.current);
      ws.current?.close();ws.current=null;};
  },[]);

  useEffect(()=>{
    let live=true;setLyrics(null);setPrepared(false);
    const old=player.current;player.current=null;if(old)void old.close();
    if(state?.song_id){api.selectedLyrics(state.song_id).then(r=>{if(live)setLyrics(r);})
      .catch(e=>{if(live)setError(e instanceof Error?e.message:"Letra indisponível.");});}
    return ()=>{live=false;};
  },[state?.song_id,api]);

  useEffect(()=>{
    let frame=0;const tick=()=>{
      const st=latest.current;
      if(st){const pos=isHost&&player.current?.isPlaying?player.current.position()*1000:
        positionMs(st,Date.now(),skewRef.current);
        const max=current?.duration_s?current.duration_s*1000:pos;
        setTime(Math.max(0,Math.min(pos,max)));
      }
      frame=requestAnimationFrame(tick);
    };frame=requestAnimationFrame(tick);return()=>cancelAnimationFrame(frame);
  },[current?.duration_s,isHost]);

  useEffect(()=>{
    if(!isHost)return;
    const p=player.current,st=state;
    if(!p||!st||!prepared)return;
    p.setGain("instrumental",st.instrumental);
    p.setGain("vocals",st.vocals);
    const expected=positionMs(st,Date.now(),skewRef.current)/1000;
    if(st.playing){
      if(!p.isPlaying||Math.abs(p.position()-expected)>.20){
        void p.seek(expected).then(()=>p.play()).catch(e=>setError(String(e)));
      }
    }else if(p.isPlaying)p.pause();
    else if(Math.abs(p.position()-expected)>.20)void p.seek(expected);
  },[state,isHost,prepared]);

  useEffect(()=>{
    if(!isHost)return;
    report.current=setInterval(()=>{
      if(player.current?.isPlaying&&ws.current?.readyState===WebSocket.OPEN)
        send("report",Math.round(player.current.position()*1000));
    },2000);
    return()=>{if(report.current)clearInterval(report.current);};
  },[isHost]);
  useEffect(()=>{const cb=()=>setFullscreen(document.fullscreenElement===stage.current);
    document.addEventListener("fullscreenchange",cb);return()=>document.removeEventListener("fullscreenchange",cb);},[]);

  async function arm(){
    if(!isHost||!state?.song_id)return;
    try {
      if(player.current)await player.current.close();
      const p=new SyncedStems();player.current=p;
      await p.ctx.resume(); // chamada inicia no gesto do host
      setStatus("Carregando áudio do host…");
      await p.load(api,state.song_id);
      p.setGain("instrumental",state.instrumental);p.setGain("vocals",state.vocals);
      setPrepared(true);send("ready");setStatus("Áudio do host pronto");
    }catch(e){setError(e instanceof Error?e.message:"Falha no áudio do host.");}
  }
  async function full(){try{if(!document.fullscreenElement)await stage.current?.requestFullscreen();else await document.exitFullscreen();}
    catch{setError("Tela cheia indisponível.");}}
  function background(file?:File){
    if(!file)return;
    if(!["image/jpeg","image/png","image/webp"].includes(file.type)||file.size>256000){setError("Use JPEG, PNG ou WebP até 256 KB.");return;}
    const r=new FileReader();r.onload=()=>{if(typeof r.result==="string")send("background",r.result);};r.readAsDataURL(file);
  }
  const noHost=!state?.host_online;
  const controls=Boolean(state?.song_id&&state.host_ready&&!noHost);
  return <section className="col"><h2>Sessão de karaokê</h2>
    <p role="status">{status}{state?.song_id?` · ${current?.title||"música selecionada"}`:""}</p>
    {error&&<p role="alert" className="error">{error}</p>}
    {isHost&&<div className="row"><label>Selecionar música <select value={selection} onChange={e=>setSelection(e.target.value)}>
      <option value="">Escolha uma música</option>{valid.map(s=><option key={s.id} value={s.id}>{s.title} — {s.artist}</option>)}</select></label>
      <button disabled={!selection||!ws.current} onClick={()=>send("select",selection)}>Exibir música para todos</button>
      <button disabled={!state?.song_id||prepared} onClick={()=>void arm()}>Habilitar áudio do host</button></div>}
    {state?.song_id&&<>
      {!state.host_ready&&<p>Aguardando o host preparar e habilitar o áudio. Convidados permanecem sem áudio.</p>}
      <div className="row"><button disabled={!controls} onClick={()=>send(state.playing?"pause":"play")}>{state.playing?"Pausar":"Play"}</button>
        <button onClick={()=>void full()}>{fullscreen?"Sair da tela cheia":"Tela cheia"}</button>
        <span>{(time/1000).toFixed(1)} / {(current?.duration_s||0).toFixed(1)} s</span></div>
      <label>Progresso <input type="range" min="0" max={(current?.duration_s||1)*1000} step="100" value={time}
        disabled={!controls} onChange={e=>send("seek",Number(e.target.value))} /></label>
      <label>Instrumental {Math.round(state.instrumental*100)}% <input type="range" min="0" max="1" step=".01" value={state.instrumental}
        disabled={!controls} onChange={e=>send("volume",{stem:"instrumental",level:Number(e.target.value)})} /></label>
      <label>Vocais {Math.round(state.vocals*100)}% <input type="range" min="0" max="1" step=".01" value={state.vocals}
        disabled={!controls} onChange={e=>send("volume",{stem:"vocals",level:Number(e.target.value)})} /></label>
      <p>Backing separado: indisponível; não há controle simulado.</p>
      {isHost&&<div className="col"><label>Imagem de fundo compartilhada (até 256 KB)
        <input type="file" accept="image/png,image/jpeg,image/webp" onChange={e=>background(e.target.files?.[0])} /></label>
        <div className="row"><span>Offset da letra: {pickOffset} ms</span>
          {[-500,-50,50,500].map(x=><button key={x} onClick={()=>setPickOffset(v=>Math.max(-10000,Math.min(10000,v+x)))}>{x>0?"+":""}{x} ms</button>)}
          <button onClick={()=>send("offset",pickOffset)}>Aplicar para todos</button></div></div>}
      <div ref={stage} className="karaoke-stage" style={{backgroundImage:state.background?`linear-gradient(#0008,#0009),url(${JSON.stringify(state.background)})`:"linear-gradient(135deg,#111,#282856)"}}>
        <div className="karaoke-lines" aria-live="off">{lines.map(([ms,text],i)=><p key={`${ms}-${i}`} className={i===index?"karaoke-active":""}>{text||"♪"}</p>)}</div>
        {fullscreen&&<button className="karaoke-exit" onClick={()=>void full()}>Sair da tela cheia</button>}
      </div>
      {!isHost&&<p className="hint">Este dispositivo não reproduz áudio. Apenas o host emite som.</p>}
    </>}
  </section>;
}
