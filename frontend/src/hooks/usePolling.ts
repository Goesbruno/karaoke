import { useCallback, useEffect, useRef, useState } from "react";

export function usePolling<T>(fn: () => Promise<T>, ms: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef(fn);
  ref.current = fn;
  const reload = useCallback(async () => {
    try { setData(await ref.current()); setError(null); }
    catch (e) { setError(e instanceof Error ? e.message : "erro"); }
  }, []);
  useEffect(() => {
    void reload();
    const id = setInterval(() => void reload(), ms);
    return () => clearInterval(id);
  }, [reload, ms]);
  return { data, error, reload };
}
