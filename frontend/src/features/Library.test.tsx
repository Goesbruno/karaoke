import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Library } from "./Library";
import type { Song } from "../domain/types";
import type { ApiPort } from "../ports/api";

function song(over: Partial<Song["library"]> = {}): Song {
  return {
    id: "s1", title: "Minha canção", artist: "Artista", status: "CONCLUIDA",
    source_video_id: null, original_name: "a.mp3", duration_s: 120, key_manual: null,
    lyrics_offset_ms: 0,
    library: {
      ready: true, issues: [], key_estimated: null, key_confidence: null, key_warning: "",
      lead_backing_available: true, lead_backing_reason: "", lyrics_status: "LETRA_SINCRONIZADA", ...over,
    },
  };
}

function setup(s: Song, isHost: boolean) {
  const onChooseLyrics = vi.fn();
  const onSing = vi.fn();
  render(<Library api={{} as ApiPort} songs={[s]} isHost={isHost} reload={vi.fn()}
                  onChooseLyrics={onChooseLyrics} onSing={onSing} />);
  return { onChooseLyrics, onSing };
}

describe("Library: letra e canto no card", () => {
  it("host escolhe a letra e canta direto pelo card", () => {
    const s = song();
    const { onChooseLyrics, onSing } = setup(s, true);
    fireEvent.click(screen.getByRole("button", { name: "Selecionar letra" }));
    fireEvent.click(screen.getByRole("button", { name: "Cantar" }));
    expect(onChooseLyrics).toHaveBeenCalledWith(s);
    expect(onSing).toHaveBeenCalledWith(s);
  });

  it("Cantar fica desabilitado sem letra sincronizada", () => {
    setup(song({ lyrics_status: "SEM_LETRA" }), true);
    expect(screen.getByRole("button", { name: "Cantar" })).toBeDisabled();
    expect(screen.getByText(/selecione uma letra sincronizada/)).toBeInTheDocument();
  });

  it("convidado não recebe o botão Cantar", () => {
    setup(song(), false);
    expect(screen.queryByRole("button", { name: "Cantar" })).toBeNull();
    expect(screen.getByRole("button", { name: "Ver letras" })).toBeInTheDocument();
  });
});
