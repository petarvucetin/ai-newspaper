import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/rate": "http://localhost:8000",
      "/dismiss": "http://localhost:8000",
      "/restore": "http://localhost:8000",
      "/source": "http://localhost:8000",
      "/admin": "http://localhost:8000",
    },
  },
})
