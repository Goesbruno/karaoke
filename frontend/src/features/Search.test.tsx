import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Search } from "./Search";
import { ApiError, type ApiPort } from "../ports/api";

const item = { video_id: "dQw4w9WgXcQ", title: "Título do vídeo", channel: "Canal Teste", thumbnail: null, duration_s: 205, embeddable: true };

function makeApi(over: Partial<ApiPort> = {}): ApiPort {
  return {
    search: vi.fn().mockResolvedValue({ mode: "text", attribution: "YouTube", items: [item] }),
    createSong: vi.fn().mockResolvedValue({ id: "s1", title: "Minha música", artist: "Eu" }),
    upload: vi.fn().mockResolvedValue({}),
    ...over,
  } as unknown as ApiPort;
}

async function searchAndAdd(api: ApiPort, isHost: boolean, onAdded = vi.fn()) {
  render(<Search api={api} onAdded={onAdded} isHost={isHost} />);
  fireEvent.change(screen.getByLabelText(/Nome da música ou URL/), { target: { value: "queen" } });
  fireEvent.click(screen.getByRole("button", { name: "Buscar" }));
  await screen.findByText("Título do vídeo");
  fireEvent.click(screen.getByRole("button", { name: "Adicionar" }));
  fireEvent.change(screen.getByLabelText(/Título da música/), { target: { value: "Minha música" } });
  fireEvent.change(screen.getByLabelText(/Artista/), { target: { value: "Eu" } });
  fireEvent.click(screen.getByRole("button", { name: "Confirmar" }));
  await screen.findByText(/foi adicionada/);
}

describe("Search", () => {
  it("mostra atribuição, canal e duração, diferenciando do nome da música", async () => {
    render(<Search api={makeApi()} onAdded={vi.fn()} isHost={false} />);
    fireEvent.change(screen.getByLabelText(/Nome da música ou URL/), { target: { value: "queen" } });
    fireEvent.click(screen.getByRole("button", { name: "Buscar" }));
    expect(await screen.findByText("Título do vídeo")).toBeInTheDocument();
    expect(screen.getByText(/Canal: Canal Teste/)).toBeInTheDocument();
    expect(screen.getByText(/Duração: 3:25/)).toBeInTheDocument();
    expect(screen.getByText(/Fonte: YouTube/)).toBeInTheDocument();
    expect(screen.getByText(/podem precisar de correção/)).toBeInTheDocument();
  });

  it("adiciona com título e artista corrigidos e envia o ID do vídeo", async () => {
    const api = makeApi(); const onAdded = vi.fn();
    await searchAndAdd(api, false, onAdded);
    expect(api.createSong).toHaveBeenCalledWith({ title: "Minha música", artist: "Eu", source_video_id: "dQw4w9WgXcQ" });
    expect(onAdded).toHaveBeenCalled();
  });

  it("host vê o campo de upload logo após adicionar e envia o arquivo", async () => {
    const api = makeApi();
    await searchAndAdd(api, true);
    const input = screen.getByLabelText(/Arquivo de áudio autorizado/);
    const file = new File(["x"], "a.mp3", { type: "audio/mpeg" });
    fireEvent.change(input, { target: { files: [file] } });
    expect(await screen.findByText(/Arquivo recebido/)).toBeInTheDocument();
    expect(api.upload).toHaveBeenCalledWith("s1", file, false);
  });

  it("convidado é informado de que o host precisa enviar o áudio", async () => {
    await searchAndAdd(makeApi(), false);
    expect(screen.getByText(/Aguardando o host enviar/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Arquivo de áudio autorizado/)).toBeNull();
  });

  it("mostra erro de upload sem esconder o campo", async () => {
    const api = makeApi({ upload: vi.fn().mockRejectedValue(new ApiError(422, "extensao", "x")) });
    await searchAndAdd(api, true);
    fireEvent.change(screen.getByLabelText(/Arquivo de áudio autorizado/), { target: { files: [new File(["x"], "a.exe")] } });
    expect(await screen.findByRole("alert")).toHaveTextContent(/Extensão/);
    expect(screen.getByLabelText(/Arquivo de áudio autorizado/)).toBeInTheDocument();
  });

  it("exibe mensagem clara quando o servidor está sem internet", async () => {
    const api = makeApi({ search: vi.fn().mockRejectedValue(new ApiError(503, "sem_internet", "x")) });
    render(<Search api={api} onAdded={vi.fn()} isHost={false} />);
    fireEvent.change(screen.getByLabelText(/Nome da música ou URL/), { target: { value: "queen" } });
    fireEvent.click(screen.getByRole("button", { name: "Buscar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/Sem internet/);
  });
});
