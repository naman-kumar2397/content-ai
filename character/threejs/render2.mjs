// v2 renderer: N headless Chromium workers (SwiftShader) render interleaved frames of scene2.js; each frame's RGBA8
// pixels are POSTed (binary) to this process and streamed in order into ffmpeg's stdin (rawvideo). Frames whose rig +
// camera state hash equals the previous frame's are not rendered, the previous frame is re-sent instead.
//   node render2.mjs --still [--t 1.7] [--out out/still2.png]
//   node render2.mjs --anim --seconds 6 --fps 24 --workers 2 [--timeline timeline.json] [--audio x.wav] [--out out/demo_v2.mp4]
// Options: --w --h --no-plate --ao baked|gtao|none --no-dof --aa msaa|smaa|none --msaa 4 --shadow 1024 --backend swiftshader|llvmpipe
//          --capture raw|png  --json '{...}' (any scene2.js setup option)  --frames N (render only the first N frames)
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..');
const argv = process.argv.slice(2);
const A = (n, d) => (argv.includes(n) ? argv[argv.indexOf(n) + 1] : d);
const has = (n) => argv.includes(n);

export function optsFromArgs(extra = {}) {
  const tl = A('--timeline', null);
  return {
    w: +A('--w', 1080), h: +A('--h', 1920), plate: !has('--no-plate'), ao: A('--ao', 'baked'), dof: !has('--no-dof'),
    aa: A('--aa', 'msaa'), msaa: +A('--msaa', 4), shadowSize: +A('--shadow', 1024),
    timeline: tl ? JSON.parse(fs.readFileSync(tl, 'utf8')) : null,
    ...JSON.parse(A('--json', '{}')), ...extra,
  };
}

// static files + frame sink
export async function startServer(sink) {
  const types = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.glb': 'model/gltf-binary' };
  const srv = http.createServer((req, res) => {
    const u = new URL(req.url, 'http://x');
    if (req.method === 'POST') {
      const chunks = []; req.on('data', (c) => chunks.push(c));
      req.on('end', () => { const [, kind, i] = u.pathname.split('/'); sink?.(kind, +i, Buffer.concat(chunks)); res.writeHead(200); res.end(); });
      return;
    }
    const p = path.join(ROOT, decodeURIComponent(u.pathname));
    if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
    res.writeHead(200, { 'content-type': types[path.extname(p)] || 'application/octet-stream' });
    fs.createReadStream(p).pipe(res);
  });
  await new Promise((r) => srv.listen(0, '127.0.0.1', r));
  return srv;
}

const BACKENDS = {
  swiftshader: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
  // Mesa llvmpipe through ANGLE's desktop-GL backend. Needs a headed browser under Xvfb (xvfb-run); headless
  // Chromium silently falls back to SwiftShader. LP_NUM_THREADS controls llvmpipe's raster threads.
  llvmpipe: ['--use-angle=gl', '--ignore-gpu-blocklist', '--disable-gpu-sandbox'],
};

export async function openWorker(srv, opts, backend = 'swiftshader') {
  const exe = process.env.CHROMIUM_PATH;
  const browser = await chromium.launch({ ...(exe ? { executablePath: exe } : {}), args: BACKENDS[backend], headless: backend !== 'llvmpipe',
    env: { ...process.env, LP_NUM_THREADS: process.env.LP_NUM_THREADS || '4', GALLIUM_DRIVER: 'llvmpipe' } });
  const page = await browser.newPage({ viewport: { width: 270, height: 480 } });
  page.on('console', (m) => { if (m.type() === 'error') console.log('[page]', m.text()); });
  page.on('pageerror', (e) => console.log('[pageerror]', e.message));
  await page.goto(`http://127.0.0.1:${srv.address().port}/threejs/index2.html`);
  await page.waitForFunction(() => window.__ready === true);
  const t0 = Date.now();
  const info = await page.evaluate((o) => window.setup(o), opts);
  info.setupMs = Date.now() - t0;
  info.renderer = await page.evaluate(() => { const gl = document.querySelector('canvas').getContext('webgl2'); const e = gl.getExtension('WEBGL_debug_renderer_info'); return e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : '?'; });
  return { browser, page, info };
}

export async function still(opts, t, out, backend) {
  const srv = await startServer();
  const { browser, page, info } = await openWorker(srv, opts, backend);
  await page.evaluate((t) => window.renderAt(t), t);                    // warm-up (shader compile)
  const t0 = Date.now(); await page.evaluate((t) => window.renderAt(t), t); const ms = Date.now() - t0;
  const b64 = await page.evaluate(() => window.toPNG());
  fs.mkdirSync(path.dirname(out), { recursive: true }); fs.writeFileSync(out, Buffer.from(b64, 'base64'));
  await browser.close(); srv.close();
  return { ms, info };
}

// Render frames [0, n) at fps into an mp4. Returns timing stats.
export async function animate({ opts, fps, n, workers = 1, out, audio, backend = 'swiftshader', capture = 'pipelined', dedupe = true, crf = 18, preset = 'medium' }) {
  const { w, h } = opts;
  const args = ['-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', `${w}x${h}`, '-r', String(fps), '-i', '-'];
  if (audio) args.push('-i', audio);
  args.push('-vf', 'vflip', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', String(crf), '-preset', preset);
  if (audio) args.push('-c:a', 'aac', '-b:a', '160k', '-shortest');
  args.push('-movflags', '+faststart', out);
  fs.mkdirSync(path.dirname(out), { recursive: true });
  const ff = spawn('ffmpeg', args, { stdio: ['pipe', 'inherit', 'inherit'] });
  const ffDone = new Promise((r) => ff.on('close', r));

  // ordered writer: frames arrive out of order from the workers
  const pending = new Map(); let next = 0; let last = null; let dupOf = [];
  const flush = () => {
    while (pending.has(next) || (dupOf[next] !== undefined && last)) {
      let buf = pending.get(next);
      if (!buf) buf = last;            // dedupe: repeat previous frame
      pending.delete(next); ff.stdin.write(buf); last = buf; next++;
    }
  };
  const srv = await startServer((kind, i, buf) => {
    if (kind === 'frame') pending.set(i, buf);
    flush();
  });

  const T0 = Date.now();
  const W = [];
  for (let k = 0; k < workers; k++) W.push(openWorker(srv, opts, backend));
  const ws = await Promise.all(W);
  const tSetup = Date.now() - T0;
  // hash pre-pass (one page; pose only, no rendering) -> which frames are duplicates of their predecessor
  const hashes = await ws[0].page.evaluate(({ n, fps }) => window.hashFrames(n, fps), { n, fps });
  dupOf = hashes.map((x, i) => (dedupe && i > 0 && x === hashes[i - 1] ? i - 1 : undefined));
  const todo = []; for (let i = 0; i < n; i++) if (dupOf[i] === undefined) todo.push(i);
  // warm-up: compile shaders on every worker
  await Promise.all(ws.map((x) => x.page.evaluate(() => window.renderAt(0))));
  const T1 = Date.now();
  let renderMs = 0;
  await Promise.all(ws.map(async (x, k) => {
    for (let j = k; j < todo.length; j += workers) {
      const i = todo[j];
      const r = await x.page.evaluate(async ({ t, i, capture }) => {
        if (capture === 'pipelined') return window.renderSend(t, i);
        const a = performance.now(); await window.renderAt(t); const px = window.grab(); const b = performance.now();
        await fetch('/frame/' + i, { method: 'POST', body: new Blob([px]) });
        return { r: b - a, c: performance.now() - b };
      }, { t: i / fps, i, capture });
      renderMs += r.r;
      if (j % 24 === 0) console.log(`  frame ${i}/${n} w${k} render ${r.r.toFixed(0)}ms capture ${r.c.toFixed(0)}ms`);
    }
    await x.page.evaluate(() => window.flushSend());
  }));
  flush();
  const T2 = Date.now();
  ff.stdin.end(); await ffDone;
  const T3 = Date.now();
  for (const x of ws) await x.browser.close();
  srv.close();
  return { n, rendered: todo.length, dups: n - todo.length, workers, setupS: tSetup / 1000, renderPerFrame: renderMs / todo.length / 1000,
    wallPerFrame: (T3 - T1) / n / 1000, wallS: (T3 - T0) / 1000, encodeTailS: (T3 - T2) / 1000, renderer: ws[0].info.renderer, charFrac: ws[0].info.charFrac, plateMs: ws[0].info.plateMs };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const opts = optsFromArgs();
  const backend = A('--backend', 'swiftshader');
  if (has('--anim')) {
    const fps = +A('--fps', 24), secs = +A('--seconds', opts.timeline?.duration ?? 6);
    const n = +A('--frames', Math.round(fps * secs));
    const r = await animate({ opts, fps, n, workers: +A('--workers', 2), out: A('--out', path.join(HERE, 'out', 'anim2.mp4')),
      audio: A('--audio', null), backend, capture: A('--capture', 'pipelined'), dedupe: !has('--no-dedupe') });
    console.log('ANIM', JSON.stringify(r));
  } else {
    const r = await still(opts, +A('--t', 0), A('--out', path.join(HERE, 'out', 'still2.png')), backend);
    console.log('STILL', JSON.stringify(r));
  }
}
