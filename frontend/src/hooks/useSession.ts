import { useCallback, useEffect, useRef, useState } from "react";
import { parseTokenFromHash } from "../domain/session";
import type { Role } from "../domain/types";
import type { ApiPort } from "../ports/api";

const KEY = "karaoke.token";
export type SessionState =
  | { status: "loading" } | { status: "need-token" } | { status: "denied" }
  | { status: "ready"; role: Role; permissions: string[] };

export function useSession(api: ApiPort) {
  const [state, setState] = useState<SessionState>({ status: "loading" });
  const started = useRef(false);

  const login = useCallback(async (token: string) => {
    try {
      api.setToken(token);
      const r = await api.join(token);
      sessionStorage.setItem(KEY, token);
      setState({ status: "ready", role: r.role, permissions: r.permissions });
    } catch {
      api.setToken(null);
      sessionStorage.removeItem(KEY);
      setState({ status: "denied" });
    }
  }, [api]);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const t = parseTokenFromHash(window.location.hash) ?? sessionStorage.getItem(KEY);
    if (window.location.hash) history.replaceState(null, "", window.location.pathname + window.location.search);
    if (t) void login(t); else setState({ status: "need-token" });
  }, [login]);

  return { state, login };
}
