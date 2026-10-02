import {describe,it,expect} from "vitest";
import {lineIndex,newer,positionMs,type SessionState} from "./liveClock";
const s:SessionState={version:3,song_id:"s",playing:true,position_ms:1000,started_at_ms:10000,
 server_ms:10000,host_online:true,host_ready:true,instrumental:.8,vocals:0,backing:0,offset_ms:0,background:""};
describe("relógio compartilhado",()=>{
 it("progride sem áudio no convidado e respeita pausa",()=>{
  expect(positionMs(s,11000,0)).toBe(2000);
  expect(positionMs({...s,playing:false},11000,0)).toBe(1000);
 });
 it("compensa diferença do relógio e aplica offset à letra",()=>{
  expect(positionMs(s,9000,2000)).toBe(2000);
  expect(lineIndex([[1000,"A"],[2000,"B"]],1900,100)).toBe(1);
  expect(lineIndex([[1000,"A"],[2000,"B"]],1900,-100)).toBe(0);
 });
 it("descarta versões antigas",()=>{
  expect(newer(s,{...s,version:2})).toBe(false);
  expect(newer(s,{...s,version:4})).toBe(true);
 });
});
