"""
qm — 四角ポリゴン主体のモデリング用の関数集（run_script の中で `qm` として使える）

座標は Z が上、単位はメートル。関数はどれも、できたオブジェクトを返す。
面はすべて四角形で作り、穴は四角形の格子でふさぐ（頂点数が奇数の輪だけは三角形の扇になる）。
"""
from __future__ import annotations

import json
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

__all__ = ["material", "obj", "box", "cylinder", "lathe", "loft", "sweep", "tube", "quad_sphere", "cap_grid",
           "circle", "arc", "pivot", "copy", "bevel", "subsurf", "solidify", "expect", "HELP"]


# ---------------------------------------------------------------- マテリアルとオブジェクト

def material(name: str, color=None, metal: float | None = None, rough: float | None = None,
             tile: float | None = None, alpha: float | None = None):
    """マテリアルを作る（同じ名前があればそれを使う）。textures の画像と同じ名前なら、その画像が貼られる。
    color: (r, g, b) 0〜1 / metal: 金属らしさ / rough: 粗さ / tile: 画像1枚が何メートル分か / alpha: 透明度"""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    if m.node_tree is None:  # Blender 4 以前。5 では常にノードがある
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    if color is not None:
        b.inputs["Base Color"].default_value = (*color[:3], 1)
    if metal is not None:
        b.inputs["Metallic"].default_value = metal
    if rough is not None:
        b.inputs["Roughness"].default_value = rough
    if alpha is not None:
        b.inputs["Alpha"].default_value = alpha
    if tile is not None:
        m["tile"] = float(tile)
    return m


def obj(name: str, bm, material=None, location=(0, 0, 0)):
    """bmesh からオブジェクトを作ってシーンに置く（bm はこの中で解放する）。material は1つかリスト"""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in (material if isinstance(material, (list, tuple)) else [material] if material else []):
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    ob.location = location
    bpy.context.scene.collection.objects.link(ob)
    return ob


def _origin_shift(origin: str, h: float) -> float:
    return {"bottom": 0.0, "center": -h / 2, "top": -h}[origin]


# ---------------------------------------------------------------- 基本の形

def box(name: str, size=(1, 1, 1), segs=(1, 1, 1), origin: str = "bottom", material=None,
        location=(0, 0, 0), bevel: float | None = None):
    """箱。size=(幅X, 奥行Y, 高さZ)、segs=各方向の分割数、origin="bottom" なら底面の中心が原点。
    bevel を指定すると、その幅で角を丸める（Bevel モディファイア、2 分割）"""
    w, d, h = size
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(w, d, h), verts=bm.verts)
    bmesh.ops.translate(bm, vec=(0, 0, h / 2 + _origin_shift(origin, h)), verts=bm.verts)
    for axis, n, length in ((0, segs[0], w), (1, segs[1], d), (2, segs[2], h)):
        lo = -length / 2 if axis != 2 else _origin_shift(origin, h)
        for k in range(1, int(n)):
            co = [0, 0, 0]
            co[axis] = lo + length * k / n
            no = [0, 0, 0]
            no[axis] = 1
            bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=co, plane_no=no)
    ob = obj(name, bm, material, location)
    if bevel:
        globals()["bevel"](ob, bevel)
    return ob


def circle(n: int, r: float = 1.0, start: float = 0.0):
    """XY 平面の円周の点 [(x, y), ...]（反時計回り、n 個）"""
    return [(r * math.cos(start + 2 * math.pi * i / n), r * math.sin(start + 2 * math.pi * i / n)) for i in range(n)]


def arc(r: float, a0: float, a1: float, n: int):
    """円弧の点 [(x, y), ...]（角度は度、a0 から a1 まで n 分割 = n+1 点）"""
    return [(r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), r * math.sin(math.radians(a0 + (a1 - a0) * i / n)))
            for i in range(n + 1)]


def cap_grid(bm, ring, relax: int = 30):
    """閉じた頂点の輪（BMVert のリスト、順番どおり）を、四角形の格子でふさぐ。作った面を返す。
    頂点数が偶数なら四角形だけ、奇数なら中心から三角形の扇になる"""
    n = len(ring)
    if n < 3:
        return []
    if n == 4:
        return [bm.faces.new(ring)]
    if n % 2:
        c = bm.verts.new(sum((v.co for v in ring), Vector()) / n)
        return [bm.faces.new((ring[i], ring[(i + 1) % n], c)) for i in range(n)]
    half = n // 2
    P = [v.co.copy() for v in ring]
    seg = [(P[(i + 1) % n] - P[i]).length for i in range(n)]

    def turn(i):  # 頂点 i での曲がり具合（角ほど大きい）
        a, b = P[i] - P[i - 1], P[(i + 1) % n] - P[i]
        if a.length < 1e-12 or b.length < 1e-12:
            return 0.0
        return a.angle(b)

    def side(i, k):
        return sum(seg[(i + t) % n] for t in range(k))

    best = None
    for s in range(n):
        for a in range(1, half):
            b = half - a
            c = [s, s + a, s + a + b, s + 2 * a + b]
            L = [side(c[0], a), side(c[1], b), side(c[2], a), side(c[3], b)]
            per = sum(L) or 1.0
            score = (abs(L[0] - L[2]) + abs(L[1] - L[3])) / per - 0.5 * sum(turn(x % n) for x in c)
            # 1マスがなるべく正方形に近い分け方を少し優先する
            score += 0.2 * abs(math.log(max(L[0] / a, 1e-9) / max(L[1] / b, 1e-9)))
            if best is None or score < best[0]:
                best = (score, s, a, b)
    _, s, a, b = best
    R = lambda k: ring[(s + k) % n]
    g = {}
    for i in range(a + 1):
        g[i, 0] = R(i)
        g[a - i, b] = R(a + b + i)
    for j in range(b + 1):
        g[a, j] = R(a + j)
        g[0, b - j] = R(2 * a + b + j)
    co = lambda i, j: g[i, j].co
    for i in range(1, a):
        for j in range(1, b):
            u, v = i / a, j / b
            p = ((1 - v) * co(i, 0) + v * co(i, b) + (1 - u) * co(0, j) + u * co(a, j)
                 - ((1 - u) * (1 - v) * co(0, 0) + u * (1 - v) * co(a, 0) + (1 - u) * v * co(0, b) + u * v * co(a, b)))
            g[i, j] = bm.verts.new(p)
    for _ in range(relax):
        for i in range(1, a):
            for j in range(1, b):
                g[i, j].co = (co(i - 1, j) + co(i + 1, j) + co(i, j - 1) + co(i, j + 1)) / 4
    return [bm.faces.new((g[i, j], g[i + 1, j], g[i + 1, j + 1], g[i, j + 1])) for i in range(a) for j in range(b)]


def loft(name: str, sections, closed: bool = True, cap: bool = True, loop: bool = False, material=None,
         location=(0, 0, 0)):
    """断面の輪（同じ点数の [(x, y, z), ...]）を順に四角形でつなぐ。cap で両端を四角形の格子でふさぐ。
    closed=False なら断面を開いた線として扱う（板状になる）。loop=True なら最後の断面を最初につなぐ（輪になる）"""
    n = len(sections[0])
    if any(len(s) != n for s in sections):
        raise ValueError("loft: 断面ごとの点数をそろえてください")
    bm = bmesh.new()
    rings = [[bm.verts.new(p) for p in s] for s in sections]
    pairs = list(zip(rings, rings[1:])) + ([(rings[-1], rings[0])] if loop else [])
    for A, B in pairs:
        for i in range(n if closed else n - 1):
            j = (i + 1) % n
            bm.faces.new((A[i], A[j], B[j], B[i]))
    if closed and cap and not loop:
        cap_grid(bm, rings[0])
        cap_grid(bm, rings[-1])
    return obj(name, bm, material, location)


def lathe(name: str, profile, seg: int = 16, cap: bool = True, material=None, location=(0, 0, 0)):
    """回転体。profile=[(半径, 高さ), ...] を下から上へ。Z 軸まわりに回す。
    半径 0 の点は極（三角形）になる。端が半径>0 なら cap で四角形の格子でふさぐ（seg は偶数に）"""
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        if abs(r) < 1e-9:
            rings.append([bm.verts.new((0, 0, z))])
        else:
            rings.append([bm.verts.new((x, y, z)) for x, y in circle(seg, r)])
    for A, B in zip(rings, rings[1:]):
        for i in range(seg):
            j = (i + 1) % seg
            if len(A) == 1 and len(B) == 1:
                continue
            if len(A) == 1:
                bm.faces.new((A[0], B[i], B[j]))
            elif len(B) == 1:
                bm.faces.new((A[i], A[j], B[0]))
            else:
                bm.faces.new((A[i], A[j], B[j], B[i]))
    if cap:
        for ring in (rings[0], rings[-1]):
            if len(ring) > 1:
                cap_grid(bm, ring)
    return obj(name, bm, material, location)


def cylinder(name: str, r: float = 0.5, h: float = 1.0, seg: int = 16, rows: int = 1, axis: str = "Z",
             origin: str = "bottom", material=None, location=(0, 0, 0)):
    """円柱。axis="Z" なら origin="bottom" で底面の中心が原点。axis="X" / "Y" のときは中心が原点"""
    z0 = _origin_shift(origin, h) if axis == "Z" else -h / 2
    ob = lathe(name, [(r, z0 + h * k / rows) for k in range(rows + 1)], seg, True, material)
    if axis != "Z":
        rot = Matrix.Rotation(math.radians(90), 4, "Y" if axis == "X" else "X")
        ob.data.transform(rot)
    ob.location = location
    return ob


def quad_sphere(name: str, size=1.0, n: int = 4, origin: str = "center", material=None, location=(0, 0, 0)):
    """四角形だけの球（立方体を膨らませたもの）。size は直径か (X, Y, Z) の大きさ。n は1面あたりの分割数"""
    sx, sy, sz = (size, size, size) if isinstance(size, (int, float)) else size
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    if n > 1:
        bmesh.ops.subdivide_edges(bm, edges=bm.edges, cuts=n - 1, use_grid_fill=True)
    for v in bm.verts:  # tan で等間隔に近づけてから球に
        q = Vector(math.tan(c * math.pi / 4) for c in v.co)
        v.co = q.normalized()
    # 分割数が奇数だと極に頂点がなく少し小さくなるので、外接箱がちょうど size になるようにそろえる
    ext = [max(v.co[i] for v in bm.verts) for i in range(3)]
    bmesh.ops.scale(bm, vec=(sx / 2 / ext[0], sy / 2 / ext[1], sz / 2 / ext[2]), verts=bm.verts)
    if origin == "bottom":
        bmesh.ops.translate(bm, vec=(0, 0, sz / 2), verts=bm.verts)
    return obj(name, bm, material, location)


def sweep(name: str, path, profile, up=None, closed_path: bool = False, cap: bool = True, scale=None,
          material=None):
    """断面（2D の点 [(u, v), ...]、反時計回り）を、道すじ [(x, y, z), ...] に沿って並べた形。
    断面の u は道すじの横方向、v は up 方向（up を省くと、なるべくねじれない向きを自動で選ぶ）。
    closed_path=True なら道すじを輪にする（箱に巻く帯・額縁・リング）。角は留め継ぎ（マイター）でつなぐ。
    scale は数値か、点ごとの倍率のリスト（先細りの管など）"""
    pts = [Vector(p) for p in path]
    n = len(pts)
    sc = scale if isinstance(scale, (list, tuple)) else [scale or 1.0] * n
    tans, miter = [], []
    for i in range(n):
        if closed_path or 0 < i < n - 1:
            a = (pts[i] - pts[i - 1]).normalized()
            b = (pts[(i + 1) % n] - pts[i]).normalized()
            t = (a + b).normalized() if (a + b).length > 1e-9 else b
            miter.append(1.0 / max(math.cos(a.angle(b) / 2), 0.2))
        else:
            t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
            miter.append(1.0)
        tans.append(t)
    if up is not None:
        upv = Vector(up).normalized()
        bins = [(upv - t * upv.dot(t)).normalized() for t in tans]
    else:
        ref = Vector((0, 0, 1)) if abs(tans[0].z) < 0.9 else Vector((1, 0, 0))
        b0 = (ref - tans[0] * ref.dot(tans[0])).normalized()
        bins = [b0]
        for t in tans[1:]:  # 前の向きを引き継いで、ねじれを抑える
            b = bins[-1] - t * bins[-1].dot(t)
            bins.append(b.normalized() if b.length > 1e-9 else bins[-1])
    sections = []
    for i, p in enumerate(pts):
        side = tans[i].cross(bins[i]).normalized()
        sections.append([p + (side * u * miter[i] + bins[i] * v) * sc[i] for u, v in profile])
    return loft(name, sections, closed=True, cap=cap, loop=closed_path, material=material)


def tube(name: str, points, radius=0.02, seg: int = 8, cap: bool = True, material=None):
    """線（[(x, y, z), ...]）に沿った丸い管。radius は数値か、点ごとの半径のリスト。取っ手・パイプ・つるなどに"""
    rad = radius if isinstance(radius, (list, tuple)) else [radius] * len(points)
    return sweep(name, points, circle(seg, 1.0), cap=cap, scale=rad, material=material)


# ---------------------------------------------------------------- 配置と仕上げ

def pivot(objects, point, rotate=(0, 0, 0)):
    """オブジェクトを、point を中心に回す（度、X→Y→Z の順）。蝶番で開くふた、傾けた脚などに"""
    objects = objects if isinstance(objects, (list, tuple)) else [objects]
    p = Vector(point)
    rot = (Matrix.Rotation(math.radians(rotate[2]), 4, "Z") @ Matrix.Rotation(math.radians(rotate[1]), 4, "Y")
           @ Matrix.Rotation(math.radians(rotate[0]), 4, "X"))
    m = Matrix.Translation(p) @ rot @ Matrix.Translation(-p)
    bpy.context.view_layer.update()  # 置いたばかりの位置を matrix_world に反映してから回す
    for ob in objects:
        ob.matrix_world = m @ ob.matrix_world
    return objects


def copy(ob, name: str, location=None, rotate=None, scale=None):
    """オブジェクトを複製する（メッシュも別に持つ）。rotate は度"""
    new = ob.copy()
    new.data = ob.data.copy()
    new.name = new.data.name = name
    bpy.context.scene.collection.objects.link(new)
    if location is not None:
        new.location = location
    if rotate is not None:
        new.rotation_euler = [math.radians(a) for a in rotate]
    if scale is not None:
        new.scale = scale
    return new


def bevel(ob, width: float = 0.01, segments: int = 2, angle: float = 30.0):
    """角を丸める（Bevel モディファイア。angle 度より鋭い辺だけ）"""
    md = ob.modifiers.new("Bevel", "BEVEL")
    md.width, md.segments, md.limit_method = width, segments, "ANGLE"
    md.angle_limit = math.radians(angle)
    return ob


def subsurf(ob, levels: int = 1):
    """なめらかにする（Subdivision Surface。面が 4^levels 倍になる）"""
    md = ob.modifiers.new("Subdivision", "SUBSURF")
    md.levels = md.render_levels = levels
    return ob


def solidify(ob, thickness: float = 0.01):
    """板に厚みを付ける（Solidify モディファイア）"""
    md = ob.modifiers.new("Solidify", "SOLIDIFY")
    md.thickness = thickness
    return ob


def expect(target: str = "*", size=None, floating: bool = False, tol: float = 0.03):
    """仕上がりの寸法を宣言しておくと、サーバーが実際の寸法と照合する。
    target: オブジェクト名か "*"（全体）/ size: (幅X, 奥行Y, 高さZ)。分からない方向は None
    floating=True: 地面にも他の部品にも接していなくてよい（吊り下げる物など）/ tol: 許す差（割合）"""
    sc = bpy.context.scene
    items = json.loads(sc.get("qm_expect", "[]"))
    items.append({"target": target, "size": list(size) if size else None, "floating": floating, "tol": tol})
    sc["qm_expect"] = json.dumps(items)


HELP = """qm（四角ポリゴン主体のモデリング用の関数。run_script の中でそのまま使える。Z が上、メートル単位）

形を作る（どれもオブジェクトを返す。material は qm.material(...) の戻り値か、そのリスト）
- qm.box(name, size=(w, d, h), segs=(nx, ny, nz), origin="bottom"|"center", material, location, bevel=幅)
- qm.cylinder(name, r, h, seg=16, rows=1, axis="Z"|"X"|"Y", origin="bottom", material, location)   フタも四角形の格子
- qm.lathe(name, [(半径, 高さ), ...], seg=16, cap=True, material)   Z 軸まわりの回転体（壺・瓶・脚・取っ手の玉など）
- qm.loft(name, [断面の輪, ...], closed=True, cap=True, material)   断面（同じ点数の [(x,y,z),...]）を順につなぐ
- qm.tube(name, [(x,y,z), ...], radius=0.02 または点ごとのリスト, seg=8)   線に沿った管（取っ手・パイプ・つる）
- qm.sweep(name, 道すじ[(x,y,z),...], 断面[(u,v),...], up=(0,0,1), closed_path=False)   断面を道すじに沿って並べる。
    closed_path=True で輪（箱に巻く帯・額縁）。角は留め継ぎ。断面 u は道すじの横、v は up 方向
- qm.quad_sphere(name, size=直径 または (X,Y,Z), n=4, origin="center"|"bottom")   四角形だけの球・楕円体
- qm.cap_grid(bm, [BMVert の輪])   自分で組んだ bmesh の穴を四角形の格子でふさぐ（頂点数は偶数に）
- qm.obj(name, bm, material)   自分で組んだ bmesh をオブジェクトにする（法線もそろえる）
- 点の補助: qm.circle(n, r) → [(x,y)...]、qm.arc(r, 開始角, 終了角, 分割数) → [(x,y)...]（度）

置く・仕上げる
- qm.pivot(objs, point=(x,y,z), rotate=(rx,ry,rz))   point を軸に回す（蝶番のふた・傾けた脚。度）
- qm.copy(ob, name, location=, rotate=, scale=)   複製（左右の脚など）
- qm.bevel(ob, width, segments=2) / qm.subsurf(ob, levels=1) / qm.solidify(ob, thickness)
- qm.material(name, color=(r,g,b), metal=, rough=, tile=画像1枚のメートル, alpha=)

確かめる
- qm.expect("Body", size=(0.9, 0.55, 0.42))   寸法を宣言 → サーバーが照合して、違えば問題として返す
- qm.expect("*", size=(None, None, 1.2))   全体の高さだけ宣言、のようにも書ける
- qm.expect("Lamp", floating=True)   宙に浮いていてよい部品（それ以外は浮いていると指摘される）

例:
  wood = qm.material("Wood", tile=0.6)
  body = qm.box("Body", (0.9, 0.55, 0.42), material=wood, bevel=0.012)
  lid = qm.loft("Lid", [[(x, y, 0.42 + z) for y, z in sec] for x in (-0.45, 0.45)], material=wood)
  qm.pivot(lid, point=(0, 0.275, 0.42), rotate=(-35, 0, 0))
  qm.expect("Body", size=(0.9, 0.55, 0.42))
"""
