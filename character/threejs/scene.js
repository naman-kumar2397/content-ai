// Duo shot (Joey + Ball/Hugsy) recreated in three.js. Driven externally and deterministically:
//   await window.setup({w, h, dof, ao, sidekick, shadows})  -> builds scene once
//   await window.renderAt(t)                                  -> poses everything for time t (s) and renders one frame
// No realtime clock anywhere: the same t always gives the same image.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { GTAOPass } from 'three/addons/postprocessing/GTAOPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';

const GLTF_DIR = '../gltf/';
let S = null;  // state

// ---------------------------------------------------------------- helpers
const lerp = (a, b, u) => a + (b - a) * u;
const smooth = (u) => { u = Math.min(1, Math.max(0, u)); return u * u * (3 - 2 * u); };
function seeded(seed) { let s = seed >>> 0; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); }

function deskTexture() {
  // dark wood bands, like the Blender wave texture (bands along X, distorted)
  const c = document.createElement('canvas'); c.width = 1024; c.height = 1024;
  const g = c.getContext('2d'); const img = g.createImageData(1024, 1024); const rnd = seeded(3);
  const ph = Array.from({ length: 6 }, () => [rnd() * 6.28, 1 + rnd() * 5, rnd() * 0.6]);
  for (let y = 0; y < 1024; y++) for (let x = 0; x < 1024; x++) {
    let w = y / 1024 * 14 * 6.28;
    for (const [p, f, a] of ph) w += a * 2.2 * Math.sin(x / 1024 * f * 6.28 + p + y / 300);
    const v = 0.5 + 0.5 * Math.sin(w);
    // Blender ramp (linear) 0.03,0.017,0.012 -> 0.11,0.06,0.04 ; write sRGB
    const lin = [lerp(0.03, 0.11, v), lerp(0.017, 0.06, v), lerp(0.012, 0.04, v)];
    const i = (y * 1024 + x) * 4;
    for (let k = 0; k < 3; k++) img.data[i + k] = 255 * (lin[k] <= 0.0031308 ? lin[k] * 12.92 : 1.055 * lin[k] ** (1 / 2.4) - 0.055);
    img.data[i + 3] = 255;
  }
  g.putImageData(img, 0, 0);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 4;
  return t;
}

function glowTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const g = c.getContext('2d'); const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.25, 'rgba(255,255,255,0.35)');
  gr.addColorStop(0.6, 'rgba(255,255,255,0.07)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(c);
}

// Environment map built from the same area lights -> glossy highlights on eyes/nose/desk look like Cycles'
function buildEnv(renderer, lights) {
  const env = new THREE.Scene();
  env.background = new THREE.Color(0.03 * 0.35, 0.06 * 0.35, 0.16 * 0.35);
  for (const L of lights) {
    const area = L.size * L.size;
    const rad = L.energy / (area * Math.PI) * 0.02;            // relative radiance of the emitter
    const m = new THREE.MeshBasicMaterial({ color: new THREE.Color(...L.color).multiplyScalar(rad), side: THREE.DoubleSide });
    const p = new THREE.Mesh(new THREE.PlaneGeometry(L.size, L.size), m);
    p.position.set(...L.location); p.lookAt(new THREE.Vector3(...L.location).add(new THREE.Vector3(...L.direction)));
    env.add(p);
  }
  const pm = new THREE.PMREMGenerator(renderer);
  const rt = pm.fromScene(env, 0.0, 0.1, 100);
  pm.dispose();
  return rt.texture;
}

// ---------------------------------------------------------------- DOF (physical CoC, scatter-as-gather)
const DofShader = {
  uniforms: {
    tDiffuse: { value: null }, tDepth: { value: null },
    near: { value: 0.1 }, far: { value: 100 }, focus: { value: 6.5 },
    cocK: { value: 1 }, maxCoc: { value: 24 }, res: { value: new THREE.Vector2() },
  },
  vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.); }`,
  fragmentShader: `
    uniform sampler2D tDiffuse, tDepth; uniform float near, far, focus, cocK, maxCoc; uniform vec2 res; varying vec2 vUv;
    float viewZ(vec2 uv){ float d = texture2D(tDepth, uv).x; return near * far / (far - d * (far - near)); }
    float coc(vec2 uv){ float z = viewZ(uv); return clamp(cocK * abs(z - focus) / z, 0., maxCoc); }   // radius in px
    void main(){
      float c0 = coc(vUv);
      vec4 acc = vec4(texture2D(tDiffuse, vUv).rgb, 1.);
      const int N = 40; const float GA = 2.39996323;
      for (int i = 1; i < N; i++) {
        float r = sqrt(float(i) / float(N)) * maxCoc; float a = float(i) * GA;
        vec2 o = vec2(cos(a), sin(a)) * r / res; vec2 uv = vUv + o;
        float cs = coc(uv);
        // a sample contributes if its own blur disc reaches us (background can't bleed over sharp foreground)
        float w = smoothstep(r - 1.5, r + 0.5, min(cs, c0 + 2.0 + cs * step(viewZ(uv), viewZ(vUv))));
        acc += vec4(texture2D(tDiffuse, uv).rgb * w, w);
      }
      gl_FragColor = vec4(acc.rgb / acc.a, 1.);
    }`,
};

// ---------------------------------------------------------------- setup
async function setup(opts = {}) {
  const o = Object.assign({ w: 1080, h: 1920, dof: true, ao: true, sidekick: 'ball', shadows: true, msaa: 4,
    tone: 'agx', exposure: 0.42, env: 0.3, hemi: 1.2, key: 0.8, rim: 1.5, fill: 1, desk: 0.55, deskSpec: 0.35, sheen: 0.15,
    glow: 0.05, rimShadow: true }, opts);
  const sc = await (await fetch(GLTF_DIR + 'scene.json')).json();

  const canvas = document.createElement('canvas'); document.body.appendChild(canvas);
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(1); renderer.setSize(o.w, o.h, false);
  canvas.style.width = '100%';
  renderer.shadowMap.enabled = o.shadows;
  renderer.shadowMap.type = o.shadowType === 'pcf' ? THREE.PCFSoftShadowMap : THREE.VSMShadowMap;
  renderer.toneMapping = { aces: THREE.ACESFilmicToneMapping, agx: THREE.AgXToneMapping, neutral: THREE.NeutralToneMapping }[o.tone];
  renderer.toneMappingExposure = o.exposure;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0, 0, 0);
  scene.environment = buildEnv(renderer, sc.lights);
  scene.environmentIntensity = o.env;

  // ---- camera: Blender lens 65mm, 36mm sensor fit horizontally
  const C = sc.camera; const aspect = o.w / o.h;
  const vfov = 2 * Math.atan(Math.tan(Math.atan(C.sensor_width / 2 / C.lens)) / aspect) * 180 / Math.PI;
  const camera = new THREE.PerspectiveCamera(vfov, aspect, 0.5, 60);
  const camPos = new THREE.Vector3(...C.location), camTgt = new THREE.Vector3(...C.target);
  camera.position.copy(camPos); camera.lookAt(camTgt);
  const focusPt = new THREE.Vector3(...C.focus_point);

  // ---- desk + wall
  const desk = new THREE.Mesh(new THREE.PlaneGeometry(40, 30), new THREE.MeshPhysicalMaterial({ map: deskTexture(), roughness: o.deskRough ?? 0.72, envMapIntensity: 0.4, specularIntensity: o.deskSpec ?? 1 }));
  desk.material.map.repeat.set(1.5, 1.5); desk.material.color.setScalar(o.desk ?? 1);
  desk.rotation.x = -Math.PI / 2; desk.position.set(0, 0, -4); desk.receiveShadow = true; scene.add(desk);
  const wall = new THREE.Mesh(new THREE.PlaneGeometry(40, 12), new THREE.MeshStandardMaterial({ color: new THREE.Color(0.02, 0.04, 0.10), roughness: 0.9 }));
  wall.position.set(0, 5, -7); wall.receiveShadow = true; scene.add(wall);

  // ---- bokeh city lights: the exact spheres from the Blender scene + soft glow they cast on the wall
  const glow = glowTexture();
  for (const b of sc.bokeh) {
    const col = new THREE.Color(...b.color);
    const sph = new THREE.Mesh(new THREE.SphereGeometry(b.radius, 16, 10), new THREE.MeshBasicMaterial({ color: col.clone().multiplyScalar(b.strength) }));
    sph.position.set(...b.location); scene.add(sph);
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: glow, color: col.clone().multiplyScalar(o.glow * b.strength),
      blending: THREE.AdditiveBlending, depthWrite: false, transparent: true }));
    sp.scale.setScalar(b.radius * 5); sp.position.set(b.location[0], b.location[1], b.location[2] - 0.35); scene.add(sp);
  }

  // ---- lights (Blender area lights -> spot lights; same positions/colours, energy scaled)
  scene.add(new THREE.HemisphereLight(new THREE.Color(0.03, 0.06, 0.16), new THREE.Color(0.16, 0.09, 0.05), o.hemi));
  const tgt = new THREE.Object3D(); tgt.position.copy(camTgt); scene.add(tgt);
  const K = { Key: 0.020 * o.key, Fill: 0.020 * o.fill, Rim: 0.030 * o.rim, Rim2: 0.030 * o.rim };
  for (const L of sc.lights) {
    const s = new THREE.SpotLight(new THREE.Color(...L.color), L.energy * (K[L.name] ?? 0.02) * 50, 0, Math.PI / 3, 1.0, 2);
    s.position.set(...L.location); s.target = tgt;
    if (L.name === 'Key' && o.shadows) {
      s.castShadow = true; s.shadow.mapSize.set(2048, 2048); s.shadow.camera.near = 2; s.shadow.camera.far = 20;
      s.shadow.radius = 14; s.shadow.blurSamples = 16; s.shadow.bias = -0.0004;
    }
    if (L.name === 'Rim' && o.shadows && o.rimShadow) {
      s.castShadow = true; s.shadow.mapSize.set(1024, 1024); s.shadow.camera.near = 2; s.shadow.camera.far = 20;
      s.shadow.radius = 20; s.shadow.blurSamples = 16; s.shadow.bias = -0.0006;
    }
    scene.add(s);
  }

  // ---- characters
  const loader = new GLTFLoader();
  const load = async (n) => (await loader.loadAsync(GLTF_DIR + n + '.glb')).scene;
  const mats = sc.materials;
  const physical = (name) => {  // Blender Principled params -> MeshPhysicalMaterial (albedo*tint is in COLOR_0)
    const p = mats[name] || { roughness: 0.8, specular: 0.3, sheen: 0, coat: 0 };
    return new THREE.MeshPhysicalMaterial({
      name, vertexColors: true, flatShading: true, roughness: p.roughness,
      specularIntensity: Math.min(1, p.specular * 2), sheen: p.sheen * (o.sheen ?? 1), sheenRoughness: 0.6,
      sheenColor: new THREE.Color(1, 0.95, 0.85).multiplyScalar(0.35),
      clearcoat: p.coat, clearcoatRoughness: 0.08,
    });
  };
  const prep = (root) => root.traverse((m) => {
    if (!m.isMesh) return;
    const side = m.material.side;
    m.material = physical(m.material.name); m.material.side = side;   // glTF doubleSided (ball seam ribbon)
    // per-material fixes for what doesn't survive the port: Cycles occludes the mouth cavity (no env light leak),
    // and the ball's procedural fuzz bump darkens it noticeably
    const fix = { J_Mouth: { env: 0.1 }, J_Tongue: { env: 0.4 }, B_Fuzz: { albedo: 0.62 } }[m.material.name];
    if (fix?.env !== undefined) m.material.envMapIntensity = fix.env;
    if (fix?.albedo !== undefined) m.material.color.setScalar(fix.albedo);
    m.castShadow = m.receiveShadow = true;
  });
  const joey = await load('joey'); prep(joey); scene.add(joey);
  const nodes = {}; joey.traverse((n) => (nodes[n.name] = n));
  let side;
  if (o.sidekick === 'hugsy') {
    side = await load('hugsy'); prep(side);
    const hb = side.getObjectByName('Hugsy_Body');
    hb.position.set(1.30, 0, 1.0); hb.rotation.set(-0.2, -0.85, 0, 'YZX');   // = Blender HUGSY_POS, rot (-0.2,0,-0.85)
  } else { side = await load('ball'); prep(side); }
  scene.add(side); side.traverse((n) => (nodes[n.name] = n));
  const rest = {};
  for (const [k, n] of Object.entries(nodes)) rest[k] = { p: n.position.clone(), r: n.rotation.clone(), s: n.scale.clone() };

  // ---- render targets / passes
  const depthTex = new THREE.DepthTexture(o.w, o.h); depthTex.type = THREE.UnsignedIntType;
  const rtScene = new THREE.WebGLRenderTarget(o.w, o.h, { type: THREE.HalfFloatType, samples: o.msaa, depthTexture: depthTex });
  const rtA = new THREE.WebGLRenderTarget(o.w, o.h, { type: THREE.HalfFloatType });
  const rtB = new THREE.WebGLRenderTarget(o.w, o.h, { type: THREE.HalfFloatType });
  let gtao = null;
  if (o.ao) {
    gtao = new GTAOPass(scene, camera, o.w, o.h);
    gtao.setGBuffer(depthTex);   // reuse the scene depth; normals reconstructed from depth (exact for flat shading)
    gtao.output = GTAOPass.OUTPUT.Default;
    gtao.blendIntensity = 1.0;
    gtao.updateGtaoMaterial({ radius: 0.35, distanceExponent: 1.5, thickness: 1.0, scale: 1.0, samples: 16 });
    gtao.updatePdMaterial({ lumaPhi: 10, depthPhi: 2, normalPhi: 3, radius: 6, rings: 2, samples: 12 });
  }
  let dof = null;
  if (o.dof) {
    dof = new ShaderPass(DofShader);
    const u = dof.uniforms;
    u.tDepth.value = depthTex; u.near.value = camera.near; u.far.value = camera.far;
    u.res.value.set(o.w, o.h);
    // physical CoC radius in px: 0.5 * A * f/(df-f) * |z-df|/z / sensor * width ; A=f/N (mm), df in mm
    const f = C.lens, A = f / C.fstop;
    const fd = () => camera.position.distanceTo(focusPt);
    u.focus.value = fd();
    u.cocK.value = 0.5 * A * f / (fd() * 1000 - f) / C.sensor_width * o.w * (o.dofBoost ?? 1);
    u.maxCoc.value = Math.max(4, o.w / 90);
  }
  const out = new OutputPass();

  S = { o, sc, renderer, scene, camera, camPos, camTgt, focusPt, nodes, rest, rtScene, rtA, rtB, gtao, dof, out };
  return { vfov, tris: renderer.info.render.triangles };
}

// ---------------------------------------------------------------- animation (pure function of t)
function blinkAmt(t, times) {
  let b = 0;
  for (const c of times) { const d = Math.abs(t - c); if (d < 0.09) b = Math.max(b, 1 - d / 0.09); }
  return b;
}

function pose(t) {
  const { nodes: N, rest: R } = S;
  for (const [k, r] of Object.entries(R)) { const n = N[k]; n.position.copy(r.p); n.rotation.copy(r.r); n.scale.copy(r.s); }
  // Joey: talk (jaw), blink, ear wiggle, slight head bob
  const talk = Math.max(0, Math.sin(t * 2 * Math.PI * 2.6)) * smooth((t - 0.3) / 0.2) * (1 - smooth((t - 2.5) / 0.2));
  if (N.Joey_Jaw) N.Joey_Jaw.rotation.x = R.Joey_Jaw.r.x + THREE.MathUtils.degToRad(-6 + 22 * talk);
  const bl = blinkAmt(t, [0.9, 2.2]);
  for (const e of ['Joey_EyeL', 'Joey_EyeR']) if (N[e]) N[e].scale.y = R[e].s.y * (1 - 0.9 * bl);
  const wig = Math.sin(t * 2 * Math.PI * 1.7) * Math.exp(-((t - 1.6) ** 2) / 0.35);
  if (N.Joey_EarL) { N.Joey_EarL.rotation.z = R.Joey_EarL.r.z - 0.18 * wig; N.Joey_EarL.rotation.x = R.Joey_EarL.r.x + 0.08 * wig; }
  if (N.Joey_EarR) { N.Joey_EarR.rotation.z = R.Joey_EarR.r.z + 0.18 * wig; N.Joey_EarR.rotation.x = R.Joey_EarR.r.x - 0.08 * wig; }
  if (N.Joey_Head) { N.Joey_Head.rotation.z = R.Joey_Head.r.z + 0.04 * Math.sin(t * 2.1); N.Joey_Head.rotation.x = R.Joey_Head.r.x + 0.03 * talk; }
  // sidekick: deadpan squint around t=1.2..2.4 (+ flipper raise for Hugsy)
  const sq = smooth((t - 1.1) / 0.25) * (1 - smooth((t - 2.3) / 0.25));
  for (const e of ['Ball_EyeL', 'Ball_EyeR', 'Hugsy_EyeL', 'Hugsy_EyeR']) if (N[e]) N[e].scale.y = R[e].s.y * (1 - 0.6 * sq - 0.9 * blinkAmt(t, [0.5]));
  if (N.Hugsy_FlipperR) N.Hugsy_FlipperR.rotation.z = R.Hugsy_FlipperR.r.z + 0.7 * sq;
  if (N.Hugsy_Brows) N.Hugsy_Brows.position.y = R.Hugsy_Brows.p.y - 0.02 * sq;
  if (N.Ball_Body) N.Ball_Body.scale.y = R.Ball_Body.s.y * (1 - 0.03 * sq);
  // camera: slow push-in (8% closer over the clip), focus follows
  const u = smooth(t / 3);
  S.camera.position.lerpVectors(S.camPos, S.camTgt, 0.08 * u); S.camera.lookAt(S.camTgt);
  if (S.dof) S.dof.uniforms.focus.value = S.camera.position.distanceTo(S.focusPt);
}

async function renderAt(t) {
  pose(t);
  const { renderer: r, scene, camera, rtScene, rtA, rtB, gtao, dof, out } = S;
  r.setRenderTarget(rtScene); r.render(scene, camera);
  let src = rtScene;
  if (gtao) { gtao.render(r, rtA, src); src = rtA; }
  if (dof) { const dst = src === rtA ? rtB : rtA; dof.render(r, dst, src); src = dst; }
  out.renderToScreen = true; out.render(r, null, src);
  const gl = r.getContext(); const px = new Uint8Array(4); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px);  // sync GPU
  return true;
}

window.setup = setup;
window.renderAt = renderAt;
window.__ready = true;
