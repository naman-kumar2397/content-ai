// v2 duo shot (Joey + Hugsy + set dressing). Same external contract as scene.js:
//   await window.setup(opts)  -> builds the scene once
//   await window.renderAt(t)  -> poses for time t (pure function of t), renders one frame
//   window.grab()             -> RGBA8 pixels of the last frame (bottom-up rows)
// Modes:
//   plate: false -> everything rendered every frame (+ optional GTAO / DOF), like round 1
//   plate: true  -> background (wall, window, city, desk, props + the characters' rest-pose shadows) is rendered once
//                   with DOF into an HDR plate; per frame only the characters are rendered over it. The plate is
//                   re-projected through the plane at the focus distance, so push-ins and handheld drift line up.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { GTAOPass } from 'three/addons/postprocessing/GTAOPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { SMAAPass } from 'three/addons/postprocessing/SMAAPass.js';
import { createAnim } from './anim.js';

const GLTF_DIR = '../gltf/';
const BG = 0, FG = 1;          // layers: background (plate) / characters
let S = null;

const lerp = (a, b, u) => a + (b - a) * u;
function seeded(seed) { let s = seed >>> 0; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); }
const toSRGB = (x) => 255 * (x <= 0.0031308 ? x * 12.92 : 1.055 * x ** (1 / 2.4) - 0.055);

function deskTexture() {
  const c = document.createElement('canvas'); c.width = 1024; c.height = 1024;
  const g = c.getContext('2d'); const img = g.createImageData(1024, 1024); const rnd = seeded(3);
  const ph = Array.from({ length: 6 }, () => [rnd() * 6.28, 1 + rnd() * 5, rnd() * 0.6]);
  for (let y = 0; y < 1024; y++) for (let x = 0; x < 1024; x++) {
    let w = y / 1024 * 14 * 6.28;
    for (const [p, f, a] of ph) w += a * 2.2 * Math.sin(x / 1024 * f * 6.28 + p + y / 300);
    const v = 0.5 + 0.5 * Math.sin(w);
    const lin = [lerp(0.03, 0.11, v), lerp(0.017, 0.06, v), lerp(0.012, 0.04, v)];
    const i = (y * 1024 + x) * 4;
    for (let k = 0; k < 3; k++) img.data[i + k] = toSRGB(lin[k]);
    img.data[i + 3] = 255;
  }
  g.putImageData(img, 0, 0);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 4;
  return t;
}

// lit-window facade: dark grid, ~35% windows lit warm/cool, some with blinds
function facadeTexture(seed) {
  const c = document.createElement('canvas'); c.width = 128; c.height = 256; const g = c.getContext('2d'); const rnd = seeded(seed);
  g.fillStyle = 'rgb(3,4,9)'; g.fillRect(0, 0, 128, 256);
  for (let y = 8; y < 248; y += 20) for (let x = 8; x < 120; x += 18) {
    if (rnd() > 0.2) continue;
    const warm = rnd() < 0.7, k = 0.45 + 0.55 * rnd();
    g.fillStyle = warm ? `rgb(${255 * k | 0},${190 * k | 0},${100 * k | 0})` : `rgb(${150 * k | 0},${190 * k | 0},${255 * k | 0})`;
    g.fillRect(x, y, 10, 12);
  }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.magFilter = THREE.LinearFilter;
  return t;
}

function screenTexture() {   // laptop: dark editor with coloured code lines
  const c = document.createElement('canvas'); c.width = 256; c.height = 160; const g = c.getContext('2d'); const rnd = seeded(9);
  g.fillStyle = '#0d1424'; g.fillRect(0, 0, 256, 160);
  g.fillStyle = '#16213a'; g.fillRect(0, 0, 256, 12);
  const cols = ['#7fd4ff', '#ffcf6b', '#c792ea', '#9ece6a', '#e8eaf0'];
  for (let y = 18; y < 156; y += 8) {
    let x = 8 + 8 * Math.floor(rnd() * 3);
    while (x < 230 && rnd() < 0.8) { const w = 10 + rnd() * 40; g.fillStyle = cols[Math.floor(rnd() * cols.length)]; g.fillRect(x, y, w, 4); x += w + 5; }
  }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function skyTexture() {
  const c = document.createElement('canvas'); c.width = 4; c.height = 256; const g = c.getContext('2d');
  const gr = g.createLinearGradient(0, 0, 0, 256);
  gr.addColorStop(0, '#05081a'); gr.addColorStop(0.65, '#141a3d'); gr.addColorStop(1, '#3a2c4a');
  g.fillStyle = gr; g.fillRect(0, 0, 4, 256);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}

function buildEnv(renderer, lights) {
  const env = new THREE.Scene();
  env.background = new THREE.Color(0.03 * 0.35, 0.06 * 0.35, 0.16 * 0.35);
  for (const L of lights) {
    const rad = L.energy / (L.size * L.size * Math.PI) * 0.02;
    const p = new THREE.Mesh(new THREE.PlaneGeometry(L.size, L.size),
      new THREE.MeshBasicMaterial({ color: new THREE.Color(...L.color).multiplyScalar(rad), side: THREE.DoubleSide }));
    p.position.set(...L.location); p.lookAt(new THREE.Vector3(...L.location).add(new THREE.Vector3(...L.direction)));
    env.add(p);
  }
  const pm = new THREE.PMREMGenerator(renderer); const rt = pm.fromScene(env, 0.0, 0.1, 100); pm.dispose();
  return rt.texture;
}

// ---------------------------------------------------------------- DOF: gather, CoC grows outside a sharp focus band
function dofShader(N) {
  return {
    uniforms: {
      tDiffuse: { value: null }, tDepth: { value: null }, near: { value: 0.1 }, far: { value: 100 }, focus: { value: 6.5 },
      band: { value: 1.2 }, cocK: { value: 1 }, maxCoc: { value: 24 }, res: { value: new THREE.Vector2() },
    },
    vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.); }`,
    fragmentShader: `
      uniform sampler2D tDiffuse, tDepth; uniform float near, far, focus, band, cocK, maxCoc; uniform vec2 res; varying vec2 vUv;
      float viewZ(vec2 uv){ float d = texture2D(tDepth, uv).x; return near * far / (far - d * (far - near)); }
      float coc(float z){ return clamp(cocK * max(0., abs(z - focus) - band) / z, 0., maxCoc); }
      void main(){
        float z0 = viewZ(vUv); float c0 = coc(z0);
        vec4 acc = vec4(texture2D(tDiffuse, vUv).rgb, 1.);
        const int N = ${N}; const float GA = 2.39996323;
        for (int i = 1; i < N; i++) {
          float r = sqrt(float(i) / float(N)) * maxCoc; float a = float(i) * GA;
          vec2 uv = vUv + vec2(cos(a), sin(a)) * r / res;
          float zs = viewZ(uv); float cs = coc(zs);
          float w = smoothstep(r - 1.5, r + 0.5, min(cs, c0 + 2.0 + cs * step(zs, z0)));
          acc += vec4(texture2D(tDiffuse, uv).rgb * w, w);
        }
        gl_FragColor = vec4(acc.rgb / acc.a, 1.);
      }`,
  };
}

// plate re-projection: screen ray of the current camera -> plane at focus distance -> plate camera UV
const PlateShader = {
  uniforms: { tPlate: { value: null }, invVP: { value: new THREE.Matrix4() }, plateVP: { value: new THREE.Matrix4() },
    pN: { value: new THREE.Vector3() }, pD: { value: 0 } },
  vertexShader: `varying vec2 vNdc; void main(){ vNdc = position.xy; gl_Position = vec4(position.xy, 0., 1.); }`,
  fragmentShader: `
    uniform sampler2D tPlate; uniform mat4 invVP, plateVP; uniform vec3 pN; uniform float pD; varying vec2 vNdc;
    void main(){
      vec4 a = invVP * vec4(vNdc, -1., 1.); vec4 b = invVP * vec4(vNdc, 1., 1.); a /= a.w; b /= b.w;
      vec3 d = b.xyz - a.xyz; float s = -(dot(pN, a.xyz) + pD) / dot(pN, d);
      vec4 q = plateVP * vec4(a.xyz + d * s, 1.); vec2 uv = q.xy / q.w * 0.5 + 0.5;
      gl_FragColor = vec4(texture2D(tPlate, uv).rgb, 1.);
    }`,
};

// plate mode composite: re-projected plate + characters layer (premultiplied, rendered only inside its screen
// rect), tone-mapped (AgX) and sRGB-encoded in one full-screen pass
const CompositeShader = {
  uniforms: { tPlate: { value: null }, tChar: { value: null }, invVP: { value: new THREE.Matrix4() }, plateVP: { value: new THREE.Matrix4() },
    pN: { value: new THREE.Vector3() }, pD: { value: 0 }, rect: { value: new THREE.Vector4() }, toneMappingExposure: { value: 1 } },
  vertexShader: PlateShader.vertexShader,
  fragmentShader: `
    #include <tonemapping_pars_fragment>
    uniform sampler2D tPlate, tChar; uniform mat4 invVP, plateVP; uniform vec3 pN; uniform float pD; uniform vec4 rect; varying vec2 vNdc;
    void main(){
      vec4 a = invVP * vec4(vNdc, -1., 1.); vec4 b = invVP * vec4(vNdc, 1., 1.); a /= a.w; b /= b.w;
      vec3 d = b.xyz - a.xyz; float s = -(dot(pN, a.xyz) + pD) / dot(pN, d);
      vec4 q = plateVP * vec4(a.xyz + d * s, 1.);
      vec3 c = texture2D(tPlate, q.xy / q.w * 0.5 + 0.5).rgb;
      vec2 cu = (gl_FragCoord.xy - rect.xy) / rect.zw;
      if (all(greaterThanEqual(cu, vec2(0.))) && all(lessThanEqual(cu, vec2(1.)))) { vec4 ch = texture2D(tChar, cu); c = ch.rgb + c * (1. - ch.a); }
      gl_FragColor = sRGBTransferOETF(vec4(AgXToneMapping(c), 1.));
    }`,
};

// baked GI/AO: COLOR_1 (rgb = Cycles indirect irradiance, a = AO) -> occludes ambient, adds warm bounce
function withBake(mat, U) {
  mat.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, U);
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nattribute vec4 color_1; varying vec4 vGI;')
      .replace('#include <color_vertex>', '#include <color_vertex>\nvGI = color_1;');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying vec4 vGI; uniform float uAO, uDirAO, uGI;')
      .replace('#include <aomap_fragment>', `#include <aomap_fragment>
        float bAO = mix(1.0, vGI.a, uAO);
        reflectedLight.indirectDiffuse *= bAO; reflectedLight.indirectSpecular *= bAO;
        reflectedLight.directDiffuse *= mix(1.0, vGI.a, uDirAO);
        totalEmissiveRadiance += diffuseColor.rgb * vGI.rgb * uGI;`);
  };
  mat.customProgramCacheKey = () => 'baked';
}

// ---------------------------------------------------------------- setup
async function setup(opts = {}) {
  const o = Object.assign({
    w: 1080, h: 1920, plate: true, ao: 'baked', dof: true, dofN: 40, plateDofN: 160, aa: 'msaa', msaa: 4,
    shadows: true, shadowSize: 1024, shadowFocus: 0.45, rimShadow: true, shadowType: 'vsm', overscan: 1.08,
    tone: 'agx', exposure: 0.42, env: 0.3, hemi: 0.55, key: 0.8, rim: 1.5, fill: 1, desk: 0.55, deskSpec: 0.35,
    sheen: 0.15, bakeAO: 0.85, bakeDirAO: 0.35, bakeGI: 0.9, dofBoost: 8, band: 1.4, city: 3.2, screen: 1.6,
    seed: 1, timeline: null,
  }, opts);
  const sc = await (await fetch(GLTF_DIR + 'scene2.json')).json();

  const canvas = document.createElement('canvas'); document.body.appendChild(canvas);
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(1); renderer.setSize(o.w, o.h, false); canvas.style.width = '100%';
  renderer.shadowMap.enabled = o.shadows;
  renderer.shadowMap.type = { vsm: THREE.VSMShadowMap, pcf: THREE.PCFSoftShadowMap, basic: THREE.PCFShadowMap }[o.shadowType];
  renderer.toneMapping = { aces: THREE.ACESFilmicToneMapping, agx: THREE.AgXToneMapping, neutral: THREE.NeutralToneMapping }[o.tone];
  renderer.toneMappingExposure = o.exposure;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0, 0, 0);
  scene.environment = buildEnv(renderer, sc.lights);
  scene.environmentIntensity = o.env;
  const bg = (obj) => { obj.traverse((n) => n.layers.set(BG)); scene.add(obj); return obj; };

  // ---- camera
  const C = sc.camera; const aspect = o.w / o.h;
  const vfov = 2 * Math.atan(Math.tan(Math.atan(C.sensor_width / 2 / C.lens)) / aspect) * 180 / Math.PI;
  const camera = new THREE.PerspectiveCamera(vfov, aspect, 0.5, 120);
  const camPos = new THREE.Vector3(...C.location), camTgt = new THREE.Vector3(...C.target);
  camera.position.copy(camPos); camera.lookAt(camTgt);
  const focusPt = new THREE.Vector3(...C.focus_point);

  // ---- desk, wall with window opening, city outside
  const desk = new THREE.Mesh(new THREE.PlaneGeometry(40, 30), new THREE.MeshPhysicalMaterial({ map: deskTexture(), roughness: 0.72, envMapIntensity: 0.4, specularIntensity: o.deskSpec }));
  desk.material.map.repeat.set(1.5, 1.5); desk.material.color.setScalar(o.desk);
  desk.rotation.x = -Math.PI / 2; desk.position.set(0, 0, -4); desk.receiveShadow = true; bg(desk);
  const W = sc.window;
  const wallShape = new THREE.Shape([new THREE.Vector2(-20, -1), new THREE.Vector2(20, -1), new THREE.Vector2(20, 11), new THREE.Vector2(-20, 11)]);
  wallShape.holes.push(new THREE.Path([new THREE.Vector2(W.x0, W.y0), new THREE.Vector2(W.x0, W.y1), new THREE.Vector2(W.x1, W.y1), new THREE.Vector2(W.x1, W.y0)]));
  const wall = new THREE.Mesh(new THREE.ShapeGeometry(wallShape), new THREE.MeshStandardMaterial({ color: new THREE.Color(0.02, 0.04, 0.10), roughness: 0.9 }));
  wall.position.z = W.z; wall.receiveShadow = true; bg(wall);
  // reveal (wall thickness) around the opening
  const revealM = new THREE.MeshStandardMaterial({ color: new THREE.Color(0.015, 0.03, 0.075), roughness: 0.9 });
  for (const [x, y, sx, sy] of [[(W.x0 + W.x1) / 2, W.y0, W.x1 - W.x0, 0.01], [(W.x0 + W.x1) / 2, W.y1, W.x1 - W.x0, 0.01], [W.x0, (W.y0 + W.y1) / 2, 0.01, W.y1 - W.y0], [W.x1, (W.y0 + W.y1) / 2, 0.01, W.y1 - W.y0]]) {
    const r = new THREE.Mesh(new THREE.BoxGeometry(sx, sy, 0.3), revealM); r.position.set(x, y, W.z - 0.15); bg(r);
  }
  const city = new THREE.Group(); const rnd = seeded(17);
  const sky = new THREE.Mesh(new THREE.PlaneGeometry(160, 70), new THREE.MeshBasicMaterial({ map: skyTexture(), depthWrite: true }));
  sky.position.set(0, 20, -90); city.add(sky);
  for (let layer = 0; layer < 3; layer++) {
    const z = -24 - layer * 12, n = 9 + layer * 3;
    for (let i = 0; i < n; i++) {
      const bw = 2 + rnd() * 3.5, bh = 6 + rnd() * (14 + layer * 8);
      const tex = facadeTexture(100 + layer * 50 + i); tex.wrapS = tex.wrapT = THREE.RepeatWrapping; tex.repeat.set(bw / 3, bh / 6);
      const k = o.city * (1 - 0.25 * layer);
      const m = new THREE.Mesh(new THREE.PlaneGeometry(bw, bh), new THREE.MeshBasicMaterial({ map: tex, color: new THREE.Color(k, k, k) }));
      m.position.set(-14 + (i + rnd() * 0.6) * (30 / n), bh / 2 - 4 + layer * 1.5, z - rnd() * 3); city.add(m);
    }
  }
  bg(city);

  // ---- lights
  const hemi = new THREE.HemisphereLight(new THREE.Color(0.03, 0.06, 0.16), new THREE.Color(0.16, 0.09, 0.05), o.hemi);
  hemi.layers.enableAll(); scene.add(hemi);
  const tgt = new THREE.Object3D(); tgt.position.copy(camTgt); scene.add(tgt);
  const K = { Key: 0.020 * o.key, Fill: 0.020 * o.fill, Rim: 0.030 * o.rim, Rim2: 0.030 * o.rim };
  const shadowLights = [];
  for (const L of sc.lights) {
    const s = new THREE.SpotLight(new THREE.Color(...L.color), L.energy * (K[L.name] ?? 0.02) * 50, 0, Math.PI / 3, 1.0, 2);
    s.position.set(...L.location); s.target = tgt; s.layers.enableAll();
    const sh = (size, radius, bias) => {
      s.castShadow = true; s.shadow.mapSize.set(size, size); s.shadow.camera.near = 2; s.shadow.camera.far = 20;
      s.shadow.radius = radius; s.shadow.blurSamples = o.blurSamples ?? 16; s.shadow.bias = bias; s.shadow.focus = o.shadowFocus;
      shadowLights.push(s);
    };
    if (L.name === 'Key' && o.shadows) sh(o.shadowSize, 14 * o.shadowSize / 2048, -0.0004);
    if (L.name === 'Rim' && o.shadows && o.rimShadow) sh(o.shadowSize / 2, 20 * o.shadowSize / 2048, -0.0006);
    scene.add(s);
  }
  // laptop glow on the desk/props only (background layer; baked into the plate)
  const scrLight = new THREE.PointLight(new THREE.Color(0.45, 0.6, 1.0), 2.5, 3.5, 2); scrLight.layers.set(BG);

  // ---- glTF: characters + props
  const loader = new GLTFLoader();
  const load = async (n) => (await loader.loadAsync(GLTF_DIR + n + '.glb')).scene;
  const mats = sc.materials;
  const U = { uAO: { value: o.ao === 'baked' ? o.bakeAO : 0 }, uDirAO: { value: o.ao === 'baked' ? o.bakeDirAO : 0 }, uGI: { value: o.ao === 'baked' ? o.bakeGI : 0 } };
  const physical = (name) => {
    const p = mats[name] || { roughness: 0.8, specular: 0.3, sheen: 0, coat: 0 };
    const m = new THREE.MeshPhysicalMaterial({
      name, vertexColors: true, flatShading: true, roughness: p.roughness,
      specularIntensity: Math.min(1, p.specular * 2), sheen: p.sheen * o.sheen, sheenRoughness: 0.6,
      sheenColor: new THREE.Color(1, 0.95, 0.85).multiplyScalar(0.35), clearcoat: p.coat, clearcoatRoughness: 0.08,
    });
    withBake(m, U); return m;
  };
  const screenTex = screenTexture();
  const prep = (root, layer) => root.traverse((m) => {
    m.layers.set(layer);
    if (!m.isMesh) return;
    const side = m.material.side; const name = m.material.name;
    if (name === 'P_Screen') {
      m.material = new THREE.MeshBasicMaterial({ map: screenTex, color: new THREE.Color().setScalar(o.screen) });
      m.add(scrLight); scrLight.position.set(0, 0.0, 0.5);
      return;
    }
    m.material = physical(name); m.material.side = side;
    const fix = { J_Mouth: { env: 0.1 }, J_Tongue: { env: 0.4 } }[name];
    if (fix?.env !== undefined) m.material.envMapIntensity = fix.env;
    m.castShadow = true; m.receiveShadow = true;
  });
  const [joey, hugsy, props] = await Promise.all([load('joey2'), load('hugsy2'), load('props')]);
  prep(joey, FG); prep(hugsy, FG); prep(props, BG);
  scene.add(joey, hugsy, props);
  const nodes = {}; for (const r of [joey, hugsy]) r.traverse((n) => { if (/^(Joey|Hugsy)_[A-Za-z]+$/.test(n.name)) nodes[n.name] = n; });

  // ---- render targets / passes
  const depthTex = new THREE.DepthTexture(o.w, o.h); depthTex.type = THREE.UnsignedIntType;
  const rtScene = new THREE.WebGLRenderTarget(o.w, o.h, { type: THREE.HalfFloatType, samples: o.aa === 'msaa' ? o.msaa : 0, depthTexture: depthTex });
  const rtA = new THREE.WebGLRenderTarget(o.w, o.h, { type: THREE.HalfFloatType });
  const rtB = new THREE.WebGLRenderTarget(o.w, o.h, { type: THREE.HalfFloatType });
  let gtao = null;
  if (o.ao === 'gtao' && !o.plate) {
    gtao = new GTAOPass(scene, camera, o.w, o.h); gtao.setGBuffer(depthTex); gtao.output = GTAOPass.OUTPUT.Default; gtao.blendIntensity = 1.0;
    gtao.updateGtaoMaterial({ radius: 0.35, distanceExponent: 1.5, thickness: 1.0, scale: 1.0, samples: 16 });
    gtao.updatePdMaterial({ lumaPhi: 10, depthPhi: 2, normalPhi: 3, radius: 6, rings: 2, samples: 12 });
  }
  const makeDof = (N, w, h, cam) => {
    const d = new ShaderPass(dofShader(N)); const u = d.uniforms;
    u.near.value = cam.near; u.far.value = cam.far; u.res.value.set(w, h); u.band.value = o.band;
    const f = C.lens, A = f / C.fstop, fd = cam.position.distanceTo(focusPt);
    u.focus.value = fd; u.cocK.value = 0.5 * A * f / (fd * 1000 - f) / C.sensor_width * w * o.dofBoost;
    u.maxCoc.value = Math.max(4, w / 45);
    return d;
  };
  let dof = null;
  if (o.dof && !o.plate) { dof = makeDof(o.dofN, o.w, o.h, camera); dof.uniforms.tDepth.value = depthTex; }
  const smaa = o.aa === 'smaa' ? new SMAAPass(o.w, o.h) : null;
  const out = new OutputPass();
  const rtOut = new THREE.WebGLRenderTarget(o.w, o.h, { type: THREE.UnsignedByteType });

  const anim = createAnim({ nodes, camera, camPos, camTgt, focusPt, seed: o.seed, timeline: o.timeline });

  S = { charRoots: [joey, hugsy], o, sc, renderer, scene, camera, camPos, camTgt, focusPt, nodes, rtScene, rtA, rtB, gtao, dof, smaa, out, rtOut,
    shadowLights, anim, makeDof, depthTex, plate: null, lastHash: null };
  if (o.plate) { buildPlate(); scene.background = null; }
  return { vfov, plateMs: S.plate?.ms, charRect: S.plate?.rect, charFrac: S.plate?.frac, plate: !!o.plate, morphs: Object.fromEntries(Object.entries(nodes).filter(([, n]) => n.morphTargetDictionary).map(([k, n]) => [k, Object.keys(n.morphTargetDictionary)])) };
}

function setLayers(cameraMask, shadowMask) {
  S.camera.layers.mask = cameraMask;
  for (const l of S.shadowLights) l.shadow.camera.layers.mask = shadowMask;
}

// ---------------------------------------------------------------- plate
function buildPlate(t0 = 0) {
  const { o, renderer: r, scene, camera } = S;
  const t = performance.now();
  S.anim.apply(t0, { restCamera: true });   // shot camera (no drift / push-in), characters at their t0 pose for the shadows
  const pw = Math.round(o.w * o.overscan), ph = Math.round(o.h * o.overscan);
  const pcam = camera.clone();
  pcam.fov = 2 * Math.atan(Math.tan(camera.fov * Math.PI / 360) * o.overscan) * 180 / Math.PI; pcam.updateProjectionMatrix();
  pcam.layers.mask = 1 << BG;
  const depth = new THREE.DepthTexture(pw, ph); depth.type = THREE.UnsignedIntType;
  const rtP = new THREE.WebGLRenderTarget(pw, ph, { type: THREE.HalfFloatType, samples: 4, depthTexture: depth });
  const rtD = new THREE.WebGLRenderTarget(pw, ph, { type: THREE.HalfFloatType });
  for (const l of S.shadowLights) l.shadow.camera.layers.mask = (1 << BG) | (1 << FG);   // characters' shadows land on the plate
  r.setRenderTarget(rtP); r.render(scene, pcam);
  const d = S.makeDof(o.plateDofN, pw, ph, pcam); d.uniforms.tDepth.value = depth;
  d.render(r, rtD, rtP);
  rtP.dispose();
  // plane through the focus point, facing the plate camera
  const n = new THREE.Vector3(); pcam.getWorldDirection(n);
  const plateVP = new THREE.Matrix4().multiplyMatrices(pcam.projectionMatrix, pcam.matrixWorldInverse);
  const mat = new THREE.ShaderMaterial({ ...PlateShader, uniforms: THREE.UniformsUtils.clone(PlateShader.uniforms), depthTest: false, depthWrite: false });
  mat.uniforms.tPlate.value = rtD.texture; mat.uniforms.plateVP.value.copy(plateVP);
  mat.uniforms.pN.value.copy(n); mat.uniforms.pD.value = -n.dot(S.focusPt);
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute([-1, -1, 0, 3, -1, 0, -1, 3, 0], 3));
  const quad = new THREE.Mesh(g, mat); quad.frustumCulled = false; quad.layers.enableAll();
  const qs = new THREE.Scene(); qs.add(quad);
  // characters' screen rect over the whole shot (sampled poses + push-in), + margin; fixed for the shot
  const box = new THREE.Box3(), v = new THREE.Vector3(); let x0 = 1, y0 = 1, x1 = -1, y1 = -1;
  for (let tt = 0; tt <= S.anim.duration + 1e-6; tt += 0.25) {
    S.anim.apply(tt);
    for (const root of S.charRoots) {
      box.setFromObject(root);
      for (let k = 0; k < 8; k++) {
        v.set(k & 1 ? box.max.x : box.min.x, k & 2 ? box.max.y : box.min.y, k & 4 ? box.max.z : box.min.z).project(camera);
        x0 = Math.min(x0, v.x); x1 = Math.max(x1, v.x); y0 = Math.min(y0, v.y); y1 = Math.max(y1, v.y);
      }
    }
  }
  const m = 0.04 * o.w, px = (u, n) => (u * 0.5 + 0.5) * n;
  const rx0 = Math.max(0, Math.floor((px(x0, o.w) - m) / 8) * 8), rx1 = Math.min(o.w, Math.ceil((px(x1, o.w) + m) / 8) * 8);
  const ry0 = Math.max(0, Math.floor((px(y0, o.h) - m) / 8) * 8), ry1 = Math.min(o.h, Math.ceil((px(y1, o.h) + m) / 8) * 8);
  const rect = { x: rx0, y: ry0, w: rx1 - rx0, h: ry1 - ry0 };                       // bottom-left origin, px
  const rtChar = new THREE.WebGLRenderTarget(rect.w, rect.h, { type: THREE.HalfFloatType, samples: o.aa === 'msaa' ? o.msaa : 0 });
  const comp = new THREE.ShaderMaterial({ ...CompositeShader, uniforms: THREE.UniformsUtils.clone(CompositeShader.uniforms), depthTest: false, depthWrite: false });
  const cu = comp.uniforms;
  cu.tPlate.value = rtD.texture; cu.tChar.value = rtChar.texture; cu.plateVP.value.copy(plateVP); cu.pN.value.copy(n); cu.pD.value = -n.dot(S.focusPt);
  cu.rect.value.set(rect.x, rect.y, rect.w, rect.h); cu.toneMappingExposure.value = o.exposure;
  const cq = new THREE.Mesh(g, comp); cq.frustumCulled = false; cq.layers.enableAll(); const cs = new THREE.Scene(); cs.add(cq);
  S.plate = { rt: rtD, mat, qs, comp, cs, rtChar, rect, frac: rect.w * rect.h / (o.w * o.h), ms: performance.now() - t };
}

// ---------------------------------------------------------------- frame
async function renderAt(t) {
  const { renderer: r, scene, camera, rtScene, rtA, rtB, gtao, dof, smaa, out, rtOut, o } = S;
  const st = S.anim.apply(t);
  const hash = st.hash;
  if (o.dedupe && hash === S.lastHash) return { skipped: true, hash };
  S.lastHash = hash;
  if (S.plate && o.layered !== false) {
    // characters only, inside their rect (setViewOffset), transparent background, then one composite pass
    camera.updateMatrixWorld();
    const P = S.plate, cu = P.comp.uniforms, R = P.rect;
    cu.invVP.value.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse).invert();
    camera.setViewOffset(o.w, o.h, R.x, o.h - R.y - R.h, R.w, R.h);
    setLayers(1 << FG, 1 << FG);
    r.setRenderTarget(P.rtChar); r.setClearColor(0x000000, 0); r.clear();
    r.render(scene, camera);
    camera.clearViewOffset();
    r.setRenderTarget(rtOut); r.render(P.cs, camera);
    return { skipped: false, hash };
  }
  r.setRenderTarget(rtScene);
  if (S.plate) {
    camera.updateMatrixWorld();
    const m = S.plate.mat.uniforms;
    m.invVP.value.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse).invert();
    r.autoClear = false; r.clear();
    r.render(S.plate.qs, camera);
    setLayers(1 << FG, 1 << FG);
    r.render(scene, camera);
    r.autoClear = true;
  } else {
    setLayers((1 << BG) | (1 << FG), (1 << BG) | (1 << FG));
    if (dof) dof.uniforms.focus.value = camera.position.distanceTo(S.focusPt);
    r.render(scene, camera);
  }
  let src = rtScene;
  if (gtao) { gtao.render(r, rtA, src); src = rtA; }
  if (dof) { const dst = src === rtA ? rtB : rtA; dof.render(r, dst, src); src = dst; }
  if (smaa) {   // SMAA expects display-referred input: tone-map first, then AA into the output target
    const dst = src === rtA ? rtB : rtA; out.renderToScreen = false; out.render(r, dst, src);
    smaa.renderToScreen = false; smaa.render(r, rtOut, dst);
  } else { out.renderToScreen = false; out.render(r, rtOut, src); }
  return { skipped: false, hash };
}

// RGBA8 rows bottom-up (ffmpeg flips)
function grab() {
  const { renderer: r, rtOut, o } = S;
  const px = new Uint8Array(o.w * o.h * 4);
  r.readRenderTargetPixels(rtOut, 0, 0, o.w, o.h, px);
  return px;
}

// PNG of the last frame (debug / stills)
function toPNG() {
  const { renderer: r, rtOut, o } = S;
  const px = grab(); const c = document.createElement('canvas'); c.width = o.w; c.height = o.h;
  const g = c.getContext('2d'); const img = g.createImageData(o.w, o.h);
  for (let y = 0; y < o.h; y++) img.data.set(px.subarray((o.h - 1 - y) * o.w * 4, (o.h - y) * o.w * 4), y * o.w * 4);
  g.putImageData(img, 0, 0); return c.toDataURL('image/png').split(',')[1];
}

// render + post the raw frame to the driver's HTTP endpoint (binary, no base64)
async function renderAndPost(t, idx) {
  const res = await renderAt(t);
  const t1 = performance.now();
  if (!res.skipped) await fetch('/frame/' + idx, { method: 'POST', body: grab() });
  else await fetch('/dup/' + idx, { method: 'POST' });
  return { ...res, postMs: performance.now() - t1 };
}

// pipelined: render + read back frame i, start its upload, and only wait for the previous upload (1 in flight)
let inflight = null;
async function renderSend(t, idx) {
  const a = performance.now(); await renderAt(t); const px = grab(); const b = performance.now();
  if (inflight) await inflight;
  inflight = fetch('/frame/' + idx, { method: 'POST', body: px });
  return { r: b - a, c: performance.now() - b };
}
window.flushSend = async () => { if (inflight) await inflight; inflight = null; };
window.renderSend = renderSend;
window.setup = setup; window.renderAt = renderAt; window.grab = grab; window.toPNG = toPNG; window.renderAndPost = renderAndPost;
window.hashFrames = (n, fps) => Array.from({ length: n }, (_, i) => S.anim.apply(i / fps).hash);
window.__ready = true;
