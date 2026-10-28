import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const port = parseInt(env.FRONTEND_PORT || env.VITE_PORT || "3100", 10);

  return {
    plugins: [react()],
    server: {
      host: "127.0.0.1",
      port: port,
    },
  };
});
