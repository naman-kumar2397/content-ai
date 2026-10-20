"""Hugsy: low-poly faceted penguin plush toy. build_hugsy(location) creates objects in the current scene.
Facing -Y. L/R = viewer's left (-X) / right (+X) from the front camera. Height ~1.25 (Joey ~2.3).
Hierarchy: Hugsy_Body (root, origin at ground centre)
  Belly, Face, Tag, FlipperL/R (pivot at shoulder), FootL/R (pivot at ankle/centre), EyeL/R (origin at centre),
  Brows (empty at brow centre) -> BrowL/BrowR, Beak (pivot at base hinge) -> BeakLower (same hinge).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, math
from mathutils import Vector
from common import *

C_NAVY = '#34476B'; C_WING = '#2C3C5C'; C_CREAM = '#F6EEDA'; C_BEAK = '#FF9A1F'; C_FOOT = '#FF8A1A'
C_EYE = '#07080A'; C_BROW = '#1B2438'; C_TAG = '#E8D9B0'

SHOULDER = 0.50, 0.0, 0.84
BEAK_HINGE = (0, -0.43, 0.775)


def build_hugsy(location=(0, 0, 0), seed=11):
    mats = dict(
        navy=make_mat('H_Navy', C_NAVY, 0.9, tint=1, sheen=0.8, spec=0.2),
        wing=make_mat('H_Wing', C_WING, 0.9, tint=1, sheen=0.8, spec=0.2),
        cream=make_mat('H_Cream', C_CREAM, 0.92, tint=1, sheen=0.7, spec=0.2),
        beak=make_mat('H_Beak', C_BEAK, 0.5, tint=1, spec=0.4),
        foot=make_mat('H_Foot', C_FOOT, 0.55, tint=1, spec=0.3),
        eye=make_mat('H_Eye', C_EYE, 0.1, spec=1.0, coat=1.0),
        brow=make_mat('H_Brow', C_BROW, 0.95, tint=1),
        tag=make_mat('H_Tag', C_TAG, 0.9, tint=1),
    )
    # ---- body: one egg (no neck); wide squishy base, slightly narrower head
    body = build_mesh_obj('Hugsy_Body', [
        ((0, 0.0, 0.58), (0.54, 0.47, 0.54)),
        ((0, 0.0, 0.14), (0.47, 0.43, 0.13)),             # flat plush bottom
        ((0, -0.02, 0.90), (0.48, 0.43, 0.36)),           # head dome
        ((0, 0.40, 0.18), (0.14, 0.14, 0.10)),            # stubby tail
    ], seg=28, rings=18)
    facet(body, voxel=0.03, tris=1100, lump=0.035, lump_scale=1.8, seed=seed)
    assign(body, mats['navy'])
    set_pivot(body, (0, 0, 0))

    # ---- belly (cream, pear shaped, hugging the front)
    belly = build_mesh_obj('Hugsy_Belly', [
        ((0, -0.15, 0.44), (0.40, 0.34, 0.37)),
        ((0, -0.20, 0.30), (0.38, 0.32, 0.26)),
        ((0, -0.12, 0.60), (0.31, 0.30, 0.22)),
    ])
    facet(belly, voxel=0.028, tris=560, lump=0.02, seed=seed + 1)
    assign(belly, mats['cream'])
    set_pivot(belly, (0, 0, 0))

    # ---- face mask: heart-shaped (two cheek lobes + pointed chin)
    face = build_mesh_obj('Hugsy_Face', [
        ((-0.15, -0.32, 1.00), (0.24, 0.17, 0.20)), ((0.15, -0.32, 1.00), (0.24, 0.17, 0.20)),
        ((0, -0.31, 0.92), (0.36, 0.17, 0.18)),
        ((0, -0.32, 0.83), (0.24, 0.16, 0.14)),
    ])
    facet(face, voxel=0.025, tris=480, lump=0.012, seed=seed + 2)
    assign(face, mats['cream'])
    set_pivot(face, (0, 0, 0))

    # ---- beak (upper + lower, rounded cones), hinge at base
    ub = build_mesh_obj('Hugsy_Beak', [
        ((0, -0.525, 0.80), (0.115, 0.13, 0.055)),
        ((0, -0.57, 0.795), (0.075, 0.095, 0.042)),
        ((0, -0.46, 0.81), (0.14, 0.10, 0.07)),
    ], seg=14, rings=9)
    facet(ub, voxel=0.015, tris=170, seed=seed + 3)
    assign(ub, mats['beak']); set_pivot(ub, BEAK_HINGE)
    lb = build_mesh_obj('Hugsy_BeakLower', [
        ((0, -0.515, 0.745), (0.095, 0.105, 0.035)),
        ((0, -0.46, 0.75), (0.11, 0.08, 0.04)),
    ], seg=12, rings=8)
    facet(lb, voxel=0.015, tris=120, seed=seed + 4)
    assign(lb, mats['beak']); set_pivot(lb, BEAK_HINGE)

    # ---- eyes: glossy black ovals, origin at centre
    eyes = {}
    for side, sx in (('L', -1), ('R', 1)):
        e = build_mesh_obj('Hugsy_Eye' + side, [((0, 0, 0), (0.048, 0.03, 0.068))], seg=12, rings=8)
        finish(e); assign(e, mats['eye'])
        e.location = (sx * 0.15, -0.47, 0.975)
        e.rotation_euler = (0.1, 0, sx * -0.1)
        eyes[side] = e

    # ---- brows: felt strips, parent empty at brow centre
    brows = bpy.data.objects.new('Hugsy_Brows', None); bpy.context.collection.objects.link(brows)
    brows.empty_display_type = 'PLAIN_AXES'; brows.empty_display_size = 0.05
    brows.location = (0, -0.465, 1.065)
    brow = {}
    for side, sx in (('L', -1), ('R', 1)):
        b = box_obj('Hugsy_Brow' + side, (0.075, 0.012, 0.016), bevel=0.01)
        finish(b); assign(b, mats['brow'])
        b.location = (sx * 0.15, -0.465, 1.065)
        b.rotation_euler = (0.1, 0, sx * 0.0)
        brow[side] = b

    # ---- flippers: pivot at shoulder, hang down & out
    flip = {}
    for side, sx in (('L', -1), ('R', 1)):
        f = build_mesh_obj('Hugsy_Flipper' + side, [
            ((sx * 0.52, 0.0, 0.72), (0.085, 0.17, 0.20), (0, sx * 0.10, 0)),
            ((sx * 0.55, 0.0, 0.54), (0.075, 0.15, 0.22), (0, sx * 0.18, 0)),
            ((sx * 0.58, 0.0, 0.40), (0.06, 0.11, 0.12), (0, sx * 0.22, 0)),
        ], seg=14, rings=10)
        facet(f, voxel=0.025, tris=260, lump=0.015, seed=seed + 5 + sx)
        assign(f, mats['wing'])
        set_pivot(f, (sx * SHOULDER[0], 0, SHOULDER[2]))
        flip[side] = f

    # ---- feet: flat orange, three stubby toes
    feet = {}
    for side, sx in (('L', -1), ('R', 1)):
        ft = build_mesh_obj('Hugsy_Foot' + side, [
            ((0, 0, 0), (0.16, 0.20, 0.045)),
            ((-0.095, -0.17, 0), (0.07, 0.10, 0.04)), ((0, -0.20, 0), (0.07, 0.11, 0.04)), ((0.095, -0.17, 0), (0.07, 0.10, 0.04)),
        ], seg=12, rings=8)
        facet(ft, voxel=0.018, tris=240, seed=seed + 8 + sx)
        assign(ft, mats['foot'])
        ft.data.transform(Matrix.Translation((0, 0, 0)))
        ft.location = (sx * 0.21, -0.33, 0.045)
        feet[side] = ft

    # ---- fabric tag on the right flank
    tag = box_obj('Hugsy_Tag', (0.012, 0.07, 0.10), bevel=0.008)
    finish(tag); assign(tag, mats['tag'])
    tag.location = (0.52, 0.12, 0.30); tag.rotation_euler = (0.0, 0.0, 0.0)
    tag.rotation_euler = (0.15, -0.35, 0.1)

    # ---- hierarchy
    for ob in (belly, face, flip['L'], flip['R'], feet['L'], feet['R'], tag, eyes['L'], eyes['R'], brows, ub):
        parent_keep(ob, body)
    parent_keep(lb, ub)
    parent_keep(brow['L'], brows); parent_keep(brow['R'], brows)
    body.location = Vector(location)
    bpy.context.view_layer.update()
    return body


if __name__ == '__main__':
    build_hugsy()
