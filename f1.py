"""
f1 — F1 マシン（2026 年規定）の部品を作る関数集（run_script の中で `f1` として使える）

座標: 前後が Y（前 = -Y、前輪の軸が y=0）、左右が X、上が Z。単位はメートル。
どの関数も qm で組み立てるので、面はすべて四角形。左右対称の部品は左を作って qm.mirror で右を作る。

寸法の出典
- SPEC: 公式発表・報道で確認できた 2026 年規定の値
- EST : 規定書の本文で確かめられなかった値（2022 年規定からの変化の報道や、実車の写真からの推定）
"""
from __future__ import annotations

import math

import qm
from mathutils import Vector

SPEC = {
    "wheelbase": 3.40,                 # 最大 3,400mm（2022 年の 3,600mm から短縮）
    "width": 1.90,                     # 全幅 1,900mm（2,000mm から）
    "min_weight": 768,                 # kg（ドライバー込み、燃料なし、タイヤの重さ込み）
    "front_tyre": (0.705, 0.280),      # 直径・幅（2022 年の 720×305mm から）
    "rear_tyre": (0.710, 0.375),       # 直径・幅（2022 年の 720×405mm から）
    "rim_inch": 18,
}
EST = {
    "height": 0.95,                    # 全高（2022 年規定の上限を流用）
    "front_wing_span": 1.80,           # フロントウイングの幅（2022 年から 100mm 狭いという報道から）
    "rear_wing_span": 0.95,
    "front_overhang": 1.05,            # 前輪の軸からノーズ先端まで
    "rear_overhang": 0.75,             # 後輪の軸からリアウイング後端まで
    "plank_z": 0.035,                  # フロアの下面の高さ
}


def materials(livery=(0.85, 0.05, 0.05)):
    """よく使うマテリアルの組。livery は車体の色"""
    return {
        "paint": qm.material("F1_Paint", livery, metal=0.3, rough=0.25),
        "carbon": qm.material("F1_Carbon", (0.025, 0.025, 0.03), metal=0.2, rough=0.35),
        "tyre": qm.material("F1_Tyre", (0.02, 0.02, 0.02), rough=0.85),
        "rim": qm.material("F1_Rim", (0.08, 0.08, 0.09), metal=0.8, rough=0.3),
        "titanium": qm.material("F1_Titanium", (0.45, 0.45, 0.47), metal=1.0, rough=0.3),
        "helmet": qm.material("F1_Helmet", (0.95, 0.85, 0.1), metal=0.1, rough=0.3),
        "light": qm.material("F1_Light", (0.9, 0.1, 0.1), rough=0.2),
    }


def _m(mats, key):
    """マテリアルの組から 1 つ取り出す。組を渡していなければ、標準の組（赤い車体）を使う"""
    return (mats or materials()).get(key)


def rrect(w: float, h: float, r: float, n: int = 3):
    """角を丸めた長方形の断面（XZ 平面、中心が原点）の点 [(x, z), ...]。点は 4×(n+1) 個"""
    r = max(1e-4, min(r, w / 2 * 0.999, h / 2 * 0.999))
    cx, cz = w / 2 - r, h / 2 - r
    pts = []
    for k, (sx, sz, a0) in enumerate(((1, -1, -90), (1, 1, 0), (-1, 1, 90), (-1, -1, 180))):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((sx * cx + r * math.cos(a), sz * cz + r * math.sin(a)))
    return pts


def body(name: str, stations, material=None, n: int = 3, cap: bool = True):
    """前から後ろへの断面の並びで、なめらかな胴体を作る（モノコック・ノーズ・エンジンカバー・サイドポッドに）。
    stations = [(y, 中心x, 下端z, 幅, 高さ, 角の半径), ...]"""
    secs = []
    for y, cx, z0, w, h, r in stations:
        secs.append([(cx + x, y, z0 + h / 2 + z) for x, z in rrect(w, h, r, n)])
    return qm.loft(name, secs, cap=cap, material=material)


def wing_element(name: str, span: float, chord: float, y_le: float, z: float, aoa: float = 0.0,
                 thickness: float = 0.10, camber: float = -0.05, x0: float = 0.0, sweep_z=None, material=None,
                 n: int = 10, span_segs: int = 8):
    """翼 1 枚。前縁が y_le、高さ z、左右に span、迎え角 aoa（度。正で後縁が上がる）。
    sweep_z は左右方向の高さの変化 [(x の割合 -1〜1, dz), ...]（フロントウイングの中央を上げる、など）"""
    prof = qm.airfoil(chord, thickness, camber, n=n)
    ca, sa = math.cos(math.radians(aoa)), math.sin(math.radians(aoa))
    secs = []
    for k in range(span_segs + 1):
        t = -1 + 2 * k / span_segs
        dz = 0.0
        if sweep_z:
            pts = sorted(sweep_z)
            for (t0, z0), (t1, z1) in zip(pts, pts[1:]):
                if t0 <= t <= t1:
                    dz = z0 + (z1 - z0) * (t - t0) / max(t1 - t0, 1e-9)
        x = x0 + t * span / 2
        secs.append([(x, y_le + u * ca - v * sa, z + dz + u * sa + v * ca) for u, v in prof])
    return qm.loft(name, secs, material=material)


def plate(name: str, outline, thickness: float, axis: str = "X", at: float = 0.0, material=None):
    """板（翼端板・フィン）。outline は板の面内の輪郭 [(a, b), ...]（偶数点、反時計回り）。
    axis="X" なら YZ 面の板（a=y, b=z）、"Z" なら XY 面の板（a=x, b=y）。at はその軸での中心位置"""
    def p(a, b, d):
        return (at + d, a, b) if axis == "X" else (a, b, at + d)
    secs = [[p(a, b, -thickness / 2) for a, b in outline], [p(a, b, thickness / 2) for a, b in outline]]
    return qm.loft(name, secs, material=material)


# ---------------------------------------------------------------- 部品

def tyre_and_wheel(name: str, front: bool = True, location=(0, 0, 0), mats=None, cover: bool = True, wheel: bool = True):
    """タイヤ・18 インチのホイール・ホイールカバー。軸は X（車の左右）。location はホイールの中心。
    戻り値 [タイヤ, ホイール, カバー]"""
    D, W = SPEC["front_tyre"] if front else SPEC["rear_tyre"]
    R, rim = D / 2, SPEC["rim_inch"] * 0.0254 / 2
    hw = W / 2
    prof = [(rim + 0.01, -hw * 0.92), (R - 0.03, -hw), (R - 0.006, -hw * 0.85), (R, -hw * 0.6), (R, 0.0),
            (R, hw * 0.6), (R - 0.006, hw * 0.85), (R - 0.03, hw), (rim + 0.01, hw * 0.92), (rim + 0.012, 0.0)]
    tyre = qm.lathe(f"{name}_Tyre", prof, seg=40, closed=True, material=_m(mats, "tyre"))
    parts = [tyre]
    if wheel:  # wheel=False ならタイヤだけ（f1.rim の精密なホイールと組み合わせるとき）
        parts.append(qm.ring(f"{name}_Wheel", rim + 0.012, rim - 0.012, W * 0.92, seg=40, origin="center", material=_m(mats, "rim")))
    if cover and wheel:
        parts.append(qm.cylinder(f"{name}_Cover", rim - 0.012, 0.012, seg=24, origin="center", material=_m(mats, "carbon"),
                                 location=(0, 0, hw * 0.92 - 0.01)))
    side = 1 if location[0] >= 0 else -1
    return qm._place(parts, location, rotate=(0, 90 * side, 0))


def monocoque(name: str = "Monocoque", mats=None):
    """サバイバルセル（ドライバーが座る中央の胴体）。前輪の軸の少し前から、エンジンの前まで"""
    z0 = EST["plank_z"] + 0.03
    st = [(-0.35, 0, z0 + 0.10, 0.30, 0.30, 0.08), (0.0, 0, z0 + 0.05, 0.40, 0.40, 0.10), (0.45, 0, z0, 0.58, 0.52, 0.12),
          (0.95, 0, z0, 0.62, 0.56, 0.12), (1.30, 0, z0, 0.58, 0.60, 0.12)]
    return body(name, st, _m(mats, "paint"))


def nose(name: str = "Nose", mats=None):
    """ノーズ。モノコックの前から、前に向かって細く低くなる"""
    z0 = EST["plank_z"] + 0.03
    tip = -EST["front_overhang"] + 0.02
    st = [(tip, 0, 0.17, 0.10, 0.07, 0.03), (tip + 0.15, 0, 0.18, 0.16, 0.11, 0.05), (-0.65, 0, z0 + 0.15, 0.24, 0.20, 0.07),
          (-0.35, 0, z0 + 0.10, 0.30, 0.30, 0.08)]
    return body(name, st, _m(mats, "paint"))


def front_wing(name: str = "FrontWing", elements: int = 3, mats=None):
    """フロントウイング（主翼と、可動のフラップ）、翼端板、ノーズとつなぐ支柱 2 本。戻り値はリスト"""
    span = EST["front_wing_span"]
    y0 = -EST["front_overhang"]
    parts = []
    chord, y, z, aoa = 0.30, y0 + 0.04, 0.09, 4.0
    raise_center = [(-1, 0.0), (-0.25, 0.0), (0, 0.05), (0.25, 0.0), (1, 0.0)]  # 中央（ノーズの下）を少し上げる
    for k in range(elements):
        parts.append(wing_element(f"{name}_E{k + 1}", span, chord, y, z, aoa, thickness=0.09 if k == 0 else 0.11,
                                  camber=-0.06, sweep_z=raise_center if k == 0 else None, material=_m(mats, "carbon")))
        y += chord * 0.78
        z += 0.035 + 0.01 * k
        chord *= 0.62
        aoa += 10
    ep = [(y0, 0.04), (y0 + 0.55, 0.04), (y0 + 0.55, 0.32), (y0 + 0.30, 0.30), (y0 + 0.08, 0.20), (y0, 0.12)]
    left = plate(f"{name}_Endplate_L", ep, 0.012, axis="X", at=-span / 2, material=_m(mats, "carbon"))
    parts += [left, qm.mirror(left, "X")]
    pyl = [(y0 + 0.10, 0.10), (y0 + 0.40, 0.10), (y0 + 0.36, 0.22), (y0 + 0.14, 0.22)]
    pl = plate(f"{name}_Pylon_L", pyl, 0.01, axis="X", at=-0.035, material=_m(mats, "carbon"))
    parts += [pl, qm.mirror(pl, "X")]
    return parts


def floor_and_diffuser(name: str = "Floor", mats=None):
    """フロア（平らな板）とディフューザー（後ろで跳ね上がる部分）。戻り値 [フロア, ディフューザー]"""
    zb, t = EST["plank_z"], 0.03
    wb = SPEC["wheelbase"]
    hw = 0.70
    # 上から見た輪郭（前は細く、中ほどで広い）。偶数点・反時計回り
    outline = [(-0.25, 0.15), (0.25, 0.15), (0.45, 0.45), (hw, 0.75), (hw, wb - 0.70), (0.55, wb - 0.35),
               (-0.55, wb - 0.35), (-hw, wb - 0.70), (-hw, 0.75), (-0.45, 0.45)]
    floor = plate(name, [(x, y) for x, y in outline], t, axis="Z", at=zb + t / 2, material=_m(mats, "carbon"))
    st = []
    for i in range(5):
        f = i / 4
        y = wb - 0.40 + f * 0.75
        st.append((y, 0, zb + 0.005 + 0.22 * f * f, 1.10 - 0.05 * f, 0.03 + 0.02 * f, 0.012))
    diff = body(f"{name}_Diffuser", st, _m(mats, "carbon"), n=2)
    return [floor, diff]


def sidepods(name: str = "Sidepod", mats=None):
    """左右のサイドポッド（ラジエーターの入る張り出し）。戻り値 [左, 右]"""
    z0 = EST["plank_z"] + 0.03
    st = [(0.55, -0.46, z0 + 0.10, 0.30, 0.32, 0.08), (0.80, -0.48, z0, 0.36, 0.44, 0.12), (1.40, -0.44, z0, 0.36, 0.42, 0.14),
          (2.10, -0.34, z0, 0.26, 0.30, 0.12), (2.70, -0.22, z0, 0.14, 0.18, 0.06)]
    left = body(f"{name}_L", st, _m(mats, "paint"))
    return [left, qm.mirror(left, "X")]


def engine_cover(name: str = "EngineCover", mats=None):
    """エンジンカバー（ロールフープとエアボックスから後ろへ絞り込む）とギアボックス。戻り値 [カバー, ギアボックス]"""
    z0 = EST["plank_z"] + 0.03
    top = EST["height"]
    st = [(1.20, 0, z0 + 0.40, 0.30, top - z0 - 0.42, 0.10), (1.45, 0, z0 + 0.10, 0.50, top - z0 - 0.14, 0.14),
          (2.10, 0, z0 + 0.05, 0.42, 0.62, 0.14), (2.80, 0, z0 + 0.10, 0.26, 0.38, 0.10), (3.20, 0, z0 + 0.14, 0.18, 0.24, 0.06)]
    cover = body(name, st, _m(mats, "paint"))
    gst = [(3.10, 0, z0 + 0.12, 0.26, 0.26, 0.05), (3.70, 0, z0 + 0.16, 0.16, 0.20, 0.04)]
    gearbox = body("Gearbox", gst, _m(mats, "carbon"))
    return [cover, gearbox]


def airbox_inlet(name: str = "Airbox", mats=None):
    """エアボックスの吸気口（ドライバーの頭の上）と、その上のカメラ（T カム）。戻り値 [吸気口, カメラ]"""
    top = EST["height"]
    inlet = body(name, [(1.18, 0, top - 0.20, 0.20, 0.14, 0.05), (1.26, 0, top - 0.21, 0.22, 0.16, 0.06)], _m(mats, "carbon"))
    cam = qm.box("TCam", (0.10, 0.05, 0.03), origin="bottom", location=(0, 1.24, top - 0.05), material=_m(mats, "carbon"))
    return [inlet, cam]


def rear_wing(name: str = "RearWing", mats=None):
    """リアウイング（3 枚）、翼端板、ギアボックスから伸びる支柱（スワンネック）。戻り値はリスト"""
    span = EST["rear_wing_span"]
    y_end = SPEC["wheelbase"] + EST["rear_overhang"]
    parts = []
    y, z, chord, aoa = y_end - 0.55, 0.76, 0.24, 6.0
    for k in range(3):
        parts.append(wing_element(f"{name}_E{k + 1}", span, chord, y, z, aoa, thickness=0.10, camber=-0.07,
                                  material=_m(mats, "carbon")))
        y += chord * 0.75
        z += 0.045
        chord *= 0.75
        aoa += 14
    top = EST["height"]
    ep = [(y_end - 0.62, 0.55), (y_end - 0.02, 0.62), (y_end, top), (y_end - 0.62, top)]
    left = plate(f"{name}_Endplate_L", ep, 0.012, axis="X", at=-span / 2 - 0.006, material=_m(mats, "carbon"))
    parts += [left, qm.mirror(left, "X")]
    z0 = EST["plank_z"] + 0.03
    neck = qm.sweep(f"{name}_Pylon", [(0, 3.55, z0 + 0.36), (0, 3.62, 0.60), (0, y_end - 0.40, 0.80)],
                    [(-0.008, -0.04), (0.008, -0.04), (0.008, 0.04), (-0.008, 0.04)], up=(0, 1, 0), material=_m(mats, "carbon"))
    parts.append(neck)
    parts.append(qm.box(f"{name}_RainLight", (0.06, 0.02, 0.05), origin="center", location=(0, 3.705, z0 + 0.20),
                        material=_m(mats, "light")))
    return parts


def halo(name: str = "Halo", mats=None):
    """ヘイロー（頭部保護の輪）。前の 1 本の支柱と、後ろの左右 2 か所でモノコックに付く"""
    z0 = EST["plank_z"] + 0.03
    top = z0 + 0.56 + 0.14
    hoop = [(-0.28, 1.12, z0 + 0.55), (-0.28, 0.90, top), (-0.22, 0.62, top + 0.03), (-0.10, 0.48, top + 0.05),
            (0.0, 0.45, top + 0.05), (0.10, 0.48, top + 0.05), (0.22, 0.62, top + 0.03), (0.28, 0.90, top), (0.28, 1.12, z0 + 0.55)]
    ring = qm.tube(name, hoop, radius=0.022, seg=10, material=_m(mats, "titanium"))
    pillar = qm.tube(f"{name}_Pillar", [(0, 0.45, top + 0.05), (0, 0.38, top - 0.04), (0, 0.32, z0 + 0.52)], radius=0.018,
                     seg=10, material=_m(mats, "titanium"))
    return [ring, pillar]


def driver(name: str = "Driver", mats=None):
    """ドライバーのヘルメット（コクピットから頭だけが見える）"""
    z0 = EST["plank_z"] + 0.03
    return qm.quad_sphere(f"{name}_Helmet", (0.24, 0.28, 0.26), n=4, location=(0, 0.80, z0 + 0.60), material=_m(mats, "helmet"))


def mirrors(name: str = "Mirror", mats=None):
    """左右のバックミラー（ステーでモノコックに付く）。戻り値 [左ミラー, 左ステー, 右ミラー, 右ステー]"""
    z0 = EST["plank_z"] + 0.03
    head = qm.box(f"{name}_L", (0.16, 0.04, 0.06), origin="center", location=(-0.42, 0.42, z0 + 0.62),
                  material=_m(mats, "carbon"), bevel=0.008)
    stay = qm.tube(f"{name}_Stay_L", [(-0.34, 0.44, z0 + 0.60), (-0.29, 0.46, z0 + 0.52)], radius=0.01, seg=8,
                   material=_m(mats, "carbon"))
    return [head, stay, qm.mirror(head, "X"), qm.mirror(stay, "X")]


def suspension(name: str, front: bool = True, mats=None):
    """片側のサスペンション（上下の A アーム、プッシュロッド、トラックロッド、アップライト）。左側を作る。
    戻り値はリスト（右は qm.mirror で）"""
    D, W = SPEC["front_tyre"] if front else SPEC["rear_tyre"]
    y = 0.0 if front else SPEC["wheelbase"]
    wx = (SPEC["width"] - W) / 2
    zc = D / 2
    z0 = EST["plank_z"] + 0.03
    ux = -(wx - W * 0.25)                              # アップライトの位置（ホイールの内側）
    inner = 0.17 if front else 0.12                    # 胴体側の付け根の x
    lo, hi = (z0 + 0.12, z0 + 0.40) if front else (z0 + 0.14, z0 + 0.36)
    up = qm.box(f"{name}_Upright", (0.06, 0.12, 0.30), origin="center", location=(ux, y, zc), material=_m(mats, "titanium"))
    parts = [up]
    for tag, zi, zo in (("Lower", lo, zc - 0.11), ("Upper", hi, zc + 0.11)):
        for k, dy in enumerate((-0.18, 0.20)):
            parts.append(qm.tube(f"{name}_{tag}_{k + 1}", [(-inner, y + dy, zi), (ux + 0.03, y, zo)], radius=0.011, seg=8,
                                 material=_m(mats, "carbon")))
    parts.append(qm.tube(f"{name}_Pushrod", [(ux + 0.03, y + 0.02, zc - 0.10), (-inner, y + 0.05, hi + 0.08)], radius=0.012,
                         seg=8, material=_m(mats, "carbon")))
    parts.append(qm.tube(f"{name}_TrackRod", [(-inner, y + 0.12, (lo + hi) / 2), (ux + 0.03, y + 0.10, zc)], radius=0.009,
                         seg=8, material=_m(mats, "carbon")))
    return parts


# ---------------------------------------------------------------- 1 台にまとめる

def car(livery=(0.85, 0.05, 0.05), front_wing_elements: int = 3, wheel_covers: bool = True):
    """全部の部品で 1 台を組み立てる。戻り値は {部品の種類: [オブジェクト, ...]}"""
    mats = materials(livery)
    wb, W = SPEC["wheelbase"], SPEC["width"]
    fD, fW = SPEC["front_tyre"]
    rD, rW = SPEC["rear_tyre"]
    out = {
        "monocoque": [monocoque(mats=mats)],
        "nose": [nose(mats=mats)],
        "front_wing": front_wing(elements=front_wing_elements, mats=mats),
        "floor": floor_and_diffuser(mats=mats),
        "sidepods": sidepods(mats=mats),
        "engine_cover": engine_cover(mats=mats),
        "airbox": airbox_inlet(mats=mats),
        "rear_wing": rear_wing(mats=mats),
        "halo": halo(mats=mats),
        "driver": [driver(mats=mats)],
        "mirrors": mirrors(mats=mats),
        "wheels": [],
        "suspension": [],
    }
    for tag, front, y, D, Wt in (("FL", True, 0.0, fD, fW), ("RL", False, wb, rD, rW)):
        x = (W - Wt) / 2
        left = tyre_and_wheel(f"Wheel_{tag}", front, location=(-x, y, D / 2), mats=mats, cover=wheel_covers)
        right = tyre_and_wheel(f"Wheel_{tag[0]}R", front, location=(x, y, D / 2), mats=mats, cover=wheel_covers)
        out["wheels"] += left + right
        sus = suspension(f"Susp_{tag}", front, mats=mats)
        right_tag = tag[0] + "R"
        out["suspension"] += sus + [qm.mirror(o, "X", name=o.name.replace(f"_{tag}_", f"_{right_tag}_")) for o in sus]
    return out


# ================================================================ 精密部品（シャシー・足まわり）
#
# 実在の値: ブレーキディスク 前 直径 328mm・後ろ 280mm、厚み 32mm（2025 年の Brembo の値）。キャリパーは 6 ピストン。
# それ以外（ロッドエンド・アーム・ダンパー・ハブなどの寸法）は、写真と一般的なレース部品からの推定。

BRAKE = {"front": (0.328, 0.032), "rear": (0.280, 0.032)}  # 直径・厚み [m]


def _mk(mats, key, color, metal=0.8, rough=0.35):
    return (mats or {}).get(key) or qm.material(f"F1_{key.capitalize()}", color, metal=metal, rough=rough)


def _box_into(bm, center, size, angle=0.0):
    """bmesh に箱を足す（Z 軸まわりに angle ラジアン回す）。たくさんの小さな箱を 1 つのメッシュにまとめるときに"""
    import bmesh
    from mathutils import Matrix
    r = bmesh.ops.create_cube(bm, size=1.0)
    vs = r["verts"]
    bmesh.ops.scale(bm, vec=size, verts=vs)
    bmesh.ops.transform(bm, matrix=Matrix.Rotation(angle, 4, "Z"), verts=vs)
    bmesh.ops.translate(bm, vec=center, verts=vs)


def rod_end(name: str, bore: float = 0.008, shank: float = 0.03, mats=None):
    """ロッドエンド（球面軸受）。原点が球の中心、軸受の穴は Z 方向、ねじの軸は -X へ伸びる。
    qm.orient で据える。戻り値 [ハウジング, ボール, 軸, ロックナット]"""
    steel = _mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    ro = bore * 1.45
    house = qm.ring(f"{name}_Housing", ro, bore * 1.0, bore * 0.85, seg=16, origin="center", material=steel)
    # ボール：外側が球面で、中心に穴のある輪（断面を閉じて回す）
    rb, h = bore * 1.0, bore * 0.85
    prof = [(bore * 0.5, -h * 0.62), (rb * 0.82, -h * 0.62), (rb, -h * 0.3), (rb, h * 0.3), (rb * 0.82, h * 0.62), (bore * 0.5, h * 0.62)]
    ball = qm.lathe(f"{name}_Ball", prof, seg=16, closed=True, material=steel)
    sh = qm.cylinder(f"{name}_Shank", bore * 0.62, shank, seg=12, axis="X", location=(-ro * 0.85 - shank / 2, 0, 0), material=steel)
    nut = qm.nut(f"{name}_LockNut", bore * 1.25, m=bore * 0.6, location=(0, 0, 0), material=steel)  # 薄いロックナット
    qm.orient(nut, origin=(-ro - shank * 0.35, 0, 0), x_axis=(0, 1, 0), z_axis=(-1, 0, 0))
    return [house, ball, sh, nut]


def aero_strut(name: str, p0, p1, chord: float = 0.035, thickness: float = 0.30, flow=(0, 1, 0), mats=None):
    """翼断面の支柱（サスペンションアームの腕）。p0 から p1 へ。断面の弦は flow の向き（前縁が flow の逆側）"""
    prof = [(v, u - chord / 2) for u, v in qm.airfoil(chord, thickness, 0.0, n=8)]
    return qm.sweep(name, [p0, p1], prof, up=flow, material=_m(mats, "carbon"))


def wishbone(name: str, front_in, rear_in, outer, chord: float = 0.032, bore: float = 0.008, mats=None):
    """A アーム（翼断面の腕 2 本、胴体側のロッドエンド 2 個、外側の球面軸受）。点は車の座標。
    戻り値はリスト"""
    fi, ri, ou = Vector(front_in), Vector(rear_in), Vector(outer)
    pivot = (ri - fi).normalized()
    parts = [aero_strut(f"{name}_Front", fi, ou, chord, mats=mats), aero_strut(f"{name}_Rear", ri, ou, chord, mats=mats)]
    for tag, p in (("F", fi), ("R", ri)):
        re_ = rod_end(f"{name}_RodEnd{tag}", bore, shank=0.025, mats=mats)
        qm.orient(re_, origin=p, x_axis=(p - ou).normalized(), z_axis=pivot)
        parts += re_
    joint = rod_end(f"{name}_Outer", bore * 1.1, shank=0.01, mats=mats)
    qm.orient(joint, origin=ou, x_axis=((ou - (fi + ri) / 2) * -1).normalized(), z_axis=(0, 0, 1))
    return parts + joint


def pushrod(name: str, p0, p1, r: float = 0.008, bore: float = 0.007, mats=None):
    """プッシュロッド（丸パイプと両端のロッドエンド）"""
    a, b = Vector(p0), Vector(p1)
    d = (b - a).normalized()
    side = d.cross(Vector((0, 0, 1)))
    if side.length < 1e-6:
        side = Vector((1, 0, 0))
    parts = [qm.tube(name, [a + d * 0.03, b - d * 0.03], radius=r, seg=12, material=_m(mats, "carbon"))]
    for tag, p, x in (("A", a, -d), ("B", b, d)):
        re_ = rod_end(f"{name}_RodEnd{tag}", bore, shank=0.022, mats=mats)
        qm.orient(re_, origin=p, x_axis=x, z_axis=side)
        parts += re_
    return parts


def damper(name: str, p0, p1, body_r: float = 0.022, bore: float = 0.007, mats=None):
    """ダンパー（本体・ロッド・コイルばね・ばね受け・両端のロッドエンド）。p0 が本体側"""
    a, b = Vector(p0), Vector(p1)
    L = (b - a).length
    steel = _mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    spring_mat = _mk(mats, "spring", (0.05, 0.25, 0.75), metal=0.6, rough=0.4)
    alu = _mk(mats, "alu", (0.75, 0.76, 0.78), metal=0.9, rough=0.3)
    e = bore * 1.45
    body = qm.cylinder(f"{name}_Body", body_r, L * 0.55, seg=16, location=(0, 0, e), material=alu)
    rod = qm.cylinder(f"{name}_Rod", body_r * 0.3, L * 0.45 - 2 * e, seg=12, location=(0, 0, e + L * 0.55), material=steel)
    perch1 = qm.ring(f"{name}_Perch1", body_r + 0.010, body_r, 0.006, seg=16, location=(0, 0, e + L * 0.12), material=alu)
    perch2 = qm.ring(f"{name}_Perch2", body_r + 0.010, body_r * 0.3, 0.006, seg=16, location=(0, 0, L - e - 0.02), material=alu)
    z0, z1 = e + L * 0.12 + 0.006, L - e - 0.02
    turns = 7
    spring = qm.tube(f"{name}_Spring", qm.helix(body_r + 0.005, (z1 - z0) / turns, turns, per_turn=12, z0=z0),
                     radius=0.0035, seg=8, material=spring_mat)
    parts = [body, rod, perch1, perch2, spring]
    for tag, z, xdir in (("A", 0.0, (0, 0, 1)), ("B", L, (0, 0, -1))):
        re_ = rod_end(f"{name}_RodEnd{tag}", bore, shank=0.012, mats=mats)
        qm.orient(re_, origin=(0, 0, z), x_axis=(0, 0, -1) if tag == "A" else (0, 0, 1), z_axis=(1, 0, 0))
        parts += re_
    d = (b - a).normalized()
    qm.orient(parts, origin=a, x_axis=d.orthogonal(), z_axis=d)
    return parts


def rocker(name: str, pivot, arms, normal=(1, 0, 0), thickness: float = 0.012, mats=None):
    """ロッカー（ベルクランク）。pivot を軸（normal 方向）に、arms の各点へ腕を伸ばす。
    arms は腕の先の点（車の座標）。腕の先と軸に穴のあるボスが付く。戻り値はリスト"""
    alu = _mk(mats, "alu", (0.75, 0.76, 0.78), metal=0.9, rough=0.3)
    pv, n = Vector(pivot), Vector(normal).normalized()
    parts = [qm.ring(f"{name}_Hub", 0.020, 0.008, thickness * 1.6, seg=16, origin="center", material=alu)]
    qm.orient(parts[0], origin=pv, x_axis=n.orthogonal(), z_axis=n)
    for k, end in enumerate(arms):
        e = Vector(end)
        e = e - n * n.dot(e - pv)            # 腕の先を、軸に垂直な面に乗せる
        web = qm.sweep(f"{name}_Arm{k + 1}", [pv, e], [(-0.009, -thickness / 2), (0.009, -thickness / 2),
                                                        (0.009, thickness / 2), (-0.009, thickness / 2)], up=n, material=alu)
        boss = qm.ring(f"{name}_Boss{k + 1}", 0.013, 0.006, thickness * 1.3, seg=16, origin="center", material=alu)
        qm.orient(boss, origin=e, x_axis=n.orthogonal(), z_axis=n)
        parts += [web, boss]
    return parts


def brake_disc(name: str, front: bool = True, vanes: int = 48, mats=None):
    """ベンチレーテッドのカーボンディスク（2 枚の摩擦板と、その間の放射状の通風羽根）と、取り付けのベル。
    軸は Z、中心が原点。直径・厚みは BRAKE の値。戻り値 [ディスク, ベル]"""
    import bmesh
    D, T = BRAKE["front" if front else "rear"]
    ro, ri = D / 2, D / 2 - 0.050
    carbon = _mk(mats, "carbonbrake", (0.06, 0.06, 0.065), metal=0.1, rough=0.7)
    bm = bmesh.new()
    face = T * 0.32
    qm._annulus(bm, qm.circle(48, ro), qm.circle(48, ri), T / 2 - face, T / 2)
    qm._annulus(bm, qm.circle(48, ro), qm.circle(48, ri), -T / 2, -T / 2 + face)
    for k in range(vanes):
        ang = 2 * math.pi * k / vanes
        rm = (ro + ri) / 2
        _box_into(bm, (rm * math.cos(ang), rm * math.sin(ang), 0), (ro - ri - 0.004, 0.003, T - 2 * face + 0.0004), ang)
    disc = qm.obj(name, bm, carbon)
    bell = qm.ring(f"{name}_Bell", ri + 0.004, 0.044, 0.006, seg=24, origin="center",   # ハブまで届く取り付けのベル
                   material=_mk(mats, "alu", (0.75, 0.76, 0.78)))
    return [disc, bell]


def caliper(name: str, front: bool = True, span_deg: float = 52, mats=None):
    """6 ピストンの一体型キャリパー（ディスクをはさむ内外 2 つの本体と、外周をまたぐブリッジ、ピストン 3 つずつ）。
    ディスクの軸 Z、中心が原点で、+X 方向（角度 0）を中心に置く。戻り値はリスト"""
    D, T = BRAKE["front" if front else "rear"]
    ro = D / 2
    red = _mk(mats, "caliper", (0.75, 0.05, 0.05), metal=0.4, rough=0.35)
    steel = _mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    rc, h, w = ro - 0.024, 0.062, 0.030
    parts = []
    for tag, zc in (("In", -(T / 2 + w / 2 + 0.003)), ("Out", T / 2 + w / 2 + 0.003)):
        secs = []
        for k in range(9):
            a = math.radians(-span_deg / 2 + span_deg * k / 8)
            ca, sa = math.cos(a), math.sin(a)
            secs.append([((rc + x) * ca, (rc + x) * sa, zc + z) for x, z in rrect(h, w, 0.008, 2)])
        parts.append(qm.loft(f"{name}_{tag}", secs, material=red))
        for i, frac in enumerate((-0.3, 0.0, 0.3)):
            a = math.radians(span_deg * frac)
            out = 1 if zc > 0 else -1
            parts.append(qm.cylinder(f"{name}_{tag}_Piston{i + 1}", 0.013, 0.006, seg=16, origin="bottom",
                                     location=(rc * math.cos(a), rc * math.sin(a), zc + out * (w / 2 - 0.001)), material=red))
            if out < 0:
                qm.pivot(parts[-1], (rc * math.cos(a), rc * math.sin(a), zc - w / 2), (180, 0, 0))
    secs = []
    for k in range(5):
        a = math.radians(-span_deg * 0.35 + span_deg * 0.7 * k / 4)
        secs.append([((ro + 0.012 + x) * math.cos(a), (ro + 0.012 + x) * math.sin(a), z)
                     for x, z in rrect(0.020, T + 2 * w + 0.006, 0.006, 2)])
    parts.append(qm.loft(f"{name}_Bridge", secs, material=red))
    parts.append(qm.cylinder(f"{name}_Bleed", 0.004, 0.014, seg=8, axis="X",
                             location=(ro + 0.024 + 0.007, 0, T / 2 + w / 2), material=steel))
    return parts


def hub_and_nut(name: str, mats=None):
    """ハブ（軸受の外輪をつなぐ筒と、ホイールを回す 6 本のドライブピン）とセンターロックナット。
    軸 Z、ホイールの取り付け面が z=0、外側が +Z。戻り値はリスト"""
    steel = _mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    ti = _mk(mats, "titanium", (0.45, 0.45, 0.47), metal=1.0, rough=0.3)
    parts = [qm.ring(f"{name}_Hub", 0.042, 0.022, 0.10, seg=24, location=(0, 0, -0.08), material=ti),
             qm.ring(f"{name}_Flange", 0.075, 0.042, 0.010, seg=24, location=(0, 0, -0.010), material=ti)]
    for k in range(6):
        a = 2 * math.pi * k / 6
        parts.append(qm.cylinder(f"{name}_DrivePin{k + 1}", 0.006, 0.018, seg=12, location=(0.060 * math.cos(a), 0.060 * math.sin(a), 0),
                                 material=steel))
    nut = qm.ring(f"{name}_Nut", 0.038, 0.020, 0.028, seg=24, location=(0, 0, 0.020), material=_mk(mats, "nut", (0.8, 0.65, 0.1), 0.9, 0.3))
    parts.append(nut)
    for k in range(6):
        a = 2 * math.pi * (k + 0.5) / 6
        parts.append(qm.box(f"{name}_NutLug{k + 1}", (0.014, 0.010, 0.020), origin="bottom",
                            location=(0.042 * math.cos(a), 0.042 * math.sin(a), 0.024), material=nut.data.materials[0]))
        qm.pivot(parts[-1], (0.042 * math.cos(a), 0.042 * math.sin(a), 0), (0, 0, math.degrees(a)))
    return parts


def rim(name: str, front: bool = True, spokes: int = 10, mats=None):
    """18 インチのホイール（リムの断面を回した殻、スポーク、中心の筒）。軸 Z、取り付け面 z=0、外側が +Z。
    戻り値はリスト"""
    _, W = SPEC["front_tyre"] if front else SPEC["rear_tyre"]
    mag = _mk(mats, "rim", (0.08, 0.08, 0.09), metal=0.8, rough=0.3)
    bead = SPEC["rim_inch"] * 0.0254 / 2
    w = W * 0.95
    z0, z1 = -w * 0.55, w * 0.45                     # 取り付け面がホイールの中央より少し外側
    ri, fl = bead - 0.010, 0.017
    prof = [(ri, z0), (bead + fl, z0), (bead + fl, z0 + 0.007), (bead, z0 + 0.016), (bead - 0.004, (z0 + z1) / 2),
            (bead, z1 - 0.016), (bead + fl, z1 - 0.007), (bead + fl, z1), (ri, z1), (ri - 0.004, (z0 + z1) / 2)]
    shell = qm.lathe(f"{name}_Barrel", prof, seg=48, closed=True, material=mag)
    center = qm.ring(f"{name}_Center", 0.068, 0.040, 0.050, seg=24, location=(0, 0, -0.010), material=mag)
    parts = [shell, center]
    for k in range(spokes):
        a = 2 * math.pi * k / spokes
        ca, sa = math.cos(a), math.sin(a)
        path = [(0.062 * ca, 0.062 * sa, 0.030), (0.14 * ca, 0.14 * sa, 0.045), ((ri - 0.002) * ca, (ri - 0.002) * sa, z1 - 0.025)]
        parts.append(qm.sweep(f"{name}_Spoke{k + 1}", path, [(-0.009, -0.006), (0.009, -0.006), (0.009, 0.006), (-0.009, 0.006)],
                              up=(0, 0, 1), material=mag))
    return parts


def upright(name: str, center, upper, lower, steer, axis=(-1, 0, 0), mats=None):
    """アップライト（軸受のハウジングと、上・下・ステア用の 3 本の腕。腕の先に球面軸受の受け）。
    center は軸受の中心、axis はホイールの外向き。upper / lower / steer は腕の先の点。戻り値はリスト"""
    ti = _mk(mats, "titanium", (0.45, 0.45, 0.47), metal=1.0, rough=0.3)
    c, ax = Vector(center), Vector(axis).normalized()
    house = qm.ring(f"{name}_Housing", 0.068, 0.042, 0.075, seg=24, origin="center", material=ti)
    qm.orient(house, origin=c, x_axis=ax.orthogonal(), z_axis=ax)
    parts = [house]
    for tag, p in (("Upper", upper), ("Lower", lower), ("Steer", steer)):
        p = Vector(p)
        start = c + (p - c).normalized() * 0.055
        parts.append(qm.sweep(f"{name}_{tag}Arm", [start, (start + p) / 2 - ax * 0.01, p],
                              [(-0.012, -0.016), (0.012, -0.016), (0.012, 0.016), (-0.012, 0.016)], up=ax, material=ti))
        boss = qm.ring(f"{name}_{tag}Boss", 0.016, 0.009, 0.022, seg=16, origin="center", material=ti)
        qm.orient(boss, origin=p, x_axis=ax, z_axis=(0, 0, 1) if tag != "Steer" else (0, 1, 0))
        parts.append(boss)
    return parts


def steering_rack(name: str, center, half: float = 0.17, mats=None):
    """ステアリングラック（本体の筒、ピニオンの箱、左右の蛇腹ブーツ）。X 方向に置く。戻り値はリスト"""
    alu = _mk(mats, "alu", (0.75, 0.76, 0.78), metal=0.9, rough=0.3)
    rubber = _m(mats, "tyre") or qm.material("F1_Boot", (0.03, 0.03, 0.03), rough=0.8)
    c = Vector(center)
    body = qm.cylinder(f"{name}_Body", 0.022, half * 1.2, seg=16, axis="X", location=c, material=alu)
    pinion = qm.cylinder(f"{name}_Pinion", 0.026, 0.07, seg=16, location=c + Vector((0.04, 0, 0.0)), material=alu)
    qm.pivot(pinion, c + Vector((0.04, 0, 0)), (-35, 0, 0))
    parts = [body, pinion]
    for side in (-1, 1):
        prof = [(0.018 if k % 2 == 0 else 0.027, k * 0.0075) for k in range(13)]
        boot = qm.lathe(f"{name}_Boot{'L' if side < 0 else 'R'}", prof, seg=16, material=rubber)
        qm.orient(boot, origin=c + Vector((side * half * 0.6, 0, 0)), x_axis=(0, 1, 0), z_axis=(side, 0, 0))
        parts.append(boot)
    return parts


def tub(name: str = "Tub", mats=None):
    """モノコックの殻（上が開いたバスタブ形、厚み 8mm）、前後の隔壁、ロールフープ。戻り値はリスト"""
    z0 = EST["plank_z"] + 0.03
    st = [(-0.35, 0.30, 0.36), (0.0, 0.40, 0.44), (0.45, 0.56, 0.52), (0.95, 0.60, 0.56), (1.30, 0.58, 0.60)]

    def u_section(w, h, n=4, r=0.08):
        pts = [(-w / 2, z0 + h)]
        for k in range(n + 1):                                    # 左下の角
            a = math.radians(180 + 90 * k / n)
            pts.append((-w / 2 + r + r * math.cos(a), z0 + r + r * math.sin(a)))
        for k in range(n + 1):                                    # 右下の角
            a = math.radians(270 + 90 * k / n)
            pts.append((w / 2 - r + r * math.cos(a), z0 + r + r * math.sin(a)))
        pts.append((w / 2, z0 + h))
        return pts

    secs = [[(x, y, z) for x, z in u_section(w, h)] for y, w, h in st]
    shell = qm.loft(name, secs, closed=False, material=_m(mats, "carbon"))
    qm.solidify(shell, 0.008)
    front = plate(f"{name}_FrontBulkhead", [(-0.15, z0), (0.15, z0), (0.15, z0 + 0.36), (-0.15, z0 + 0.36)],
                                0.010, axis="Z", at=0, material=_m(mats, "carbon"))
    qm.pivot(front, (0, 0, 0), (90, 0, 0))
    qm._place(front, (0, -0.35, 0))
    rear = plate(f"{name}_RearBulkhead", [(-0.29, z0), (0.29, z0), (0.29, z0 + 0.60), (-0.29, z0 + 0.60)],
                 0.010, axis="Z", at=0, material=_m(mats, "carbon"))
    qm.pivot(rear, (0, 0, 0), (90, 0, 0))
    qm._place(rear, (0, 1.30, 0))
    hoop = qm.tube(f"{name}_RollHoop", [(-0.18, 1.30, z0 + 0.60), (-0.06, 1.24, z0 + 0.86), (0.06, 1.24, z0 + 0.86), (0.18, 1.30, z0 + 0.60)],
                   radius=0.02, seg=10, material=_m(mats, "titanium") or qm.material("F1_Titanium", (0.45, 0.45, 0.47), metal=1.0, rough=0.3))
    return [shell, front, rear, hoop]


HELP = """f1（F1 マシン 2026 年規定の部品。run_script の中でそのまま使える。前 = -Y、前輪の軸 y=0、上 = Z）

まとめて作る: f1.car(livery=(r,g,b), front_wing_elements=3, wheel_covers=True) → {種類: [オブジェクト...]}

部品ごと（mats=f1.materials(livery) を渡すと色が付く）
- f1.monocoque() / f1.nose()                 サバイバルセル / ノーズ
- f1.front_wing(elements=3)                  フロントウイング（翼・翼端板・支柱）
- f1.rear_wing()                             リアウイング 3 枚・翼端板・スワンネック・レインライト
- f1.floor_and_diffuser()                    フロア・ディフューザー
- f1.sidepods() / f1.engine_cover() / f1.airbox_inlet()   サイドポッド左右 / エンジンカバーとギアボックス / 吸気口と T カム
- f1.halo() / f1.driver() / f1.mirrors()     ヘイロー / ヘルメット / ミラー左右
- f1.tyre_and_wheel(name, front=True, location=(x,y,z))   タイヤ・18 インチホイール・カバー
- f1.suspension(name, front=True)            左側のサスペンション（qm.mirror で右）

部品づくりの道具
- f1.body(name, [(y, 中心x, 下端z, 幅, 高さ, 角の半径), ...])   断面を並べたなめらかな胴体
- f1.wing_element(name, span, chord, y_le, z, aoa, camber=-0.05)  翼 1 枚（NACA 断面）
- f1.plate(name, 輪郭, 厚み, axis="X"|"Z", at=)                   翼端板・フィン・フロアの板
- f1.rrect(w, h, r) 角の丸い長方形の断面

精密部品（シャシー・足まわり。どれも原点に作って qm.orient で据えるか、車の座標の点で直接作る）
- f1.rod_end(name, bore=0.008)               ロッドエンド（球面軸受・ねじ軸・ロックナット）。球の中心が原点、穴は Z、軸は -X
- f1.aero_strut(name, p0, p1, chord=0.035)  翼断面の支柱
- f1.wishbone(name, front_in, rear_in, outer)   A アーム（翼断面の腕 2 本＋ロッドエンド＋外側の球面軸受）
- f1.pushrod(name, p0, p1) / f1.damper(name, p0, p1)   プッシュロッド / ダンパー（本体・ロッド・コイルばね・ばね受け）
- f1.rocker(name, pivot, [腕の先の点...], normal)   ロッカー（ベルクランク）
- f1.brake_disc(name, front=True) / f1.caliper(name, front=True)   ベンチレーテッドディスク（前 328×32mm / 後ろ 280×32mm）/ 6 ピストンキャリパー
- f1.hub_and_nut(name) / f1.rim(name, front=True, spokes=10)   ハブ・ドライブピン・センターナット / 18 インチホイール
- f1.upright(name, center, upper, lower, steer, axis)   アップライト（軸受ハウジングと 3 本の腕）
- f1.steering_rack(name, center) / f1.tub()   ステアリングラック（蛇腹ブーツ付き）/ モノコックの殻・隔壁・ロールフープ

寸法: f1.SPEC（2026 年規定で確認できた値）、f1.EST（推定値）、f1.BRAKE（ディスクの直径・厚み）。変えたいときは f1.EST["height"] = 0.93 のように上書きしてから作る
"""
