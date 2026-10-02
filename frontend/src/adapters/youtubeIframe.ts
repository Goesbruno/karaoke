export interface YTPlayer {
  pauseVideo(): void;
  destroy(): void;
}
export interface YTNamespace {
  Player: new (el: HTMLElement, opts: {
    events: {
      onReady?: () => void;
      onStateChange?: (e: { data: number }) => void;
      onError?: (e: { data: number }) => void;
      onAutoplayBlocked?: () => void;
    };
  }) => YTPlayer;
  PlayerState: { PLAYING: number; BUFFERING: number; PAUSED: number; ENDED: number };
}
declare global {
  interface Window { YT?: YTNamespace; onYouTubeIframeAPIReady?: () => void }
}

let loading: Promise<YTNamespace> | null = null;

/** Carrega o script oficial do YouTube IFrame Player API (exige internet). */
export function loadYouTubeApi(): Promise<YTNamespace> {
  if (window.YT?.Player) return Promise.resolve(window.YT);
  if (!loading) {
    loading = new Promise<YTNamespace>((resolve, reject) => {
      const prev = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = () => { prev?.(); resolve(window.YT!); };
      const s = document.createElement("script");
      s.src = "https://www.youtube.com/iframe_api";
      s.onerror = () => { loading = null; reject(new Error("offline")); };
      document.head.appendChild(s);
    });
  }
  return loading;
}
