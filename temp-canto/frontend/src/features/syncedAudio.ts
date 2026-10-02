export type Buffers = { instrumental: AudioBuffer; vocals: AudioBuffer };
export type Stems = "instrumental" | "vocals";

/** Um AudioContext, um instante de start, duas fontes one-shot. */
export class SyncedStems {
  readonly ctx: AudioContext;
  private buffers: Buffers | null = null;
  private nodes: AudioBufferSourceNode[] = [];
  private gains: Record<Stems, GainNode>;
  private startedAt = 0;
  private base = 0;
  private playing = false;
  duration = 0;

  constructor(ctx: AudioContext = new AudioContext()) {
    this.ctx = ctx;
    this.gains = { instrumental: ctx.createGain(), vocals: ctx.createGain() };
    this.gains.instrumental.gain.value = 0.85;
    this.gains.vocals.gain.value = 0;
    this.gains.instrumental.connect(ctx.destination);
    this.gains.vocals.connect(ctx.destination);
  }
  async load(api: {audioBlobUrl(id: string, stem: Stems): Promise<string>}, id: string) {
    const urls: string[] = [];
    try {
      const map = {} as Buffers;
      for (const stem of (["instrumental", "vocals"] as const)) {
        const url = await api.audioBlobUrl(id,stem); urls.push(url);
        const data = await (await fetch(url)).arrayBuffer();
        map[stem] = await this.ctx.decodeAudioData(data);
      }
      if (Math.abs(map.instrumental.duration - map.vocals.duration) > 0.1)
        throw new Error("Stems com durações diferentes; verifique o processamento.");
      this.buffers = map;
      this.duration = Math.min(map.instrumental.duration,map.vocals.duration);
    } finally { urls.forEach(u => URL.revokeObjectURL(u)); }
  }
  setGain(stem: Stems,value: number) {
    this.gains[stem].gain.setTargetAtTime(Math.max(0,Math.min(1,value)),this.ctx.currentTime,.01);
  }
  get isPlaying() { return this.playing; }
  position() {
    return Math.max(0,Math.min(this.duration,this.base + (this.playing ? Math.max(0,this.ctx.currentTime-this.startedAt) : 0)));
  }
  private halt() {
    this.nodes.forEach(n => {try{n.stop();}catch{ /* já terminou */ } n.disconnect();});
    this.nodes = [];this.playing = false;
  }
  async play() {
    if (!this.buffers || this.playing) return;
    await this.ctx.resume();
    if (this.base >= this.duration) this.base = 0;
    const at=this.ctx.currentTime+.05;
    this.startedAt=at;
    const created = (["instrumental","vocals"] as const).map(stem => {
      const n=this.ctx.createBufferSource();n.buffer=this.buffers![stem];n.connect(this.gains[stem]);return n;
    });
    this.nodes=created;this.playing=true;
    created.forEach(n => n.start(at,this.base));
  }
  pause() { if (this.playing) {this.base=this.position();this.halt();} }
  seek(seconds: number) {
    const wasPlaying=this.playing;
    this.pause();this.base=Math.max(0,Math.min(this.duration,seconds));
    if (wasPlaying) return this.play();
    return Promise.resolve();
  }
  async close() {this.halt();await this.ctx.close();}
}

export function activeLine(lines: [number,string][],timeSeconds: number,offsetMs: number): number {
  const ms=timeSeconds*1000+offsetMs;
  let lo=0,hi=lines.length;
  while(lo<hi){const m=(lo+hi)>>>1;if(lines[m][0]<=ms)lo=m+1;else hi=m;}
  return lo-1;
}
