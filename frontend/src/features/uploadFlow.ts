import { ApiError, type ApiPort } from "../ports/api";

export const UP_ERR: Record<string, string> = {
  extensao: "Extensão de arquivo não permitida.",
  tamanho: "Arquivo maior que o limite de upload.",
  duracao: "Duração fora do intervalo permitido.",
  vazio: "O arquivo está vazio.",
  conteudo_invalido: "O arquivo não é um áudio válido.",
  conteudo_extensao: "O conteúdo do arquivo não corresponde à extensão.",
  sem_audio: "Nenhuma faixa de áudio encontrada.",
  espaco: "Espaço em disco insuficiente no servidor.",
  ffprobe_ausente: "FFmpeg/ffprobe não encontrado no servidor.",
  duplicado: "Este arquivo idêntico já existe na biblioteca.",
};

export async function uploadSong(
  api: ApiPort, id: string, file: File, confirmHomonym: () => boolean, allowHomonym = false,
): Promise<{ ok: boolean; message: string }> {
  try {
    await api.upload(id, file, allowHomonym);
    return { ok: true, message: "Arquivo recebido e enviado para a fila de processamento." };
  } catch (e) {
    if (e instanceof ApiError) {
      if (e.code === "homonimo" && !allowHomonym && confirmHomonym()) {
        return uploadSong(api, id, file, confirmHomonym, true);
      }
      return { ok: false, message: (e.code && UP_ERR[e.code]) || e.message };
    }
    return { ok: false, message: "Erro inesperado." };
  }
}

export const HOMONYM_QUESTION =
  "Já existe uma música com o mesmo título e artista, mas com conteúdo diferente. Manter as duas?";
