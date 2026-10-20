// Seconds/frame benchmark: resolutions x (DOF, AO) toggles. Each config: fresh page, 1 warm-up frame, then N timed
// frames at different t (render only = until GPU finished; capture = canvas -> PNG -> disk, reported separately).
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { openPage, frame } from './render.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const N = +(process.argv[process.argv.indexOf('--n') + 1] || 4);
const sidekick = process.argv.includes('--hugsy') ? 'hugsy' : 'ball';
const configs = [];
for (const [w, h] of [[1080, 1920], [720, 1280]])
  for (const [dof, ao] of [[true, true], [false, true], [true, false], [false, false]]) configs.push({ w, h, dof, ao, sidekick });
// 'lean' variant: no MSAA, key shadow only — what's left once the expensive extras go
configs.push({ w: 720, h: 1280, dof: false, ao: false, sidekick, msaa: 0, rimShadow: false });

const rows = [];
fs.mkdirSync(path.join(HERE, 'out', 'bench'), { recursive: true });
for (const c of configs) {
  const { page, info, close } = await openPage(c);
  await frame(page, 0);
  let r = 0, cap = 0;
  for (let i = 0; i < N; i++) {
    const f = path.join(HERE, 'out', 'bench', `${c.w}_${c.dof ? 'dof' : 'nodof'}_${c.ao ? 'ao' : 'noao'}.png`);
    const t = await frame(page, 0.4 + i * 0.5, f);
    r += t.renderMs; cap += t.captureMs;
  }
  await close();
  const row = { res: `${c.w}x${c.h}${c.msaa === 0 ? " lean" : ""}`, dof: c.dof, ao: c.ao, render_s: +(r / N / 1000).toFixed(2), capture_s: +(cap / N / 1000).toFixed(2), setup_s: +(info.setupMs / 1000).toFixed(1) };
  rows.push(row); console.log(JSON.stringify(row));
}
console.log('\n| Resolution | DOF | AO | render s/frame | + PNG capture s/frame | total s/frame |\n|---|---|---|---|---|---|');
for (const r of rows) console.log(`| ${r.res} | ${r.dof ? 'on' : 'off'} | ${r.ao ? 'on' : 'off'} | ${r.render_s} | ${r.capture_s} | ${(r.render_s + r.capture_s).toFixed(2)} |`);
