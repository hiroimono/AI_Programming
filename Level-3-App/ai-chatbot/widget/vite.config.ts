import { defineConfig } from "vite";

// Production build emits a single self-mounting IIFE bundle (dist/widget.js)
// that a tenant drops onto their site with data-* attributes. The dev server
// (`vite`) serves index.html as a demo host instead.
export default defineConfig({
  build: {
    lib: {
      entry: "src/embed.ts",
      name: "ChatbotWidget",
      formats: ["iife"],
      fileName: () => "widget.js",
    },
    rollupOptions: {
      output: { inlineDynamicImports: true },
    },
  },
});
