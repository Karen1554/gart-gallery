const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const net = require('node:net');
const path = require('node:path');
const { setTimeout: delay } = require('node:timers/promises');

const root = path.resolve(__dirname, '..');

async function availablePort() {
  const server = net.createServer();
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  const { port } = server.address();
  await new Promise((resolve, reject) => {
    server.close((error) => error ? reject(error) : resolve());
  });
  return port;
}

async function main() {
  const port = await availablePort();
  const origin = `http://127.0.0.1:${port}`;
  const server = spawn(process.execPath, ['api-gateway/server.js'], {
    cwd: root,
    env: { ...process.env, PORT: String(port) },
    stdio: 'ignore',
  });

  try {
    let health;
    for (let attempt = 0; attempt < 40; attempt += 1) {
      if (server.exitCode !== null) {
        throw new Error(`Gateway exited with code ${server.exitCode}`);
      }
      try {
        health = await fetch(`${origin}/health`);
        break;
      } catch {
        await delay(250);
      }
    }

    assert.ok(health, 'Gateway did not become available');
    assert.equal(health.status, 200);
    assert.deepEqual(await health.json(), { service: 'api-gateway', status: 'ok' });

    for (const route of ['/', '/works', '/works/1', '/galleries/1', '/login']) {
      const response = await fetch(`${origin}${route}`);
      assert.equal(response.status, 200, `${route} should return 200`);
      assert.match(response.headers.get('content-type') || '', /text\/html/);
    }
  } finally {
    server.kill();
    if (server.exitCode === null) {
      await Promise.race([
        new Promise((resolve) => server.once('exit', resolve)),
        delay(3000).then(() => {
          if (server.exitCode === null) {
            throw new Error('Gateway process did not stop after integration checks');
          }
        }),
      ]);
    }
  }

  console.log('Gateway and rendered Astro routes passed integration checks.');
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
