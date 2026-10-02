export interface SessionState {
  version:number; song_id:string|null; playing:boolean; position_ms:number; started_at_ms:number;
  server_ms:number; host_online:boolean; host_ready:boolean;
  instrumental:number; vocals:number; backing:number; offset_ms:number; background:string;
}
export function positionMs(s:SessionState, nowMs:number, clockSkewMs:number):number {
  return Math.max(0,s.position_ms+(s.playing?Math.max(0,nowMs+clockSkewMs-s.started_at_ms):0));
}
export function lineIndex(lines:[number,string][],ms:number,offsetMs:number):number {
  let lo=0,hi=lines.length;
  while(lo<hi){const mid=(lo+hi)>>>1;if(lines[mid][0]<=ms+offsetMs)lo=mid+1;else hi=mid;}
  return lo-1;
}
export function newer(current:SessionState|null,incoming:SessionState):boolean {
  return current===null || incoming.version>=current.version;
}
