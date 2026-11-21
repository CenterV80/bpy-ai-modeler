"""
qm — 四角ポリゴン主体のモデリング用の関数集（run_script の中で `qm` として使える）

座標は Z が上、単位はメートル。関数はどれも、できたオブジェクトを返す。
面はすべて四角形で作り、穴は四角形の格子でふさぐ（頂点数が奇数の輪だけは三角形の扇になる）。
"""
from __future__ import annotations

import json
import math
import re

import bmesh
import bpy
from mathutils import Matrix, Vector

__all__ = ["material", "obj", "box", "cylinder", "lathe", "loft", "sweep", "tube", "quad_sphere", "cap_grid",
           "circle", "arc", "polygon", "helix", "airfoil", "ring", "nut", "washer", "bolt", "gear", "flange", "wheel",
           "pivot", "orient", "copy", "array", "radial", "mirror", "bevel", "subsurf", "solidify", "expect", "units", "MM", "METRIC", "HELP"]


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


def lathe(name: str, profile, seg: int = 16, cap: bool = True, closed: bool = False, material=None, location=(0, 0, 0)):
    """回転体。profile=[(半径, 高さ), ...] を下から上へ。Z 軸まわりに回す。
    半径 0 の点は極（三角形）になる。端が半径>0 なら cap で四角形の格子でふさぐ（seg は偶数に）。
    closed=True なら断面を閉じた輪として扱い、ドーナツ状にする（タイヤ・Oリング・取っ手の輪）"""
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        if abs(r) < 1e-9:
            rings.append([bm.verts.new((0, 0, z))])
        else:
            rings.append([bm.verts.new((x, y, z)) for x, y in circle(seg, r)])
    pairs = list(zip(rings, rings[1:])) + ([(rings[-1], rings[0])] if closed else [])
    for A, B in pairs:
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
    if cap and not closed:
        for ring in (rings[0], rings[-1]):
            if len(ring) > 1:
                cap_grid(bm, ring)
    return obj(name, bm, material, location)


def cylinder(name: str, r: float = 0.5, h: float = 1.0, seg: int = 16, rows: int = 1, axis: str = "Z",
             origin: str = "bottom", material=None, location=(0, 0, 0)):
    """円柱。axis="Z" なら origin="bottom" で底面の中心が原点。axis="X" / "Y" のときは中心が原点"""
    z0 = _origin_shift(origin, h) if axis == "Z" else -h / 2
    ob = lathe(name, [(r, z0 + h * k / rows) for k in range(rows + 1)], seg=seg, cap=True, material=material)
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


# ---------------------------------------------------------------- 部品

# メートルねじ（並目）の寸法 [m]。
# s（六角の二面幅）と m（ナットの高さ）は ISO 4032 の値（最大値）。k（ボルト頭の高さ）と pitch（並目ピッチ）は
# ISO 4017 / ISO 261 の参考値（規格で要確認）。ここにない寸法は、bolt / nut の引数で直接指定する
METRIC = {
    "M3":  {"d": 0.003, "s": 0.0055, "m": 0.0024, "k": 0.002,  "pitch": 0.0005},
    "M4":  {"d": 0.004, "s": 0.007,  "m": 0.0032, "k": 0.0028, "pitch": 0.0007},
    "M5":  {"d": 0.005, "s": 0.008,  "m": 0.0047, "k": 0.0035, "pitch": 0.0008},
    "M6":  {"d": 0.006, "s": 0.010,  "m": 0.0052, "k": 0.004,  "pitch": 0.001},
    "M8":  {"d": 0.008, "s": 0.013,  "m": 0.0068, "k": 0.0053, "pitch": 0.00125},
    "M10": {"d": 0.010, "s": 0.016,  "m": 0.0084, "k": 0.0064, "pitch": 0.0015},
    "M12": {"d": 0.012, "s": 0.018,  "m": 0.0108, "k": 0.0075, "pitch": 0.00175},
}


def _spec(size, **over):
    if isinstance(size, str):
        if size.upper() not in METRIC:
            raise ValueError(f"{size} の寸法表がありません（{', '.join(METRIC)}）。d=, s=, m=, k= を数値で指定してください")
        sp = dict(METRIC[size.upper()])
    else:  # 直径を数値で渡したときは、おおよその比率で決める
        d = float(size)
        sp = {"d": d, "s": 1.6 * d, "m": 0.85 * d, "k": 0.65 * d, "pitch": 0.15 * d}
    sp.update({k: v for k, v in over.items() if v is not None})
    return sp


def polygon(n: int, r: float, start: float = 0.0, per_edge: int = 1):
    """正 n 角形の頂点 [(x, y), ...]（r は外接円の半径、反時計回り）。per_edge で各辺を分割する"""
    corners = [(r * math.cos(start + 2 * math.pi * i / n), r * math.sin(start + 2 * math.pi * i / n)) for i in range(n)]
    out = []
    for i in range(n):
        (x0, y0), (x1, y1) = corners[i], corners[(i + 1) % n]
        out += [(x0 + (x1 - x0) * k / per_edge, y0 + (y1 - y0) * k / per_edge) for k in range(per_edge)]
    return out


def airfoil(chord: float = 1.0, thickness: float = 0.12, camber: float = 0.0, camber_pos: float = 0.4, n: int = 12):
    """翼の断面（NACA 4 桁の式）の点 [(u, v), ...]。u は前縁 0 → 後縁 chord、v は厚み方向。点は 2n 個（偶数）。
    camber を負にすると下向きに反った翼（F1 のウイングのように下に押し付ける）になる"""
    def yt(x):
        return 5 * thickness * (0.2969 * math.sqrt(x) - 0.126 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1036 * x ** 4)

    def yc(x):
        m, p = camber, camber_pos
        if m == 0:
            return 0.0
        return m / p ** 2 * (2 * p * x - x * x) if x < p else m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * x - x * x)

    xs = [0.5 * (1 - math.cos(math.pi * i / n)) for i in range(n + 1)]   # 前縁・後縁を細かく
    upper = [(x, yc(x) + yt(x)) for x in reversed(xs)]                     # 後縁 → 前縁
    lower = [(x, yc(x) - yt(x)) for x in xs[1:-1]]                         # 前縁の次 → 後縁の手前
    return [(x * chord, y * chord) for x, y in upper + lower]


def helix(r: float, pitch: float, turns: float, per_turn: int = 16, z0: float = 0.0):
    """らせんの点 [(x, y, z), ...]（Z 軸まわり）。qm.tube と組み合わせて、ばね・コイル・ねじの山に"""
    n = max(2, int(round(turns * per_turn)))
    return [(r * math.cos(2 * math.pi * t / per_turn), r * math.sin(2 * math.pi * t / per_turn), z0 + pitch * t / per_turn)
            for t in range(n + 1)]


def _annulus(bm, outer, inner, z0: float, z1: float):
    """同じ点数の外側・内側の輪（2D）で、穴のあいた立体（上下・外壁・内壁）を四角形で作る"""
    O0 = [bm.verts.new((x, y, z0)) for x, y in outer]
    O1 = [bm.verts.new((x, y, z1)) for x, y in outer]
    I0 = [bm.verts.new((x, y, z0)) for x, y in inner]
    I1 = [bm.verts.new((x, y, z1)) for x, y in inner]
    n = len(outer)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((O0[i], O0[j], O1[j], O1[i]))   # 外壁
        bm.faces.new((I0[j], I0[i], I1[i], I1[j]))   # 内壁
        bm.faces.new((O1[i], O1[j], I1[j], I1[i]))   # 上
        bm.faces.new((O0[j], O0[i], I0[i], I0[j]))   # 下


def _place(objects, location=(0, 0, 0), rotate=None):
    """原点を基準に回してから location へ動かす（rotate は度）"""
    objects = objects if isinstance(objects, (list, tuple)) else [objects]
    if rotate:
        pivot(objects, (0, 0, 0), rotate)
    bpy.context.view_layer.update()
    for ob in objects:
        ob.matrix_world = Matrix.Translation(Vector(location)) @ ob.matrix_world
    return objects


def ring(name: str, r_out: float, r_in: float, h: float, seg: int = 16, origin: str = "bottom", material=None,
         location=(0, 0, 0), rotate=None):
    """穴のあいた円柱（カラー・座金・管の一部・リム）。Z 方向に高さ h。rotate（度）で向きを変える"""
    bm = bmesh.new()
    z0 = _origin_shift(origin, h)
    _annulus(bm, circle(seg, r_out), circle(seg, r_in), z0, z0 + h)
    ob = obj(name, bm, material)
    return _place(ob, location, rotate)[0]


def nut(name: str, size="M8", s=None, m=None, material=None, location=(0, 0, 0), rotate=None):
    """六角ナット（ISO 4032 の寸法。size は "M3"〜"M12" か直径の数値）。底面の中心が原点、穴は Z 方向"""
    sp = _spec(size, s=s, m=m)
    R = sp["s"] / 2 / math.cos(math.pi / 6)
    bm = bmesh.new()
    _annulus(bm, polygon(6, R, per_edge=2), circle(12, sp["d"] / 2), 0.0, sp["m"])
    return _place(obj(name, bm, material), location, rotate)[0]


def washer(name: str, size="M8", material=None, location=(0, 0, 0), rotate=None):
    """平座金（寸法はおおよそ。内径 ≒ 1.08d、外径 ≒ 2d、厚み ≒ 0.18d）"""
    d = _spec(size)["d"]
    return ring(name, d, d * 0.54, d * 0.18, seg=16, material=material, location=location, rotate=rotate)


def bolt(name: str, size="M8", length: float = 0.03, thread: bool = False, s=None, k=None, material=None,
         location=(0, 0, 0), rotate=None):
    """六角ボルト（頭は上、軸は -Z へ length）。原点は頭の座面の中心。thread=True でねじ山の見た目を付ける。
    寸法は size（"M3"〜"M12" か直径の数値）から。向きは rotate（度）で変える"""
    sp = _spec(size, s=s, k=k)
    d, R = sp["d"], sp["s"] / 2 / math.cos(math.pi / 6)
    bm = bmesh.new()
    hex_pts, circ = polygon(6, R, per_edge=2), circle(12, d / 2)
    top = [bm.verts.new((x, y, sp["k"])) for x, y in hex_pts]
    bot = [bm.verts.new((x, y, 0.0)) for x, y in hex_pts]
    rings = [[bm.verts.new((x, y, 0.0)) for x, y in circ]]
    if thread:
        p = sp["pitch"]
        steps = max(2, int(length / (p / 2)))
        for t in range(1, steps + 1):
            z = -length * t / steps
            rr = d / 2 * (1.0 if t % 2 == 0 else 0.9)
            if t == steps:
                rr = d / 2 * 0.85  # 先端の面取り
            rings.append([bm.verts.new((x * rr / (d / 2), y * rr / (d / 2), z)) for x, y in circ])
    else:
        rings.append([bm.verts.new((x * 0.9, y * 0.9, -length)) for x, y in circ])
        rings.insert(1, [bm.verts.new((x, y, -length + d * 0.1)) for x, y in circ])
    for i in range(12):
        j = (i + 1) % 12
        bm.faces.new((bot[i], bot[j], top[j], top[i]))                  # 頭の側面
        bm.faces.new((bot[j], bot[i], rings[0][i], rings[0][j]))        # 頭の座面
        for A, B in zip(rings, rings[1:]):
            bm.faces.new((A[j], A[i], B[i], B[j]))                      # 軸
    cap_grid(bm, top)
    cap_grid(bm, rings[-1])
    return _place(obj(name, bm, material), location, rotate)[0]


def gear(name: str, teeth: int = 20, module: float = 0.002, width: float = 0.01, bore=None, material=None,
         location=(0, 0, 0), rotate=None):
    """平歯車（歯は台形で近似）。基準円の直径 = module × teeth、歯先 +module、歯底 -1.25×module。
    bore は軸穴の半径（省略時は歯底の円の 3 割）。Z 方向に厚み width、底面が原点"""
    rp = module * teeth / 2
    ra, rf = rp + module, rp - 1.25 * module
    rb = bore if bore is not None else rf * 0.3
    a = 2 * math.pi / teeth
    outer, inner = [], []
    for i in range(teeth):
        c = i * a
        for frac, rr in ((-0.25, rf), (-0.12, ra), (0.12, ra), (0.25, rf)):
            ang = c + frac * a
            outer.append((rr * math.cos(ang), rr * math.sin(ang)))
            inner.append((rb * math.cos(ang), rb * math.sin(ang)))
    bm = bmesh.new()
    _annulus(bm, outer, inner, 0.0, width)
    return _place(obj(name, bm, material), location, rotate)[0]


def flange(name: str, r_in: float, r_out: float, thickness: float, bolts: int = 4, bolt_size="M8",
           material=None, bolt_material=None, location=(0, 0, 0), rotate=None):
    """フランジ（穴あきの円盤）と、上面の円周に並べたボルト。戻り値は [フランジ, ボルト...]"""
    seg = max(16, bolts * 4)
    fl = ring(name, r_out, r_in, thickness, seg=seg, material=material)
    rc = (r_in + r_out) / 2
    parts = [fl]
    for i in range(bolts):
        ang = 2 * math.pi * (i + 0.5) / bolts
        parts.append(bolt(f"{name}_Bolt_{i + 1}", bolt_size, length=thickness, material=bolt_material or material,
                          location=(rc * math.cos(ang), rc * math.sin(ang), thickness)))
    return _place(parts, location, rotate)


def wheel(name: str, radius: float = 0.33, width: float = 0.22, rim_radius=None, spokes: int = 5,
          tire_material=None, rim_material=None, location=(0, 0, 0), rotate=None):
    """車輪（タイヤ・リム・ハブ・スポーク）。軸は Z、中心が原点。車に付けるなら rotate=(90, 0, 0) で軸を Y に。
    戻り値は [タイヤ, リム, ハブ, スポーク...]"""
    rr = rim_radius or radius * 0.62
    hw, c = width / 2, min(width, radius - rr) * 0.25
    prof = [(rr, -hw * 0.9), (radius - c, -hw), (radius, -hw + c), (radius, hw - c), (radius - c, hw), (rr, hw * 0.9)]
    # 断面の各辺を分けて、なめらかに
    dense = []
    for i in range(len(prof)):
        (r0, z0), (r1, z1) = prof[i], prof[(i + 1) % len(prof)]
        dense += [(r0 + (r1 - r0) * t / 2, z0 + (z1 - z0) * t / 2) for t in range(2)]
    tire = lathe(f"{name}_Tire", dense, seg=32, closed=True, material=tire_material)
    rim = ring(f"{name}_Rim", rr, rr * 0.9, width * 0.85, seg=32, origin="center", material=rim_material)
    hub = cylinder(f"{name}_Hub", rr * 0.28, width * 0.5, seg=16, origin="center", material=rim_material)
    parts = [tire, rim, hub]
    if spokes:
        sp = box(f"{name}_Spoke_1", (rr * 0.66, rr * 0.16, width * 0.18), origin="center",
                 location=(rr * 0.28 + rr * 0.31, 0, 0), material=rim_material)
        parts += radial(sp, spokes)
    return _place(parts, location, rotate)


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


def orient(objects, origin=(0, 0, 0), x_axis=(1, 0, 0), z_axis=(0, 0, 1)):
    """原点に作った部品を、origin へ動かし、部品の X 軸を x_axis、Z 軸を z_axis の向きにする。
    （z_axis は x_axis に直交するよう自動で直す。棒・ダンパー・ロッドエンドを 2 点の間に据えるときに）"""
    objects = objects if isinstance(objects, (list, tuple)) else [objects]
    x = Vector(x_axis).normalized()
    z = Vector(z_axis)
    z = (z - x * z.dot(x))
    if z.length < 1e-9:
        z = x.orthogonal()
    z.normalize()
    y = z.cross(x)
    m = Matrix(((x.x, y.x, z.x, 0), (x.y, y.y, z.y, 0), (x.z, y.z, z.z, 0), (0, 0, 0, 1)))
    m = Matrix.Translation(Vector(origin)) @ m
    bpy.context.view_layer.update()
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


def array(ob, count: int, offset, name: str | None = None):
    """直線に並べて複製する（ob を含めて count 個）。offset は 1 個ごとのずれ (dx, dy, dz)。戻り値は全部のリスト"""
    out = [ob]
    base = Vector(ob.location)
    label = re.sub(r"_1$", "", name or ob.name)
    for k in range(1, count):
        out.append(copy(ob, f"{label}_{k + 1}", location=tuple(base + Vector(offset) * k)))
    return out


def radial(ob, count: int, center=(0, 0, 0), axis: str = "Z", name: str | None = None):
    """center を通る軸のまわりに、等間隔に並べて複製する（ob を含めて count 個）。スポーク・ボルト円・花びらなどに"""
    base = re.sub(r"_1$", "", name or ob.name)
    out = [ob]
    for k in range(1, count):
        c = copy(ob, f"{base}_{k + 1}")
        rot = [0, 0, 0]
        rot["XYZ".index(axis.upper())] = 360 * k / count
        pivot(c, center, rot)
        out.append(c)
    return out


def mirror(ob, axis: str = "X", about: float = 0.0, name: str | None = None):
    """左右反転した複製を作る（axis 方向に、座標 about の面で反転）。形はメッシュに焼き込み、面の向きも直す"""
    bpy.context.view_layer.update()
    new = copy(ob, name or (ob.name[:-2] + "_R" if ob.name.endswith("_L") else ob.name + "_Mirror"))
    me = new.data
    me.transform(ob.matrix_world)
    new.matrix_world = Matrix.Identity(4)
    i = "XYZ".index(axis.upper())
    flip = Matrix.Identity(4)
    flip[i][i] = -1
    me.transform(Matrix.Translation(Vector([about if k == i else 0 for k in range(3)])) @ flip
                 @ Matrix.Translation(Vector([-about if k == i else 0 for k in range(3)])))
    me.flip_normals()
    me.update()
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


MM = 0.001  # ミリをメートルに直す係数。寸法をミリで書くときに 120 * qm.MM のように使う


def units(u: str = "mm"):
    """報告の単位を切り替える（"mm" か "cm"）。モデル自体の単位はメートルのまま"""
    if u not in ("mm", "cm"):
        raise ValueError('units は "mm" か "cm"')
    bpy.context.scene["qm_units"] = u


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
- 点の補助: qm.circle(n, r) → [(x,y)...]、qm.arc(r, 開始角, 終了角, 分割数) → [(x,y)...]（度）、
    qm.polygon(n, r, per_edge=1) 正多角形、qm.helix(r, pitch, turns) らせん（qm.tube と組んでばね・コイル）、
    qm.airfoil(chord, thickness=0.12, camber=0) 翼の断面 [(u,v)...]（qm.loft で翼・羽根・プロペラに）

部品（寸法付き。どれも四角形だけの閉じた立体。rotate=(rx,ry,rz) 度で向きを変える）
- qm.bolt(name, "M8", length=0.03, thread=False)   六角ボルト。原点は頭の座面、軸は -Z へ。"M3"〜"M12"、または直径の数値
- qm.nut(name, "M8") / qm.washer(name, "M8")   六角ナット（ISO 4032 の寸法） / 平座金（おおよその寸法）
- qm.ring(name, r_out, r_in, h, seg=16)   穴のあいた円柱（カラー・管の一部・リム）
- qm.gear(name, teeth=20, module=0.002, width=0.01, bore=None)   平歯車（基準円の直径 = module × teeth）
- qm.flange(name, r_in, r_out, thickness, bolts=4, bolt_size="M8")   フランジとボルト → [フランジ, ボルト...]
- qm.wheel(name, radius=0.33, width=0.22, spokes=5, rotate=(90,0,0))   タイヤ・リム・ハブ・スポーク → リスト
- qm.lathe(..., closed=True)   断面を閉じた輪として回す（タイヤ・Oリング・ドーナツ）

置く・仕上げる
- qm.pivot(objs, point=(x,y,z), rotate=(rx,ry,rz))   point を軸に回す（蝶番のふた・傾けた脚。度）
- qm.orient(objs, origin, x_axis, z_axis)   原点に作った部品を、origin に、X 軸・Z 軸を指定の向きにして据える
- qm.copy(ob, name, location=, rotate=, scale=)   複製（左右の脚など）
- qm.array(ob, count, offset=(dx,dy,dz))   直線に並べる / qm.radial(ob, count, center=, axis="Z")   円周に並べる
- qm.mirror(ob, axis="X", about=0.0)   反転した複製（左右対称の部品。名前が _L なら _R になる）
- qm.bevel(ob, width, segments=2) / qm.subsurf(ob, levels=1) / qm.solidify(ob, thickness)
- qm.material(name, color=(r,g,b), metal=, rough=, tile=画像1枚のメートル, alpha=)

確かめる
- qm.expect("Body", size=(0.9, 0.55, 0.42))   寸法を宣言 → サーバーが照合して、違えば問題として返す
- qm.expect("*", size=(None, None, 1.2))   全体の高さだけ宣言、のようにも書ける
- qm.expect("Lamp", floating=True)   宙に浮いていてよい部品（それ以外は浮いていると指摘される）
- qm.expect("*", floating=True)   全体が地面に接していなくてよい（タイヤを外した図面用など）。部品どうしのつながりは引き続き見る
- qm.units("mm")   報告の寸法と位置をミリで出す（精密な部品や図面用）。qm.MM = 0.001 を掛けるとミリで書ける

例:
  wood = qm.material("Wood", tile=0.6)
  body = qm.box("Body", (0.9, 0.55, 0.42), material=wood, bevel=0.012)
  lid = qm.loft("Lid", [[(x, y, 0.42 + z) for y, z in sec] for x in (-0.45, 0.45)], material=wood)
  qm.pivot(lid, point=(0, 0.275, 0.42), rotate=(-35, 0, 0))
  qm.expect("Body", size=(0.9, 0.55, 0.42))
"""
