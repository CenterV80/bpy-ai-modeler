"""
f1_fasten — 留め具（ボルト・ナット・座金・スペーサー）と、ロッドエンドを受けるクレビス（二股の金具）

同じ寸法の留め具はメッシュを 1 つだけ作って使い回す（オブジェクトは別、形のデータは共有）。
何千本ものボルトを置いても、作る時間と書き出すファイルが軽く済む。

穴あけ: fasten / clevis はボルトが入る部品（サバイバルセル・ギアボックスなど）に穴を「予約」する。
最後に drill_all() を呼ぶと、部品ごとにまとめて 1 回のブーリアンで穴をあける。
"""
from __future__ import annotations

import math

import bmesh
import bpy
import qm
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

import f1

_PROTO: dict = {}        # (種類, 寸法…) → メッシュ
_DRILL: dict = {}        # 部品の名前 → [(始点, 終点, 半径)]
COUNT: dict = {}         # 種類ごとに置いた数（報告用）


def _mat(key):
    if key == "steel":
        return qm.material("F1_Steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    if key == "ti":
        return qm.material("F1_Titanium", (0.45, 0.45, 0.47), metal=1.0, rough=0.3)
    if key == "alu":
        return qm.material("F1_Alu", (0.75, 0.76, 0.78), metal=0.9, rough=0.3)
    if key == "bronze":
        return qm.material("F1_Bronze", (0.70, 0.50, 0.25), metal=0.9, rough=0.35)
    return key


def _keep(ob):
    """作った見本のオブジェクトをシーンから外し、メッシュだけ残す"""
    me = ob.data
    me.use_fake_user = True
    bpy.data.objects.remove(ob)
    return me


def proto(kind: str, size, length: float = 0.0, mat="ti"):
    """留め具の見本のメッシュ。kind は bolt / nut / washer / spacer / stud / insert / pin"""
    key = (kind, size if isinstance(size, str) else round(float(size), 5), round(length, 4), str(mat))
    if key in _PROTO:
        return _PROTO[key]
    m = _mat(mat)
    nm = "_proto_" + "_".join(str(k) for k in key)
    if kind == "bolt":
        ob = qm.bolt(nm, size, length, material=m)
    elif kind == "nut":
        ob = qm.nut(nm, size, material=m)
    elif kind == "washer":
        ob = qm.washer(nm, size, material=m)
    elif kind == "stud":                    # 両端にねじのある棒（原点は下の端、+Z へ length）
        d = qm._spec(size)["d"]
        ob = qm.cylinder(nm, d / 2, length, seg=12, origin="bottom", material=m)
    elif kind == "pin":                     # ピン・ころ（原点は中心、Z 方向に length）
        ob = qm.cylinder(nm, float(size) / 2, length, seg=12, origin="center", material=m)
    elif kind == "spacer":                  # スペーサー（つば付き）。size は穴の径、原点は下の面、+Z へ length
        d = qm._spec(size)["d"] if isinstance(size, str) else float(size)
        ob = qm.lathe(nm, [(d * 0.55, 0), (d * 1.05, 0), (d * 1.05, length * 0.3), (d * 0.8, length * 0.3),
                           (d * 0.8, length), (d * 0.55, length)], seg=16, closed=True, material=m)
    elif kind == "insert":                  # カーボンに埋める金属のねじ穴（原点は表面、-Z へ length）
        d = qm._spec(size)["d"]
        ob = qm.ring(nm, d * 0.95, d * 0.5, length, seg=12, origin="bottom", material=m, location=(0, 0, -length))
        ob.data.transform(qm._mw(ob))
        ob.matrix_world = Matrix()
    else:
        raise ValueError(kind)
    _PROTO[key] = _keep(ob)
    return _PROTO[key]


def proto_mesh(key: str, make):
    """make(名前) で作ったオブジェクトのメッシュを、key で覚えて使い回す（同じ形の部品をたくさん置くとき）"""
    if key in _PROTO:
        return _PROTO[key]
    _PROTO[key] = _keep(make(key))
    return _PROTO[key]


def frame(origin, z_axis, x_axis=None) -> Matrix:
    """origin に置き、部品の Z を z_axis へ向ける行列"""
    z = Vector(z_axis).normalized()
    x = Vector(x_axis) if x_axis is not None else z.orthogonal()
    x = (x - z * x.dot(z))
    if x.length < 1e-9:
        x = z.orthogonal()
    x.normalize()
    y = z.cross(x)
    m = Matrix(((x.x, y.x, z.x, 0), (x.y, y.y, z.y, 0), (x.z, y.z, z.z, 0), (0, 0, 0, 1)))
    return Matrix.Translation(Vector(origin)) @ m


def place(name: str, mesh, matrix: Matrix, kind: str = "other"):
    """共有のメッシュでオブジェクトを置く"""
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(ob)
    ob.matrix_world = matrix
    COUNT[kind] = COUNT.get(kind, 0) + 1
    return ob


def reserve(target: str, p0, p1, r: float):
    """target に、p0 から p1 への穴（半径 r）を予約する"""
    _DRILL.setdefault(target, []).append((Vector(p0), Vector(p1), r))


ALIAS: dict = {}     # 穴を「Cell」に予約したら、ハニカムや内の皮にも同じ穴をあける、などの対応 {名前: [名前...]}


def drill_all(skip=()):
    """予約した穴を、部品ごとに 1 回のブーリアンであける。戻り値 {部品: 穴の数}"""
    done = {}
    for t0, holes in list(_DRILL.items()):
        for t in ALIAS.get(t0, []):
            if t != t0 and t in bpy.data.objects:
                _DRILL.setdefault(t, []).extend(holes)
    for target, holes in list(_DRILL.items()):
        ob = bpy.data.objects.get(target)
        if ob is None or target in skip:
            continue
        cutters = []
        for k, (a, b, r) in enumerate(holes):
            L = (b - a).length
            c = qm.cylinder(f"_drill_{target}_{k}", r, L, seg=10, origin="center")
            c.matrix_world = frame((a + b) / 2, b - a)
            cutters.append(c)
        qm.cut(ob, cutters)
        done[target] = len(holes)
    _DRILL.clear()
    return done


def fasten(name: str, head, axis, grip: float, size="M6", nut: bool = True, washer: bool = True,
           drill=(), mat="ti", insert: bool = False):
    """ボルト 1 本で留める。head はボルトの頭の座面（つかむ部品の表面）、axis は軸の向き（頭から先へ）、
    grip はつかむ厚み。nut=False なら、相手のねじ穴（insert=True ならカーボンに埋めた金属のねじ）へねじ込む。
    drill に部品の名前を並べると、その部品にボルトの穴を予約する。戻り値は置いたオブジェクトのリスト"""
    sp = qm._spec(size)
    a = Vector(axis).normalized()
    h = Vector(head)
    out = []
    wt = sp["d"] * 0.18 if washer else 0.0
    if washer:
        out.append(place(f"{name}_Washer", proto("washer", size, mat=mat), frame(h - a * wt, a), "washer"))
    if nut:
        length = grip + sp["m"] + wt * 2 + sp["pitch"] * 2
    else:
        length = grip + sp["d"] * 1.5                # ねじ込み：径の 1.5 倍ほど入る
    length = math.ceil(length * 1000) / 1000          # 1mm 刻み（見本の数を減らす）
    out.append(place(f"{name}_Bolt", proto("bolt", size, length, mat), frame(h - a * wt, -a), "bolt"))
    end = h + a * grip
    if nut:
        if washer:
            out.append(place(f"{name}_NutWasher", proto("washer", size, mat=mat), frame(end, a), "washer"))
        out.append(place(f"{name}_Nut", proto("nut", size, mat=mat), frame(end + a * wt, a), "nut"))
    elif insert:
        out.append(place(f"{name}_Insert", proto("insert", size, round(sp["d"] * 2, 3), "steel"),
                         frame(h + a * grip, -a), "insert"))
    for t in drill:
        reserve(t, h - a * 0.001, h + a * (grip if nut else grip + sp["d"] * 1.5), sp["d"] / 2 * 1.05)
    return out


def stud_nut(name: str, base, axis, height: float, size="M8", drill=(), mat="ti"):
    """スタッドボルトとナット（base は留める面、axis は外向き、height はつかむ厚み）"""
    sp = qm._spec(size)
    a, b = Vector(axis).normalized(), Vector(base)
    L = math.ceil((height + sp["m"] + sp["d"] * 1.5 + sp["pitch"] * 2) * 1000) / 1000
    out = [place(f"{name}_Stud", proto("stud", size, L, mat), frame(b - a * sp["d"] * 1.5, a), "stud"),
           place(f"{name}_Nut", proto("nut", size, mat=mat), frame(b + a * height, a), "nut")]
    for t in drill:
        reserve(t, b - a * sp["d"] * 1.5, b + a * height, sp["d"] / 2 * 1.05)
    return out


def bolt_circle(name: str, center, axis, radius: float, n: int, grip: float, size="M6", start: float = 0.0,
                nut: bool = False, washer: bool = False, drill=(), mat="ti", x_axis=None):
    """円周に並べたボルト（フランジ・カバー・ハブ）。center は頭の座面の中心"""
    m = frame(center, axis, x_axis)
    out = []
    for k in range(n):
        ang = start + 2 * math.pi * k / n
        p = m @ Vector((radius * math.cos(ang), radius * math.sin(ang), 0))
        out += fasten(f"{name}{k + 1}", p, axis, grip, size, nut=nut, washer=washer, drill=drill, mat=mat)
    return out


def bolt_row(name: str, points, axis, grip: float, size="M6", nut: bool = False, washer: bool = False, drill=(), mat="ti"):
    """並べた点にボルト（カバーのふち・ブラケット）"""
    out = []
    for k, p in enumerate(points):
        out += fasten(f"{name}{k + 1}", p, axis, grip, size, nut=nut, washer=washer, drill=drill, mat=mat)
    return out


def perimeter(points2d, n: int, inset: float = 0.0):
    """閉じた折れ線（2D）の上に、等間隔に n 点。inset だけ内側（重心の方）へ寄せる"""
    pts = [Vector((p[0], p[1])) for p in points2d]
    segs = list(zip(pts, pts[1:] + pts[:1]))
    total = sum((b - a).length for a, b in segs)
    c = sum(pts, Vector((0, 0))) / len(pts)
    out = []
    for k in range(n):
        s = total * (k + 0.5) / n
        for a, b in segs:
            L = (b - a).length
            if s <= L:
                q = a + (b - a) * (s / L)
                if inset:
                    q = q + (c - q).normalized() * inset
                out.append(q)
                break
            s -= L
    return out


# ---------------------------------------------------------------- 形の問い合わせ（BVH）
_BVH: dict = {}


def bvh(name: str):
    """オブジェクトの、ワールド座標での BVH（何度も使うので覚えておく）"""
    if name in _BVH:
        return _BVH[name]
    ob = bpy.data.objects[name]
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.transform(qm._mw(ob))
    t = BVHTree.FromBMesh(bm)
    bm.free()
    _BVH[name] = t
    return t


def forget(name: str | None = None):
    if name is None:
        _BVH.clear()
    else:
        _BVH.pop(name, None)


def nearest(point, names):
    """names の部品の表面で、point にいちばん近い点 (点, 法線, 部品の名前, 距離)"""
    best = None
    for n in names:
        if n not in bpy.data.objects:
            continue
        hit = bvh(n).find_nearest(Vector(point))
        if hit[0] is not None and (best is None or hit[3] < best[3]):
            best = (hit[0], hit[1], n, hit[3])
    return best


def ray(point, direction, names, far: float = 0.5):
    """point から direction へ光線を飛ばし、最初に当たる部品の表面 (点, 法線, 部品の名前, 距離)"""
    best = None
    d = Vector(direction).normalized()
    for n in names:
        if n not in bpy.data.objects:
            continue
        hit = bvh(n).ray_cast(Vector(point), d, far)
        if hit[0] is not None and (best is None or hit[3] < best[3]):
            best = (hit[0], hit[1], n, hit[3])
    return best


# ---------------------------------------------------------------- 耳（ラグ）とクレビス
def lug(name: str, center, pin_axis, out_dir, R: float, r_hole: float, length: float, t: float, material=None, seg: int = 24):
    """穴のあいた耳の板。center が穴の中心（板の厚みの中心）、板は pin_axis に垂直、
    out_dir の向きへ length だけ伸びる（反対側は半径 R の半円）"""
    pts_o, pts_i = [], []
    for k in range(seg):
        th = 2 * math.pi * k / seg
        c, s = math.cos(th), math.sin(th)
        if c <= 1e-6:
            ro = R
        else:
            ro = min(length / c, R / abs(s) if abs(s) > 1e-6 else 1e9)
        pts_o.append((ro * c, ro * s))
        pts_i.append((r_hole * c, r_hole * s))
    bm = bmesh.new()
    qm._annulus(bm, pts_o, pts_i, -t / 2, t / 2)
    ob = qm.obj(name, bm, material)
    ob.matrix_world = frame(center, pin_axis, out_dir)
    return ob


def clevis(name: str, center, pin_axis, out_dir, gap: float, length: float, bore: float, t: float = 0.005,
           R: float | None = None, base: float = 0.006, material=None):
    """二股の金具（耳 2 枚と、その根元をつなぐ台）。center がピンの中心、gap は耳の間のすき間、
    length はピンの中心から台の外の面まで。戻り値 [耳, 耳, 台]"""
    p, a, o = Vector(center), Vector(pin_axis).normalized(), Vector(out_dir)
    o = (o - a * o.dot(a)).normalized()
    R = R or bore * 1.6
    out = []
    for k, sgn in enumerate((-1, 1)):
        out.append(lug(f"{name}_Lug{k + 1}", p + a * sgn * (gap / 2 + t / 2), a, o, R, bore / 2 * 1.04,
                       length - base, t, material))
    span = gap + 2 * t
    blk = qm.box(f"{name}_Base", (3.4 * R, span, base), origin="center", material=material)
    blk.matrix_world = frame(p + o * (length - base / 2), o, a.cross(o))
    out.append(blk)
    return out


def joint(prefix: str, c, ax, half: float, rr: float, size="M8", host=(), bolted: bool = True, out=None,
          length: float | None = None, base_bolts: int = 2, base_size="M6", mat="ti", insert: bool = True,
          spacer: bool = True, hardpoint: float = 0.0):
    """軸受（球面軸受・ロッカーのボス）を、二股の金具（クレビス）とボルトで受ける。
    c は軸受の中心、ax はボルトの軸、half は軸受の幅の半分、rr は軸受の外の半径。
    host の部品のいちばん近い面へ金具の台を伸ばす（out で向きを決めることもできる）。
    bolted=True なら台を host へ base_bolts 本のボルトで留め（host にねじ穴を予約）、False なら台は host と一体"""
    c, ax = Vector(c), Vector(ax).normalized()
    sp = qm._spec(size)
    out_objs = []
    sl = rr * 0.35 if spacer else 0.0005
    if spacer:
        for k, sgn in enumerate((-1, 1)):                # ボールの両側のスペーサー（つばが耳の側）
            m = frame(c + ax * sgn * (half + sl), -ax * sgn)
            out_objs.append(place(f"{prefix}_Spacer{k + 1}", proto("spacer", sp["d"], round(sl, 4), "steel"), m, "spacer"))
    gap = 2 * (half + sl)
    t = max(0.004, sp["d"] * 0.6)
    R = max(rr * 1.25, sp["d"] * 1.6)
    hit = nearest(c, host) if host else None
    if out is not None:
        o = Vector(out)
    elif hit is not None:
        o = hit[0] - c
    else:
        o = ax.orthogonal()
    o = o - ax * o.dot(ax)
    if o.length < 1e-6:
        o = ax.orthogonal()
    o.normalize()
    if length is not None:
        L = length
    elif hit is not None:
        r2 = ray(c, o, host, far=0.4)
        L = (r2[3] if r2 else hit[3]) + (0.0003 if bolted else 0.004)
        L = max(L, R + 0.008)
    else:
        L = R + 0.008
    out_objs += clevis(f"{prefix}_Clevis", c, ax, o, gap, L, sp["d"], t=t, R=R, material=_mat(mat))
    head = c - ax * (gap / 2 + t)                        # ピンのボルト：耳の外の面から反対の耳の外の面まで
    out_objs += fasten(f"{prefix}_Pin", head, ax, gap + 2 * t, size, nut=True, washer=True, mat=mat)
    if bolted and hit is not None:
        base_c = c + o * L
        side = ax.cross(o).normalized()
        if hardpoint:     # 相手の壁に埋めるチタンのインサート（取り付け部の補強。実車ではセルに接着する）
            hp = qm.box(f"{prefix}_Hardpoint", (3.4 * R + 0.008, gap + 2 * t + 0.008, hardpoint), origin="center", material=_mat("ti"))
            hp.matrix_world = frame(base_c + o * (hardpoint / 2 + 0.0005), o, side)
            out_objs.append(hp)
        for k, u in enumerate((-1, 1)[:base_bolts]):     # ボールを避けて、台の両端に
            out_objs += fasten(f"{prefix}_Base{k + 1}", base_c - o * 0.006 + side * R * 1.2 * u, o, 0.006, base_size,
                               nut=False, washer=False, drill=(hit[2],), mat=mat, insert=insert and hit[2].startswith("Cell"))
    return out_objs


def rod_end_geom(prefix: str):
    """ロッドエンド（prefix_Housing / _Ball / _Shank）の (中心, ボルトの軸, ボールの幅の半分, ボールの半径, 穴の径, ねじの軸の向き)"""
    import numpy as np
    ball = bpy.data.objects[f"{prefix}_Ball"]
    house = bpy.data.objects[f"{prefix}_Housing"]
    hw, bw = qm._mw(house), qm._mw(ball)
    vs = [hw @ v.co for v in house.data.vertices]
    c = sum(vs, Vector()) / len(vs)
    A = np.array([tuple(v - c) for v in vs])
    w, V = np.linalg.eigh(A.T @ A)
    ax = Vector(V[:, 0]).normalized()                    # 薄い輪のいちばん薄い向きが軸
    bv = [bw @ v.co - c for v in ball.data.vertices]
    half = max(abs(ax.dot(v)) for v in bv)
    rad = [(v - ax * ax.dot(v)).length for v in bv]
    sh = bpy.data.objects.get(f"{prefix}_Shank")
    if sh is not None:
        swm = qm._mw(sh)
        sv = [swm @ v.co for v in sh.data.vertices]
        shank = sum(sv, Vector()) / len(sv) - c
        shank = (shank - ax * shank.dot(ax)).normalized()
    else:
        shank = (hw.to_3x3() @ Vector((-1, 0, 0))).normalized()
    return c, ax, half, max(rad), min(rad) * 2, shank


def rod_end_joint(prefix: str, host=(), bolted: bool = True, outward: bool = False, **kw):
    """ロッドエンドを、host の近くの面へクレビスで留める（joint の説明を参照）。
    outward=True なら、金具をねじの軸と反対の向きへ伸ばす（相手の部品が腕の先にあるとき）"""
    c, ax, half, rr, bore, shank = rod_end_geom(prefix)
    size = "M8" if bore >= 0.0075 else "M6" if bore >= 0.0055 else "M5"
    if outward:
        kw.setdefault("out", -shank)
    elif host:
        hit = nearest(c, host)
        if hit is not None:
            o = hit[0] - c
            o = o - ax * o.dot(ax)
            if o.length < 1e-4 or o.normalized().dot(shank) > 0.7:
                kw.setdefault("out", -shank)
    return joint(prefix, c, ax, half, rr, size, host=host, bolted=bolted, **kw)


def hull2d(points):
    """2D の点の凸包（反時計回り）"""
    pts = sorted(set((round(p[0], 6), round(p[1], 6)) for p in points))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def bbox(name: str):
    """オブジェクトのワールド座標の外接箱 (最小, 最大)"""
    ob = bpy.data.objects[name]
    mw = qm._mw(ob)
    vs = [mw @ v.co for v in ob.data.vertices]
    return (Vector([min(v[i] for v in vs) for i in range(3)]), Vector([max(v[i] for v in vs) for i in range(3)]))


def vband(name: str, center, axis, r: float, width: float = 0.010, mat="steel"):
    """V バンドクランプ（管と管の継ぎ目を締める輪と、締めるボルト・ナット）。center は継ぎ目の中心、axis は管の向き、r は管の外の半径"""
    a = Vector(axis).normalized()
    ring_ = qm.ring(f"{name}", r + 0.005, r, width, seg=24, origin="center", material=_mat(mat))
    ring_.matrix_world = frame(center, a)
    side = a.orthogonal().normalized()
    lug_c = Vector(center) + side * (r + 0.008)
    t = a.cross(side).normalized()
    lugs = [qm.box(f"{name}_Lug{k + 1}", (0.010, 0.004, width), origin="center", material=_mat(mat)) for k in range(2)]
    for k, lg in enumerate(lugs):
        lg.matrix_world = frame(lug_c + t * (0.004 if k else -0.004) * 1.5, a, side)
    out = [ring_] + lugs
    out += fasten(f"{name}_T", lug_c - t * 0.009, t, 0.018, "M5", nut=True, washer=False, mat=mat)
    return out


def report():
    """置いた留め具の数（種類ごと）"""
    return dict(sorted(COUNT.items()))
