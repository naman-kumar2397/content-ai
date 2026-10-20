// v2 benchmark: per-config s/frame at 1080x1920 (render + GPU sync + readback), plus multi-worker throughput.
//   node bench2.mjs [--n 6] [--only a,b] [--throughput]
// Each config: fresh browser, 1 warm-up frame, N timed frames at different t. "frame" = renderAt(t) + readPixels
// (the readback forces SwiftShader to finish, so it is the real cost of a frame).
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { startServer, openWorker, animate } from './render2.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const argv = process.argv.slice(2);
const A = (n, d) => (argv.includes(n) ? argv[argv.indexOf(n) + 1] : d);
const N = +A('--n', 6);
const only = A('--only', null)?.split(',');

const base = { w: 1080, h: 1920 };
const full = { ...base, plate: false, ao: 'gtao', dof: true, aa: 'msaa', msaa: 4, shadowSize: 2048, shadowFocus: 1, dofBoost: 1, band: 0 };
export const CONFIGS = {
  'v2-full (r1 settings: GTAO, DOF, MSAA4, VSM 2048)': full,
  'baked AO, GTAO off': { ...full, ao: 'baked' },
  'baked AO, no DOF': { ...full, ao: 'baked', dof: false },
  'baked AO + half-res-equivalent DOF (N=20)': { ...full, ao: 'baked', dofN: 20 },
  'shadow 1024 + focus': { ...full, ao: 'baked', shadowSize: 1024, shadowFocus: 0.45 },
  'shadow 512 + focus': { ...full, ao: 'baked', shadowSize: 512, shadowFocus: 0.45 },
  'plate (bg once), MSAA4, shadow 1024': { ...base, plate: true, layered: false, ao: 'baked', aa: 'msaa', msaa: 4, shadowSize: 1024 },
  'plate, MSAA2': { ...base, plate: true, layered: false, ao: 'baked', aa: 'msaa', msaa: 2, shadowSize: 1024 },
  'plate, SMAA': { ...base, plate: true, layered: false, ao: 'baked', aa: 'smaa', shadowSize: 1024 },
  'plate, no AA': { ...base, plate: true, layered: false, ao: 'baked', aa: 'none', shadowSize: 1024 },
  'plate, MSAA4, shadow 512': { ...base, plate: true, layered: false, ao: 'baked', aa: 'msaa', msaa: 4, shadowSize: 512 },
  'plate, MSAA4, PCF 1024': { ...base, plate: true, layered: false, ao: 'baked', aa: 'msaa', msaa: 4, shadowSize: 1024, shadowType: 'pcf' },
  'layered plate, MSAA4, VSM 1024': { ...base, plate: true, layered: true, ao: 'baked', aa: 'msaa', msaa: 4, shadowSize: 1024 },
  'layered plate, MSAA4, PCF 1024': { ...base, plate: true, layered: true, ao: 'baked', aa: 'msaa', msaa: 4, shadowSize: 1024, shadowType: 'pcf' },
  'layered plate, MSAA2, PCF 1024': { ...base, plate: true, layered: true, ao: 'baked', aa: 'msaa', msaa: 2, shadowSize: 1024, shadowType: 'pcf' },
  'layered plate, no AA, PCF 1024': { ...base, plate: true, layered: true, ao: 'baked', aa: 'none', shadowSize: 1024, shadowType: 'pcf' },
  'plate, MSAA4, VSM blur 8': { ...base, plate: true, layered: false, ao: 'baked', aa: 'msaa', msaa: 4, shadowSize: 1024, blurSamples: 8 },
};

export async function measure(opts, backend = 'swiftshader', n = N) {
  const srv = await startServer(() => {});
  const { browser, page, info } = await openWorker(srv, opts, backend);
  await page.evaluate(() => { window.renderAt(0.3); window.grab(); });
  const r = await page.evaluate(async (n) => {
    let fr = 0, raw = 0, png = 0, pip = 0;
    { const a = performance.now(); for (let i = 0; i < n; i++) await window.renderSend(0.5 + i * 0.37, 0); await window.flushSend(); pip = (performance.now() - a) / n / 1000; }
    for (let i = 0; i < n; i++) {
      const a = performance.now(); await window.renderAt(0.5 + i * 0.37); const px = window.grab(); const b = performance.now();
      await fetch('/frame/0', { method: 'POST', body: new Blob([px]) }); const c = performance.now();
      if (i === 0) { window.toPNG(); png = performance.now() - c; }
      fr += b - a; raw += c - b;
    }
    return { frame: fr / n / 1000, post: raw / n / 1000, png: png / 1000, pipelined: pip };
  }, n);
  await browser.close(); srv.close();
  return { ...r, setup: info.setupMs / 1000, plate: (info.plateMs || 0) / 1000, renderer: info.renderer };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const rows = [];
  const backend = A('--backend', 'swiftshader');
  if (!argv.includes('--throughput')) {
    for (const [name, c] of Object.entries(CONFIGS)) {
      if (only && !only.some((k) => name.includes(k))) continue;
      const r = await measure(c, backend);
      rows.push({ name, ...r }); console.log(JSON.stringify({ name, ...r }));
    }
    console.log(`\n| config (${backend}) | s/frame (render+readback) | raw POST s | PNG encode s | pipelined render+capture s/frame | plate s (once) |\n|---|---|---|---|---|---|`);
    for (const r of rows) console.log(`| ${r.name} | **${r.frame.toFixed(2)}** | ${r.post.toFixed(2)} | ${r.png.toFixed(2)} | ${r.pipelined.toFixed(2)} | ${r.plate.toFixed(1)} |`);
  } else {
    const opts = { ...CONFIGS['layered plate, MSAA4, PCF 1024'], ...JSON.parse(A('--json', '{}')) };
    const n = +A('--frames', 48);
    for (const w of (A('--workers', '1,2,3')).split(',').map(Number)) {
      const r = await animate({ opts, fps: 24, n, workers: w, out: path.join(HERE, 'out', `bench_w${w}.mp4`), backend, dedupe: false });
      console.log(JSON.stringify(r));
      rows.push(r);
    }
    console.log('\n| workers | wall s/frame (render+capture+encode) | per-worker render s/frame |\n|---|---|---|');
    for (const r of rows) console.log(`| ${r.workers} | **${r.wallPerFrame.toFixed(2)}** | ${r.renderPerFrame.toFixed(2)} |`);
  }
}
