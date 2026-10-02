import { describe, expect, it, vi } from "vitest";
import { activeLine, SyncedStems } from "./syncedAudio";

describe("letra e relógio",()=>{
  const lines:[[number,string],[number,string],[number,string]]=[[1000,"A"],[2500,"B"],[4000,"C"]];
  it("aplica offset sem alterar timestamps",()=>{
    expect(activeLine(lines,.9,0)).toBe(-1);
    expect(activeLine(lines,.9,100)).toBe(0);
    expect(activeLine(lines,2.4,100)).toBe(1);
    expect(activeLine(lines,2.5,-100)).toBe(0);
    expect(activeLine(lines,10,0)).toBe(2);
  });
  it("agenda instrumental e vocais no mesmo instante e offset",async()=>{
    const starts:[number,number][]=[];
    const makeSource=()=>({buffer:null,connect:vi.fn(),disconnect:vi.fn(),start:(t:number,o:number)=>starts.push([t,o]),stop:vi.fn()});
    const ctx={currentTime:10,destination:{},createGain:()=>({gain:{value:0,setTargetAtTime:vi.fn()},connect:vi.fn()}),
      createBufferSource:makeSource,resume:vi.fn().mockResolvedValue(undefined),close:vi.fn().mockResolvedValue(undefined),
      decodeAudioData:vi.fn().mockResolvedValue({duration:20})} as unknown as AudioContext;
    const p=new SyncedStems(ctx);
    const oldFetch=globalThis.fetch;
    globalThis.fetch=vi.fn().mockResolvedValue({arrayBuffer:async()=>new ArrayBuffer(2)}) as typeof fetch;
    const oldRevoke=URL.revokeObjectURL;
    URL.revokeObjectURL=vi.fn();
    try{
      await p.load({audioBlobUrl:async(_,stem)=>`blob:${stem}`},"s");
      await p.seek(3);await p.play();
      expect(starts).toEqual([[10.05,3],[10.05,3]]);
      expect(p.position()).toBe(3);
      await p.close();
    }finally{globalThis.fetch=oldFetch;URL.revokeObjectURL=oldRevoke;}
  });
});
