// Character animation as a pure function of t (deterministic; no clock, no Math.random).
//   - lip-sync: Rhubarb mouth cues (A-H, X) -> jaw angle + morph targets, short crossfades
//   - secondary motion: spring/damper sims stepped at a fixed dt from t=0 (ears, tongue, flippers, head follow-through)
//   - acting: anticipation + overshoot moves, Hugsy squash/stretch
//   - idle life: breathing, smoothed-noise head drift, eye saccades, seeded blinks, handheld camera drift
import * as THREE from 'three';

const D2R = Math.PI / 180;
const clamp01 = (u) => Math.min(1, Math.max(0, u));
const smooth = (u) => { u = clamp01(u); return u * u * (3 - 2 * u); };
function seeded(seed) { let s = seed >>> 0; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); }

// 1D smoothed value noise in [-1, 1] (two octaves), deterministic per seed
function noise1(seed) {
  const r = seeded(seed); const tab = Array.from({ length: 256 }, () => r() * 2 - 1);
  const v = (x) => { const i = Math.floor(x), f = x - i; const a = tab[i & 255], b = tab[(i + 1) & 255]; const s = f * f * f * (f * (f * 6 - 15) + 10); return a + (b - a) * s; };
  return (x) => 0.7 * v(x) + 0.3 * v(x * 2.3 + 17.1);
}

// move from 0 -> 1 over [t0, t0+dur] with anticipation (dips below 0 first) and overshoot (passes 1, settles)
function anticOver(t, t0, dur, antic = 0.12, over = 0.1) {
  const u = (t - t0) / dur;
  if (u <= 0) return 0;
  if (u >= 1.6) return 1;
  const ua = 0.28;                                   // anticipation phase
  if (u < ua) return -antic * Math.sin(Math.PI * u / ua * 0.5) ** 2 * (u < ua ? 1 : 0);
  if (u < 1) { const k = (u - ua) / (1 - ua); return -antic + (1 + over + antic) * (1 - (1 - k) ** 3); }
  const k = (u - 1) / 0.6;                           // settle the overshoot
  return 1 + over * Math.cos(Math.PI * k * 1.5) * Math.exp(-4 * k) * (1 - smooth(k));
}
const pulse = (t, t0, t1, ramp = 0.2) => smooth((t - t0) / ramp) * (1 - smooth((t - t1) / ramp));

// seeded natural blink times: gaps 2..5.5 s, ~20% doubles
function blinkTimes(seed, dur, start = 0.6) {
  const r = seeded(seed); const out = []; let t = start + r() * 1.2;
  while (t < dur + 1) { out.push(t); if (r() < 0.2) out.push(t + 0.28); t += 2 + r() * 3.5; }
  return out;
}
const blinkAmt = (t, times) => { let b = 0; for (const c of times) { const d = t - c; if (d > -0.06 && d < 0.14) b = Math.max(b, d < 0 ? 1 + d / 0.06 : 1 - d / 0.14); } return clamp01(b); };

// saccades: piecewise-constant gaze targets with fast (40 ms) transitions
function saccades(seed, dur) {
  const r = seeded(seed); const out = [{ t: -1, x: 0, y: 0 }]; let t = 0.3 + r() * 0.5;
  while (t < dur + 1) { out.push({ t, x: (r() * 2 - 1), y: (r() * 2 - 1) * 0.6 }); t += 0.5 + r() * 1.4; }
  return (tt) => { let a = out[0], b = out[0]; for (const s of out) { if (s.t <= tt) { a = b; b = s; } } const k = smooth((tt - b.t) / 0.04); return { x: a.x + (b.x - a.x) * k, y: a.y + (b.y - a.y) * k }; };
}

// Rhubarb shapes -> rig params. jaw in degrees relative to rest (rest = happy open pant).
const VISEMES = {
  X: { jaw: -12, close: 0.35, wide: 0.0, narrow: 0.0, fv: 0, tIn: 0.4, tUp: 0 },
  A: { jaw: -24, close: 1.0, wide: 0.1, narrow: 0.0, fv: 0, tIn: 1.0, tUp: 0 },   // M B P: closed
  B: { jaw: -16, close: 0.65, wide: 0.5, narrow: 0.0, fv: 0, tIn: 0.9, tUp: 0 },  // K S T ...: slightly open, teeth
  C: { jaw: -4, close: 0.2, wide: 0.8, narrow: 0.0, fv: 0, tIn: 0.6, tUp: 0 },    // EH AE: open
  D: { jaw: 8, close: 0.0, wide: 0.35, narrow: 0.0, fv: 0, tIn: 0.3, tUp: 0 },    // AA: wide open
  E: { jaw: -6, close: 0.3, wide: 0.0, narrow: 0.7, fv: 0, tIn: 0.7, tUp: 0 },    // AO ER: rounded
  F: { jaw: -14, close: 0.55, wide: 0.0, narrow: 1.0, fv: 0, tIn: 1.0, tUp: 0 },  // UW OW W: puckered
  G: { jaw: -18, close: 0.75, wide: 0.25, narrow: 0.0, fv: 1, tIn: 1.0, tUp: 0 }, // F V
  H: { jaw: -4, close: 0.2, wide: 0.3, narrow: 0.0, fv: 0, tIn: 0.2, tUp: 1 },    // L: tongue up
};
const IDLE = { jaw: -2, close: 0, tIn: 0.15 };   // between lines: Joey's happy open pant
const VKEYS = ['jaw', 'close', 'wide', 'narrow', 'fv', 'tIn', 'tUp'];
function visemeTrack(cues, offset, xfade = 0.06) {
  // cues: [{start, end, value}] (Rhubarb JSON). Blend each new shape in over xfade seconds.
  const list = (cues || []).map((c) => ({ t: c.start + offset, v: VISEMES[c.value] || VISEMES.X }));
  return (t) => {
    let cur = { ...VISEMES.X }, prev = VISEMES.X;
    for (let i = 0; i < list.length && list[i].t <= t; i++) {
      const k = smooth((t - list[i].t) / xfade);
      const from = { ...cur };
      for (const key of VKEYS) cur[key] = from[key] + (list[i].v[key] - from[key]) * (i + 1 < list.length && list[i + 1].t <= t ? 1 : k);
      prev = list[i].v;
    }
    return cur;
  };
}

// critically-damped-ish spring, explicit fixed-step integration
class Spring {
  constructor(freq, damp) { this.k = (2 * Math.PI * freq) ** 2; this.c = 2 * damp * 2 * Math.PI * freq; this.x = 0; this.v = 0; }
  step(target, dt, force = 0) { const a = this.k * (target - this.x) - this.c * this.v + force; this.v += a * dt; this.x += this.v * dt; return this.x; }
}

export function createAnim({ nodes: N, camera, camPos, camTgt, focusPt, seed = 1, timeline, debugCam }) {
  const TL = Object.assign({ duration: 6, lineStart: 0.45, cues: [], push: 0.07 }, timeline || {});
  const rest = {};
  for (const [k, n] of Object.entries(N)) rest[k] = { p: n.position.clone(), r: n.rotation.clone(), s: n.scale.clone() };
  // morph handles: node name -> [{mesh}] (multi-primitive nodes are groups of meshes)
  const morphMeshes = {};
  for (const [k, n] of Object.entries(N)) {
    const ms = [];
    if (n.isMesh && n.morphTargetDictionary) ms.push(n);
    for (const c of n.children) if (c.isMesh && c.morphTargetDictionary && !Object.values(N).includes(c)) ms.push(c);
    if (ms.length) morphMeshes[k] = ms;
  }
  const setMorph = (node, key, v) => { for (const m of morphMeshes[node] || []) { const i = m.morphTargetDictionary[key]; if (i !== undefined) m.morphTargetInfluences[i] = v; } };
  const allMorphs = () => { for (const ms of Object.values(morphMeshes)) for (const m of ms) m.morphTargetInfluences.fill(0); };

  const nHead = [noise1(seed * 11 + 1), noise1(seed * 11 + 2), noise1(seed * 11 + 3)];
  const nHug = [noise1(seed * 13 + 1), noise1(seed * 13 + 2)];
  const nCam = [noise1(seed * 17 + 1), noise1(seed * 17 + 2), noise1(seed * 17 + 3), noise1(seed * 17 + 4)];
  const jBlinks = blinkTimes(seed * 7 + 1, TL.duration), hBlinks = blinkTimes(seed * 7 + 2, TL.duration, 1.1);
  const jSac = saccades(seed * 5 + 1, TL.duration), hSac = saccades(seed * 5 + 2, TL.duration);
  const vis = visemeTrack(TL.cues, TL.lineStart);
  const lineEnd = TL.lineStart + (TL.cues.length ? TL.cues[TL.cues.length - 1].start : 2.5);
  const talking = (t) => pulse(t, TL.lineStart - 0.05, lineEnd, 0.15);

  // ---- choreography (targets, before springs). All times in seconds.
  const hugReact = lineEnd + 0.15;          // Hugsy: deadpan squint after Joey's line
  const hugFlip = hugReact + 0.55;          // ...then the flipper goes up
  const joeyBeat = hugFlip + 0.9;           // Joey notices: worried brows, head tilt
  function targets(t) {
    const pop = anticOver(t, TL.lineStart - 0.35, 0.55, 0.35, 0.18);          // excited head pop as he starts talking
    const tilt = anticOver(t, joeyBeat, 0.6, 0.2, 0.15);
    const nod = Math.sin(t * 2 * Math.PI * 2.2) * 0.5 * talking(t);            // speech emphasis
    const head = {
      x: 0.035 * nHead[0](t * 0.45) - 0.06 * pop + 0.025 * nod + 0.04 * tilt,
      y: 0.06 * nHead[1](t * 0.35) + 0.05 * pop - 0.10 * tilt,
      z: 0.03 * nHead[2](t * 0.4) + 0.025 * talking(t) * Math.sin(t * 5.1) + 0.12 * tilt,
    };
    const squint = smooth((t - hugReact) / 0.35);
    const flip = anticOver(t, hugFlip, 0.5, 0.25, 0.14);
    return { pop, tilt, head, squint, flip };
  }

  // ---- springs (state persists between sequential calls; re-simulated from 0 when t goes backwards)
  const DT = 1 / 240;
  let sim = null;
  function resetSim() {
    sim = { t: 0, prevHead: { x: 0, y: 0, z: 0 }, prevVel: { x: 0, y: 0, z: 0 },
      head: { x: new Spring(3.2, 0.55), y: new Spring(3.2, 0.55), z: new Spring(3.0, 0.5) },
      earL: new Spring(2.2, 0.18), earR: new Spring(2.3, 0.18), earLx: new Spring(2.0, 0.2), earRx: new Spring(2.1, 0.2),
      tongue: new Spring(4.5, 0.22), jaw: new Spring(9, 0.75),
      flipR: new Spring(3.6, 0.32), flipL: new Spring(2.6, 0.2), hugBody: new Spring(3.0, 0.3), hugTwist: new Spring(2.0, 0.6) };
  }
  function stepSim(T) {
    if (!sim || T < sim.t - 1e-9) resetSim();
    while (sim.t < T - 1e-9) {
      const t = sim.t, tg = targets(t), s = sim;
      const hx = s.head.x.step(tg.head.x, DT), hy = s.head.y.step(tg.head.y, DT), hz = s.head.z.step(tg.head.z, DT);
      const vel = { x: (hx - s.prevHead.x) / DT, y: (hy - s.prevHead.y) / DT, z: (hz - s.prevHead.z) / DT };
      const acc = { x: (vel.x - s.prevVel.x) / DT, y: (vel.y - s.prevVel.y) / DT, z: (vel.z - s.prevVel.z) / DT };
      s.prevHead = { x: hx, y: hy, z: hz }; s.prevVel = vel;
      // ears are pendulums hanging from the head: driven by the head's angular acceleration (inertia)
      const v = vis(t);
      s.earL.step(0, DT, -acc.z * 0.9 - acc.y * 0.4); s.earR.step(0, DT, -acc.z * 0.9 + acc.y * 0.4);
      s.earLx.step(0, DT, -acc.x * 0.8); s.earRx.step(0, DT, -acc.x * 0.8);
      const jawT = (v.jaw * talking(t) + IDLE.jaw * (1 - talking(t))) * D2R;
      const jawPrev = s.jaw.x; s.jaw.step(jawT, DT);
      s.tongue.step(0, DT, -(s.jaw.x - jawPrev) / DT * 60 - acc.x * 0.6);
      // Hugsy: flipper R goes up with anticipation/overshoot, L follows through, body squashes & counter-twists
      s.flipR.step(tg.flip, DT); s.flipL.step(0, DT, -s.flipR.v * 6);
      s.hugBody.step(0, DT, -s.flipR.v * 9 + (tg.squint > 0 && tg.squint < 1 ? 4 : 0));
      s.hugTwist.step(0.55 * tg.squint, DT);   // deadpan glance to camera
      sim.t += DT;
    }
    return sim;
  }

  const cam0 = { pos: camPos.clone(), tgt: camTgt.clone() };
  const tmpV = new THREE.Vector3();
  function apply(t, opt = {}) {
    for (const [k, r] of Object.entries(rest)) { const n = N[k]; n.position.copy(r.p); n.rotation.copy(r.r); n.scale.copy(r.s); }
    allMorphs();
    const s = stepSim(t), tg = targets(t), v = vis(t), talk = talking(t);
    const R = (k) => rest[k];
    // ---------------- Joey
    const br = Math.sin(2 * Math.PI * t / 3.4);                                  // breathing
    if (N.Joey_Body) { N.Joey_Body.scale.set(R('Joey_Body').s.x * (1 + 0.006 * br), R('Joey_Body').s.y * (1 + 0.012 * br), R('Joey_Body').s.z * (1 + 0.006 * br)); }
    if (N.Joey_Head) {
      const h = N.Joey_Head.rotation, r0 = R('Joey_Head').r;
      h.set(r0.x + s.head.x.x, r0.y + s.head.y.x, r0.z + s.head.z.x, r0.order);
    }
    if (N.Joey_Jaw) N.Joey_Jaw.rotation.x = R('Joey_Jaw').r.x + s.jaw.x;
    const vw = talk, smile = 0.45 + 0.35 * tg.pop * (1 - smooth((t - lineEnd) / 0.5)) - 0.35 * tg.tilt;
    for (const n of ['Joey_Muzzle', 'Joey_Head', 'Joey_Mouth', 'Joey_Jaw']) {
      setMorph(n, 'Wide', v.wide * vw); setMorph(n, 'Narrow', v.narrow * vw);
      if (n !== 'Joey_Jaw') setMorph(n, 'Close', v.close * vw + IDLE.close * (1 - vw));
      if (n !== 'Joey_Jaw') setMorph(n, 'Smile', Math.max(0, smile));
    }
    setMorph('Joey_Jaw', 'FV', v.fv * vw);
    setMorph('Joey_Tongue', 'In', (v.tIn * vw + IDLE.tIn * (1 - vw)));
    setMorph('Joey_Tongue', 'Up', v.tUp * vw);
    if (N.Joey_Tongue) N.Joey_Tongue.rotation.x = R('Joey_Tongue').r.x + s.tongue.x;
    // brows: up with excitement, worried at the beat; little emphasis bumps while talking
    const browUp = clamp01(0.85 * tg.pop * (1 - smooth((t - lineEnd) / 0.6)) + 0.25 * talk * Math.max(0, Math.sin(t * 7.3)));
    setMorph('Joey_Brows', 'Up', browUp * (1 - tg.tilt));
    setMorph('Joey_Brows', 'Worried', clamp01(tg.tilt));
    setMorph('Joey_Brows', 'Down', clamp01(-tg.pop * 2.5));                    // anticipation frown
    // ears: spring sway + perk at the beat
    if (N.Joey_EarL) { N.Joey_EarL.rotation.z = R('Joey_EarL').r.z + s.earL.x - 0.12 * tg.tilt; N.Joey_EarL.rotation.x = R('Joey_EarL').r.x + s.earLx.x; }
    if (N.Joey_EarR) { N.Joey_EarR.rotation.z = R('Joey_EarR').r.z + s.earR.x + 0.12 * tg.tilt; N.Joey_EarR.rotation.x = R('Joey_EarR').r.x + s.earRx.x; }
    // eyes: blinks + saccades (tiny bead translation)
    const jb = blinkAmt(t, jBlinks), js = jSac(t);
    for (const e of ['Joey_EyeL', 'Joey_EyeR']) if (N[e]) {
      N[e].scale.y = R(e).s.y * (1 - 0.92 * jb) * (1 - 0.12 * smile);
      N[e].position.x = R(e).p.x + 0.012 * js.x; N[e].position.y = R(e).p.y + 0.008 * js.y;
    }
    // ---------------- Hugsy
    if (N.Hugsy_Body) {
      const hb = N.Hugsy_Body, r0 = R('Hugsy_Body');
      const hbr = Math.sin(2 * Math.PI * (t + 0.7) / 2.9);
      const sq = s.hugBody.x;                                                    // + = stretch, - = squash
      const sy = 1 + 0.06 * sq + 0.008 * hbr, sxz = 1 / Math.sqrt(sy);
      hb.scale.set(r0.s.x * sxz, r0.s.y * sy, r0.s.z * sxz);
      setMorph('Hugsy_Body', 'Squash', clamp01(-sq * 0.8) + 0.15 * (0.5 + 0.5 * hbr));
      setMorph('Hugsy_Belly', 'Squash', clamp01(-sq * 0.8) + 0.15 * (0.5 + 0.5 * hbr));
      setMorph('Hugsy_Face', 'Squash', clamp01(-sq * 0.8) + 0.15 * (0.5 + 0.5 * hbr));
      for (const n of ['Hugsy_Body', 'Hugsy_Belly', 'Hugsy_Face']) setMorph(n, 'Stretch', clamp01(sq * 0.8));
      hb.rotation.y = r0.r.y + s.hugTwist.x + 0.03 * nHug[0](t * 0.3);
      hb.rotation.x = r0.r.x + 0.02 * nHug[1](t * 0.35);
    }
    const hbk = blinkAmt(t, hBlinks), hs = hSac(t);
    for (const e of ['Hugsy_EyeL', 'Hugsy_EyeR']) if (N[e]) {
      N[e].scale.y = R(e).s.y * (1 - 0.6 * tg.squint) * (1 - 0.9 * hbk);
      N[e].position.x = R(e).p.x + 0.006 * hs.x * (1 - tg.squint);
    }
    // deadpan: flat brows (inner ends down), then one sarcastic raise as the flipper peaks
    const sarc = pulse(t, hugFlip + 0.35, TL.duration + 1, 0.25);
    setMorph('Hugsy_BrowL', 'InnerDown', 0.3 * tg.squint); setMorph('Hugsy_BrowR', 'InnerDown', 0.3 * tg.squint * (1 - sarc));
    setMorph('Hugsy_BrowR', 'Raise', sarc); setMorph('Hugsy_BrowR', 'InnerUp', 0.4 * sarc);
    if (N.Hugsy_Brows) N.Hugsy_Brows.position.y = R('Hugsy_Brows').p.y - 0.03 * tg.squint;   // brows sit low on the lids: deadpan
    setMorph('Hugsy_BeakLower', 'Open', 0.12 * pulse(t, hugFlip + 0.1, hugFlip + 0.5, 0.1));   // tiny "hmph"
    // the camera-side flipper (L) does the raise; the far one (R) only follows through
    if (N.Hugsy_FlipperL) { N.Hugsy_FlipperL.rotation.z = R('Hugsy_FlipperL').r.z - 1.25 * s.flipR.x; N.Hugsy_FlipperL.rotation.x = R('Hugsy_FlipperL').r.x - 0.5 * s.flipR.x; }
    if (N.Hugsy_FlipperR) N.Hugsy_FlipperR.rotation.z = R('Hugsy_FlipperR').r.z + 0.25 * s.flipL.x + 0.03 * Math.sin(t * 1.7);
    // ---------------- camera: slow push-in + handheld drift (rotation noise ~0.15 deg, position ~1 cm)
    camera.position.copy(cam0.pos); camera.up.set(0, 1, 0); camera.lookAt(cam0.tgt);
    if (!opt.restCamera) {
      const u = smooth(t / TL.duration);
      camera.position.lerpVectors(cam0.pos, focusPt, TL.push * u);
      camera.position.x += 0.012 * nCam[0](t * 0.5); camera.position.y += 0.010 * nCam[1](t * 0.45);
      tmpV.copy(cam0.tgt); camera.lookAt(tmpV);
      camera.rotateY(0.0026 * nCam[2](t * 0.6)); camera.rotateX(0.0022 * nCam[3](t * 0.55));
      camera.rotateZ(0.0015 * nCam[0](t * 0.4 + 9));
    }
    if (debugCam) { camera.position.set(...debugCam.pos); camera.lookAt(new THREE.Vector3(...debugCam.tgt)); }
    camera.updateMatrixWorld();
    return { hash: stateHash() };
  }

  function stateHash() {   // FNV-1a over every transform, morph weight and the camera (quantised to 1e-5)
    let h = 2166136261;
    const add = (x) => { const q = Math.round(x * 1e5) | 0; h ^= q; h = Math.imul(h, 16777619) >>> 0; };
    for (const n of Object.values(N)) { for (const a of [n.position, n.scale]) { add(a.x); add(a.y); add(a.z); } add(n.rotation.x); add(n.rotation.y); add(n.rotation.z); }
    for (const ms of Object.values(morphMeshes)) for (const m of ms) for (const w of m.morphTargetInfluences) add(w);
    for (const e of camera.matrixWorld.elements) add(e);
    return h.toString(16);
  }

  return { apply, duration: TL.duration, lineEnd };
}
