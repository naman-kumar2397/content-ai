"""Ball: low-poly tennis-ball sidekick. Facing -Y. Body origin at ball centre-ish (world 0,0,0 + location)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh, math
from mathutils import Vector
from common import *

R = 0.40
FOOT_H = 0.10


def seam_obj(body, zc, k=0.22, half_w=0.062, nseg=260, ncol=7, rot=(0, 0, 0)):
    """White tennis-ball seam ribbon, projected onto the faceted body (shrinkwrap) so it follows the facets."""
    from mathutils import Euler
    rm = Euler(rot).to_matrix()
    def P(t):
        x = (1 - k) * math.cos(t) + k * math.cos(3 * t)
        y = (1 - k) * math.sin(t) - k * math.sin(3 * t)
        z = 2 * math.sqrt(k * (1 - k)) * math.cos(2 * t)
        return rm @ Vector((x, y, z)).normalized()
    bm = bmesh.new()
    rows = []
    for i in range(nseg):
        t = 2 * math.pi * i / nseg
        p = P(t); tg = (P(t + 1e-3) - P(t - 1e-3)).normalized()
        side = p.cross(tg).normalized()
        row = []
        for c in range(ncol):
            u = (c / (ncol - 1)) * 2 - 1
            q = (p + side * half_w * u).normalized() * R * 1.05 + Vector((0, 0, zc))
            row.append(bm.verts.new(q))
        rows.append(row)
    for i in range(nseg):
        a, b = rows[i], rows[(i + 1) % nseg]
        for c in range(ncol - 1):
            bm.faces.new((a[c], a[c + 1], b[c + 1], b[c]))
    me = bpy.data.meshes.new('Ball_Seam'); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new('Ball_Seam', me); bpy.context.collection.objects.link(ob)
    sw = ob.modifiers.new('SW', 'SHRINKWRAP'); sw.target = body
    sw.wrap_method = 'NEAREST_SURFACEPOINT'; sw.offset = 0.012
    bpy.context.view_layer.update()
    from common import _replace_with_evaluated
    _replace_with_evaluated(ob)
    finish(ob, seed=9, amp=0.04)
    return ob


def build_ball(location=(0, 0, 0), seed=5, seam_rot=None, yaw=0.0, tilt=0.0):
    import os
    if seam_rot is None:
        seam_rot = tuple(float(x) for x in os.environ.get('SEAMROT', '1.3,0,2.2').split(','))
    mats = dict(
        ball=make_mat('B_Fuzz', '#B4D61C', 0.95, tint=1, sheen=1.0, spec=0.15),
        seam=make_mat('B_Seam', '#F4F4EA', 0.9, tint=1, sheen=0.3),
        eye=make_mat('B_Eye', '#050505', 0.2, spec=0.8, coat=0.8),
        foot=make_mat('B_Foot', '#7C9610', 0.7),
    )
    # fuzz bump on ball material
    nt = mats['ball'].node_tree
    tex = nt.nodes.new('ShaderNodeTexNoise'); tex.inputs['Scale'].default_value = 220; tex.inputs['Detail'].default_value = 4
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.35; bump.inputs['Distance'].default_value = 0.01
    nt.links.new(tex.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], nt.nodes['Principled BSDF'].inputs['Normal'])

    zc = FOOT_H + R - 0.02
    body = build_mesh_obj('Ball_Body', [((0, 0, zc), (R, R, R * 0.98))], seg=28, rings=18)
    facet(body, voxel=0.03, tris=420, lump=0.02, lump_scale=2.5, seed=seed)
    assign(body, mats['ball'])
    set_pivot(body, (0, 0, zc))

    seam = seam_obj(body, zc, rot=seam_rot)
    # seam built relative to world origin; move into body-local space (body origin at zc)
    assign(seam, mats['seam'])
    set_pivot(seam, (0, 0, zc))

    eyes = {}
    for side, sx in (('L', -1), ('R', 1)):
        e = box_obj('Ball_Eye' + side, (0.05, 0.03, 0.115), bevel=0.018)
        finish(e); assign(e, mats['eye'])
        e.location = (sx * 0.13, -R * 0.93, zc + 0.13)
        e.rotation_euler = (0.0, sx * 0.08, 0)
        # bevel-ish: squash sphere to rect-ish via 'cube' look using scale
        eyes[side] = e
    feet = {}
    for side, sx in (('L', -1), ('R', 1)):
        f = build_mesh_obj('Ball_Foot' + side, [((0, 0, 0), (0.12, 0.17, 0.075))], seg=10, rings=6)
        finish(f); assign(f, mats['foot'])
        f.location = (sx * 0.16, -0.06, 0.07)
        feet[side] = f

    for ob in (seam, eyes['L'], eyes['R'], feet['L'], feet['R']):
        parent_keep(ob, body)
    body.location = Vector(location) + Vector((0, 0, zc))
    body.rotation_euler = (tilt, 0, yaw)
    bpy.context.view_layer.update()
    return body


if __name__ == '__main__':
    build_ball()
