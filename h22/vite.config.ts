import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    port: 5173,
    open: true
  },
  worker: {
    format: 'es'
  },
  build: {
    target: 'es2020',
    sourcemap: true
  }
});
