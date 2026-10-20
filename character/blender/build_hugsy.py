"""Hugsy: low-poly faceted penguin plush in knit hat, swim goggles, yellow quilted vest and red check scarf.
build_hugsy(location) creates objects in the current scene. Facing -Y. L/R = viewer's left (-X) / right (+X).
Height ~1.4 incl. hat (Joey ~2.3).
Hierarchy (all under Hugsy_Body, root, origin at ground centre):
  Belly, Face, Tag, FlipperL/R (pivot = shoulder), FootL/R (origin centre), EyeL/R (pupils, origin centre),
  Brows (empty) -> BrowL/BrowR (hidden in render: hat/goggles occupy that spot),
  Beak (pivot = base hinge) -> BeakLower (same hinge),
  Hat (pivot = head centre; checker band + dotted cap) -> Pompom (pivot = hat tip),
  Goggles (pivot = head centre; rims+bridge+strap) -> LensL/LensR,
  Vest (origin ground) -> VestHem, Scarf (pivot = neck) , ScarfTails (pivot = knot) -> ScarfFringe.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh, math, random
from mathutils import Vector, Matrix, Euler
from common import *
from common import _replace_with_evaluated

C_BODY = '#262F46'; C_WING = '#222A3F'; C_CREAM = '#F5F2EC'; C_YEL = '#E6B000'
C_EYE = '#07080A'
SHOULDER_X, SHOULDER_Z = 0.42, 0.72
BEAK_HINGE = (0, -0.42, 0.745)
HEAD_C = (0, 0, 0.92)
TAU = 2 * math.pi


# ---------------- procedural material helpers
def _n(nt, t, **kw):
    n = nt.nodes.new(t)
    for k, v in kw.items(): setattr(n, k, v)
    return n

def _in(nt, sock, v):
    if isinstance(v, (int, float)): sock.default_value = v
    elif v is not None: nt.links.new(v, sock)

def mth(nt, op, a, b=None):
    n = _n(nt, 'ShaderNodeMath', operation=op)
    _in(nt, n.inputs[0], a); _in(nt, n.inputs[1], 0.0 if b is None else b)
    return n.outputs[0]

def xyz(nt):
    tc = _n(nt, 'ShaderNodeTexCoord'); sp = _n(nt, 'ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Object'], sp.inputs[0])
    return sp.outputs[0], sp.outputs[1], sp.outputs[2]

def polar_u(nt, x, y, k):
    return mth(nt, 'MULTIPLY', mth(nt, 'ARCTAN2', y, x), k / TAU)

def pick(nt, fac, a, b):
    m = _n(nt, 'ShaderNodeMix', data_type='RGBA'); m.inputs[6].default_value = a; m.inputs[7].default_value = b
    _in(nt, m.inputs[0], fac)
    return m.outputs[2]

def tint_mat(name, col, rough, builder=None, **kw):
    m = make_mat(name, col, rough, tint=1, **kw)
    if builder:
        nt = m.node_tree
        out = builder(nt)
        mix = [n for n in nt.nodes if n.type == 'MIX'][0]
        nt.links.new(out, mix.inputs[6])
    return m

def lines(nt, v, thr):  # 1 where fract(v) < thr
    return mth(nt, 'LESS_THAN', mth(nt, 'FRACT', v), thr)

RED = hex_lin('#7C1D2C'); WHITE = hex_lin('#F4ECE6')

def b_plaid_polar(nt):
    x, y, z = xyz(nt)
    u = polar_u(nt, x, y, 26); v = mth(nt, 'MULTIPLY', z, 11)
    f = mth(nt, 'MAXIMUM', lines(nt, u, 0.11), lines(nt, v, 0.11))
    return pick(nt, f, RED, WHITE)

def b_plaid_planar(nt):
    x, y, z = xyz(nt)
    u = mth(nt, 'MULTIPLY', x, 11); v = mth(nt, 'MULTIPLY', z, 11)
    f = mth(nt, 'MAXIMUM', lines(nt, u, 0.11), lines(nt, v, 0.11))
    return pick(nt, f, RED, WHITE)

def b_checker(nt):
    x, y, z = xyz(nt)
    u = polar_u(nt, x, y, 30); v = mth(nt, 'MULTIPLY', z, 1 / 0.058)
    cb = _n(nt, 'ShaderNodeCombineXYZ'); nt.links.new(u, cb.inputs[0]); nt.links.new(v, cb.inputs[1])
    ck = _n(nt, 'ShaderNodeTexChecker'); ck.inputs['Scale'].default_value = 1.0
    ck.inputs['Color1'].default_value = hex_lin('#0C0C10'); ck.inputs['Color2'].default_value = hex_lin('#F2EFE8')
    nt.links.new(cb.outputs[0], ck.inputs['Vector'])
    return ck.outputs['Color']

def b_dots(nt):
    tc = _n(nt, 'ShaderNodeTexCoord')
    vo = _n(nt, 'ShaderNodeTexVoronoi'); vo.inputs['Scale'].default_value = 19; vo.inputs['Randomness'].default_value = 0.7
    nt.links.new(tc.outputs['Object'], vo.inputs['Vector'])
    f = mth(nt, 'LESS_THAN', vo.outputs['Distance'], 0.26)
    return pick(nt, f, hex_lin('#7A1A28'), hex_lin('#F4ECE6'))

def b_quilt(nt):
    x, y, z = xyz(nt)
    u = polar_u(nt, x, y, 24); v = mth(nt, 'MULTIPLY', z, 9.0)
    f = mth(nt, 'MAXIMUM', lines(nt, mth(nt, 'ADD', u, v), 0.07), lines(nt, mth(nt, 'SUBTRACT', u, v), 0.07))
    return pick(nt, f, hex_lin('#EDB400'), hex_lin('#9A6C00'))

def b_stripes(nt):
    x, y, z = xyz(nt)
    u = polar_u(nt, x, y, 44)
    return pick(nt, lines(nt, u, 0.5), hex_lin('#D3201F'), hex_lin('#F6F1EA'))


def carve2(ob, cutter):
    md = ob.modifiers.new('Cut', 'BOOLEAN'); md.operation = 'DIFFERENCE'; md.solver = 'EXACT'; md.object = cutter
    bpy.context.view_layer.update(); _replace_with_evaluated(ob); ob.data.shade_flat()


def cut_boxes(ob, boxes):
    for c, h in boxes:
        cu = box_obj('cut', h, bevel=0.0005); cu.location = c
        carve2(ob, cu); bpy.data.objects.remove(cu)


def torus_bm(bm, center, R, r, scale=(1, 1, 1), rot=(0, 0, 0), nu=22, nv=6):
    """Torus in the XZ plane (axis = Y)."""
    rows = []
    for i in range(nu):
        a = TAU * i / nu; row = []
        for j in range(nv):
            b = TAU * j / nv
            rr = R + r * math.cos(b)
            row.append(bm.verts.new((rr * math.cos(a), r * math.sin(b), rr * math.sin(a))))
        rows.append(row)
    for i in range(nu):
        for j in range(nv):
            bm.faces.new((rows[i][j], rows[i][(j + 1) % nv], rows[(i + 1) % nu][(j + 1) % nv], rows[(i + 1) % nu][j]))
    vs = [v for row in rows for v in row]
    m = Matrix.Translation(center) @ Euler(rot).to_matrix().to_4x4() @ Matrix.Diagonal((*scale, 1.0))
    bmesh.ops.transform(bm, matrix=m, verts=vs)


def vest_parts(k=1.0):
    return [((0, 0, 0.56), (0.50 * k, 0.445 * k, 0.40)), ((0, 0, 0.30), (0.50 * k, 0.45 * k, 0.30))]


def build_hugsy(location=(0, 0, 0), seed=11):
    mats = dict(
        body=make_mat('H_Body', C_BODY, 0.9, tint=1, sheen=0.8, spec=0.2),
        wing=make_mat('H_Wing', C_WING, 0.9, tint=1, sheen=0.8, spec=0.2),
        cream=make_mat('H_Cream', C_CREAM, 0.92, tint=1, sheen=0.7, spec=0.2),
        yel=make_mat('H_Yellow', C_YEL, 0.6, tint=1, spec=0.35, sheen=0.3),
        eye=make_mat('H_Eye', C_EYE, 0.1, spec=1.0, coat=1.0),
        brow=make_mat('H_Brow', '#1B2438', 0.95, tint=1),
        tag=make_mat('H_Tag', '#E8D9B0', 0.9, tint=1),
        black=make_mat('H_Black', '#0D0D10', 0.4, tint=1, spec=0.5),
        band=tint_mat('H_HatBand', '#FFFFFF', 0.95, b_checker, sheen=0.4),
        cap=tint_mat('H_HatCap', '#FFFFFF', 0.95, b_dots, sheen=0.4),
        pom=make_mat('H_Pom', '#F0E6C4', 0.95, tint=1, sheen=1.0),
        plaid=tint_mat('H_Plaid', '#FFFFFF', 0.95, b_plaid_polar, sheen=0.5),
        plaidT=tint_mat('H_PlaidT', '#FFFFFF', 0.95, b_plaid_planar, sheen=0.5),
        quilt=tint_mat('H_Quilt', '#FFFFFF', 0.45, b_quilt, spec=0.5, sheen=0.2),
        hem=tint_mat('H_Hem', '#FFFFFF', 0.8, b_stripes),
    )
    lens = bpy.data.materials.new('H_Lens'); lens.use_nodes = True
    lb = lens.node_tree.nodes['Principled BSDF']
    lb.inputs['Base Color'].default_value = hex_lin('#6C7684'); lb.inputs['Alpha'].default_value = 0.22
    lb.inputs['Roughness'].default_value = 0.05; lb.inputs['Specular IOR Level'].default_value = 0.8
    mats['lens'] = lens

    # ---- body: pear, dark; head dome merged (no neck)
    body = build_mesh_obj('Hugsy_Body', [
        ((0, 0, 0.52), (0.47, 0.41, 0.50)),
        ((0, 0, 0.15), (0.45, 0.41, 0.13)),
        ((0, 0, 0.30), (0.47, 0.42, 0.28)),
        ((0, 0, 0.85), (0.40, 0.37, 0.33)),
        ((0, 0.40, 0.15), (0.13, 0.13, 0.10)),
    ], seg=28, rings=18)
    facet(body, voxel=0.03, tris=1100, lump=0.03, lump_scale=1.8, seed=seed)
    assign(body, mats['body'])

    # ---- white face (front of head) and belly
    face = build_mesh_obj('Hugsy_Face', [((0, -0.08, 0.82), (0.385, 0.34, 0.32)),
                                         ((0, -0.04, 0.72), (0.34, 0.31, 0.22))])
    facet(face, voxel=0.025, tris=620, lump=0.012, seed=seed + 2)
    assign(face, mats['cream'])
    belly = build_mesh_obj('Hugsy_Belly', [((0, -0.15, 0.36), (0.31, 0.30, 0.30)), ((0, -0.13, 0.55), (0.28, 0.28, 0.22))])
    facet(belly, voxel=0.028, tris=400, lump=0.02, seed=seed + 1)
    assign(belly, mats['cream'])

    # ---- beak: small rounded yellow cone, hinge at base
    ub = build_mesh_obj('Hugsy_Beak', [((0, -0.43, 0.76), (0.105, 0.09, 0.08)),
                                       ((0, -0.495, 0.745), (0.07, 0.085, 0.055)),
                                       ((0, -0.535, 0.735), (0.04, 0.05, 0.033))], seg=14, rings=9)
    facet(ub, voxel=0.014, tris=180, seed=seed + 3)
    assign(ub, mats['yel']); set_pivot(ub, BEAK_HINGE)
    lbk = build_mesh_obj('Hugsy_BeakLower', [((0, -0.455, 0.705), (0.075, 0.07, 0.036)),
                                             ((0, -0.495, 0.71), (0.05, 0.06, 0.03))], seg=12, rings=8)
    facet(lbk, voxel=0.014, tris=100, seed=seed + 4)
    assign(lbk, mats['yel']); set_pivot(lbk, BEAK_HINGE)

    # ---- pupils (eyes), origin at centre, sit on the face under the lenses
    eyes = {}
    for side, sx in (('L', -1), ('R', 1)):
        e = build_mesh_obj('Hugsy_Eye' + side, [((0, 0, 0), (0.036, 0.022, 0.048))], seg=12, rings=8)
        finish(e); assign(e, mats['eye'])
        e.location = (sx * 0.16, -0.385, 0.87); e.rotation_euler = (0, 0, sx * 0.4)
        eyes[side] = e

    # ---- brows (kept as rig handles; hidden in render, goggles/hat cover that area)
    brows = bpy.data.objects.new('Hugsy_Brows', None); bpy.context.collection.objects.link(brows)
    brows.empty_display_type = 'PLAIN_AXES'; brows.empty_display_size = 0.05; brows.location = (0, -0.34, 0.98)
    brow = {}
    for side, sx in (('L', -1), ('R', 1)):
        b = box_obj('Hugsy_Brow' + side, (0.07, 0.012, 0.014), bevel=0.01)
        finish(b); assign(b, mats['brow']); b.location = (sx * 0.14, -0.34, 0.98); b.rotation_euler = (0, 0, sx * 0.4)
        b.hide_render = True; b.hide_viewport = True
        brow[side] = b

    # ---- flippers: black, long, angled down/out; pivot at shoulder
    flip = {}
    ang = 0.62
    for side, sx in (('L', -1), ('R', 1)):
        S = Vector((sx * SHOULDER_X, 0, SHOULDER_Z)); d = Vector((sx * math.sin(ang), 0, -math.cos(ang)))
        parts = []
        for t, sc in ((0.12, (0.10, 0.14, 0.15)), (0.28, (0.095, 0.145, 0.15)), (0.44, (0.088, 0.14, 0.15)),
                      (0.60, (0.075, 0.12, 0.14)), (0.74, (0.058, 0.085, 0.10))):
            p = S + d * t
            parts.append(((p.x, p.y, p.z), sc, (0, -sx * ang, 0)))
        f = build_mesh_obj('Hugsy_Flipper' + side, parts, seg=14, rings=10)
        facet(f, voxel=0.022, tris=420, lump=0.015, seed=seed + 5 + sx)
        assign(f, mats['wing']); set_pivot(f, tuple(S))
        flip[side] = f

    # ---- feet: chunky yellow, pointing forward
    feet = {}
    for side, sx in (('L', -1), ('R', 1)):
        ft = build_mesh_obj('Hugsy_Foot' + side, [((0, 0, 0), (0.16, 0.20, 0.10)),
                                                   ((0, -0.08, -0.005), (0.14, 0.16, 0.09))], seg=14, rings=9)
        facet(ft, voxel=0.02, tris=260, lump=0.01, seed=seed + 8 + sx)
        assign(ft, mats['yel'])
        ft.location = (sx * 0.20, -0.33, 0.092)
        feet[side] = ft

    # ---- tag
    tag = box_obj('Hugsy_Tag', (0.012, 0.07, 0.10), bevel=0.008)
    finish(tag); assign(tag, mats['tag']); tag.location = (0.45, 0.12, 0.32); tag.rotation_euler = (0, 0.45, 0)

    # ---- hat: checker band + dotted red cap slouching to +X
    hat = build_mesh_obj('Hugsy_Hat', [
        ((0, 0, 1.05), (0.405, 0.375, 0.115)),
        ((0, 0, 1.19), (0.34, 0.31, 0.12)),
        ((0.03, 0, 1.22), (0.28, 0.26, 0.12)),
        ((0.10, 0, 1.31), (0.21, 0.20, 0.11)),
        ((0.19, 0, 1.365), (0.145, 0.14, 0.10)),
        ((0.28, 0, 1.375), (0.105, 0.10, 0.085)),
        ((0.36, 0, 1.34), (0.07, 0.07, 0.07)),
    ], seg=24, rings=14)
    facet(hat, voxel=0.02, tris=1100, lump=0.012, seed=seed + 20)
    hat.data.materials.clear(); hat.data.materials.append(mats['band']); hat.data.materials.append(mats['cap'])
    for p in hat.data.polygons:
        p.material_index = 0 if p.center.z < 1.14 else 1
    set_pivot(hat, HEAD_C)
    prng = random.Random(5)
    pcs = [((0.40 + prng.uniform(-.04, .04), prng.uniform(-.05, .05), 1.245 + prng.uniform(-.04, .04)),
            (0.075 + prng.uniform(0, .03),) * 3) for _ in range(6)]
    pom = build_mesh_obj('Hugsy_Pompom', pcs, seg=12, rings=8)
    facet(pom, voxel=0.018, tris=420, lump=0.02, lump_scale=3.0, seed=seed + 21)
    assign(pom, mats['pom']); set_pivot(pom, (0.36, 0, 1.33))

    # ---- goggles: rims + bridge + strap (black), lenses separate
    gm = bmesh.new()
    lens_c = {}
    for side, sx in (('L', -1), ('R', 1)):
        c = Vector((sx * 0.16, -0.405, 0.87)); lens_c[side] = c
        torus_bm(gm, c, 0.115, 0.026, scale=(1.14, 1.0, 0.92), rot=(0, 0, sx * 0.4), nu=20, nv=6)
    ellipsoid_bm(gm, (0, -0.435, 0.885), (0.085, 0.025, 0.024), (0, 0, 0), 10, 6)
    for th in [x * 0.2 for x in range(0, 32)]:
        if th < 0.95 or th > TAU - 0.95: continue
        ellipsoid_bm(gm, (0.415 * math.sin(th), -0.02 - 0.385 * math.cos(th), 0.87), (0.04, 0.04, 0.032), (0, 0, th), 8, 5)
    me = bpy.data.meshes.new('Hugsy_Goggles'); gm.to_mesh(me); gm.free()
    gog = bpy.data.objects.new('Hugsy_Goggles', me); bpy.context.collection.objects.link(gog)
    finish(gog, seed=3, amp=0.05); assign(gog, mats['black']); set_pivot(gog, (0, -0.03, 0.87))
    lenses = {}
    for side, sx in (('L', -1), ('R', 1)):
        l = build_mesh_obj('Hugsy_Lens' + side, [((0, 0, 0), (0.13, 0.022, 0.102))], seg=16, rings=8)
        finish(l, amp=0.02); assign(l, mats['lens'])
        l.location = lens_c[side] + Vector((0, -0.005, 0)); l.rotation_euler = (0, 0, sx * 0.4)
        lenses[side] = l

    # ---- vest (open front slot) + striped hem
    vest = build_mesh_obj('Hugsy_Vest', vest_parts(1.0), seg=28, rings=18)
    facet(vest, voxel=0.024, tris=1500, lump=0.012, seed=seed + 30)
    assign(vest, mats['quilt'])
    cut_boxes(vest, [((0, 0, 0.30 - 0.6), (1, 1, 0.6)), ((0, 0, 0.74 + 0.6), (1, 1, 0.6)),
                     ((0, -0.5, 0.5), (0.065, 0.45, 1))])
    hem = build_mesh_obj('Hugsy_VestHem', vest_parts(1.03), seg=28, rings=18)
    facet(hem, voxel=0.024, tris=1100, seed=seed + 31)
    assign(hem, mats['hem'])
    cut_boxes(hem, [((0, 0, 0.31 + 0.6), (1, 1, 0.6)), ((0, 0, 0.19 - 0.6), (1, 1, 0.6)),
                    ((0, -0.5, 0.5), (0.065, 0.45, 1))])

    # ---- scarf ring + knot
    sp = []
    for i in range(16):
        a = TAU * i / 16
        sp.append(((0.465 * math.cos(a), -0.02 + 0.425 * math.sin(a), 0.655 + 0.02 * math.sin(a * 2)), (0.105, 0.105, 0.085)))
    sp.append(((0.10, -0.44, 0.62), (0.14, 0.11, 0.13)))
    scarf = build_mesh_obj('Hugsy_Scarf', sp, seg=14, rings=10)
    facet(scarf, voxel=0.024, tris=1100, lump=0.014, seed=seed + 40)
    assign(scarf, mats['plaid']); set_pivot(scarf, (0, -0.02, 0.655))

    # ---- scarf tails + fringe
    def yv(z): return 0.455 * math.sqrt(max(0.0, 1 - ((z - 0.5) / 0.60) ** 2))
    tp = []; ends = []
    for x0, zb, wob in ((-0.035, 0.12, 0.0), (0.145, 0.26, 0.02)):
        z = 0.60
        while z > zb:
            tp.append(((x0 + wob * (0.60 - z) * 3, -(yv(z) + 0.03), z), (0.085, 0.032, 0.075), (0, 0, 0))); z -= 0.07
        ends.append((x0, zb))
    tails = build_mesh_obj('Hugsy_ScarfTails', tp, seg=12, rings=8)
    facet(tails, voxel=0.016, tris=900, lump=0.008, seed=seed + 41)
    assign(tails, mats['plaidT']); set_pivot(tails, (0.05, -0.42, 0.62))
    fr = []
    for x0, zb in ends:
        for k in range(8):
            fr.append(((x0 - 0.075 + k * 0.0215, -(yv(zb) + 0.03) + (k % 2) * 0.005, zb - 0.05 - (k % 3) * 0.008),
                       (0.012, 0.012, 0.075), (0.15 * ((k % 3) - 1), 0, 0)))
    fringe = build_mesh_obj('Hugsy_ScarfFringe', fr, seg=6, rings=4)
    finish(fringe); assign(fringe, mats['black'])

    # ---- hierarchy
    for ob in (belly, face, flip['L'], flip['R'], feet['L'], feet['R'], tag, eyes['L'], eyes['R'], brows, ub,
               hat, gog, vest, scarf, tails):
        parent_keep(ob, body)
    parent_keep(lbk, ub); parent_keep(pom, hat)
    parent_keep(brow['L'], brows); parent_keep(brow['R'], brows)
    parent_keep(lenses['L'], gog); parent_keep(lenses['R'], gog)
    parent_keep(hem, vest); parent_keep(fringe, tails)
    body.location = Vector(location)
    bpy.context.view_layer.update()
    return body


if __name__ == '__main__':
    build_hugsy()
