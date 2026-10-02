import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SongBackgroundControl } from "./SongBackgroundControl";
import type { ApiPort } from "../ports/api";

function makeApi(ids: string[] = []) {
  return {
    listBackgrounds: vi.fn().mockResolvedValue({ song_ids: ids }),
    setSongBackground: vi.fn().mockResolvedValue({ has_background: true }),
    clearSongBackground: vi.fn().mockResolvedValue({ has_background: false }),
  } as unknown as ApiPort & { setSongBackground: ReturnType<typeof vi.fn>; clearSongBackground: ReturnType<typeof vi.fn> };
}

describe("SongBackgroundControl", () => {
  it("mostra se a música já tem imagem própria", async () => {
    render(<SongBackgroundControl api={makeApi(["s1"])} songId="s1" />);
    expect(await screen.findByText(/tem imagem própria/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remover imagem" })).toBeInTheDocument();
  });

  it("envia a imagem escolhida somente para a música indicada", async () => {
    const api = makeApi(); const onChanged = vi.fn();
    render(<SongBackgroundControl api={api} songId="s2" onChanged={onChanged} />);
    await screen.findByText(/Sem imagem própria/);
    const file = new File(["x"], "capa.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText(/Imagem de fundo/), { target: { files: [file] } });
    expect(await screen.findByText(/Imagem salva/)).toBeInTheDocument();
    expect(api.setSongBackground).toHaveBeenCalledWith("s2", file);
    expect(onChanged).toHaveBeenCalled();
  });

  it("recusa tipo inválido sem chamar a API", async () => {
    const api = makeApi();
    render(<SongBackgroundControl api={api} songId="s3" />);
    await screen.findByText(/Sem imagem própria/);
    fireEvent.change(screen.getByLabelText(/Imagem de fundo/), { target: { files: [new File(["x"], "a.gif", { type: "image/gif" })] } });
    expect(await screen.findByRole("status")).toHaveTextContent(/Use PNG, JPEG ou WebP de até 256 KB/);
    expect(api.setSongBackground).not.toHaveBeenCalled();
  });

  it("remove a imagem da música", async () => {
    const api = makeApi(["s4"]);
    render(<SongBackgroundControl api={api} songId="s4" />);
    fireEvent.click(await screen.findByRole("button", { name: "Remover imagem" }));
    expect(await screen.findByText(/Imagem removida/)).toBeInTheDocument();
    expect(api.clearSongBackground).toHaveBeenCalledWith("s4");
  });
});
