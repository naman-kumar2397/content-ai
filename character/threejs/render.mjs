// Deterministic frame renderer: headless Chromium (SwiftShader WebGL) via Playwright.
//   node render.mjs --still [--out out/still.png]           one frame at t=0
//   node render.mjs --anim  [--seconds 3 --fps 24]           PNG frames + MP4 (H.264, yuv420p)
// Options: --w 1080 --h 1920 --no-dof --no-ao --no-shadows --sidekick ball|hugsy --tone agx|aces|neutral --t 0
//          --json '{"exposure":0.42,...}'  (any scene.js setup option, e.g. look tuning)
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..');          // serves character/ (threejs/ + gltf/)
const argv = process.argv.slice(2);
const A = (n, d) => (argv.includes(n) ? argv[argv.indexOf(n) + 1] : d);
const has = (n) => argv.includes(n);

export async function startServer() {
  const types = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.glb': 'model/gltf-binary' };
  const srv = http.createServer((req, res) => {
    const p = path.join(ROOT, decodeURIComponent(new URL(req.url, 'http://x').pathname));
    if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
    res.writeHead(200, { 'content-type': types[path.extname(p)] || 'application/octet-stream' });
    fs.createReadStream(p).pipe(res);
  });
  await new Promise((r) => srv.listen(0, '127.0.0.1', r));
  return srv;
}

export async function openPage(opts) {
  const srv = await startServer();
  const exe = process.env.CHROMIUM_PATH;   // set if the Playwright build doesn't match /opt/pw-browsers
  const browser = await chromium.launch({
    ...(exe ? { executablePath: exe } : {}),
    args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
  });
  const page = await browser.newPage({ viewport: { width: Math.round(opts.w / 4), height: Math.round(opts.h / 4) } });
  page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.log('[page]', m.text()); });
  page.on('pageerror', (e) => console.log('[pageerror]', e.message));
  await page.goto(`http://127.0.0.1:${srv.address().port}/threejs/index.html`);
  await page.waitForFunction(() => window.__ready === true);
  const t0 = Date.now();
  const info = await page.evaluate((o) => window.setup(o), opts);
  info.setupMs = Date.now() - t0;
  const close = async () => { await browser.close(); srv.close(); };
  return { page, info, close };
}

// render frame t; returns {renderMs, captureMs}; writes PNG if file given
export async function frame(page, t, file) {
  const t0 = Date.now();
  await page.evaluate((t) => window.renderAt(t), t);
  const t1 = Date.now();
  if (file) {
    const b64 = await page.evaluate(() => document.querySelector('canvas').toDataURL('image/png').split(',')[1]);
    fs.writeFileSync(file, Buffer.from(b64, 'base64'));
  }
  return { renderMs: t1 - t0, captureMs: Date.now() - t1 };
}

export function optsFromArgs() {
  return {
    w: +A('--w', 1080), h: +A('--h', 1920), dof: !has('--no-dof'), ao: !has('--no-ao'), shadows: !has('--no-shadows'),
    sidekick: A('--sidekick', 'ball'), tone: A('--tone', 'agx'),
    ...JSON.parse(A('--json', '{}')),
  };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const opts = optsFromArgs();
  const { page, info, close } = await openPage(opts);
  console.log('setup', info);
  if (has('--anim')) {
    const fps = +A('--fps', 24), secs = +A('--seconds', 3), n = Math.round(fps * secs);
    const dir = A('--frames', path.join(HERE, 'out', 'frames')); fs.rmSync(dir, { recursive: true, force: true }); fs.mkdirSync(dir, { recursive: true });
    let tr = 0, tc = 0; const T0 = Date.now();
    for (let i = 0; i < n; i++) {
      const r = await frame(page, i / fps, path.join(dir, `f${String(i).padStart(4, '0')}.png`));
      tr += r.renderMs; tc += r.captureMs;
      if (i % 12 === 0) console.log(`frame ${i}/${n} render ${r.renderMs}ms capture ${r.captureMs}ms`);
    }
    console.log(`ANIM ${n} frames: render ${(tr / n / 1000).toFixed(2)} s/f, capture ${(tc / n / 1000).toFixed(2)} s/f, wall ${((Date.now() - T0) / 1000).toFixed(1)} s`);
    const mp4 = A('--out', path.join(HERE, 'out', 'test_anim.mp4'));
    execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(fps), '-i', path.join(dir, 'f%04d.png'),
      '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'medium', '-movflags', '+faststart', mp4]);
    console.log('wrote', mp4);
  } else {
    const out = A('--out', path.join(HERE, 'out', 'still.png')); fs.mkdirSync(path.dirname(out), { recursive: true });
    await frame(page, +A('--t', 0));                       // warm-up (shader compile)
    const r = await frame(page, +A('--t', 0), out);
    console.log('STILL', r, '->', out);
  }
  await close();
}
