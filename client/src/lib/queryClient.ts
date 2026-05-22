import { QueryClient } from "@tanstack/react-query";

// VITE_API_BASE from .env — empty string in dev (same-origin relative requests).
// In production, deploy_website replaces __PORT_5000__ in the built bundle
// with the actual proxy path so the deployed frontend reaches the Express API.
// If VITE_API_BASE is not set, fall back to the deploy-time sentinel.
const _RAW = import.meta.env.VITE_API_BASE ?? "__PORT_5000__";
// Guard: if the sentinel wasn't replaced (local dev), use relative URLs
const API_BASE: string = _RAW === "" || _RAW.includes("__PORT_") ? "" : _RAW;

export async function apiRequest(url: string, options?: RequestInit) {
  const fullUrl = url.startsWith("/") ? `${API_BASE}${url}` : url;
  const res = await fetch(fullUrl, options);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res;
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      queryFn: async ({ queryKey }) => {
        const url = Array.isArray(queryKey)
          ? (queryKey as string[]).join("")
          : (queryKey as string);
        const res = await apiRequest(url);
        return res.json();
      },
      staleTime: 1000 * 60 * 5,
      retry: 1,
    },
  },
});
