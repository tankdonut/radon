"use client";

import { useCallback, useEffect, useState } from "react";
import type { BlotterData } from "./types";

type UseBlotterReturn = {
  data: BlotterData | null;
  loading: boolean;
  syncing: boolean;
  error: string | null;
  syncNow: () => void;
};

export function useBlotter(): UseBlotterReturn {
  const [data, setData] = useState<BlotterData | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchCache = useCallback(async () => {
    try {
      const res = await fetch("/api/blotter");
      if (!res.ok) throw new Error("Failed to fetch blotter");
      const json = (await res.json()) as BlotterData;
      setData(json);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  const syncNow = useCallback(async () => {
    setSyncing(true);
    try {
      const res = await fetch("/api/blotter", { method: "POST" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { error?: string }).error ?? "Blotter sync failed");
      }
      const json = (await res.json()) as BlotterData;
      setData(json);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Blotter sync failed");
    } finally {
      setSyncing(false);
    }
  }, []);

  useEffect(() => {
    void fetchCache();
  }, [fetchCache]);

  return { data, loading, syncing, error, syncNow };
}
