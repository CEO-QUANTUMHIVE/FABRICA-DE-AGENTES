import { defineConfig } from 'vite';

// loader.js no pasa por acá: es JS plano sin imports, se sirve tal cual.
// Solo widget.html (y lo que importa, app.js -> livekit-client) necesita
// bundling.
export default defineConfig({
  build: {
    outDir: 'dist',
    rollupOptions: {
      input: 'widget.html',
    },
  },
});
