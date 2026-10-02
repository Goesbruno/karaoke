export type Stems = "instrumental" | "vocals" | "lead" | "backing";
export type Buffers = Partial<Record<Stems, AudioBuffer>>;

/** Um AudioContext, um instante de start, fontes one-shot sincronizadas. */
export class SyncedStems {
  readonly ctx: AudioContext;
  private buffers: Buffers | null = null;
  private active: Stems[] = [];
  private nodes: AudioBufferSourceNode[] = [];
  private gains: Record<Stems, GainNode>;
  private startedAt = 0;
  private base = 0;
  private playing = false;
  duration = 0;

  constructor(ctx: AudioContext = new AudioContext()) {
    this.ctx = ctx;
    this.gains = {
      instrumental: ctx.createGain(), vocals: ctx.createGain(),
      lead: ctx.createGain(), backing: ctx.createGain(),
    };
    this.gains.instrumental.gain.value = 0.85;
    this.gains.vocals.gain.value = 0;
    this.gains.lead.gain.value = 0;
    this.gains.backing.gain.value = 0;
    Object.values(this.gains).forEach(g => g.connect(ctx.destination));
  }
  async load(api: {audioBlobUrl(id: string, stem: Stems): Promise<string>}, id: string, split = false) {
    const urls: string[] = [];
    const stems: Stems[] = split ? ["instrumental", "lead", "backing"] : ["instrumental", "vocals"];
    try {
      const map: Buffers = {};
      for (const stem of stems) {
        const url = await api.audioBlobUrl(id, stem); urls.push(url);
        const data = await (await fetch(url)).arrayBuffer();
        map[stem] = await this.ctx.decodeAudioData(data);
      }
      const durations = stems.map(stem => map[stem]!.duration);
      if (Math.max(...durations) - Math.min(...durations) > 0.1)
        throw new Error("Stems com durações diferentes; verifique o processamento.");
      this.buffers = map;
      this.active = stems;
      this.duration = Math.min(...durations);
      this.base = 0;
    } finally { urls.forEach(u => URL.revokeObjectURL(u)); }
  }
  setGain(stem: Stems, value: number) {
    this.gains[stem].gain.setTargetAtTime(Math.max(0, Math.min(1, value)), this.ctx.currentTime, .01);
  }
  get isPlaying() { return this.playing; }
  position() {
    return Math.max(0, Math.min(this.duration,
      this.base + (this.playing ? Math.max(0, this.ctx.currentTime - this.startedAt) : 0)));
  }
  private halt() {
    this.nodes.forEach(n => { try { n.stop(); } catch { /* já terminou */ } n.disconnect(); });
    this.nodes = []; this.playing = false;
  }
  async play() {
    if (!this.buffers || this.playing) return;
    await this.ctx.resume();
    if (this.base >= this.duration) this.base = 0;
    const at = this.ctx.currentTime + .05;
    this.startedAt = at;
    const created = this.active.map(stem => {
      const n = this.ctx.createBufferSource();
      n.buffer = this.buffers![stem]!;
      n.connect(this.gains[stem]);
      return n;
    });
    this.nodes = created; this.playing = true;
    created.forEach(n => n.start(at, this.base));
  }
  pause() { if (this.playing) { this.base = this.position(); this.halt(); } }
  seek(seconds: number) {
    const wasPlaying = this.playing;
    this.pause(); this.base = Math.max(0, Math.min(this.duration, seconds));
    if (wasPlaying) return this.play();
    return Promise.resolve();
  }
  async close() { this.halt(); await this.ctx.close(); }
}

export function activeLine(lines: [number,string][], timeSeconds: number, offsetMs: number): number {
  const ms = timeSeconds * 1000 + offsetMs;
  let lo = 0, hi = lines.length;
  while (lo < hi) { const m = (lo + hi) >>> 1; if (lines[m][0] <= ms) lo = m + 1; else hi = m; }
  return lo - 1;
}
