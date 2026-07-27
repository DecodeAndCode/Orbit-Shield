import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type {
  ConjunctionResponse,
  ConjunctionDetailResponse,
  SatelliteResponse,
  PropagateResponse,
  CatalogPositionsResponse,
  MLCompareResponse,
  AlertConfigResponse,
} from "./types";

const BASE = "";

/**
 * Where the data being displayed came from.
 *
 * The API serves a bundled snapshot when its database is unreachable, so the
 * dashboard keeps working during provider outages. That data is real but
 * frozen, and the UI has to say so rather than present it as live.
 */
export type DataSource = "live" | "snapshot" | "unknown";

let currentSource: DataSource = "unknown";
let generatedAt: string | null = null;
const sourceListeners = new Set<() => void>();

function publishSource(next: DataSource, when: string | null) {
  if (next === currentSource && when === generatedAt) return;
  currentSource = next;
  generatedAt = when;
  sourceListeners.forEach((notify) => notify());
}

export function subscribeToDataSource(listener: () => void) {
  sourceListeners.add(listener);
  return () => sourceListeners.delete(listener);
}

export function getDataSource(): DataSource {
  return currentSource;
}

export function getDataGeneratedAt(): string | null {
  return generatedAt;
}

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  const source = res.headers.get("X-Data-Source");
  if (source === "snapshot" || source === "live") {
    publishSource(source, res.headers.get("X-Data-Generated-At"));
  }

  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  if (res.status === 204) return undefined as T;
  return res.json();
}

export function useSatellites(search?: string, regime?: string) {
  return useQuery({
    queryKey: ["satellites", search, regime],
    enabled: Boolean(search) || Boolean(regime),
    queryFn: () => {
      const params = new URLSearchParams();
      if (search) params.set("search", search);
      if (regime) params.set("regime", regime);
      return fetchJSON<{ items: SatelliteResponse[]; total: number }>(
        `/api/satellites?${params}`
      );
    },
  });
}

export function useConjunctions(minPc?: number, hoursAhead = 72) {
  return useQuery({
    queryKey: ["conjunctions", minPc, hoursAhead],
    queryFn: () => {
      const params = new URLSearchParams();
      if (minPc !== undefined) params.set("min_pc", String(minPc));
      params.set("hours_ahead", String(hoursAhead));
      return fetchJSON<ConjunctionResponse[]>(`/api/conjunctions?${params}`);
    },
  });
}

export function useConjunctionDetail(id: number | null) {
  return useQuery({
    queryKey: ["conjunction", id],
    queryFn: () => fetchJSON<ConjunctionDetailResponse>(`/api/conjunctions/${id}`),
    enabled: id !== null,
  });
}

export function usePropagate(noradIds: number[], durationHours = 2, stepMinutes = 1) {
  return useQuery({
    queryKey: ["propagate", noradIds, durationHours, stepMinutes],
    queryFn: () =>
      fetchJSON<PropagateResponse[]>("/api/propagate", {
        method: "POST",
        body: JSON.stringify({
          norad_ids: noradIds,
          duration_hours: durationHours,
          step_minutes: stepMinutes,
        }),
      }),
    enabled: noradIds.length > 0,
  });
}

export function useCatalogPositions() {
  return useQuery({
    queryKey: ["catalog-positions"],
    queryFn: () => fetchJSON<CatalogPositionsResponse>("/api/positions"),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}

export function useMLCompare(conjunctionId: number | null) {
  return useQuery({
    queryKey: ["ml-compare", conjunctionId],
    queryFn: () => fetchJSON<MLCompareResponse>(`/api/ml/compare/${conjunctionId}`),
    enabled: conjunctionId !== null,
  });
}

export function useAlerts() {
  return useQuery({
    queryKey: ["alerts"],
    queryFn: () => fetchJSON<AlertConfigResponse[]>("/api/alerts"),
  });
}

export function useCreateAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Omit<AlertConfigResponse, "id">) =>
      fetchJSON<AlertConfigResponse>("/api/alerts", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

export function useUpdateAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: AlertConfigResponse) =>
      fetchJSON<AlertConfigResponse>(`/api/alerts/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

export function useDeleteAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      fetchJSON<void>(`/api/alerts/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });
}
