import { defineConfig, loadEnv } from "vite";

// El bundle publicado salio una vez con VITE_API_URL=http://localhost:9999,
// tomada de una variable suelta del shell. Desde un celular eso no existe: el
// login se quedaba en "Validando..." y no habia forma de saber por que.
//
// Compilar es la ultima oportunidad de detectarlo. Despues es un archivo
// estatico servido a clientes reales, y el error aparece recien cuando
// alguien no puede entrar.
function exigirConfigDeProduccion(env) {
  const faltantes = ["VITE_API_URL", "VITE_SUPABASE_URL", "VITE_SUPABASE_ANON_KEY"]
    .filter((clave) => !(env[clave] || "").trim());
  if (faltantes.length) {
    throw new Error(
      `Falta configuracion para compilar produccion: ${faltantes.join(", ")}.\n` +
      `Se definen en frontend/panel/.env.production o en el entorno del build.`
    );
  }

  const api = env.VITE_API_URL;
  if (/localhost|127\.0\.0\.1|:9999/.test(api)) {
    throw new Error(
      `VITE_API_URL apunta a "${api}" en un build de produccion.\n` +
      `El navegador de un cliente no llega ahi. Ya paso una vez.`
    );
  }
  if (!api.startsWith("https://")) {
    throw new Error(`VITE_API_URL tiene que ser https en produccion, no "${api}".`);
  }
}

export default defineConfig(({ mode, command }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  if (command === "build" && mode === "production") exigirConfigDeProduccion(env);

  return {
    base: "/panel/",
    server: { port: 4175 },
    preview: { port: 4175 },
  };
});
