import path from "node:path";
import { defineConfig, loadEnv } from "vite";

const envDir = path.resolve(process.cwd(), "../panel");

function exigirConfigDeProduccion(env) {
  const faltantes = ["VITE_API_URL", "VITE_SUPABASE_URL", "VITE_SUPABASE_ANON_KEY"]
    .filter((clave) => !(env[clave] || "").trim());

  if (faltantes.length) {
    throw new Error(`Falta configuración de producción: ${faltantes.join(", ")}.`);
  }

  if (!env.VITE_API_URL.startsWith("https://")) {
    throw new Error("VITE_API_URL debe usar HTTPS en producción.");
  }
}

export default defineConfig(({ mode, command }) => {
  const env = loadEnv(mode, envDir, "VITE_");
  if (command === "build" && mode === "production") exigirConfigDeProduccion(env);

  return {
    base: "/fabrica/",
    envDir,
    // Las 18 muestras ya verificadas del motor viven con el widget. Se
    // comparten en el build para que la fabrica no mantenga otra copia.
    publicDir: path.resolve(process.cwd(), "../widget/public"),
    server: { port: 4176 },
    preview: { port: 4176 },
  };
});
