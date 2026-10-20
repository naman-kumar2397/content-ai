"""Build Joey + Ball, set up preview scene (night-blue bg, desk, warm key, cool rim) and render stills.
Usage: blender -b --factory-startup -P preview.py -- [--scale 100] [--samples 48] [--only joey|ball|duo] [--tag name]
"""
import sys, os, time, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy
from mathutils import Vector
import importlib
import common, build_joey, build_ball, build_hugsy

ROOT = os.path.abspath(os.path.join(HERE, '..'))
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def arg(n, d):
    return args[args.index(n) + 1] if n in args else d
SCALE = int(arg('--scale', 100)); SAMPLES = int(arg('--samples', 48))
ONLY = arg('--only', 'all'); SIDEKICK = arg('--sidekick', 'hugsy'); THREADS = int(arg('--threads', 2)); OUT = arg('--out', os.path.join(ROOT, 'renders'))
os.makedirs(OUT, exist_ok=True)

JOEY_POS = (0.0, 0.0, 0.0)
BALL_POS = (1.18, -0.95, 0.0)
HUGSY_POS = (1.30, -1.0, 0.0)


def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def setup_world():
    w = bpy.context.scene.world = bpy.data.worlds.new('W')
    w.use_nodes = True; nt = w.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    bg_cam = nt.nodes.new('ShaderNodeBackground'); bg_lit = nt.nodes.new('ShaderNodeBackground')
    lp = nt.nodes.new('ShaderNodeLightPath'); mix = nt.nodes.new('ShaderNodeMixShader')
    tc = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    nt.links.new(tc.outputs['Window'], sep.inputs[0]); nt.links.new(sep.outputs['Y'], ramp.inputs[0])
    e = ramp.color_ramp.elements
    e[0].position = 0.0; e[0].color = (0.004, 0.008, 0.03, 1)
    e[1].position = 1.0; e[1].color = (0.02, 0.05, 0.14, 1)
    nt.links.new(ramp.outputs['Color'], bg_cam.inputs['Color']); bg_cam.inputs['Strength'].default_value = 1.0
    bg_lit.inputs['Color'].default_value = (0.03, 0.06, 0.16, 1); bg_lit.inputs['Strength'].default_value = 0.35
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
    nt.links.new(bg_lit.outputs[0], mix.inputs[1]); nt.links.new(bg_cam.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])


def setup_desk():
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 4, 0))
    f = bpy.context.object; f.name = 'Desk'; f.scale = (40, 30, 1)
    m = bpy.data.materials.new('Desk'); m.use_nodes = True; nt = m.node_tree; b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (1, 14, 1)
    wv = nt.nodes.new('ShaderNodeTexWave'); wv.wave_type = 'BANDS'; wv.bands_direction = 'X'
    wv.inputs['Scale'].default_value = 0.8; wv.inputs['Distortion'].default_value = 6; wv.inputs['Detail'].default_value = 3
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.03, 0.017, 0.012, 1); ramp.color_ramp.elements[1].color = (0.11, 0.06, 0.04, 1)
    nt.links.new(tc.outputs['Object'], mp.inputs[0]); nt.links.new(mp.outputs[0], wv.inputs['Vector'])
    nt.links.new(wv.outputs['Fac'], ramp.inputs[0]); nt.links.new(ramp.outputs[0], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.72
    f.data.materials.append(m)
    # back wall
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 7, 5), rotation=(math.pi / 2, 0, 0))
    w = bpy.context.object; w.name = 'Wall'; w.scale = (40, 12, 1)
    wm = bpy.data.materials.new('Wall'); wm.use_nodes = True
    wm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.02, 0.04, 0.10, 1)
    wm.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.9
    w.data.materials.append(wm)


def setup_bokeh():
    """Dim, size-varied out-of-focus 'city window' lights at varied depth."""
    import random
    rnd = random.Random(7)
    pal = [(1.0, 0.62, 0.25), (1.0, 0.78, 0.45), (0.45, 0.62, 1.0), (0.9, 0.9, 1.0), (1.0, 0.45, 0.35)]
    for i in range(46):
        big = rnd.random() < 0.18
        r = rnd.uniform(0.22, 0.38) if big else rnd.uniform(0.04, 0.17) ** 1.0
        c = rnd.choice(pal); k = rnd.uniform(0.6, 1.0)
        col = (c[0] * k, c[1] * k, c[2] * k, 1)
        d = rnd.uniform(5.2, 9.0)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r * d / 6.5, segments=12, ring_count=8,
            location=(rnd.uniform(-5.5, 5.5) * d / 6.5, d, rnd.uniform(1.4, 6.8)))
        o = bpy.context.object; o.name = 'Bokeh%d' % i
        m = bpy.data.materials.new('Bk%d' % i); m.use_nodes = True; nt = m.node_tree
        nt.nodes.clear(); em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value = col
        em.inputs['Strength'].default_value = rnd.uniform(0.5, 1.8)
        out = nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(em.outputs[0], out.inputs[0])
        o.data.materials.append(m)
        o.visible_shadow = False


def area(name, loc, target, energy, color, size):
    d = bpy.data.lights.new(name, 'AREA'); d.energy = energy; d.color = color; d.size = size
    o = bpy.data.objects.new(name, d); bpy.context.collection.objects.link(o)
    o.location = loc; look_at(o, target); return o


def setup_lights(target):
    area('Key', (-5.5, -3.5, 3.6), target, 1500, (1.0, 0.75, 0.45), 3.5)
    area('Fill', (3.5, -5.0, 0.8), target, 160, (0.35, 0.5, 1.0), 4.0)
    area('Rim', (3.5, 3.8, 3.6), target, 700, (0.30, 0.50, 1.0), 2.5)
    area('Rim2', (-4.0, 3.5, 2.5), target, 250, (0.35, 0.5, 1.0), 2.5)


def setup_camera(loc, target, lens, focus_obj, fstop=2.8, fit='AUTO'):
    c = bpy.data.cameras.new('Cam'); c.lens = lens; c.sensor_fit = fit
    o = bpy.data.objects.new('Cam', c); bpy.context.collection.objects.link(o)
    o.location = loc; look_at(o, target)
    c.dof.use_dof = True; c.dof.focus_object = focus_obj; c.dof.aperture_fstop = fstop
    bpy.context.scene.camera = o
    return o


def setup_render(w, h, out):
    s = bpy.context.scene
    s.render.engine = 'CYCLES'; s.cycles.device = 'CPU'; s.cycles.samples = SAMPLES
    s.cycles.use_denoising = True; s.cycles.denoiser = 'OPENIMAGEDENOISE'
    s.cycles.max_bounces = 6; s.cycles.diffuse_bounces = 3; s.cycles.glossy_bounces = 3
    s.cycles.transmission_bounces = 2; s.cycles.caustics_reflective = False; s.cycles.caustics_refractive = False
    s.render.use_persistent_data = True
    s.render.resolution_x = w; s.render.resolution_y = h; s.render.resolution_percentage = SCALE
    s.render.image_settings.file_format = 'PNG'
    s.view_settings.view_transform = 'Filmic' if 'Filmic' in bpy.types.ColorManagedViewSettings.bl_rna.properties['view_transform'].enum_items.keys() else 'AgX'
    try: s.view_settings.look = 'Medium High Contrast'
    except Exception: pass
    s.render.filepath = out
    s.render.threads_mode = 'FIXED'; s.render.threads = THREADS


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def build_scene(joey=True, ball=True, hugsy=False):
    reset(); setup_world(); setup_desk(); setup_bokeh()
    j = build_joey.build_joey(JOEY_POS) if joey else None
    b = None
    if ball:
        b = build_ball.build_ball(BALL_POS, yaw=-0.5, tilt=-0.12) if joey else build_ball.build_ball((0, 0, 0))
    h = None
    if hugsy:
        if joey:
            h = build_hugsy.build_hugsy(HUGSY_POS)
            h.rotation_euler = (-0.12, 0, -0.55)   # turned toward Joey, chin up
        else:
            h = build_hugsy.build_hugsy((0, 0, 0))
    return j, b, h


def render(name, w, h, joey, ball, cam_loc, cam_tgt, lens, focus, fstop=2.8, fit='AUTO', hugsy=False):
    j, b, hg = build_scene(joey, ball, hugsy)
    if focus == 'joey': fo = bpy.data.objects['Joey_Head']
    elif focus == 'hugsy': fo = bpy.data.objects['Hugsy_Face']
    else: fo = b
    setup_lights(cam_tgt)
    setup_camera(cam_loc, cam_tgt, lens, fo, fstop, fit)
    out = os.path.join(OUT, name + '.png')
    setup_render(w, h, out)
    t = time.time(); bpy.ops.render.render(write_still=True); dt = time.time() - t
    print(f'RENDER {name} {int(w*SCALE/100)}x{int(h*SCALE/100)} spp={SAMPLES}: {dt:.1f}s', flush=True)
    return dt


if ONLY in ('all', 'joey'):
    render('joey_front', 1080, 1350, True, False, (-0.9, -8.2, 2.0), (0, 0, 1.15), 85, 'joey')
if ONLY == 'ball' or (ONLY == 'all' and SIDEKICK == 'ball'):
    render('ball_front', 1080, 1350, False, True, (-0.4, -3.6, 0.9), (0, 0, 0.5), 85, 'ball', 2.8)
if ONLY in ('hugsy', 'all') and SIDEKICK == 'hugsy':
    render('hugsy_front', 1080, 1350, False, False, (-0.5, -4.2, 0.95), (0, 0, 0.62), 85, 'hugsy', 2.8, hugsy=True)
if ONLY in ('all', 'duo'):
    if SIDEKICK == 'ball': render('duo', 1080, 1920, True, True, (0.2, -6.5, 1.35), (0.50, 0, 1.95), 65, 'joey', 3.2, 'HORIZONTAL')
    else: render('duo_hugsy', 1080, 1920, True, False, (0.2, -6.5, 1.35), (0.50, 0, 1.95), 65, 'joey', 3.2, 'HORIZONTAL', hugsy=True)
    if SCALE == 100 and ONLY == 'all' and SIDEKICK == 'ball':
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, 'characters.blend'))
    if SCALE == 100 and ONLY in ('all', 'duo') and SIDEKICK == 'hugsy':
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, 'characters_hugsy.blend'))
