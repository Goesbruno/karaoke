export function parseTokenFromHash(hash: string): string | null {
  const m = /(?:^#|&)token=([^&]+)/.exec(hash);
  if (!m) return null;
  try { return decodeURIComponent(m[1]); } catch { return null; }
}
