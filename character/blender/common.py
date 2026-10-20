"""Shared helpers for low-poly faceted character building (Blender 4.2, bpy)."""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix, Euler, noise


def hex_lin(h):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4) for x in c] + [1.0]


def make_mat(name, hexcol, rough=0.8, tint=0.0, spec=0.3, sheen=0.0, coat=0.0, sss=0.0):
    """Principled material; tint>0 multiplies colour by per-face 'tint' attribute (faceted shimmer)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes['Principled BSDF']
    col = hex_lin(hexcol)
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Specular IOR Level'].default_value = spec
    bsdf.inputs['Sheen Weight'].default_value = sheen
    bsdf.inputs['Coat Weight'].default_value = coat
    if sss:
        bsdf.inputs['Subsurface Weight'].default_value = sss
        bsdf.inputs['Subsurface Radius'].default_value = (0.6, 0.25, 0.1)
        bsdf.inputs['Subsurface Scale'].default_value = 0.15
    if tint > 0:
        at = nt.nodes.new('ShaderNodeAttribute'); at.attribute_name = 'tint'
        mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
        mix.inputs[0].default_value = 1.0
        mix.inputs[6].default_value = col
        nt.links.new(at.outputs['Color'], mix.inputs[7])
        nt.links.new(mix.outputs[2], bsdf.inputs['Base Color'])
    else:
        bsdf.inputs['Base Color'].default_value = col
    m['uses_tint'] = tint
    return m


def _link(obj, collection=None):
    (collection or bpy.context.collection).objects.link(obj)


def ellipsoid_bm(bm, loc, scale, rot=(0, 0, 0), seg=24, rings=14):
    r = bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0)
    m = (Matrix.Translation(loc) @ Euler(rot).to_matrix().to_4x4()
         @ Matrix.Diagonal((*scale, 1.0)))
    bmesh.ops.transform(bm, matrix=m, verts=r['verts'])


def build_mesh_obj(name, parts, seg=24, rings=14):
    """parts: list of (loc, scale, rot) ellipsoids merged into one (overlapping) mesh object."""
    bm = bmesh.new()
    for p in parts:
        loc, scale = p[0], p[1]
        rot = p[2] if len(p) > 2 else (0, 0, 0)
        ellipsoid_bm(bm, loc, scale, rot, seg, rings)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    _link(ob)
    return ob


def _replace_with_evaluated(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    new = bpy.data.meshes.new_from_object(ev)
    old = ob.data
    ob.modifiers.clear()
    ob.data = new
    bpy.data.meshes.remove(old)


def tri_count(me):
    return sum(len(p.vertices) - 2 for p in me.polygons)


def facet(ob, voxel=0.04, tris=500, lump=0.0, lump_scale=1.6, seed=1):
    """Voxel remesh (fuse) -> optional soft lumps -> Decimate collapse to ~tris -> flat shading + per-face tint."""
    md = ob.modifiers.new('Remesh', 'REMESH')
    md.mode = 'VOXEL'; md.voxel_size = voxel; md.adaptivity = 0.0
    bpy.context.view_layer.update()
    _replace_with_evaluated(ob)
    me = ob.data
    if lump:
        me.calc_normals_split() if hasattr(me, 'calc_normals_split') else None
        for v in me.vertices:
            n = noise.noise(v.co * lump_scale + Vector((seed * 7.3, seed * 3.1, seed * 1.7)))
            v.co += v.normal * n * lump
        me.update()
    cur = max(1, tri_count(me))
    md = ob.modifiers.new('Decimate', 'DECIMATE')
    md.decimate_type = 'COLLAPSE'; md.ratio = min(1.0, tris / cur); md.use_collapse_triangulate = True
    bpy.context.view_layer.update()
    _replace_with_evaluated(ob)
    finish(ob, seed)
    return ob


def finish(ob, seed=1, amp=0.10):
    me = ob.data
    me.shade_flat()
    rnd = random.Random(seed * 101 + len(me.polygons))
    vals = []
    for p in me.polygons:
        # mixture of spatial noise + random for natural shimmer
        c = p.center
        s = 1.0 + amp * (0.6 * (rnd.random() * 2 - 1) + 0.9 * noise.noise(c * 3.0 + Vector((seed, 0, 0))))
        vals += [s, s, s * (1 + 0.03 * (rnd.random() - 0.5)), 1.0]
    if 'tint' in me.attributes:
        me.attributes.remove(me.attributes['tint'])
    a = me.attributes.new('tint', 'FLOAT_COLOR', 'FACE')
    a.data.foreach_set('color', vals)


def set_pivot(ob, pivot):
    """Move object origin to world-space 'pivot' without moving geometry."""
    pivot = Vector(pivot)
    ob.data.transform(Matrix.Translation(-pivot))
    ob.location = pivot


def parent_keep(child, parent):
    bpy.context.view_layer.update()
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()


def assign(ob, mat):
    ob.data.materials.clear()
    ob.data.materials.append(mat)


def box_obj(name, half, bevel=0.015):
    bm = bmesh.new()
    r = bmesh.ops.create_cube(bm, size=2.0)
    bmesh.ops.transform(bm, matrix=Matrix.Diagonal((*half, 1.0)), verts=bm.verts)
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=1, affect='EDGES')
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); _link(ob)
    return ob


def carve(ob, cutter):
    """Boolean-difference 'cutter' out of ob (exact). New cut faces take the cutter's material (appended slot)."""
    md = ob.modifiers.new('Carve', 'BOOLEAN')
    md.operation = 'DIFFERENCE'; md.solver = 'EXACT'; md.object = cutter
    try:
        md.material_mode = 'TRANSFER'
    except Exception:
        pass
    bpy.context.view_layer.update()
    _replace_with_evaluated(ob)
    ob.data.shade_flat()
