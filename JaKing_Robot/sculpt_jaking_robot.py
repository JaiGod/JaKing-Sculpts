"""
JaKing Robot (JR-01 Aurum) - digital sculpt built in Blender.

Run headless:  blender -b -P sculpt_jaking_robot.py
Writes into ~/Documents/JaKing_Sculpts/JaKing_Robot/:
  JaKing_Robot.blend, JaKing_Robot.glb, render_hero.png, render_front.png, render_side.png, render_back.png

Process: block out armor forms -> fuse into one sculpt body with voxel remesh -> smooth like a
smooth brush -> sculpt layers (hammered metal + panel cuts) -> vertex-paint navy armor with gold
trim on ridges -> crisp hard-surface accents (crown, fins, wings, visor, emblem, sword, jets).
"""
import bpy, bmesh, math, os, random
from mathutils import Vector, Matrix

OUT = os.path.join(os.path.expanduser("~"), "Documents", "JaKing_Sculpts", "JaKing_Robot")
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_homefile(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.unit_settings.system = 'METRIC'


def lin(h):
    h = h.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple([(x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c])


NAVY, NAVY2, GOLD, CYAN = lin('#1f2c4a'), lin('#121a2e'), lin('#e0aa3e'), lin('#38e3ff')


def mat(name, color, metal=0.8, rough=0.3, emit=None, strength=0.0, vcol=None):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = strength
    if vcol:
        nt = m.node_tree
        ca = nt.nodes.new("ShaderNodeVertexColor"); ca.layer_name = vcol
        nt.links.new(ca.outputs["Color"], b.inputs["Base Color"])
        # gold trim (bright paint) is more metallic & glossier than the navy plates
        sep = nt.nodes.new("ShaderNodeSeparateColor"); nt.links.new(ca.outputs["Color"], sep.inputs[0])
        mr = nt.nodes.new("ShaderNodeMapRange"); mr.inputs["To Min"].default_value = 0.42; mr.inputs["To Max"].default_value = 0.18
        nt.links.new(sep.outputs[0], mr.inputs["Value"]); nt.links.new(mr.outputs[0], b.inputs["Roughness"])
        try:
            b.inputs["Coat Weight"].default_value = 0.35
        except Exception:
            pass
    return m


M_GOLD = mat("JK_Gold", GOLD, 1.0, 0.22)
M_NAVY = mat("JK_Navy", NAVY, 0.55, 0.5)
M_VISOR = mat("JK_Visor", (0.01, 0.08, 0.12), 0.2, 0.05, CYAN, 2.2)
M_BLADE = mat("JK_Blade", CYAN, 0.0, 0.2, CYAN, 3.5)
M_FLAME = mat("JK_Flame", CYAN, 0.0, 0.3, CYAN, 3.0)
M_NAVY2 = mat("JK_WingNavy", NAVY, 0.3, 0.6)


def obj_from_bm(name, bm, m=None):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); sc.collection.objects.link(o)
    if m:
        me.materials.append(m)
    return o


def box(name, size, loc, rot=(0, 0, 0), taper=1.0, m=None):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        k = taper if v.co.z > 0 else 1.0
        v.co = Vector((v.co.x * size[0] * k, v.co.y * size[1] * (k if taper != 1 else 1), v.co.z * size[2]))
    o = obj_from_bm(name, bm, m); o.location = loc; o.rotation_euler = rot
    return o


def ball(name, r, loc, scale=(1, 1, 1), m=None):
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=3, radius=r)
    for v in bm.verts:
        v.co = Vector((v.co.x * scale[0], v.co.y * scale[1], v.co.z * scale[2]))
    o = obj_from_bm(name, bm, m); o.location = loc
    return o


def cone(name, r1, r2, h, loc, rot=(0, 0, 0), segs=16, m=None, flat=1.0):
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=r1, radius2=r2, depth=h)
    for v in bm.verts:
        v.co.z += h / 2; v.co.y *= flat
    o = obj_from_bm(name, bm, m); o.location = loc; o.rotation_euler = rot
    return o


def capsule(name, a, b, r, m=None):
    a, b = Vector(a), Vector(b); d = b - a
    o = cone(name, r, r * 0.92, d.length, a, m=m, segs=20)
    o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    ball(name + "_capA", r, a); ball(name + "_capB", r * 0.92, b)
    return o


# ------------------------------------------------------------------ 1. block-out of the armored body
parts = []
P = parts.append
for s in (-1, 1):
    x = 0.15 * s
    P(box(f"Boot{s}", (0.15, 0.24, 0.17), (x, -0.025, 0.09), taper=0.85))
    P(box(f"Shin{s}", (0.11, 0.12, 0.30), (x, 0.0, 0.32), taper=1.15))
    P(capsule(f"Thigh{s}", (x, 0, 0.48), (x * 0.9, 0, 0.70), 0.065))
    P(ball(f"Knee{s}", 0.06, (x, -0.035, 0.47)))
    P(ball(f"Pauldron{s}", 0.125, (0.31 * s, 0, 1.13), (1.15, 1.05, 0.85)))
    P(capsule(f"UpperArm{s}", (0.31 * s, 0, 1.08), (0.34 * s, -0.02, 0.92), 0.05))
    P(box(f"Gauntlet{s}", (0.10, 0.10, 0.20), (0.35 * s, -0.04, 0.82), (0.12, 0.0, 0.08 * s), taper=1.25))
    P(ball(f"Fist{s}", 0.065, (0.36 * s, -0.06, 0.69), (1.0, 1.1, 1.0)))
P(box("Pelvis", (0.30, 0.18, 0.14), (0, 0, 0.77), taper=1.1))
P(box("Abdomen", (0.24, 0.16, 0.14), (0, 0.0, 0.88)))
P(box("Chest", (0.40, 0.24, 0.28), (0, -0.01, 1.05), taper=1.2))
P(capsule("Neck", (0, 0, 1.16), (0, 0, 1.24), 0.05))
P(box("Helmet", (0.25, 0.26, 0.20), (0, -0.005, 1.33), taper=0.78))
P(ball("HelmetDome", 0.125, (0, 0.0, 1.36), (1.0, 1.05, 0.75)))
P(box("Jaw", (0.17, 0.15, 0.08), (0, -0.035, 1.245), taper=1.2))
for o in list(sc.objects):
    if o.name.endswith(("_capA", "_capB")):
        parts.append(o)

bpy.ops.object.select_all(action='DESELECT')
for o in parts:
    o.select_set(True)
bpy.context.view_layer.objects.active = parts[0]
bpy.ops.object.join()
body = bpy.context.view_layer.objects.active
body.name = "JaKing_Robot_Sculpt"

# ------------------------------------------------------------------ 2. fuse + sculpt passes
rm = body.modifiers.new("Fuse_VoxelRemesh", 'REMESH'); rm.mode = 'VOXEL'; rm.voxel_size = 0.0055
sm = body.modifiers.new("SmoothBrush", 'SMOOTH'); sm.factor = 0.6; sm.iterations = 6
bpy.ops.object.modifier_apply(modifier=rm.name)
bpy.ops.object.modifier_apply(modifier=sm.name)
# hammered-metal surface + subtle panel cuts (sculpt layers)
t1 = bpy.data.textures.new("Hammered", 'CLOUDS'); t1.noise_scale = 0.12
d1 = body.modifiers.new("Sculpt_Hammered", 'DISPLACE'); d1.texture = t1; d1.strength = 0.0007; d1.texture_coords = 'OBJECT'
t2 = bpy.data.textures.new("Panels", 'VORONOI'); t2.noise_scale = 0.09; t2.distance_metric = 'DISTANCE'
d2 = body.modifiers.new("Sculpt_PanelCuts", 'DISPLACE'); d2.texture = t2; d2.strength = -0.0016; d2.texture_coords = 'OBJECT'
bpy.ops.object.modifier_apply(modifier=d1.name)
bpy.ops.object.modifier_apply(modifier=d2.name)
for p in body.data.polygons:
    p.use_smooth = True

# ------------------------------------------------------------------ 3. vertex paint: navy plates, gold trim on ridges & bands
me = body.data
col = me.color_attributes.new("ArmorPaint", 'FLOAT_COLOR', 'POINT')
bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
for v in bm.verts:
    # convexity: how far the vertex sits outside the average of its neighbours, along its normal
    if v.link_edges:
        avg = sum((e.other_vert(v).co for e in v.link_edges), Vector()) / len(v.link_edges)
        convex = (v.co - avg).dot(v.normal) / 0.0055
    else:
        convex = 0
    x, y, z = v.co
    gold = convex > 0.11
    band = (abs(z - 0.185) < 0.012) or (abs(z - 0.84) < 0.010 and abs(x) < 0.17) or (abs(z - 1.165) < 0.012 and abs(x) < 0.2)
    band |= (abs(z - 0.735) < 0.012 and abs(x) > 0.3)  # gauntlet cuffs
    dark = (abs(x) < 0.07 and 1.15 < z < 1.24) or (0.40 < z < 0.75 and abs(x) < 0.2 and abs(abs(x) - 0.135) < 0.03 and not gold)
    c = GOLD if (gold or band) else (NAVY2 if dark else NAVY)
    col.data[v.index].color = (*c, 1.0)
bm.free()
me.materials.append(mat("JK_ArmorPainted", NAVY, 0.85, 0.35, vcol="ArmorPaint"))

# ------------------------------------------------------------------ 4. crisp accents
acc = []
A = acc.append
# visor
A(box("Visor", (0.21, 0.04, 0.055), (0, -0.13, 1.335), (math.radians(-6), 0, 0), m=M_VISOR))
# crown spikes (JaKing crown) + side fins on helmet
A(cone("Crown_C", 0.035, 0.0, 0.13, (0, -0.02, 1.45), segs=4, m=M_GOLD))
for s in (-1, 1):
    A(cone(f"Crown_{s}", 0.028, 0.0, 0.09, (0.065 * s, -0.01, 1.43), (0, math.radians(18 * s), 0), segs=4, m=M_GOLD))
    A(cone(f"HelmetFin{s}", 0.05, 0.0, 0.16, (0.13 * s, 0.01, 1.33), (0, math.radians(55 * s), 0), segs=3, m=M_GOLD, flat=0.25))
    # back wings: swept flat blades
    w = box(f"Wing{s}", (0.42, 0.012, 0.11), (0.33 * s, 0.13, 1.18), (0, math.radians(-28 * s), math.radians(-14 * s)), taper=0.35, m=M_NAVY2)
    A(w)
    A(box(f"WingTrim{s}", (0.42, 0.016, 0.02), (0.33 * s, 0.128, 1.13), (0, math.radians(-28 * s), math.radians(-14 * s)), taper=0.35, m=M_GOLD))
    # jet boots: nozzle + flame
    A(cone(f"Nozzle{s}", 0.05, 0.065, 0.05, (0.15 * s, 0.03, -0.02), m=M_GOLD))
    A(cone(f"Flame{s}", 0.055, 0.0, 0.32, (0.15 * s, 0.03, -0.02), (math.pi, 0, 0), m=M_FLAME))
    A(box(f"ShoulderTrim{s}", (0.22, 0.20, 0.018), (0.30 * s, 0, 1.215), m=M_GOLD))
# chest emblem: gold ring + "JR"
A(cone("Emblem", 0.075, 0.075, 0.02, (0, -0.14, 1.06), (math.radians(90), 0, 0), segs=40, m=M_GOLD))
A(cone("EmblemInset", 0.058, 0.058, 0.022, (0, -0.142, 1.06), (math.radians(90), 0, 0), segs=40, m=M_NAVY))
td = bpy.data.curves.new("JR", 'FONT'); td.body = "JR"; td.align_x = 'CENTER'; td.align_y = 'CENTER'; td.size = 0.075; td.extrude = 0.006
tx = bpy.data.objects.new("Emblem_JR", td); sc.collection.objects.link(tx)
tx.location = (0, -0.158, 1.06); tx.rotation_euler = (math.radians(90), 0, 0); td.materials.append(M_GOLD)
# energy sword in the right fist
A(cone("SwordHilt", 0.018, 0.018, 0.14, (0.36, -0.06, 0.63), (0, math.radians(-14), 0), m=M_GOLD))
A(box("SwordGuard", (0.14, 0.035, 0.025), (0.375, -0.06, 0.70), (0, math.radians(-14), 0), m=M_GOLD))
A(cone("SwordBlade", 0.022, 0.006, 0.80, (0.38, -0.06, 0.715), (0, math.radians(-14), 0), segs=8, m=M_BLADE, flat=0.35))
for o in acc:
    for md in ():
        pass
    bv = o.modifiers.new("Bevel", 'BEVEL'); bv.width = 0.003; bv.segments = 2

# ------------------------------------------------------------------ 5. pose root, stage, lights, camera
root = bpy.data.objects.new("JaKing_Robot", None); sc.collection.objects.link(root)
for o in [body, tx] + acc:
    o.parent = root
floor = bpy.data.meshes.new("Stage")
bmf = bmesh.new(); bmesh.ops.create_circle(bmf, cap_ends=True, segments=64, radius=1.2); bmf.to_mesh(floor); bmf.free()
fl = bpy.data.objects.new("Stage", floor); sc.collection.objects.link(fl); fl.location.z = -0.36
floor.materials.append(mat("Stage", lin('#0b0f1a'), 0.6, 0.25))

w = bpy.data.worlds.new("JK_World"); sc.world = w
try:
    w.use_nodes = True
except Exception:
    pass
bg = w.node_tree.nodes.get("Background"); bg.inputs[0].default_value = (*lin('#0a0e18'), 1); bg.inputs[1].default_value = 0.6


def light(name, kind, loc, energy, color, size=1.0, target=(0, 0, 0.8)):
    ld = bpy.data.lights.new(name, kind); ld.energy = energy; ld.color = color
    if kind == 'AREA':
        ld.size = size
    o = bpy.data.objects.new(name, ld); sc.collection.objects.link(o); o.location = loc
    t = o.constraints.new('TRACK_TO'); tg = bpy.data.objects.get("LightTarget")
    if not tg:
        tg = bpy.data.objects.new("LightTarget", None); sc.collection.objects.link(tg); tg.location = target
    t.target = tg; t.track_axis = 'TRACK_NEGATIVE_Z'; t.up_axis = 'UP_Y'
    return o


light("Key", 'AREA', (-1.4, -1.8, 2.2), 900, lin('#fff1dc'), 1.6)
light("Rim_Gold", 'AREA', (1.6, 1.2, 1.6), 700, lin('#ffc061'), 1.0)
light("Rim_Cyan", 'AREA', (-1.5, 1.4, 1.2), 600, lin('#56dcff'), 1.0)
light("Fill", 'AREA', (1.8, -1.6, 0.6), 160, lin('#9fb6ff'), 2.0)

cd = bpy.data.cameras.new("Cam"); cd.lens = 50
cam = bpy.data.objects.new("Cam", cd); sc.collection.objects.link(cam); sc.camera = cam
ct = cam.constraints.new('TRACK_TO'); ct.target = bpy.data.objects["LightTarget"]; ct.track_axis = 'TRACK_NEGATIVE_Z'; ct.up_axis = 'UP_Y'
sc.render.resolution_x = sc.render.resolution_y = 1080
for a, v in (("taa_render_samples", 64), ("use_raytracing", True), ("use_gtao", True)):
    try:
        setattr(sc.eevee, a, v)
    except Exception:
        pass
sc.view_settings.view_transform = 'AgX'
try:
    sc.view_settings.look = 'AgX - Medium High Contrast'
except Exception:
    pass
sc.render.image_settings.file_format = 'PNG'

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "JaKing_Robot.blend"), compress=True)
for name, ang, h in (("hero", -35, 1.05), ("front", 0, 0.85), ("side", 90, 0.85), ("back", 180, 0.95)):
    r = 2.6
    cam.location = (r * math.sin(math.radians(ang)), -r * math.cos(math.radians(ang)), h)
    sc.render.filepath = os.path.join(OUT, f"render_{name}.png")
    bpy.ops.render.render(write_still=True)
cam.location = (2.6 * math.sin(math.radians(-35)), -2.6 * math.cos(math.radians(-35)), 1.05)
bpy.ops.wm.save_mainfile()
try:
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "JaKing_Robot.glb"), export_format='GLB', export_apply=True,
                              export_draco_mesh_compression_enable=True, export_cameras=False, export_lights=False)
except Exception as e:
    print("GLB export failed:", e)
open(os.path.join(OUT, "DONE.txt"), "w").write("ok %d verts" % len(body.data.vertices))
