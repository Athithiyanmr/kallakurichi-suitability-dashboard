import { QueryClient } from "@tanstack/react-query";

// __PORT_5000__ is replaced at deploy time by deploy_website tool.
// In local mode, API_BASE stays as "__PORT_5000__" literal, so we handle
// that by falling back to empty string (relative URL).
const _BASE = import.meta.env.VITE_API_BASE ?? "__PORT_5000__";
const API_BASE = _BASE.includes("__PORT_") ? "" : _BASE;

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
