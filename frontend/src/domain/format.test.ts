import { describe, expect, it } from "vitest";
import { formatDuration, previewPlan } from "./format";
import { parseTokenFromHash } from "./session";
import { mapYtError } from "./ytErrors";

describe("formatDuration", () => {
  it("formata minutos e horas", () => {
    expect(formatDuration(205)).toBe("3:25");
    expect(formatDuration(3723)).toBe("1:02:03");
  });
  it("indica indisponível", () => {
    expect(formatDuration(null)).toBe("—");
    expect(formatDuration(NaN)).toBe("—");
  });
});

describe("previewPlan", () => {
  it("usa a metade da duração", () => {
    expect(previewPlan(200)).toEqual({ ok: true, start: 100, length: 5 });
  });
  it("garante que 5 s caibam no vídeo", () => {
    expect(previewPlan(8)).toEqual({ ok: true, start: 3, length: 5 });
  });
  it("vídeos muito curtos começam do zero", () => {
    expect(previewPlan(3)).toEqual({ ok: true, start: 0, length: 3 });
  });
  it("recusa duração indisponível", () => {
    expect(previewPlan(null).ok).toBe(false);
    expect(previewPlan(0).ok).toBe(false);
  });
});

describe("parseTokenFromHash", () => {
  it("lê o token do fragmento", () => {
    expect(parseTokenFromHash("#token=abc_123-x")).toBe("abc_123-x");
    expect(parseTokenFromHash("#a=1&token=zz")).toBe("zz");
  });
  it("retorna null quando ausente ou malformado", () => {
    expect(parseTokenFromHash("")).toBeNull();
    expect(parseTokenFromHash("#outro=1")).toBeNull();
    expect(parseTokenFromHash("#token=%E0%A4%A")).toBeNull();
  });
});

describe("mapYtError", () => {
  it("traduz bloqueio de incorporação", () => {
    expect(mapYtError(101)).toMatch(/bloqueou/);
    expect(mapYtError(150)).toMatch(/bloqueou/);
    expect(mapYtError(999)).toMatch(/999/);
  });
});
