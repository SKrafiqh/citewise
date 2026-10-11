"use client";

import { useCallback, useEffect, useState } from "react";
import { errorMessage } from "./api";

type State<T> = { key: string; data: T | null; error: string | null };

/** Fetch on mount and whenever `key` changes. `reload()` refetches silently (keeps stale data). */
export function useApi<T>(fetcher: () => Promise<T>, key: string) {
  const [res, setRes] = useState<State<T>>({ key: "", data: null, error: null });
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let live = true;
    fetcher().then(
      (data) => live && setRes({ key, data, error: null }),
      (e) => live && setRes({ key, data: null, error: errorMessage(e) }),
    );
    return () => {
      live = false;
    };
    // fetcher is recreated every render; `key` is the cache identity.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  const current = res.key === key;
  return {
    data: current ? res.data : null,
    error: current ? res.error : null,
    loading: !current,
    reload,
  };
}
