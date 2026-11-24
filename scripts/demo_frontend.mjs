// Owned local synthetic harness. The production Vite configuration stays unchanged.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const [frontend, cacheDir, portValue, runId] = process.argv.slice(2);
const port = Number(portValue);
assert.ok(frontend && cacheDir && Number.isInteger(port) && port >= 1 && port <= 65535 && /^[a-f0-9]{32}$/.test(runId || ''),
  'Start this owned server through scripts/demo.py with a fresh synthetic workspace.');
assert.equal(process.env.NODE_ENV, 'development');
const require = createRequire(pathToFileURL(path.join(frontend, 'package.json')));
const { createServer } = await import(pathToFileURL(require.resolve('vite')).href);
const server = await createServer({
  root: frontend,
  cacheDir,
  mode: 'development',
  server: { host: '127.0.0.1', port, strictPort: true, open: false },
  plugins: [{
    name: 'placepro-owned-demo-identity',
    configureServer(vite) {
      vite.middlewares.use((_request, response, next) => {
        response.setHeader('X-PlacePro-Demo-Run', runId);
        response.setHeader('Cache-Control', 'no-store');
        next();
      });
    },
  }],
});
let closing;
const stop = () => closing ||= server.close().then(() => { process.stdin.destroy(); process.exit(0); });
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => {
  input += chunk;
  if (/(?:^|\n)stop\r?\n/.test(input)) void stop();
});
process.stdin.on('end', () => { void stop(); });
process.on('SIGINT', () => { void stop(); });
process.on('SIGTERM', () => { void stop(); });
await server.listen();
