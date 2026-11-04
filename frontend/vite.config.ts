import path from "node:path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

// `npm run dev` serves the UI on :5174 with hot reload and a fake bot (see src/lib/bot.ts).
// `npm run build` writes dist/, which the Python app shows in its desktop window; base "./" keeps
// asset paths relative so the window can load it straight from disk.
export default defineConfig({
  base: "./",
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "./src") } },
  build: { outDir: "dist", emptyOutDir: true },
  server: { port: 5174, strictPort: true },
})
