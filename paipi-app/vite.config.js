import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    host: '0.0.0.0',        // already implied by your description
    port: 4200,
    allowedHosts: ['server']   // <-- add this line
  }
});
