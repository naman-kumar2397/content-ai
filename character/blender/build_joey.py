"""Joey: low-poly faceted golden retriever. build_joey(location) creates objects in the current scene.
Facing -Y. L/R naming = viewer's left (-X) / right (+X) when looking at Joey from the front camera.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, math
from mathutils import Vector
from common import *

# palette (sRGB hex)
C_FUR = '#E7C777'; C_EAR = '#C98E1E'; C_MUZZLE = '#F2E0AC'; C_PAW = '#F7EDD0'; C_RUFF = '#EFD596'
C_NOSE = '#2A1A16'; C_EYE = '#120C0B'; C_MOUTH = '#2B0F14'; C_TONGUE = '#F0707F'; C_LIP = '#4A2A22'

NECK = (0, -0.05, 1.35)


def build_joey(location=(0, 0, 0), seed=3):
    mats = dict(
        fur=make_mat('J_Fur', C_FUR, 0.85, tint=1, sheen=0.5, sss=0.1),
        ear=make_mat('J_Ear', C_EAR, 0.85, tint=1, sheen=0.5),
        muzzle=make_mat('J_Muzzle', C_MUZZLE, 0.85, tint=1, sheen=0.4),
        paw=make_mat('J_Paw', C_PAW, 0.85, tint=1, sheen=0.4),
        ruff=make_mat('J_Ruff', C_RUFF, 0.9, tint=1, sheen=0.6),
        nose=make_mat('J_Nose', C_NOSE, 0.25, spec=0.6),
        eye=make_mat('J_Eye', C_EYE, 0.12, spec=1.0, coat=1.0),
        mouth=make_mat('J_Mouth', C_MOUTH, 0.6),
        tongue=make_mat('J_Tongue', C_TONGUE, 0.45, tint=1, sss=0.2),
    )
    # ---- body (fur): torso, haunches, front legs
    body = build_mesh_obj('Joey_Body', [
        ((0, 0.08, 0.72), (0.72, 0.62, 0.74)),
        ((-0.56, -0.02, 0.30), (0.34, 0.52, 0.30)),
        ((0.56, -0.02, 0.30), (0.34, 0.52, 0.30)),
        ((-0.28, -0.48, 0.52), (0.19, 0.21, 0.52)),
        ((0.28, -0.48, 0.52), (0.19, 0.21, 0.52)),
        ((0, 0.45, 0.28), (0.28, 0.3, 0.26)),      # tail bump
    ])
    facet(body, voxel=0.035, tris=900, lump=0.05, seed=seed)
    assign(body, mats['fur'])

    # ---- chest ruff (lighter, fluffy lumps)
    ruff_parts = [((0, -0.26, 0.96), (0.64, 0.40, 0.32)),
                  ((-0.30, -0.38, 0.88), (0.30, 0.28, 0.30)), ((0.30, -0.38, 0.88), (0.30, 0.28, 0.30)),
                  ((0, -0.50, 0.78), (0.32, 0.28, 0.34)),
                  ((-0.45, -0.18, 1.02), (0.2, 0.25, 0.25)), ((0.45, -0.18, 1.02), (0.2, 0.25, 0.25)),
                  ((-0.2, -0.62, 0.92), (0.10, 0.12, 0.22), (0.3, 0.3, 0)), ((0.2, -0.62, 0.92), (0.10, 0.12, 0.22), (0.3, -0.3, 0)),
                  ((0, -0.68, 0.88), (0.10, 0.12, 0.24), (0.3, 0, 0)), ((-0.42, -0.5, 0.95), (0.10, 0.14, 0.2), (0.2, 0.5, 0)), ((0.42, -0.5, 0.95), (0.10, 0.14, 0.2), (0.2, -0.5, 0))]
    ruff = build_mesh_obj('Joey_Ruff', ruff_parts)
    facet(ruff, voxel=0.03, tris=760, lump=0.06, seed=seed + 1)
    assign(ruff, mats['ruff'])

    # ---- paws
    paws = build_mesh_obj('Joey_Paws', [((-0.28, -0.66, 0.12), (0.25, 0.32, 0.14)),
                                       ((0.28, -0.66, 0.12), (0.25, 0.32, 0.14))])
    facet(paws, voxel=0.03, tris=220, lump=0.02, seed=seed + 2)
    assign(paws, mats['paw'])

    # ---- head (fur) with cheek / chin tufts
    head = build_mesh_obj('Joey_Head', [
        ((0, -0.02, 1.80), (0.70, 0.60, 0.54)),
        ((-0.38, -0.22, 1.62), (0.30, 0.32, 0.32)), ((0.38, -0.22, 1.62), (0.30, 0.32, 0.32)),
        ((0, 0.02, 2.05), (0.45, 0.42, 0.25)),
        ((-0.30, -0.35, 2.02), (0.2, 0.2, 0.12)), ((0.30, -0.35, 2.02), (0.2, 0.2, 0.12)),  # brow bumps
        ((-0.56, -0.30, 1.42), (0.13, 0.20, 0.20), (0, 0.5, 0.4)), ((0.56, -0.30, 1.42), (0.13, 0.20, 0.20), (0, -0.5, -0.4)),
        ((-0.40, -0.40, 1.28), (0.12, 0.17, 0.17), (0.3, 0.4, 0.3)), ((0.40, -0.40, 1.28), (0.12, 0.17, 0.17), (0.3, -0.4, -0.3)),
    ])
    facet(head, voxel=0.035, tris=1000, lump=0.04, seed=seed + 3)
    assign(head, mats['fur'])

    # ---- muzzle (lighter, more forward)
    muz = build_mesh_obj('Joey_Muzzle', [
        ((0, -0.58, 1.74), (0.38, 0.42, 0.22)),
        ((-0.28, -0.54, 1.62), (0.20, 0.27, 0.16)), ((0.28, -0.54, 1.62), (0.20, 0.27, 0.16)),   # smiling cheeks
        ((-0.31, -0.42, 1.66), (0.18, 0.2, 0.16)), ((0.31, -0.42, 1.66), (0.18, 0.2, 0.16)),
    ])
    facet(muz, voxel=0.025, tris=420, lump=0.02, seed=seed + 4)
    assign(muz, mats['muzzle'])

    # ---- mouth cutter: wide "D" opening, flat-ish top, deep rounded bottom, corners curling up
    cut = build_mesh_obj('MouthCutter', [
        ((0, -0.52, 1.40), (0.42, 0.40, 0.21)),
        ((-0.40, -0.46, 1.53), (0.10, 0.2, 0.14)), ((0.40, -0.46, 1.53), (0.10, 0.2, 0.14)),
        ((0, -0.45, 1.12), (0.31, 0.30, 0.13))])
    facet(cut, voxel=0.02, tris=320, seed=seed + 11)
    assign(cut, mats['mouth'])
    for ob in (head, muz):
        ob.data.materials.append(mats['mouth'])   # slot for transferred cut faces
        carve(ob, cut)
    bpy.data.objects.remove(cut)
    set_pivot(head, NECK)

    # ---- mouth backing (dark, recessed inside the head)
    mouth = build_mesh_obj('Joey_Mouth', [((0, -0.32, 1.40), (0.34, 0.14, 0.17))], seg=14, rings=9)
    finish(mouth); assign(mouth, mats['mouth'])

    # ---- jaw: bottom lip of the D (hinge at back of mouth)
    jaw = build_mesh_obj('Joey_Jaw', [((0, -0.52, 1.06), (0.33, 0.34, 0.10)),
                                      ((0, -0.64, 1.00), (0.23, 0.24, 0.09)),
                                      ((-0.30, -0.42, 1.14), (0.10, 0.18, 0.09)), ((0.30, -0.42, 1.14), (0.10, 0.18, 0.09))])
    facet(jaw, voxel=0.025, tris=260, lump=0.01, seed=seed + 5)
    assign(jaw, mats['muzzle'])
    set_pivot(jaw, (0, -0.15, 1.42))
    # ---- tongue: ONE piece, rooted in mouth, resting on jaw, tip curling over lip & hanging below chin
    tongue = build_mesh_obj('Joey_Tongue', [((0, -0.38, 1.28), (0.20, 0.24, 0.07), (0.1, 0, 0)),
                                            ((0, -0.58, 1.20), (0.23, 0.24, 0.075), (-0.1, 0, 0)),
                                            ((0, -0.75, 1.14), (0.21, 0.16, 0.08), (-0.5, 0, 0)),
                                            ((0, -0.81, 1.06), (0.17, 0.10, 0.09), (-0.9, 0, 0))])
    facet(tongue, voxel=0.02, tris=230, seed=seed + 6)
    assign(tongue, mats['tongue'])
    set_pivot(tongue, (0, -0.30, 1.30))

    # ---- nose
    nose = build_mesh_obj('Joey_Nose', [((0, -1.00, 1.80), (0.17, 0.11, 0.11))], seg=14, rings=9)
    facet(nose, voxel=0.02, tris=110, seed=seed + 7)
    assign(nose, mats['nose'])

    # ---- eyes (dark glossy beads, origin at centre)
    eyes = {}
    for side, sx in (('L', -1), ('R', 1)):
        e = build_mesh_obj('Joey_Eye' + side, [((0, 0, 0), (0.115, 0.09, 0.125))], seg=12, rings=8)
        finish(e); assign(e, mats['eye'])
        e.location = (sx * 0.29, -0.49, 1.93)
        eyes[side] = e

    # ---- ears (golden, hanging); pivot at top attachment
    ears = {}
    for side, sx in (('L', -1), ('R', 1)):
        ear = build_mesh_obj('Joey_Ear' + side, [
            ((sx * 0.70, 0.05, 1.70), (0.17, 0.38, 0.56), (0, -sx * 0.12, 0)),
            ((sx * 0.69, 0.02, 1.40), (0.16, 0.33, 0.36), (0, -sx * 0.16, 0))])
        facet(ear, voxel=0.03, tris=300, lump=0.03, seed=seed + 8 + sx)
        assign(ear, mats['ear'])
        set_pivot(ear, (sx * 0.62, 0.0, 2.10))
        ears[side] = ear

    # ---- hierarchy
    parent_keep(head, body)
    for ob in (muz, mouth, jaw, nose, eyes['L'], eyes['R'], ears['L'], ears['R']):
        parent_keep(ob, head)
    parent_keep(tongue, jaw)
    parent_keep(ruff, body); parent_keep(paws, body)
    for ob in (body,):
        ob.location = Vector(location)
    bpy.context.view_layer.update()
    return body


if __name__ == '__main__':
    build_joey()
