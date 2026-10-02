export function mapYtError(code: number): string {
  switch (code) {
    case 2: return "Identificador de vídeo inválido.";
    case 5: return "Erro do player HTML5 do YouTube.";
    case 100: return "Vídeo não encontrado, removido ou privado.";
    case 101:
    case 150: return "O proprietário do vídeo bloqueou a reprodução incorporada.";
    case 153: return "O YouTube não recebeu a origem (Referer) da página e recusou o player (erro 153).";
    default: return `Erro do player do YouTube (código ${code}).`;
  }
}
