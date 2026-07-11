/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Builds into ../static/spa with STABLE filenames (no content hash) so the
// Jinja template can reference them directly; cache-busting comes from the
// ?v= query param, matching how the rest of the app versions assets.
export default defineConfig({
  plugins: [react()],
  base: "/static/spa/",
  build: {
    outDir: "../static/spa",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: "spa.js",
        chunkFileNames: "chunk-[name].js",
        assetFileNames: "spa.[ext]",
      },
    },
  },
  test: {
    environment: "node",
  },
});
