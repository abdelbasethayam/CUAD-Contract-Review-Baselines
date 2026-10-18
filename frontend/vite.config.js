import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const base = process.env.CONTRACT_REVIEW_BASE_PATH || "/";
const port = Number(process.env.PORT || 5173);
const basePrefix = base === "/" ? "" : base.replace(/\/+$/, "");
const backendProxy = (target) => ({
  target,
  changeOrigin: true,
  rewrite: (path) => (basePrefix && path.startsWith(basePrefix) ? path.slice(basePrefix.length) : path),
});

export default defineConfig({
  base,
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port,
    strictPort: true,
    proxy: {
      [`${basePrefix}/documents`]: backendProxy("http://127.0.0.1:8000"),
      [`${basePrefix}/query`]: backendProxy("http://127.0.0.1:8000"),
      [`${basePrefix}/health`]: backendProxy("http://127.0.0.1:8000"),
    },
  },
});
