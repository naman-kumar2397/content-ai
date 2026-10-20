"""v2 export for the three.js renderer: Joey + Hugsy duo with
  - baked AO + indirect (GI bounce) per corner -> second colour attribute 'GI' (rgb = indirect irradiance, a = AO)
  - shape keys (glTF morph targets): Joey visemes / brows / cheeks, Hugsy beak / brows / body squash
  - low-poly set dressing (laptop, mug, plant, window frame, whiteboard) in the same faceted style
Usage: blender -b --factory-startup -P export_gltf_v2.py -- [--out ../gltf] [--samples 64] [--no-bake]
Writes joey2.glb, hugsy2.glb, props.glb, whiteboard.glb and scene2.json (camera, lights, window, materials).
v1 (export_gltf.py) is untouched so the round-1 baseline stays reproducible.
"""
import sys, os, json, math, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy, bmesh
from mathutils import Vector, Matrix, Euler

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
arg = lambda n, d: argv[argv.index(n) + 1] if n in argv else d
OUT = os.path.abspath(arg('--out', os.path.join(HERE, '..', 'gltf')))
SAMPLES = int(arg('--samples', 64))
BAKE = '--no-bake' not in argv
os.makedirs(OUT, exist_ok=True)

_src = open(os.path.join(HERE, 'preview_duo_base.py')).read().split("if ONLY in ('all', 'joey')")[0]
NS = {'__file__': os.path.join(HERE, 'preview_duo_base.py'), '__name__': 'preview_setup'}
sys.argv = [sys.argv[0], '--', '--out', '/tmp/_unused_preview']
exec(compile(_src, 'preview.py', 'exec'), NS)
from common import *
import build_joey, build_hugsy
V1 = {'__file__': os.path.join(HERE, 'export_gltf.py'), '__name__': 'v1'}
exec(compile(open(os.path.join(HERE, 'export_gltf.py')).read().split('\ndef main')[0], 'export_gltf.py', 'exec'), V1)

HUGSY_POS, HUGSY_ROT = (1.06, -1.05, 0.0), (-0.2, 0.0, -0.85)
CAM = dict(location=(0.2, -6.5, 1.35), target=(0.45, 0, 1.95))
WINDOW = dict(x0=-0.9, x1=2.5, z0=2.55, z1=6.2, y=7.0)    # opening in the back wall (Blender coords)
y_up = V1['y_up']


# ---------------------------------------------------------------- shape keys
def shape_key(ob, name, fn):
    """Add shape key 'name'; fn(world_co) -> new world_co (world space so separate meshes deform coherently)."""
    if ob.data.shape_keys is None:
        ob.shape_key_add(name='Basis', from_mix=False)
    k = ob.shape_key_add(name=name, from_mix=False)
    mw = ob.matrix_world; inv = mw.inverted()
    for i, v in enumerate(ob.data.vertices):
        k.data[i].co = inv @ fn(mw @ v.co)
    return k


def falloff(d, r):
    return max(0.0, 1.0 - d / r) ** 2 * (3 - 2 * max(0.0, 1.0 - d / r)) if d < r else 0.0


def joey_shapes():
    O = bpy.data.objects
    mouth_c = Vector((0, -0.55, 1.40))
    def near_mouth(p, r=0.55):
        return falloff((p - mouth_c).length, r)
    # Wide (E / C): corners pull outward + up; Narrow (O/U): corners in, lips forward
    def wide(p):
        w = near_mouth(p); return p + Vector((0.16 * p.x / 0.4 * w, 0, 0.05 * abs(p.x) / 0.4 * w))
    def narrow(p):
        w = near_mouth(p); return p + Vector((-0.20 * p.x / 0.4 * w, -0.08 * w, 0))
    # Smile: cheek lobes squash up + out (eyes squint a touch via the head key too)
    def smile(p):
        w = 0.0
        for sx in (-1, 1):
            w = max(w, falloff((p - Vector((sx * 0.33, -0.45, 1.62))).length, 0.32))
        return p + Vector((0.03 * (1 if p.x > 0 else -1) * w, -0.01 * w, 0.06 * w))
    # Close: upper lip drops over the carved mouth opening (front verts only) so closed visemes really close
    def close(p):
        if p.y > -0.3: return p
        w = falloff((Vector((p.x * 0.8, 0, p.z)) - Vector((0, 0, 1.50))).length, 0.36)
        return p + Vector((0, 0.02 * w, -0.17 * w))
    for n in ('Joey_Muzzle', 'Joey_Head', 'Joey_Mouth'):
        ob = O[n]
        shape_key(ob, 'Wide', wide); shape_key(ob, 'Narrow', narrow); shape_key(ob, 'Smile', smile)
        shape_key(ob, 'Close', close)
    jaw = O['Joey_Jaw']
    shape_key(jaw, 'Wide', wide); shape_key(jaw, 'Narrow', narrow)
    # FV: lower lip tucks up and back under the upper teeth
    shape_key(jaw, 'FV', lambda p: p + Vector((0, 0.05, 0.05)) * falloff(abs(p.y + 0.62), 0.25))
    tg = O['Joey_Tongue']
    # Tongue: In = retract into the mouth (closed visemes); Up = tip raised (L / H)
    piv = Vector((0, -0.30, 1.30))
    shape_key(tg, 'In', lambda p: piv + (p - piv) * 0.55 + Vector((0, 0.04, 0.03)))
    def tup(p):
        d = max(0.0, -(p.y + 0.45)) / 0.4
        return p + Vector((0, 0.10 * d, 0.18 * d))
    shape_key(tg, 'Up', tup)


def joey_brows(mats):
    """Low-poly brow tufts (one mesh, both sides) with Up / Down / Worried / Angry keys."""
    parts = []
    for sx in (-1, 1):
        parts += [((sx * 0.29, -0.585, 2.03), (0.10, 0.04, 0.028), (0, sx * 0.12, 0)),
                  ((sx * 0.21, -0.60, 2.02), (0.055, 0.035, 0.026))]
    b = build_mesh_obj('Joey_Brows', parts, seg=12, rings=8)
    facet(b, voxel=0.018, tris=160, lump=0.01, seed=21)
    assign(b, mats)
    set_pivot(b, (0, -0.59, 2.025))
    inner = lambda p: max(0.0, 1.0 - abs(p.x) / 0.45)            # 1 at the inner ends, 0 outside
    shape_key(b, 'Up', lambda p: p + Vector((0, 0.01, 0.07)))
    shape_key(b, 'Down', lambda p: p + Vector((0, -0.01, -0.045)))
    shape_key(b, 'Worried', lambda p: p + Vector((0, 0, 0.09 * inner(p) - 0.02)))
    shape_key(b, 'Angry', lambda p: p + Vector((0, -0.01, -0.07 * inner(p))))
    return b


def hugsy_shapes():
    O = bpy.data.objects
    # Beak open: lower beak rotates 28 deg about the hinge, upper lifts 8 deg (as morphs, so the hinge can't gap)
    hinge = Vector(build_hugsy.BEAK_HINGE)
    hp = Vector(HUGSY_POS); R = Euler(HUGSY_ROT).to_matrix(); Ri = R.inverted()
    def rot_about(p, deg):
        lp = Ri @ (p - hp)                       # into Hugsy's local frame (keys are built in world space)
        q = Matrix.Rotation(math.radians(deg), 3, 'X') @ (lp - hinge) + hinge
        return R @ q + hp
    shape_key(O['Hugsy_BeakLower'], 'Open', lambda p: rot_about(p, -28))
    shape_key(O['Hugsy_Beak'], 'Open', lambda p: rot_about(p, 8))
    # Squash: plush sags (lower half bulges out, top drops); Stretch: the opposite. Body/belly/face share the
    # same world-space field, so the separate meshes stay glued together.
    def field(p, s):
        lp = Ri @ (p - hp)
        h = max(0.0, min(1.0, lp.z / 1.25))
        bulge = math.sin(math.pi * min(1.0, h * 1.6)) * s
        lp2 = Vector((lp.x * (1 + 0.16 * bulge), lp.y * (1 + 0.16 * bulge), lp.z * (1 - 0.10 * s)))
        return R @ lp2 + hp
    for n in ('Hugsy_Body', 'Hugsy_Belly', 'Hugsy_Face'):
        shape_key(O[n], 'Squash', lambda p: field(p, 1.0))
        shape_key(O[n], 'Stretch', lambda p: field(p, -1.0))
    # Brows (felt strips): inner end down = flat/sarcastic squint, inner up = surprised
    for side, sx in (('L', -1), ('R', 1)):
        b = O['Hugsy_Brow' + side]
        c = b.matrix_world.translation.copy()
        def tilt(p, a, c=c, sx=sx):
            lp = Ri @ (p - c); lp.z += a * (-sx) * lp.x / 0.075 * 0.035; return R @ lp + c
        shape_key(b, 'InnerDown', lambda p, t=tilt: t(p, -1))
        shape_key(b, 'InnerUp', lambda p, t=tilt: t(p, 1))
        shape_key(b, 'Raise', lambda p, c=c: p + R @ Vector((0, 0, 0.035)))


# ---------------------------------------------------------------- props
def cyl(name, r, h, seg=10, r_top=None, loc=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r if r_top is None else r_top, depth=h,
                          matrix=Matrix.Translation(Vector(loc) + Vector((0, 0, h / 2))))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
    return ob


def join(objs, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join(); objs[0].name = name; objs[0].data.name = name
    return objs[0]


def place(ob, loc, rz=0.0):
    ob.location = loc; ob.rotation_euler = (0, 0, rz)


def build_props():
    M = dict(
        alu=make_mat('P_Alu', '#8D96A6', 0.45, tint=1, spec=0.5),
        key=make_mat('P_Keys', '#262B35', 0.7, tint=1),
        screen=make_mat('P_Screen', '#1B2A4A', 0.25, spec=0.6),
        mug=make_mat('P_Mug', '#D9573B', 0.45, tint=1, spec=0.4),
        coffee=make_mat('P_Coffee', '#3A1E10', 0.15, spec=0.6),
        pot=make_mat('P_Pot', '#B8643C', 0.85, tint=1),
        soil=make_mat('P_Soil', '#2B1C14', 0.95, tint=1),
        leaf=make_mat('P_Leaf', '#4F9A4A', 0.6, tint=1, sheen=0.2),
        frame=make_mat('P_Frame', '#2C3A55', 0.7, tint=1),
        sill=make_mat('P_Sill', '#3A4A6A', 0.6, tint=1),
        board=make_mat('P_Board', '#F2F2EE', 0.35, tint=1, spec=0.4),
        bframe=make_mat('P_BoardFrame', '#9AA3B0', 0.5, tint=1),
    )
    props = []
    # ---- laptop (back-left on the desk, angled to camera); lid open ~105 deg, screen glows
    base = box_obj('P_LaptopBase', (0.55, 0.38, 0.022), bevel=0.012); finish(base, 31); assign(base, M['alu'])
    base.location = (0, 0, 0.022)
    kb = box_obj('P_LaptopKeys', (0.47, 0.20, 0.004), bevel=0.002); finish(kb, 32); assign(kb, M['key'])
    kb.location = (0, 0.04, 0.046)
    lid = box_obj('P_LaptopLid', (0.55, 0.018, 0.36), bevel=0.012); finish(lid, 33); assign(lid, M['alu'])
    lid.location = (0, 0.40, 0.40); lid.rotation_euler = (math.radians(-12), 0, 0)
    lap = join([base, kb, lid], 'Props_Laptop')
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    # screen: UV'd plane in front of the lid (three.js draws its glowing canvas content on it)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0.375, 0.40), rotation=(math.radians(90 - 12), 0, 0))
    scr = bpy.context.object; scr.name = 'Props_LaptopScreen'; scr.scale = (1.0, 0.62, 1)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    assign(scr, M['screen']); finish(scr, 34, amp=0.0)
    scr.location = lap.location + Vector((0, -0.003, 0))
    parent_keep(scr, lap)
    place(lap, (-1.55, 2.4, 0), math.radians(-28)); props.append(lap)
    # ---- mug (front-left, beside Joey's paw)
    body = cyl('mugb', 0.17, 0.36, seg=11); finish(body, 41); assign(body, M['mug'])
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=11, radius1=0.145, radius2=0.145, depth=0.01,
                          matrix=Matrix.Translation((0, 0, 0.31)))
    me = bpy.data.meshes.new('cof'); bm.to_mesh(me); bm.free()
    cof = bpy.data.objects.new('cof', me); bpy.context.collection.objects.link(cof); finish(cof, 42, amp=0.03)
    assign(cof, M['coffee'])
    bpy.ops.mesh.primitive_torus_add(major_radius=0.10, minor_radius=0.03, major_segments=10, minor_segments=5,
                                     location=(0.19, 0, 0.19), rotation=(math.pi / 2, 0, 0))
    hd = bpy.context.object; bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    finish(hd, 43); assign(hd, M['mug'])
    mug = join([body, cof, hd], 'Props_Mug')
    place(mug, (-1.22, 0.85, 0), math.radians(200)); props.append(mug)
    # ---- plant (back-right; leaves rise above Hugsy)
    pot = cyl('pot', 0.24, 0.55, seg=9, r_top=0.30); finish(pot, 51); assign(pot, M['pot'])
    soil = cyl('soil', 0.27, 0.02, seg=9, loc=(0, 0, 0.51)); finish(soil, 52); assign(soil, M['soil'])
    leaves = []
    import random
    rnd = random.Random(7)
    for i in range(9):
        a = i * 2.39996 + rnd.uniform(-0.2, 0.2); tilt = rnd.uniform(0.25, 0.75); L = rnd.uniform(0.7, 1.15)
        d = Vector((math.cos(a) * math.sin(tilt), math.sin(a) * math.sin(tilt), math.cos(tilt)))
        c = Vector((0, 0, 0.55)) + d * (L * 0.55)
        lf = build_mesh_obj('leaf%d' % i, [(c, (0.12, 0.035, L * 0.5))], seg=8, rings=6)
        lf.data.transform(Matrix.Translation(-c))
        lf.rotation_euler = d.to_track_quat('Z', 'Y').to_euler(); lf.location = c
        bpy.context.view_layer.objects.active = lf; lf.select_set(True)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        finish(lf, 60 + i, amp=0.18); assign(lf, M['leaf']); leaves.append(lf)
    plant = join([pot, soil] + leaves, 'Props_Plant')
    place(plant, (2.25, 3.0, 0), 0.3); props.append(plant)
    # ---- window frame on the back wall (the wall itself, with its hole, is built in three.js)
    W = WINDOW; t = 0.09; cx = (W['x0'] + W['x1']) / 2; cz = (W['z0'] + W['z1']) / 2
    hw, hh = (W['x1'] - W['x0']) / 2, (W['z1'] - W['z0']) / 2
    bars = []
    for (lx, lz, sx, sz) in [(cx, W['z0'], hw + t, t), (cx, W['z1'], hw + t, t), (W['x0'], cz, t, hh + t),
                             (W['x1'], cz, t, hh + t), (cx, cz, 0.045, hh), (cx, cz + hh * 0.18, hw, 0.04)]:
        b = box_obj('bar', (sx, 0.08, sz), bevel=0.02); b.location = (lx, W['y'] - 0.04, lz); bars.append(b)
    for b in bars: finish(b, 70, amp=0.06); assign(b, M['frame'])
    sill = box_obj('sill', (hw + 0.25, 0.22, 0.045), bevel=0.02); sill.location = (cx, W['y'] - 0.18, W['z0'] - 0.1)
    finish(sill, 71); assign(sill, M['sill'])
    win = join(bars + [sill], 'Props_Window'); props.append(win)
    # ---- whiteboard (separate asset for future explainers; not placed in this shot)
    bd = box_obj('P_Board', (1.6, 0.03, 0.95), bevel=0.01); finish(bd, 81, amp=0.03); assign(bd, M['board'])
    fr = []
    for (lx, lz, sx, sz) in [(0, 0.98, 1.66, 0.05), (0, -0.98, 1.66, 0.05), (-1.63, 0, 0.05, 1.0), (1.63, 0, 0.05, 1.0)]:
        b = box_obj('bf', (sx, 0.05, sz), bevel=0.015); b.location = (lx, -0.02, lz); finish(b, 82); assign(b, M['bframe']); fr.append(b)
    tray = box_obj('tray', (0.7, 0.08, 0.02), bevel=0.01); tray.location = (0, -0.1, -1.0); finish(tray, 83); assign(tray, M['bframe'])
    wb = join([bd] + fr + [tray], 'Whiteboard'); bpy.context.view_layer.objects.active = wb
    wb.location = (0, 0, 0)
    return props, wb, M


# ---------------------------------------------------------------- bake
def bake(objs, samples):
    """Cycles bake to a corner colour attribute 'GI': rgb = indirect diffuse irradiance, a = AO."""
    s = bpy.context.scene
    s.render.engine = 'CYCLES'; s.cycles.device = 'CPU'; s.cycles.samples = samples
    s.cycles.diffuse_bounces = 3; s.cycles.max_bounces = 4
    s.render.bake.target = 'VERTEX_COLORS'; s.render.bake.margin = 0
    s.world.light_settings.distance = 0.5        # AO distance (scene units; Joey is ~2.4 tall)
    for o in objs:
        me = o.data
        for nm in ('GI', 'AOtmp'):
            if nm in me.attributes: me.attributes.remove(me.attributes[nm])
        me.color_attributes.new('AOtmp', 'FLOAT_COLOR', 'CORNER')
        me.color_attributes.new('GI', 'FLOAT_COLOR', 'CORNER')
    def run(attr, **kw):
        bpy.ops.object.select_all(action='DESELECT')
        for o in objs:
            o.select_set(True); o.data.color_attributes.active_color = o.data.color_attributes[attr]
        bpy.context.view_layer.objects.active = objs[0]
        t = time.time(); bpy.ops.object.bake(**kw); print(f'BAKE {attr} {kw.get("type")} {time.time() - t:.1f}s', flush=True)
    run('AOtmp', type='AO')
    run('GI', type='DIFFUSE', pass_filter={'INDIRECT'})
    for o in objs:
        me = o.data
        ao = [0.0] * (len(me.loops) * 4); gi = [0.0] * (len(me.loops) * 4)
        me.color_attributes['AOtmp'].data.foreach_get('color', ao)
        me.color_attributes['GI'].data.foreach_get('color', gi)
        for i in range(len(me.loops)):
            gi[i * 4 + 3] = ao[i * 4]                 # AO (grey) -> alpha
            for k in range(3): gi[i * 4 + k] = min(1.0, gi[i * 4 + k])
        me.color_attributes['GI'].data.foreach_set('color', gi)
        me.attributes.remove(me.attributes['AOtmp'])
        me.color_attributes.active_color = me.color_attributes['Col']


def export(objs, path):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_yup=True,
                              export_apply=False, export_materials='EXPORT', export_extras=True,
                              export_animations=False, export_all_vertex_colors=True,
                              export_morph=True, export_morph_normal=False)
    print('EXPORTED', path, os.path.getsize(path), 'bytes', flush=True)


def main():
    NS['reset'](); NS['setup_world'](); NS['setup_desk']()
    tgt = CAM['target']
    NS['setup_lights']((0.50, 0, 1.95))
    # window opening: cut the bake wall so light/AO near it matches the three.js wall
    j = build_joey.build_joey((0, 0, 0))
    jm = make_mat('J_Brow', '#B98A3C', 0.9, tint=1, sheen=0.4)
    brows = joey_brows(jm); parent_keep(brows, bpy.data.objects['Joey_Head'])
    h = build_hugsy.build_hugsy((0, 0, 0))
    h.location = HUGSY_POS; h.rotation_euler = HUGSY_ROT
    bpy.context.view_layer.update()
    props, wb, PM = build_props()

    params = {}
    for m in bpy.data.materials:
        if m.name.startswith(('J_', 'H_', 'P_')):
            params[m.name] = V1['simplify_material'](m)
    chars = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith(('Joey_', 'Hugsy_', 'Props_', 'Whiteboard'))]
    for o in chars:
        V1['bake_colors'](o, params)
    wb.hide_render = True                       # not in this shot
    if BAKE:
        bake([o for o in chars if o is not wb], SAMPLES)
    else:
        for o in chars:
            a = o.data.color_attributes.new('GI', 'FLOAT_COLOR', 'CORNER')
            a.data.foreach_set('color', [0.0, 0.0, 0.0, 1.0] * len(o.data.loops))
    if BAKE:   # whiteboard alone: AO only, no bounce
        wb.hide_render = False
        bake([wb], max(16, SAMPLES // 2))
    joey_shapes(); hugsy_shapes()

    O = bpy.data.objects
    export([o for o in O if o.name.startswith('Joey_')], os.path.join(OUT, 'joey2.glb'))
    export([o for o in O if o.name.startswith('Hugsy_')], os.path.join(OUT, 'hugsy2.glb'))
    export([o for o in O if o.name.startswith('Props_')], os.path.join(OUT, 'props.glb'))
    export([wb], os.path.join(OUT, 'whiteboard.glb'))

    sc = dict(materials=params, lights=[])
    for o in O:
        if o.type == 'LIGHT':
            d = o.data; fwd = o.matrix_world.to_3x3() @ Vector((0, 0, -1))
            sc['lights'].append(dict(name=o.name, type=d.type, energy=d.energy, color=list(d.color), size=d.size,
                                     location=y_up(o.location), direction=y_up(fwd)))
    sc['camera'] = dict(location=y_up(CAM['location']), target=y_up(tgt), lens=65, sensor_width=36,
                        sensor_fit='HORIZONTAL', fstop=3.2, focus='Joey_Head',
                        focus_point=y_up(O['Joey_Head'].matrix_world.translation))
    sc['window'] = dict(x0=WINDOW['x0'], x1=WINDOW['x1'], y0=WINDOW['z0'], y1=WINDOW['z1'], z=-WINDOW['y'])
    sc['hugsy'] = dict(location=y_up(HUGSY_POS), rotation_zup=list(HUGSY_ROT))
    json.dump(sc, open(os.path.join(OUT, 'scene2.json'), 'w'), indent=1)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, '_v2_debug.blend'))


main()
