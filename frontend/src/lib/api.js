const APP_BASE = import.meta.env.BASE_URL || "/";

export const appPath = (path) => APP_BASE + String(path || "").replace(/^\/+/, "");
export const API_URL = appPath("documents/classify/stream");

export const ANALYSIS_KEY = "clausewise.analysis_id";

export function rememberAnalysis(id) {
  try { window.sessionStorage.setItem(ANALYSIS_KEY, id); } catch { /* storage unavailable */ }
}

export function forgetAnalysis() {
  try { window.sessionStorage.removeItem(ANALYSIS_KEY); } catch { /* storage unavailable */ }
  try {
    const url = new URL(window.location.href);
    if (url.searchParams.has("analysis_id")) {
      url.searchParams.delete("analysis_id");
      window.history.replaceState({}, "", url.pathname + (url.search || "") + url.hash);
    }
  } catch { /* non-critical */ }
}

export function savedAnalysisId() {
  const requested = new URLSearchParams(window.location.search).get("analysis_id");
  if (requested) rememberAnalysis(requested);
  if (requested) return requested;
  try { return window.sessionStorage.getItem(ANALYSIS_KEY); } catch { return null; }
}
