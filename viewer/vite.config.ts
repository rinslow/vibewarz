import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Single-bundle SPA. The build output is committed at
// sdk-python/src/vibewarz/viewer_dist/ and served by the Python CLI via
// importlib.resources — keeping the bundle as one JS file + one CSS file
// keeps the package-data force-include trivial.
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: {
    outDir: "../sdk-python/src/vibewarz/viewer_dist",
    emptyOutDir: true,
    sourcemap: false,
    // Single entry chunk; no vendor split. The whole bundle is small.
    rollupOptions: {
      output: {
        manualChunks: undefined,
        entryFileNames: "assets/[name].js",
        chunkFileNames: "assets/[name].js",
        assetFileNames: "assets/[name][extname]",
      },
    },
  },
});
