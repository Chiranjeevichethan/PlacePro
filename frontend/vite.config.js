import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Keep the development page on the backend's explicitly allowed cookie site.
const developmentOrigin = {
  name: "placepro-development-origin",
  configureServer(server) {
    if (server.config.server.https) return;
    server.middlewares.use((request, response, next) => {
      if (!['GET', 'HEAD'].includes(request.method) ||
          !request.headers.accept?.includes('text/html')) return next();
      try {
        const origin = new URL(`http://${request.headers.host}`);
        if (origin.hostname !== 'localhost' ||
            origin.port !== String(server.config.server.port)) return next();
        const target = new URL(request.url, origin);
        if (target.origin !== origin.origin) return next();
        target.hostname = '127.0.0.1';
        response.writeHead(307, { Location: target.href, 'Cache-Control': 'no-store' });
        response.end();
      } catch {
        next();
      }
    });
  },
};

// Validate the resolved build environment, including Vercel's build-time values.
// Never publish a frontend that silently calls the visitor's loopback API.
const productionApi = {
  name: "placepro-production-api",
  configResolved(config) {
    if (config.command !== 'build') return;
    if (config.env.PROD !== true) {
      throw new Error('Build PLACE PRO with NODE_ENV=production; development builds must not be published.');
    }
    const configured = config.env.VITE_API_BASE_URL;
    let api;
    try { api = new URL(configured?.trim()); } catch { /* Report configuration without echoing its value. */ }
    if (!api || api.protocol !== 'https:' || api.username || api.password ||
        api.pathname !== '/' || api.search || api.hash ||
        api.hostname === 'localhost' || api.hostname.endsWith('.localhost') ||
        /^127\./.test(api.hostname) || ['0.0.0.0', '[::]', '[::1]'].includes(api.hostname)) {
      throw new Error('Set VITE_API_BASE_URL to a non-loopback absolute HTTPS API origin, without /api, credentials, query or fragment, before building.');
    }
  },
};

export default defineConfig({
  plugins: [react(), developmentOrigin, productionApi],
  server: {
    port: 5173,
    strictPort: true,
  },
});
