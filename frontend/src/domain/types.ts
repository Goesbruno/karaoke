export type Role = "host" | "guest";

export interface SearchItem {
  video_id: string;
  title: string;
  channel: string;
  thumbnail: string | null;
  duration_s: number | null;
  embeddable: boolean | null;
}
export interface SearchResponse { mode: "text" | "url"; attribution: string; items: SearchItem[] }

export interface Song {
  id: string; title: string; artist: string; status: string;
  source_video_id: string | null; original_name: string; duration_s: number | null;
  key_manual: string | null;
  lyrics_offset_ms: number;
  library: LibraryStatus;
}
export interface LibraryStatus {
  ready: boolean;
  issues: string[];
  key_estimated: string | null;
  key_confidence: number | null;
  key_warning: string;
  lead_backing_available: boolean;
  lead_backing_reason: string;
  lyrics_status: string;
}
export interface Job {
  id: number; song_id: string; state: string; step: string; message: string;
  attempts: number; max_attempts: number; error: string; position: number | null;
}
export interface NetworkInfo {
  interfaces: { name: string; ip: string; private: boolean; virtual: boolean }[];
  selected: { name: string; ip: string } | null;
  url: string | null;
  diagnostics: string[];
  internet_dependencies: string[];
}
export interface Diagnostics {
  songs: { id: string; title: string; status: string; issues: string[]; pronta: boolean }[];
  orphan_dirs: string[];
}
export interface JoinResult { role: Role; permissions: string[] }
