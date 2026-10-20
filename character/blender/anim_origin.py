"""Animated 'Joey asks Claude to create the ball' clip.
Usage: blender -b --factory-startup -P anim_origin.py -- --timing T.json --out DIR [--frames a-b|a,b,c]
        [--w 720 --h 1280 --samples 16] [--save file.blend]
Reuses the duo scene setup from preview.py (exec'd up to its render calls) + build_joey/build_ball.
"""
import sys, os, math, json, time, random
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def A(n, d):
    return argv[argv.index(n) + 1] if n in argv else d

# ---- reuse preview.py scene setup without triggering its renders ----
_src = open(os.path.join(HERE, 'preview_duo_base.py')).read().split("if ONLY in ('all', 'joey')")[0]
NS = {'__file__': os.path.join(HERE, 'preview_duo_base.py'), '__name__': 'preview_setup'}
sys.argv = [sys.argv[0], '--'] + ['--out', '/tmp/_unused_preview', '--samples', A('--samples', '16')]
exec(compile(_src, 'preview.py', 'exec'), NS)
sys.argv = ['blender', '--'] + argv

T = json.load(open(A('--timing', '')))
FPS = T['fps']; NF = T['nframes']
ev = T['events']
OUT = A('--out', os.path.join(HERE, '..', '..', 'output', 'clips', 'origin_frames'))
os.makedirs(OUT, exist_ok=True)
W, H = int(A('--w', 720)), int(A('--h', 1280))

def ramp(t, a, b):
    if t <= a: return 0.0
    if t >= b: return 1.0
    u = (t - a) / (b - a)
    return u * u * (3 - 2 * u)

def env_at(arr, t):
    f = t * FPS
    i = int(math.floor(f)); fr = f - i
    i0 = min(max(i, 0), len(arr) - 1); i1 = min(max(i + 1, 0), len(arr) - 1)
    return arr[i0] * (1 - fr) + arr[i1] * fr

J_ENV, B_ENV = T['joey_env'], T['ball_env']

# ---- build scene ----
joey, ball = NS['build_scene'](True, True)
CAM_TGT = (0.50, 0, 1.95); CAM_LOC = Vector((0.2, -6.5, 1.35))
NS['setup_lights'](CAM_TGT)
cam = NS['setup_camera'](CAM_LOC, CAM_TGT, 65, bpy.data.objects['Joey_Head'], 2.4, 'HORIZONTAL')
cam.data.dof.focus_object = None
scn = bpy.context.scene
scn.render.fps = FPS
scn.frame_start = 0; scn.frame_end = NF - 1
NS['SCALE'] = 100
NS['setup_render'](W, H, os.path.join(OUT, 'f'))
scn.cycles.use_adaptive_sampling = True
scn.cycles.adaptive_threshold = 0.02
scn.cycles.use_denoising = True

O = bpy.data.objects
head, jaw, body = O['Joey_Head'], O['Joey_Jaw'], O['Joey_Body']
earL, earR, eyeL, eyeR = O['Joey_EarL'], O['Joey_EarR'], O['Joey_EyeL'], O['Joey_EyeR']
bball, bEL, bER = O['Ball_Body'], O['Ball_EyeL'], O['Ball_EyeR']
head0 = head.location.copy(); ball0 = bball.location.copy(); ball_rot0 = tuple(bball.rotation_euler)
jeye_s0 = eyeL.scale.copy(); beye_s0 = bEL.scale.copy()
BALL_C = 0.48  # centre height at rest

# ---- key times ----
j1s, j1e = ev['j1']; bs, be = ev['ball']; j4s, j4e = ev['j4']
tdrop, tland = ev['drop_start'], ev['land']
tend = T['duration']

# ---- ball bounce profile ----
G = 40.0
def ball_state(t):
    """-> (h, sz, sxy): bottom height above rest, vertical scale, horizontal scale."""
    if t < tdrop:
        return 6.6, 1.0, 1.0
    if t < tland:
        Tf = tland - tdrop; H0 = 0.5 * G * Tf * Tf
        s = t - tdrop; h = H0 - 0.5 * G * s * s
        sz = 1.0 + 0.14 * (s / Tf)
        return h, sz, sz ** -0.5
    # timeline of contact (squash) / flight arcs after landing
    tt = tland; segs = []
    for kind, p1, p2 in (('c', 0.15, 0.40), ('a', 0.95, 0), ('c', 0.11, 0.22), ('a', 0.27, 0),
                         ('c', 0.09, 0.09), ('a', 0.055, 0), ('c', 0.07, 0.04)):
        if kind == 'c':
            segs.append((kind, tt, p1, p2)); tt += p1
        else:
            Tf = 2 * math.sqrt(2 * p1 / G); segs.append((kind, tt, Tf, p1)); tt += Tf
    for kind, t0, d, p in segs:
        if t0 <= t < t0 + d:
            u = (t - t0) / d
            if kind == 'c':
                sz = 1.0 - p * math.sin(math.pi * u)
                if t0 == tland:  # first impact: quick squash then rebound stretch
                    sz = 1.0 - p * math.sin(math.pi * min(1, u * 1.0))
                return 0.0, sz, sz ** -0.5
            s = t - t0 - d / 2
            h = p - 0.5 * G * s * s
            vel = abs(G * s) / (G * d / 2)
            sz = 1.0 + 0.10 * vel * min(1.0, p / 0.3 + 0.3)
            return max(h, 0), sz, sz ** -0.5
    ts = tt; s = t - ts
    sz = 1.0 + 0.045 * math.exp(-s * 6) * math.cos(2 * math.pi * 3.2 * s)
    return 0.0, sz, sz ** -0.5

# ---- joey blink schedule ----
rnd = random.Random(11)
blinks = []; tb = 0.9
while tb < tend - 0.3:
    tb += rnd.uniform(2.5, 3.5); blinks.append(tb)
mid_blink = bs + 0.9
blinks = [b for b in blinks if abs(b - mid_blink) > 0.9 and not (j4s - 0.3 < b < j4e)] + [mid_blink]
def blink_amt(t, times, dur=5.0 / 24):
    for b in times:
        if b <= t < b + dur:
            u = (t - b) / dur
            return math.sin(math.pi * u) ** 1.5
    return 0.0

# ---- head motion functions ----
def head_pose(t):
    je = env_at(J_ENV, t)
    look = ramp(t, tdrop - 0.05, tland)
    up = ramp(t, tdrop - 0.25, tdrop + 0.05); down = ramp(t, tdrop + 0.12, tland + 0.05)
    lean = ramp(t, j4s - 0.15, j4s + 0.5)
    tilt = ramp(t, bs + 0.3, bs + 0.9) * (1 - ramp(t, be - 0.1, be + 0.3))
    nod = math.exp(-(max(t - tland, 0)) * 7) * math.sin(max(t - tland, 0) * 22) * (t > tland) * 0.07
    yaw = 0.30 * look + 0.04 * lean
    pitch = -0.10 * up + 0.24 * down + 0.07 * lean + 0.035 * je + nod
    roll = 0.15 * tilt - 0.07 * lean + 0.012 * math.sin(t * 1.7)
    pos = Vector((0.11 * lean, -0.13 * lean, 0.018 * je + 0.006 * math.sin(t * 2.0)))
    return yaw, pitch, roll, pos

# ear spring simulation (per-frame, substepped)
ear = {'L': [0.0, 0.0, 0.0, 0.0], 'R': [0.0, 0.0, 0.0, 0.0]}  # ay, vy, ax, vx
ear_out = []
prev = [head_pose(-2 / FPS), head_pose(-1 / FPS)]
K, C = 70.0, 6.0
for f in range(NF):
    t = f / FPS
    cur = head_pose(t)
    dt = 1.0 / FPS
    acc = [(cur[i] - 2 * prev[1][i] + prev[0][i]) / dt ** 2 for i in range(3)]
    accz = (cur[3].z - 2 * prev[1][3].z + prev[0][3].z) / dt ** 2
    accx = (cur[3].x - 2 * prev[1][3].x + prev[0][3].x) / dt ** 2
    row = {}
    imp = 0.0
    if abs(t - tland) < 0.5 * dt:
        imp = 3.4
    for side, sgn in (('L', 1), ('R', -1)):
        ay, vy, ax, vx = ear[side]
        n = 6; h = dt / n
        for k in range(n):
            drive_y = -(0.10 * (acc[0] + acc[2] * sgn * -1)) - 1.6 * accx
            drive_x = 0.06 * acc[1] + 0.8 * accz
            vy += (-K * ay - C * vy + drive_y) * h
            vx += (-K * ax - C * vx + drive_x) * h
            ay += vy * h; ax += vx * h
        if imp:
            vy += imp * sgn * 1.0; vx += 1.5
        row[side] = (ay, ax)
        ear[side] = [ay, vy, ax, vx]
    ear_out.append(row)
    prev = [prev[1], cur]

# ---- sparkles ----
SPK = []
def mk_sparkle(i):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=4, ring_count=3, location=(0, 0, -20))
    o = bpy.context.object; o.name = 'Spark%d' % i
    m = bpy.data.materials.new('Sp%d' % i); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (1.0, 0.9, 0.5, 1) if i % 3 else (0.7, 0.95, 1.0, 1)
    em.inputs['Strength'].default_value = 14
    out = nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(em.outputs[0], out.inputs[0])
    o.data.materials.append(m); o.visible_shadow = False
    return o
sprnd = random.Random(7)
for i in range(14):
    o = mk_sparkle(i)
    ang = sprnd.uniform(0, 2 * math.pi); rad = sprnd.uniform(0.35, 0.9)
    SPK.append((o, ang, rad, sprnd.uniform(0.35, 1.25), sprnd.uniform(0.06, 0.13), sprnd.uniform(0, 0.12)))

# ---- camera ----
cdir = (Vector(CAM_TGT) - CAM_LOC).normalized()
JF = Vector((0.0, -0.5, 1.93)); BF = Vector((1.18, -1.25, 0.6))

# ---- write keyframes ----
def key(ob, path, idx, val, f):
    ob.keyframe_insert(path, index=idx, frame=f)

def setv(ob, attr, val, f):
    setattr(ob, attr, val)
    ob.keyframe_insert(attr, frame=f)

for f in range(NF):
    t = f / FPS
    scn.frame_set(f)
    # --- Joey
    je = env_at(J_ENV, t)
    yaw, pitch, roll, pos = head_pose(t)
    head.rotation_euler = (pitch, roll, yaw)
    head.location = head0 + pos
    head.keyframe_insert('rotation_euler', frame=f); head.keyframe_insert('location', frame=f)
    ang = math.radians(18.0) * min(1.0, je) ** 0.85
    # tongue-out smirk: hold jaw slightly open after "no promises" and at end
    if t > j4e:
        ang = max(ang, math.radians(11.0) * ramp(t, j4e, j4e + 0.2))
    jaw.rotation_euler = (ang, 0, 0); jaw.keyframe_insert('rotation_euler', frame=f)
    e = ear_out[f]
    earL.rotation_euler = (e['L'][1], 0, 0); earR.rotation_euler = (e['R'][1], 0, 0)
    earL.rotation_euler = (e['L'][1], e['L'][0], 0); earR.rotation_euler = (e['R'][1], e['R'][0], 0)
    earL.keyframe_insert('rotation_euler', frame=f); earR.keyframe_insert('rotation_euler', frame=f)
    bl = blink_amt(t, blinks)
    for eo in (eyeL, eyeR):
        eo.scale = (jeye_s0.x, jeye_s0.y, jeye_s0.z * (1 - 0.9 * bl)); eo.keyframe_insert('scale', frame=f)
    body.scale = (1, 1, 1 + 0.01 * math.sin(2 * math.pi * t / 3.3)); body.keyframe_insert('scale', frame=f)
    # --- Ball
    be_env = env_at(B_ENV, t)
    h, sz, sxy = ball_state(t)
    talk = be_env if bs - 0.05 < t < be + 0.1 else 0.0
    sz2 = sz * (1 + 0.035 * talk); sxy2 = sxy * (1 - 0.015 * talk)
    bball.scale = (sxy2, sxy2, sz2)
    bball.location = (ball0.x, ball0.y, BALL_C * sz2 + h + 0.03 * talk)
    turn = ramp(t, bs - 0.15, bs + 0.45)
    bball.rotation_euler = (ball_rot0[0] - 0.05 * talk + 0.02 * math.sin(t * 1.3) * (t > tland + 0.8),
                            0.04 * talk * math.sin(t * 14),
                            ball_rot0[2] - 0.22 * turn)
    for k in ('location', 'rotation_euler', 'scale'):
        bball.keyframe_insert(k, frame=f)
    bball.hide_render = t < tdrop - 1.5 / FPS
    bball.keyframe_insert('hide_render', frame=f)
    tm = (bs + be) / 2
    slow = 0.0
    if tm - 0.28 < t < tm + 0.28:
        slow = math.sin(math.pi * (t - (tm - 0.28)) / 0.56) ** 1.4
    sq = 0.65 * ramp(t, be + 0.1, be + 0.5)
    zs = beye_s0.z * (1 - 0.9 * slow) * (1 - sq)
    for eo in (bEL, bER):
        eo.scale = (beye_s0.x, beye_s0.y, zs); eo.keyframe_insert('scale', frame=f)
    # --- sparkles
    for o, a, rad, hh, sz0, dly in SPK:
        life = 0.65; u = (t - tland - dly) / life
        if 0 <= u <= 1:
            r = rad * (0.5 + 0.8 * ramp(u, 0, 1))
            o.location = (ball0.x + math.cos(a) * r, ball0.y + math.sin(a) * r * 0.6 - 0.2, 0.2 + hh * (0.5 + 0.6 * u))
            s = sz0 * math.sin(math.pi * u) ** 0.8
            o.scale = (s, s, s * 1.5); o.rotation_euler = (0, 0, a + u * 3)
        else:
            o.scale = (0, 0, 0); o.location = (0, 0, -20)
        for k in ('location', 'rotation_euler', 'scale'):
            o.keyframe_insert(k, frame=f)
    # --- camera
    push = 0.42 * ramp(t, 0, tend)
    cam.location = CAM_LOC + cdir * push
    cam.keyframe_insert('location', frame=f)
    dJ = (cam.location - JF).length; dB = (cam.location - BF).length
    mix = ramp(t, bs - 0.3, bs + 0.1) * (1 - ramp(t, j4s - 0.4, j4s + 0.05))
    cam.data.dof.focus_distance = dJ * (1 - mix) + dB * mix
    cam.data.dof.keyframe_insert('focus_distance', frame=f)

# Bezier easing everywhere
for act in bpy.data.actions:
    for fc in act.fcurves:
        for kp in fc.keyframe_points:
            if fc.data_path == 'hide_render':
                kp.interpolation = 'CONSTANT'
            else:
                kp.interpolation = 'BEZIER'; kp.handle_left_type = kp.handle_right_type = 'AUTO_CLAMPED'

if A('--save', ''):
    bpy.ops.wm.save_as_mainfile(filepath=A('--save', ''))

fr = A('--frames', '0-%d' % (NF - 1))
if '-' in fr and ',' not in fr:
    a, b = fr.split('-'); frames = list(range(int(a), int(b) + 1))
else:
    frames = [int(x) for x in fr.split(',')]
tot = 0.0; n = 0
for f in frames:
    path = os.path.join(OUT, 'f_%04d.png' % f)
    if os.path.exists(path) and '--force' not in argv:
        continue
    scn.frame_set(f); scn.render.filepath = path
    t0 = time.time(); bpy.ops.render.render(write_still=True); dt = time.time() - t0
    tot += dt; n += 1
    print('FRAME %d %.1fs (avg %.1f)' % (f, dt, tot / n), flush=True)
print('DONE', n, 'frames', '%.1fs' % tot, flush=True)
