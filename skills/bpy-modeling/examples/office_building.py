# 8階建てのオフィスビル（コンクリートの躯体、レンガの腰壁、ガラスの窓、屋上はパラペット付き）
import bmesh, math

BAY_X, NX = 4.0, 5        # 間口 20m（4m × 5スパン）
BAY_Y, NY = 3.5, 4        # 奥行 14m（3.5m × 4スパン）
H1, HF, FLOORS = 4.5, 3.5, 8
SPANDREL = 1.1           # 2階以上の腰壁の高さ
W, D = BAY_X * NX, BAY_Y * NY

# 外周の頂点（反時計回り）。スパンごとに柱の位置で区切る
ring = []
for i in range(NX):
    ring.append((-W/2 + i*BAY_X, -D/2))
for j in range(NY):
    ring.append((W/2, -D/2 + j*BAY_Y))
for i in range(NX):
    ring.append((W/2 - i*BAY_X, D/2))
for j in range(NY):
    ring.append((-W/2, D/2 - j*BAY_Y))

# 高さの区切り：1階は1段、2階以上は「腰壁」と「窓」の2段
levels, kinds = [0.0], []
levels.append(H1); kinds.append("ground")
for k in range(1, FLOORS):
    base = H1 + HF * (k - 1)
    levels += [base + SPANDREL, base + HF]
    kinds += ["spandrel", "window"]
bm = bmesh.new()
CONCRETE, BRICK, GLASS = 0, 1, 2
rings = [[bm.verts.new((x, y, z)) for x, y in ring] for z in levels]
n = len(ring)
walls = []  # (種類, 面)
for k in range(len(levels) - 1):
    a, b = rings[k], rings[k+1]
    for i in range(n):
        j = (i + 1) % n
        walls.append((kinds[k], bm.faces.new((a[i], a[j], b[j], b[i]))))

# 床と屋根：外周を同じ割り付けの格子でふさぐ（すべて四角形）
def cap(r, z, up):
    grid = {}
    for i in range(NX + 1):
        for j in range(NY + 1):
            x, y = -W/2 + i*BAY_X, -D/2 + j*BAY_Y
            if i in (0, NX) or j in (0, NY):
                grid[i, j] = next(v for v in r if abs(v.co.x - x) < 1e-6 and abs(v.co.y - y) < 1e-6)
            else:
                grid[i, j] = bm.verts.new((x, y, z))
    faces = []
    for i in range(NX):
        for j in range(NY):
            q = (grid[i, j], grid[i+1, j], grid[i+1, j+1], grid[i, j+1])
            faces.append(bm.faces.new(q if up else q[::-1]))
    return faces

cap(rings[0], 0.0, up=False)
roof = cap(rings[-1], levels[-1], up=True)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

# 窓：壁のスパンごとに内側へ縁を取り、0.25m 引っ込める。1階は大きめ（エントランス・店舗）
for kind, f in walls:
    if kind == "spandrel":
        f.material_index = BRICK
        continue  # 腰壁はそのまま（外壁の面）
    t = 0.25 if kind == "ground" else 0.3
    bmesh.ops.inset_individual(bm, faces=[f], thickness=t, depth=0)
    nrm = f.normal.copy()
    bmesh.ops.translate(bm, verts=f.verts, vec=-nrm * (0.35 if kind == "ground" else 0.2))
    f.material_index = GLASS  # 引っ込めた内側の面がガラス

# 屋上のパラペット：屋根の縁を内側に 0.4m 取り、内側を 1.0m 下げる
bmesh.ops.inset_region(bm, faces=roof, thickness=0.4, depth=0)
bmesh.ops.translate(bm, verts=list({v for f in roof for v in f.verts}), vec=(0, 0, -1.0))

me = bpy.data.meshes.new("Building")
for name in ("Concrete", "Brick"):
    me.materials.append(bpy.data.materials.get(name) or bpy.data.materials.new(name))
glass = bpy.data.materials.new("Glass")
bsdf = glass.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.10, 0.16, 0.22, 1)
bsdf.inputs["Roughness"].default_value = 0.05
bsdf.inputs["Metallic"].default_value = 0.6
me.materials.append(glass)
bm.to_mesh(me); bm.free()
bpy.context.scene.collection.objects.link(bpy.data.objects.new("Building", me))

# 屋上の設備（塔屋）：箱を2つ
def box(name, cx, cy, z0, sx, sy, sz):
    m = bpy.data.meshes.new(name); b = bmesh.new()
    bmesh.ops.create_cube(b, size=1.0)
    bmesh.ops.scale(b, vec=(sx, sy, sz), verts=b.verts)
    bmesh.ops.translate(b, vec=(cx, cy, z0 + sz/2), verts=b.verts)
    b.to_mesh(m); b.free()
    m.materials.append(bpy.data.materials["Concrete"])
    bpy.context.scene.collection.objects.link(bpy.data.objects.new(name, m))

roof_z = levels[-1] - 1.0
box("Roof_Stair", -5.0, 2.0, roof_z, 5.0, 4.0, 3.2)
box("Roof_Unit", 5.0, -1.5, roof_z, 3.0, 2.0, 1.5)
