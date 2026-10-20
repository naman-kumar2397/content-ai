"""Build Joey + Ball (+ Hugsy) headless and export each as GLB for the three.js renderer, plus scene.json
(camera, lights, bokeh, character placement) taken from preview_duo_base.py so the two renderers match.
Usage: blender -b --factory-startup -P export_gltf.py -- [--out ../gltf]
Materials are flattened for glTF: per-face colour = linear albedo * per-face 'tint' baked into a CORNER
colour attribute 'Col' (read by a Color Attribute node -> Base Color, so the exporter writes COLOR_0).
Object names, hierarchy and pivots (origins) are kept: Joey_Jaw, Joey_EyeL/R, Joey_EarL/R, Hugsy_FlipperL/R ...
"""
import sys, os, json, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = os.path.abspath(argv[argv.index('--out') + 1] if '--out' in argv else os.path.join(HERE, '..', 'gltf'))
os.makedirs(OUT, exist_ok=True)

# reuse the duo scene setup (world / desk / bokeh / lights / camera helpers) without rendering
_src = open(os.path.join(HERE, 'preview_duo_base.py')).read().split("if ONLY in ('all', 'joey')")[0]
NS = {'__file__': os.path.join(HERE, 'preview_duo_base.py'), '__name__': 'preview_setup'}
sys.argv = [sys.argv[0], '--', '--out', '/tmp/_unused_preview']
exec(compile(_src, 'preview.py', 'exec'), NS)
import build_joey, build_ball


def bsdf_of(mat):
    return mat.node_tree.nodes.get('Principled BSDF')


def mat_params(mat):
    b = bsdf_of(mat)
    g = lambda k: b.inputs[k].default_value
    # albedo: constant base colour, or the Mix node's A colour for tinted materials
    col = list(g('Base Color'))[:3]
    for n in mat.node_tree.nodes:
        if n.type == 'MIX' and n.data_type == 'RGBA':
            col = list(n.inputs[6].default_value)[:3]
    return dict(color=col, roughness=g('Roughness'), specular=g('Specular IOR Level'), sheen=g('Sheen Weight'),
                coat=g('Coat Weight'), sss=g('Subsurface Weight'), tint=float(mat.get('uses_tint', 0)))


def bake_colors(ob, params):
    """Per-corner colour = albedo(material of face) * face tint (if material uses tint)."""
    me = ob.data
    tint = me.attributes.get('tint')
    tv = None
    if tint is not None:
        tv = [0.0] * (len(me.polygons) * 4); tint.data.foreach_get('color', tv)
    if 'Col' in me.attributes:
        me.attributes.remove(me.attributes['Col'])
    col = me.attributes.new('Col', 'FLOAT_COLOR', 'CORNER')
    vals = [0.0] * (len(me.loops) * 4)
    for p in me.polygons:
        m = me.materials[p.material_index] if me.materials else None
        prm = params.get(m.name) if m else None
        c = prm['color'] if prm else [0.8, 0.8, 0.8]
        t = tv[p.index * 4:p.index * 4 + 3] if (tv and prm and prm['tint']) else [1, 1, 1]
        rgb = [min(1.0, c[i] * t[i]) for i in range(3)]
        for li in p.loop_indices:
            vals[li * 4:li * 4 + 4] = rgb + [1.0]
    col.data.foreach_set('color', vals)
    me.color_attributes.active_color = col
    me.color_attributes.render_color_index = me.color_attributes.find('Col')
    if tint is not None:
        me.attributes.remove(tint)


def simplify_material(mat):
    """Replace the node tree by Color Attribute 'Col' -> Principled (roughness/sheen kept)."""
    p = mat_params(mat)
    nt = mat.node_tree
    b = bsdf_of(mat)
    for n in list(nt.nodes):
        if n not in (b,) and n.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n)
    ca = nt.nodes.new('ShaderNodeVertexColor'); ca.layer_name = 'Col'
    nt.links.new(ca.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Subsurface Weight'].default_value = 0.0
    return p


def characters_root_objects(prefix):
    return [o for o in bpy.data.objects if o.name.startswith(prefix)]


def export(prefix, path):
    bpy.ops.object.select_all(action='DESELECT')
    for o in characters_root_objects(prefix):
        o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_yup=True,
                              export_apply=False, export_materials='EXPORT', export_extras=True,
                              export_animations=False)
    print('EXPORTED', path, os.path.getsize(path), 'bytes', flush=True)


def y_up(v):
    """Blender Z-up (x, y, z) -> glTF/three.js Y-up (x, z, -y)."""
    return [v[0], v[2], -v[1]]


def main():
    j, b = NS['build_scene'](True, True)
    NS['setup_lights']((0.50, 0, 1.95))
    params = {}
    for m in bpy.data.materials:
        if m.name.startswith(('J_', 'B_', 'H_')):
            params[m.name] = simplify_material(m)
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.name.startswith(('Joey_', 'Ball_', 'Hugsy_')):
            bake_colors(o, params)
    export('Joey_', os.path.join(OUT, 'joey.glb'))
    export('Ball_', os.path.join(OUT, 'ball.glb'))

    # ---- scene description (Y-up) for three.js
    sc = dict(materials=params, characters={}, lights=[], bokeh=[])
    for name in ('Joey_Body', 'Ball_Body'):
        o = bpy.data.objects[name]
        sc['characters'][name] = dict(location=y_up(o.location), rotation_euler_zup=list(o.rotation_euler))
    for o in bpy.data.objects:
        if o.type == 'LIGHT':
            d = o.data
            fwd = o.matrix_world.to_3x3() @ Vector((0, 0, -1))
            sc['lights'].append(dict(name=o.name, type=d.type, energy=d.energy, color=list(d.color), size=d.size,
                                     location=y_up(o.location), direction=y_up(fwd)))
        elif o.name.startswith('Bokeh'):
            em = o.active_material.node_tree.nodes['Emission']
            sc['bokeh'].append(dict(location=y_up(o.location), radius=o.dimensions.x / 2,
                                    color=list(em.inputs['Color'].default_value)[:3],
                                    strength=em.inputs['Strength'].default_value))
    sc['camera'] = dict(location=y_up((0.2, -6.5, 1.35)), target=y_up((0.50, 0, 1.95)), lens=65, sensor_width=36,
                        sensor_fit='HORIZONTAL', fstop=3.2, focus='Joey_Head')
    jh = bpy.data.objects['Joey_Head']
    sc['camera']['focus_point'] = y_up(jh.matrix_world.translation)
    json.dump(sc, open(os.path.join(OUT, 'scene.json'), 'w'), indent=1)

    # ---- Hugsy (WIP builder): separate pass, failures don't block the duo export
    try:
        NS['reset']()
        import build_hugsy
        h = build_hugsy.build_hugsy((0, 0, 0))
        params = {m.name: simplify_material(m) for m in bpy.data.materials if m.name.startswith('H_')}
        for o in bpy.data.objects:
            if o.type == 'MESH' and o.name.startswith('Hugsy_'):
                bake_colors(o, params)
        export('Hugsy_', os.path.join(OUT, 'hugsy.glb'))
        sc['materials'].update(params)
        json.dump(sc, open(os.path.join(OUT, 'scene.json'), 'w'), indent=1)
    except Exception as e:
        print('HUGSY EXPORT FAILED:', repr(e), flush=True)


main()
