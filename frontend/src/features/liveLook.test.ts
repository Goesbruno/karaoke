import { describe, expect, it } from "vitest";
import { clampBlur, clampContrast, clampOpacity, formatClock, isTypingTarget, lyricStyle } from "./liveLook";

describe("ajustes visuais", () => {
  it("limita blur, opacidade e contraste", () => {
    expect(clampBlur(-4)).toBe(0);
    expect(clampBlur(99)).toBe(30);
    expect(clampBlur(Number.NaN)).toBe(0);
    expect(clampOpacity(2)).toBe(1);
    expect(clampOpacity(-1)).toBe(0);
    expect(clampContrast(150)).toBe(100);
  });
  it("mais contraste escurece o fundo da letra e reforça a sombra", () => {
    const low = lyricStyle(0);
    const high = lyricStyle(100);
    expect(Number(high["--lyric-scrim"])).toBeGreaterThan(Number(low["--lyric-scrim"]));
    expect(Number(high["--lyric-shadow"])).toBeGreaterThan(Number(low["--lyric-shadow"]));
  });
  it("formata o relógio", () => {
    expect(formatClock(65_000)).toBe("1:05");
    expect(formatClock(-5)).toBe("0:00");
  });
});

describe("atalho da barra de espaço", () => {
  it("não intercepta campos de texto nem seletores", () => {
    const text = document.createElement("input"); text.type = "text";
    const select = document.createElement("select");
    const area = document.createElement("textarea");
    expect(isTypingTarget(text)).toBe(true);
    expect(isTypingTarget(select)).toBe(true);
    expect(isTypingTarget(area)).toBe(true);
  });
  it("permite tocar/pausar com foco em botão ou controle deslizante", () => {
    const button = document.createElement("button");
    const range = document.createElement("input"); range.type = "range";
    expect(isTypingTarget(button)).toBe(false);
    expect(isTypingTarget(range)).toBe(false);
    expect(isTypingTarget(null)).toBe(false);
  });
});
