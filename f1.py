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
    # バンプラバー（ロッドに通したゴム。縮みきる手前で当たる）
    packer = qm.ring(f"{name}_Packer", body_r * 0.55, body_r * 0.3, 0.010, seg=16, location=(0, 0, e + L * 0.55 + 0.001),
                     material=qm.material("F1_Rubber", (0.15, 0.15, 0.16), metal=0.0, rough=0.8))
    parts = [body, rod, perch1, perch2, spring, packer]
    for tag, z, xdir in (("A", 0.0, (0, 0, 1)), ("B", L, (0, 0, -1))):
        re_ = rod_end(f"{name}_RodEnd{tag}", bore, shank=0.012, mats=mats)
        qm.orient(re_, origin=(0, 0, z), x_axis=(0, 0, -1) if tag == "A" else (0, 0, 1), z_axis=(1, 0, 0))
        parts += re_
    d = (b - a).normalized()
    qm.orient(parts, origin=a, x_axis=d.orthogonal(), z_axis=d)
    return parts


def rocker(name: str, pivot, arms, normal=(1, 0, 0), thickness: float = 0.012, clevis: bool = False, mats=None):
    """ロッカー（ベルクランク）。pivot を軸（normal 方向）に、arms の各点へ腕を伸ばす。
    arms は腕の先の点（車の座標）。腕の先と軸に穴のあるボスが付く。軸のボスには針状ころ軸受を 2 個入れる。
    clevis=True なら腕の先のボスを作らず、腕を手前で止める（ロッドエンドを二股の金具で受ける）。戻り値はリスト"""
    alu = _mk(mats, "alu", (0.75, 0.76, 0.78), metal=0.9, rough=0.3)
    steel = _mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    pv, n = Vector(pivot), Vector(normal).normalized()
    hub_h = thickness * 1.6
    parts = [qm.ring(f"{name}_Hub", 0.020, 0.012, hub_h, seg=16, origin="center", material=alu)]
    qm.orient(parts[0], origin=pv, x_axis=n.orthogonal(), z_axis=n)
    for k, sgn in enumerate((-1, 1)):                     # 軸の針状ころ軸受（外輪だけ。中のころは省略）
        b = qm.ring(f"{name}_HubBrg{k + 1}", 0.012, 0.008, hub_h * 0.45, seg=16, origin="center", material=steel)
        qm.orient(b, origin=pv + n * sgn * hub_h * 0.25, x_axis=n.orthogonal(), z_axis=n)
        parts.append(b)
    for k, end in enumerate(arms):
        e = Vector(end)
        e = e - n * n.dot(e - pv)            # 腕の先を、軸に垂直な面に乗せる
        e2 = e - (e - pv).normalized() * (0.014 if clevis else 0.0)
        web = qm.sweep(f"{name}_Arm{k + 1}", [pv, e2], [(-0.009, -thickness / 2), (0.009, -thickness / 2),
                                                         (0.009, thickness / 2), (-0.009, thickness / 2)], up=n, material=alu)
        parts.append(web)
        if not clevis:
            boss = qm.ring(f"{name}_Boss{k + 1}", 0.013, 0.006, thickness * 1.3, seg=16, origin="center", material=alu)
            qm.orient(boss, origin=e, x_axis=n.orthogonal(), z_axis=n)
            parts.append(boss)
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
    bell = qm.ring(f"{name}_Bell", ri + 0.012, 0.044, 0.006, seg=24, origin="center",   # ハブまで届く取り付けのベル
                   material=_mk(mats, "alu", (0.75, 0.76, 0.78)))
    parts = [disc, bell]
    # ディスクの内周の切り欠きにはまり、ベルの回転を伝えるボビン（ディスクが熱で伸びても動けるように浮かせて留める。数は推定）
    steel = _mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    for k in range(12):
        a = 2 * math.pi * (k + 0.5) / 12
        parts.append(qm.cylinder(f"{name}_Bobbin{k + 1}", 0.0035, T * 0.9, seg=12, origin="center",
                                 location=((ri + 0.006) * math.cos(a), (ri + 0.006) * math.sin(a), 0), material=steel))
    return parts


CALIPER = {"w": 0.030, "h": 0.062, "pad": 0.018, "backing": 0.004}   # 本体の厚み・高さ、パッドの摩擦材と裏板の厚み（推定）


def caliper_body_offset(front: bool = True):
    """ディスクの中心から、キャリパーの片側の本体の中心までの (軸方向の距離, 半径)"""
    D, T = BRAKE["front" if front else "rear"]
    c = CALIPER
    return T / 2 + c["pad"] + c["backing"] + 0.001 + c["w"] / 2, D / 2 - 0.024


def caliper(name: str, front: bool = True, span_deg: float = 52, mats=None):
    """6 ピストンの一体型（モノブロック）キャリパー。ディスクをはさむ内外の本体と外周のブリッジを 1 つの部品にし、
    ディスクの側にピストンの穴を 3 つずつ掘る。ピストンが裏板つきのパッドをディスクへ押す。パッドは上から通すピンで止める。
    ディスクの軸 Z、中心が原点で、+X 方向（角度 0）を中心に置く。戻り値はリスト"""
    D, T = BRAKE["front" if front else "rear"]
    ro = D / 2
    red = _mk(mats, "caliper", (0.75, 0.05, 0.05), metal=0.4, rough=0.35)
    steel = _mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    ti = _mk(mats, "titanium", (0.45, 0.45, 0.47), metal=1.0, rough=0.3)
    padm = _mk(mats, "carbonbrake", (0.06, 0.06, 0.065), metal=0.1, rough=0.7)
    C = CALIPER
    w, h = C["w"], C["h"]
    zoff, rc = caliper_body_offset(front)
    face = zoff - w / 2                                   # 本体のディスク側の面

    def arc_loft(nm, r0, rad_h, z0, z1, frac, mat, n=9):
        secs = []
        for k in range(n):
            a = math.radians(span_deg * frac * (-0.5 + k / (n - 1)))
            ca, sa = math.cos(a), math.sin(a)
            secs.append([((r0 + x) * ca, (r0 + x) * sa, (z0 + z1) / 2 + z) for x, z in rrect(rad_h, z1 - z0, 0.004, 2)])
        return qm.loft(nm, secs, material=mat)

    body = arc_loft(name, rc, h, face, face + w, 1.0, red)
    half_in = arc_loft(f"{name}_tmpIn", rc, h, -face - w, -face, 1.0, red)
    bridge = arc_loft(f"{name}_tmpBridge", ro + 0.012, 0.020, -face - w, face + w, 0.7, red, n=5)
    qm.union(body, [half_in, bridge])
    parts = [body]
    cut = []
    for side in (-1, 1):
        for i, frac in enumerate((-0.3, 0.0, 0.3)):
            a = math.radians(span_deg * frac)
            p = (rc * math.cos(a), rc * math.sin(a))
            c = qm.cylinder(f"_bore{side}{i}", 0.0135, 0.016, seg=24, origin="bottom", location=(p[0], p[1], 0))
            c.matrix_world = fasten.frame((p[0], p[1], side * (face - 0.001)), (0, 0, side))
            cut.append(c)
            pst = qm.cylinder(f"{name}_Piston{'In' if side < 0 else 'Out'}{i + 1}", 0.013, 0.014, seg=24, material=ti)
            pst.matrix_world = fasten.frame((p[0], p[1], side * (face - 0.001)), (0, 0, side))
            parts.append(pst)
    pin_r = rc + h / 2 - 0.004                              # パッドの上の縁を通るピン
    cut.append(qm.cylinder("_pinhole", 0.0032, 2 * (face + w) + 0.002, seg=12, origin="center", location=(pin_r, 0, 0)))
    qm.cut(body, cut)
    for side, tag in ((-1, "In"), (1, "Out")):
        z_bk = side * (face - 0.001 - C["backing"] / 2)
        z_pd = side * (T / 2 + 0.0005 + C["pad"] / 2)
        bk = arc_loft(f"{name}_PadPlate{tag}", rc + 0.002, h - 0.004, z_bk - C["backing"] / 2, z_bk + C["backing"] / 2, 0.86, ti)
        pd = arc_loft(f"{name}_Pad{tag}", rc - 0.002, h - 0.012, z_pd - C["pad"] / 2, z_pd + C["pad"] / 2, 0.82, padm)
        parts += [bk, pd]
    parts.append(qm.cylinder(f"{name}_PadPin", 0.003, 2 * (face + w) + 0.006, seg=12, origin="center", location=(pin_r, 0, 0), material=steel))
    parts.append(qm.ring(f"{name}_PadPinClip", 0.0055, 0.003, 0.002, seg=12, origin="bottom", location=(pin_r, 0, face + w + 0.0005), material=steel))
    parts.append(qm.cylinder(f"{name}_Bleed", 0.004, 0.014, seg=8, axis="X",
                             location=(rc + h / 2 + 0.006, 0.012, face + w / 2), material=steel))
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
    # ナットの抜け止め（規定で、ナットが緩んでもホイールが外れないようにする仕組みが求められる。形は推定）
    parts.append(qm.ring(f"{name}_Retainer", 0.024, 0.018, 0.004, seg=24, location=(0, 0, 0.048), material=steel))
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


def upright(name: str, center, upper, lower, steer, axis=(-1, 0, 0), clevis: bool = False, mats=None):
    """アップライト（軸受のハウジングと、上・下・ステア用の 3 本の腕。腕の先に球面軸受の受け）。
    center は軸受の中心、axis はホイールの外向き。upper / lower / steer は腕の先の点。
    ハウジングの中に、ハブを支える玉軸受を 2 個（内と外）入れる。
    clevis=True なら腕の先の受け（輪）を作らず、腕を手前で止める（f1.fasten.rod_end_joint の二股の金具で受ける）。
    戻り値はリスト"""
    ti = _mk(mats, "titanium", (0.45, 0.45, 0.47), metal=1.0, rough=0.3)
    steel = _mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    c, ax = Vector(center), Vector(axis).normalized()
    house = qm.ring(f"{name}_Housing", 0.068, 0.056, 0.075, seg=24, origin="center", material=ti)
    qm.orient(house, origin=c, x_axis=ax.orthogonal(), z_axis=ax)
    parts = [house]
    for tag, dz in (("In", -0.0275), ("Out", 0.0275)):     # 玉軸受（内輪 r42・外輪 r56・幅 18mm。寸法は推定）
        brg = qm.ball_bearing(f"{name}_Brg{tag}", 0.084, 0.112, 0.018, balls=16, material=steel)
        qm.orient(brg, origin=c + ax * dz, x_axis=ax.orthogonal(), z_axis=ax)
        parts += brg
    for tag, p in (("Upper", upper), ("Lower", lower), ("Steer", steer)):
        p = Vector(p)
        start = c + (p - c).normalized() * 0.055
        end = p - (p - start).normalized() * (0.010 if clevis else 0.0)
        parts.append(qm.sweep(f"{name}_{tag}Arm", [start, (start + end) / 2 - ax * 0.01, end],
                              [(-0.012, -0.016), (0.012, -0.016), (0.012, 0.016), (-0.012, 0.016)], up=ax, material=ti))
        if not clevis:
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


# ---------------------------------------------------------------- シャシーの後ろ（ギアボックス・ドライブシャフトなど）
# 寸法はすべて推定（ギアボックスやドライブシャフトの寸法は公表されていない）。引数をミリ単位で考えやすいよう、
# 呼び出し側で MM = 0.001 を掛けて渡す使い方を想定している


def gearbox_flange_bolts():
    """エンジンとギアボックスをつなぐフランジのボルト 12 本の (x, z)（メートル）"""
    z0 = EST["plank_z"] + 0.03
    fz = z0 - 0.015 + 0.435 / 2
    return ([(x, fz + s * 0.195) for x in (-0.18, -0.06, 0.06, 0.18) for s in (-1, 1)] +
            [(s * 0.18, fz + t * 0.07) for s in (-1, 1) for t in (-1, 1)])


def gearbox(name: str = "Gearbox", y0: float = 2.90, length: float = 0.66, mats=None):
    """ギアボックスのケース（前のベルハウジングのフランジから、後ろへ絞り込む）。y0 がエンジン後端の面。
    戻り値 [フランジ, ケース]"""
    z0 = EST["plank_z"] + 0.03
    # クラッチはクランクの高さ（低い）にあるので、ベルハウジングと前のケースは下まで伸ばす
    flange = body(f"{name}_Flange", [(y0, 0, z0 - 0.015, 0.40, 0.435, 0.06), (y0 + 0.022, 0, z0 - 0.015, 0.40, 0.435, 0.06)],
                  _mk(mats, "magnesium", (0.32, 0.32, 0.34), 0.6, 0.5), n=4)
    st = [(y0 + 0.020, 0, z0 - 0.01, 0.32, 0.41, 0.05), (y0 + 0.20, 0, z0 + 0.0, 0.28, 0.40, 0.05),
          (y0 + 0.42, 0, z0 + 0.12, 0.30, 0.30, 0.05),      # デフ（ドライブシャフトの出口）のあたりで少し広い
          (y0 + 0.56, 0, z0 + 0.15, 0.20, 0.24, 0.04), (y0 + length, 0, z0 + 0.18, 0.15, 0.18, 0.03)]
    case = body(name, st, _m(mats, "carbon"), n=4)
    if not HOLLOW:
        return [flange, case]
    # ---- 実物どおり（中空のケース、前後の軸受の壁、デフの軸受の受け、軸・ドラム・出力の穴、フランジの開口とボルト穴）
    # 軸の位置は f1_gearbox_internals_mm.py と同じ：入力軸 z=270・出力軸 z=355（mm）、シフトドラム x=75、デフ y=3400。すべて推定
    MM = 0.001
    wall = 0.006

    def at(y):                               # 外形の断面を y で補間
        for a, b in zip(st, st[1:]):
            if a[0] <= y <= b[0]:
                t = (y - a[0]) / (b[0] - a[0])
                return tuple(a[k] + (b[k] - a[k]) * t for k in range(6))
        return st[0] if y < st[0][0] else st[-1]

    def shrink(c, y):
        return (y, c[1], c[2] + wall, c[3] - 2 * wall, c[4] - 2 * wall, max(0.004, c[5] - wall))
    def cavity(ya, yb):                      # ya〜yb の空洞（外形の断面を肉厚ぶん縮めた形）
        ys_ = [ya] + [c[0] for c in st if ya < c[0] < yb] + [yb]
        return body("_gbi", [shrink(at(min(max(y, st[0][0]), st[-1][0])), y) for y in ys_], None, n=4)
    # 空洞は 3 つ（ベルハウジング・ギアの部屋・デフの部屋）。間に残る壁が、前後の軸受の壁になる
    holes = [cavity(y0 - 0.005, y0 + 0.062), cavity(y0 + 0.089, y0 + 0.353), cavity(y0 + 0.395, y0 + length - wall)]
    for z, r in ((0.270, 0.031), (0.355, 0.036)):                       # 入力軸・出力軸の軸受の穴（前後の壁）
        for ya, yb in ((y0 + 0.056, y0 + 0.095), (y0 + 0.347, y0 + 0.401)):
            holes.append(qm.cylinder("_bb", r, yb - ya, seg=40, axis="Y", location=(0, (ya + yb) / 2, z)))
    # クラッチの軸（クランクの高さ）の軸受の穴（前の壁）。段差のギアで入力軸へ上げる
    holes.append(qm.cylinder("_cb", 0.031, 0.04, seg=40, axis="Y", location=(0, y0 + 0.0755, LAYOUT["crank_z"] * 0.001)))
    holes.append(qm.cylinder("_drum", 0.031, 0.06, seg=32, axis="Y", location=(0.075, y0 + 0.07, 0.355)))   # シフトドラムのアクチュエーター
    for s_ in (-1, 1):                                                   # 左右の横：デフの軸受の受け（別の部品）を差し込む穴
        holes.append(qm.cylinder("_dside", 0.062, 0.08, seg=48, axis="X", location=(s_ * 0.120, 3.400, 0.355)))
    qm.cut(case, holes)
    qm.cut(flange, [body("_gfo", [shrink(at(st[0][0]), y0 - 0.01), shrink(at(st[0][0]), y0 + 0.03)], None, n=4)])
    # デフの軸受の受け（左右から差し込んでボルトで留める。中に軸受、外は出力軸の穴）
    extra = []
    ti = _mk(mats, "titanium", (0.45, 0.45, 0.47), metal=1.0, rough=0.3)
    for s_, t_ in ((-1, "L"), (1, "R")):
        car = qm.ring(f"{name}_DiffCarrier{t_}", 0.062, 0.050, 0.045, seg=48, origin="center", material=ti)
        fl = qm.ring(f"{name}_DiffCarrier{t_}_Flange", 0.080, 0.033, 0.006, seg=48, origin="center", material=ti)
        qm.orient(car, origin=(s_ * 0.1045, 3.400, 0.355), x_axis=(0, 1, 0), z_axis=(1, 0, 0))
        qm.orient(fl, origin=(s_ * 0.130, 3.400, 0.355), x_axis=(0, 1, 0), z_axis=(1, 0, 0))
        extra += [car, fl]
        for k in range(6):
            a_ = 2 * math.pi * k / 6
            bo = qm.bolt(f"{name}_DiffCarrier{t_}_Bolt{k + 1}", "M6", 0.02, material=_mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3))
            qm.orient(bo, origin=(s_ * 0.133, 3.400 + 0.071 * math.cos(a_), 0.355 + 0.071 * math.sin(a_)), x_axis=(0, 1, 0), z_axis=(s_, 0, 0))
            extra.append(bo)
    # フランジのボルト穴（エンジンとギアボックスをつなぐ 12 本）
    pos = gearbox_flange_bolts()
    qm.cut(flange, [qm.cylinder("_fb", 0.0052, 0.04, seg=16, axis="Y", location=(x, y0 + 0.011, z)) for x, z in pos])
    return [flange, case] + extra


def crash_structure(name: str = "RearCrash", y0: float = 3.55, length: float = 0.40, mats=None):
    """後ろの衝撃吸収構造（ギアボックスの後ろに付く、先細りの箱）。戻り値 [構造]"""
    z0 = EST["plank_z"] + 0.03
    st = [(y0, 0, z0 + 0.20, 0.15, 0.17, 0.03), (y0 + length * 0.6, 0, z0 + 0.22, 0.12, 0.14, 0.025),
          (y0 + length, 0, z0 + 0.24, 0.09, 0.10, 0.02)]
    return [body(name, st, _m(mats, "carbon"), n=3)]


def driveshaft(name: str, p_in, p_out, r: float = 0.016, mats=None):
    """ドライブシャフト（両端の等速ジョイントのハウジング、蛇腹ブーツ、シャフト）。p_in がギアボックス側。
    戻り値はリスト"""
    a, b = Vector(p_in), Vector(p_out)
    L = (b - a).length
    steel = _mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    rubber = _mk(mats, "boot", (0.03, 0.03, 0.03), metal=0.0, rough=0.8)
    hi, ho = 0.068, 0.060                       # ハウジングの長さ（内・外）
    bl = 0.075                                  # ブーツの長さ
    parts = [qm.lathe(f"{name}_InnerCV", [(0.046, 0.0), (0.046, hi * 0.8), (0.036, hi)], seg=24, material=steel)]
    boot = [(0.034 if k % 2 == 0 else 0.026 - 0.008 * k / 10, hi + bl * k / 10) for k in range(11)]
    boot[-1] = (r + 0.002, hi + bl)
    parts.append(qm.lathe(f"{name}_InnerBoot", boot, seg=20, material=rubber))
    parts.append(qm.lathe(f"{name}_Shaft", [(r, hi + bl), (r, L - ho - bl)], seg=16, material=steel))
    boot2 = [(r + 0.002, L - ho - bl)] + [(0.026 - 0.008 * (10 - k) / 10 if k % 2 else 0.032, L - ho - bl + bl * k / 10) for k in range(1, 11)]
    parts.append(qm.lathe(f"{name}_OuterBoot", boot2, seg=20, material=rubber))
    parts.append(qm.lathe(f"{name}_OuterCV", [(0.034, L - ho), (0.042, L - ho * 0.8), (0.042, L)], seg=24, material=steel))
    d = (b - a).normalized()
    qm.orient(parts, origin=a, x_axis=d.orthogonal(), z_axis=d)
    return parts


def anti_roll_bar(name: str, center, half: float, arm: float = 0.07, r: float = 0.010, mats=None):
    """アンチロールバー（X 方向のねじり棒と、両端の腕）。center は棒の中心。腕は +Z 方向へ立つ。
    戻り値 [棒, 左の腕, 右の腕]"""
    c = Vector(center)
    steel = _mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    bar = qm.tube(name, [c + Vector((-half, 0, 0)), c + Vector((half, 0, 0))], radius=r, seg=12, material=steel)
    arms = []
    for side in (-1, 1):
        base = c + Vector((side * (half - 0.012), 0, 0))
        arms.append(qm.sweep(f"{name}_Arm{'L' if side < 0 else 'R'}", [base, base + Vector((0, 0, arm))],
                             [(-0.006, -0.012), (0.006, -0.012), (0.006, 0.012), (-0.006, 0.012)], up=(0, 1, 0), material=steel))
    return [bar] + arms


# ---------------------------------------------------------------- ギアボックスの中身
# 確認できた事実: 前進 8 段（2014 年から）、シームレスシフト（シフトドラムの溝でフォークを動かす）、
#   クラッチはカーボンの多板で直径およそ 100mm、最終減速はかさ歯車で差動制限付きのデフ（油圧制御）へ。
# 推定: 軸間距離・歯車の幅・モジュール・歯数・軸受やデフの寸法（規定の数値は確かめられなかった）。
# どの部品も軸 Z・原点中心で作るので、qm.orient で据える


def clutch(name: str = "Clutch", plates: int = 4, d: float = 0.100, mats=None):
    """カーボンの多板クラッチ（外側のバスケット、摩擦板と鋼の板を交互、押し付け板、ハブ）。
    直径 d（外径）。軸 Z、エンジン側の端が z=0、+Z へ積む。戻り値はリスト"""
    carbon = _mk(mats, "carbonbrake", (0.06, 0.06, 0.065), metal=0.1, rough=0.7)
    steel = _mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    ti = _mk(mats, "titanium", (0.45, 0.45, 0.47), metal=1.0, rough=0.3)
    r = d / 2
    t_f, t_s = 0.0030, 0.0018
    z, parts = 0.004, []
    parts.append(qm.ring(f"{name}_Flywheel", r + 0.008, 0.016, 0.004, seg=32, material=steel))
    for k in range(plates):
        parts.append(qm.ring(f"{name}_Friction{k + 1}", r, r * 0.55, t_f, seg=32, location=(0, 0, z), material=carbon))
        z += t_f
        if k < plates - 1:
            parts.append(qm.ring(f"{name}_Steel{k + 1}", r + 0.004, r * 0.62, t_s, seg=32, location=(0, 0, z), material=steel))
            z += t_s
    parts.append(qm.ring(f"{name}_PressurePlate", r + 0.004, r * 0.45, 0.005, seg=32, location=(0, 0, z), material=steel))
    z += 0.005
    parts.append(qm.ring(f"{name}_Basket", r + 0.010, r + 0.004, z, seg=32, material=ti))
    parts.append(qm.ring(f"{name}_Hub", r * 0.55, 0.016, z + 0.012, seg=24, material=ti))
    return parts


def dog_hub(name: str, r_in: float = 0.018, r_out: float = 0.032, width: float = 0.016, dogs: int = 6, mats=None):
    """ドッグハブ（シフトスリーブ。両面のドッグと、フォークがはまる溝）。軸 Z、中心が原点。戻り値はリスト"""
    steel = _mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    w = width
    parts = [qm.ring(f"{name}_Left", r_out, r_in, w * 0.35, seg=24, location=(0, 0, -w / 2), material=steel),
             qm.ring(f"{name}_Groove", r_out - 0.004, r_in, w * 0.30, seg=24, location=(0, 0, -w * 0.15), material=steel),
             qm.ring(f"{name}_Right", r_out, r_in, w * 0.35, seg=24, location=(0, 0, w * 0.15), material=steel)]
    rm = (r_in + r_out) / 2
    for side in (-1, 1):
        for k in range(dogs):
            a = 2 * math.pi * (k + (0.5 if side > 0 else 0)) / dogs
            dog = qm.box(f"{name}_Dog{'L' if side < 0 else 'R'}{k + 1}", (0.008, 0.006, 0.004), origin="bottom" if side > 0 else "top",
                         location=(rm * math.cos(a), rm * math.sin(a), side * w / 2), material=steel)
            qm.pivot(dog, (rm * math.cos(a), rm * math.sin(a), 0), (0, 0, math.degrees(a)))
            parts.append(dog)
    return parts


def shift_barrel(name: str = "ShiftBarrel", length: float = 0.22, r: float = 0.024, tracks=(), mats=None):
    """シフトドラム（溝の付いた円筒）。tracks は溝の位置（z の値、軸方向）。溝は 2 枚のつばの間として表す。
    軸 Z、手前の端が z=0。後ろに回すアクチュエーターが付く。戻り値はリスト"""
    steel = _mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    alu = _mk(mats, "alu", (0.75, 0.76, 0.78), metal=0.9, rough=0.3)
    parts = [qm.cylinder(f"{name}_Drum", r, length, seg=24, material=steel)]
    for k, z in enumerate(tracks):
        for j, dz in enumerate((-0.006, 0.003)):
            parts.append(qm.ring(f"{name}_Track{k + 1}_{'A' if j == 0 else 'B'}", r + 0.004, r - 0.001, 0.003, seg=24,
                                 location=(0, 0, z + dz), material=steel))
    parts.append(qm.cylinder(f"{name}_Actuator", r * 1.25, 0.05, seg=24, location=(0, 0, -0.05), material=alu))
    return parts


def selector_fork(name: str, shaft_r: float, barrel_at, mats=None):
    """セレクターフォーク（ハブの溝を半周はさむ弧と、シフトドラムへ伸びる腕、溝に入るピン）。
    軸 Z の原点にハブ、barrel_at はドラムの中心（XY 平面上の点、ハブの面 z=0）。戻り値はリスト"""
    steel = _mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    bx, by = barrel_at[0], barrel_at[1]
    base = math.atan2(by, bx)
    rc = shaft_r + 0.004
    secs = []
    for k in range(13):
        a = base + math.radians(-100 + 200 * k / 12)
        ca, sa = math.cos(a), math.sin(a)
        secs.append([((rc + x) * ca, (rc + x) * sa, z) for x, z in rrect(0.008, 0.004, 0.0015, 1)])
    parts = [qm.loft(f"{name}_Arc", secs, material=steel)]
    start = Vector((rc * math.cos(base), rc * math.sin(base), 0))
    end = Vector((bx, by, 0)) - Vector((bx, by, 0)).normalized() * 0.026
    parts.append(qm.sweep(f"{name}_Arm", [start, end], [(-0.003, -0.006), (0.003, -0.006), (0.003, 0.006), (-0.003, 0.006)],
                          up=(0, 0, 1), material=steel))
    pin = qm.cylinder(f"{name}_Pin", 0.003, 0.006, seg=8, material=steel)
    qm.orient(pin, origin=end - Vector((bx, by, 0)).normalized() * 0.002, x_axis=(0, 0, 1), z_axis=Vector((bx, by, 0)).normalized())
    parts.append(pin)
    return parts


def needle_bearing(name: str, r_in: float, r_out: float, width: float, n: int = 14, mats=None):
    """ニードル軸受（細いころ n 本と、両端の保持器の輪）。軸 Z、中心が原点。空転するギアと軸の間に入れる。戻り値はリスト"""
    steel = _mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    rr = (r_out - r_in) / 2 * 0.95
    rm = (r_in + r_out) / 2
    parts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        parts.append(qm.cylinder(f"{name}_Roller{k + 1}", rr, width * 0.8, seg=8, origin="center",
                                 location=(rm * math.cos(a), rm * math.sin(a), 0), material=steel))
    for s, t in ((-1, "A"), (1, "B")):
        parts.append(qm.ring(f"{name}_Cage{t}", rm + rr * 0.6, rm - rr * 0.6, width * 0.1, seg=24, origin="center",
                             location=(0, 0, s * width * 0.45), material=steel))
    return parts


def differential(name: str = "Diff", case_r: float = 0.060, case_len: float = 0.15, mats=None):
    """デフ（ケース、両側の出力フランジ）。軸 Z、中心が原点（左右の車軸の向き）。戻り値はリスト"""
    ti = _mk(mats, "titanium", (0.45, 0.45, 0.47), metal=1.0, rough=0.3)
    steel = _mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    h = case_len / 2
    prof = [(0.022, -h), (case_r * 0.7, -h), (case_r, -h * 0.6), (case_r, h * 0.6), (case_r * 0.7, h), (0.022, h)]
    parts = [qm.lathe(f"{name}_Case", prof, seg=32, material=ti)]
    for side in (-1, 1):
        parts.append(qm.ring(f"{name}_Output{'L' if side < 0 else 'R'}", 0.030, 0.012, 0.040, seg=24,
                             location=(0, 0, side * h + (0 if side > 0 else -0.040)), material=steel))
    if not HOLLOW:
        return parts
    # ---- 実物どおり：中空のケース、左右のサイドギア（16 歯）、ピニオン 2 個（10 歯）とクロスピン、差動制限のクラッチ板
    # 歯数・モジュールは推定。ピニオンのピッチ角 = atan(10/16)
    qm.cut(parts[0], [qm.lathe("_dci", [(0.013, -h - 0.01), (0.013, -0.050), (0.046, -0.047), (0.050, -0.030), (0.050, 0.030),
                                        (0.046, 0.047), (0.013, 0.050), (0.013, h + 0.01)], seg=32)])
    m_, zs, zp = 0.003, 16, 10
    gp = math.degrees(math.atan(zp / zs))
    rs, rpn = m_ * zs / 2, m_ * zp / 2
    for side, tag in ((-1, "L"), (1, "R")):
        g = qm.bevel_gear(f"{name}_SideGear{tag}", zs, m_, 0.012, 90 - gp, material=steel)
        # 外側の端（ヒール）を、軸の交点から相手の基準円の半径だけ離す（= rpn）
        qm.orient(g, origin=(0, 0, side * rpn), x_axis=(1, 0, 0), z_axis=(0, 0, -side))
        hub = qm.cylinder(f"{name}_SideGear{tag}_Spline", 0.012, 0.035, seg=24, location=(0, 0, side * 0.015 + (0 if side > 0 else -0.035)), material=steel)
        parts += [g, hub]
        for k in range(6):          # クラッチ板（摩擦板と鋼の板を交互）
            z = side * (0.020 + k * 0.004)
            parts.append(qm.ring(f"{name}_ClutchPlate{tag}{k + 1}", 0.038, 0.015, 0.0018, seg=32, origin="center", location=(0, 0, z),
                                 material=steel if k % 2 else qm.material("F1_Friction", (0.25, 0.20, 0.15), metal=0.2, rough=0.8)))
    for side, tag in ((-1, "A"), (1, "B")):
        p_ = qm.bevel_gear(f"{name}_Pinion{tag}", zp, m_, 0.012, gp, material=steel)
        qm.orient(p_, origin=(side * rs, 0, 0), x_axis=(0, 0, 1), z_axis=(-side, 0, 0))
        parts.append(p_)
    parts.append(qm.cylinder(f"{name}_CrossPin", 0.007, 0.10, seg=16, axis="X", material=steel))
    return parts



# ---------------------------------------------------------------- シャシー全体の配置（車体を除く部品の図鑑用）
# 確認できた事実: ホイールベース 3,400mm、全幅 1,900mm、V6 90°・ボア 80mm・ストローク 53mm（1.6L）、
#   エネルギーストア（バッテリー）はサバイバルセルの中（ドライバーの後ろ、燃料タンクの下）。
# 推定: ここに並べた位置と寸法はすべて推定（公表されていない）。ミリで書き、使うときに MM を掛ける
LAYOUT = {
    "tub": [(-350, 300, 360), (0, 420, 440), (500, 540, 500), (1050, 620, 570), (1500, 700, 600),
            (1850, 720, 610), (2150, 720, 600), (2500, 620, 550)],     # (y, 幅, 高さ)。下端は plank_z + 30mm。後ろの隔壁にエンジンを直接留める
    "cockpit": (1050, 1850),          # コクピットの開口（前・後ろの y）
    "fuel_cell": (1880, 2240),        # 燃料タンクの前後
    "engine_front": 2500,             # エンジンの前のカバーの前面
    "crank_z": 125,                   # クランク軸の高さ。規定：基準面（プランクの上面）の 90mm 上（2026 年 Section C）。
                                      # 基準面の高さ 35mm（= EST["plank_z"]、車高）は推定
    "gearbox_y0": 2900,               # ギアボックスのフランジ（エンジン後端）
}
V6 = {"bore": 80.0, "stroke": 53.0, "vee": 90.0,                       # 確認できた値
      "pitch": 96.0, "stagger": 16.0, "rod": 110.0, "comp_h": 25.0,   # 以下は推定
      "deck": 170.0, "head": 110.0, "cover": 55.0, "block_w": 124.0, "head_w": 150.0}


HOLLOW = False   # True にすると、管・排気管・プレナム・ターボ・MGU-K を中が空の実物どおりに作る（ブーリアン。qm.cad() と一緒に）


def hollow(ob, points, r: float, wall: float):
    """管（qm.tube で points に沿って作った半径 r の物）を、肉厚 wall の中空にする（HOLLOW のときだけ）。両端は開く"""
    if not HOLLOW or r - wall <= 1e-4:
        return ob
    pts = [Vector(p) for p in points]
    a = pts[0] - (pts[1] - pts[0]).normalized() * (wall * 3)
    b = pts[-1] + (pts[-1] - pts[-2]).normalized() * (wall * 3)
    inner = qm.tube("_hollow", [a] + pts[1:-1] + [b], radius=r - wall, seg=max(12, len(ob.data.vertices) // max(len(pts), 1)))
    return qm.cut(ob, [inner])


def _z0():
    return EST["plank_z"] + 0.03


def tub_section(y_mm: float):
    """サバイバルセルの y（ミリ）での (幅, 上端の z) をミリで返す（LAYOUT["tub"] を直線でつなぐ）"""
    st = LAYOUT["tub"]
    y = min(max(y_mm, st[0][0]), st[-1][0])
    for (y0, w0, h0), (y1, w1, h1) in zip(st, st[1:]):
        if y0 <= y <= y1:
            t = (y - y0) / (y1 - y0)
            return w0 + (w1 - w0) * t, _z0() * 1000 + h0 + (h1 - h0) * t
    return st[-1][1], _z0() * 1000 + st[-1][2]


def _u(w, h, z0, n=4, r=0.08):
    """上が開いた U 字の断面（XZ）"""
    pts = [(-w / 2, z0 + h)]
    for k in range(n + 1):
        a = math.radians(180 + 90 * k / n)
        pts.append((-w / 2 + r + r * math.cos(a), z0 + r + r * math.sin(a)))
    for k in range(n + 1):
        a = math.radians(270 + 90 * k / n)
        pts.append((w / 2 - r + r * math.cos(a), z0 + r + r * math.sin(a)))
    pts.append((w / 2, z0 + h))
    return pts


def survival_cell(name: str = "Cell", mats=None):
    """サバイバルセル（足もとからエンジンの前までの殻）。LAYOUT["tub"] の断面を U 字でつなぎ、厚み 8mm。
    コクピットの開口の前後に上ぶた、前後の隔壁、ダッシュボードの梁（脚の上を渡すアーチ）。戻り値はリスト"""
    MM = 0.001
    z0 = _z0()
    carbon = _m(mats, "carbon")
    secs = [[(x, y * MM, z) for x, z in _u(w * MM, h * MM, z0)] for y, w, h in LAYOUT["tub"]]
    shell = qm.loft(name, secs, closed=False, material=carbon)
    qm.solidify(shell, 0.008)
    parts = [shell]
    c0, c1 = LAYOUT["cockpit"]
    y_end = LAYOUT["tub"][-1][0]
    for tag, ys in (("FrontDeck", [y for y in (-350, 0, 500, c0)]), ("RearDeck", [c1, 2150, y_end])):
        st = []
        for y in ys:
            w, top = tub_section(y)
            st.append((y * MM, 0, (top - 10) * MM, w * MM, 0.010, 0.004))
        parts.append(body(f"{name}_{tag}", st, carbon, n=2))
    for tag, y in (("FrontBulkhead", -350), ("RearBulkhead", y_end)):
        w, top = tub_section(y)
        b = qm.box(f"{name}_{tag}", ((w - 16) * MM, 0.010, (top - z0 * 1000 - 18) * MM), origin="bottom",
                   location=(0, y * MM + (0.005 if y < 0 else -0.005), z0 + 0.008), material=carbon)
        parts.append(b)
    w, top = tub_section(c0)
    hw = (w / 2 - 6) * MM
    arch = [(-hw, c0 * MM, z0 + 0.32), (-hw * 0.8, c0 * MM, (top - 40) * MM), (0, c0 * MM, (top - 25) * MM),
            (hw * 0.8, c0 * MM, (top - 40) * MM), (hw, c0 * MM, z0 + 0.32)]
    parts.append(qm.sweep(f"{name}_DashBeam", arch, [(-0.015, -0.02), (0.015, -0.02), (0.015, 0.02), (-0.015, 0.02)],
                          up=(0, 1, 0), material=carbon))
    return parts


def roll_hoop(name: str = "RollHoop", y: float = 1.87, top_z: float = 0.96, half_w: float = 0.20, mats=None):
    """ロールフープ（コクピットの後ろの転倒保護。左右の脚と、中央の縦の板）。戻り値はリスト"""
    MM = 0.001
    _, base = tub_section(y / MM)
    base *= MM
    ti = _mk(mats, "titanium", (0.45, 0.45, 0.47), metal=1.0, rough=0.3)
    hoop = qm.tube(name, [(-half_w, y + 0.01, base - 0.01), (-half_w * 0.5, y, top_z - 0.06), (0, y - 0.01, top_z),
                          (half_w * 0.5, y, top_z - 0.06), (half_w, y + 0.01, base - 0.01)], radius=0.024, seg=12, material=ti)
    blade = plate(f"{name}_Blade", [(y - 0.04, base - 0.01), (y + 0.10, base - 0.01), (y + 0.02, top_z - 0.01), (y - 0.03, top_z - 0.01)],
                  0.016, axis="X", at=0, material=_m(mats, "carbon"))
    return [hoop, blade]


def halo_frame(name: str = "Halo", rear_y: float = 1.80, front_y: float = 1.10, half_w: float = 0.28,
               top_z: float = 0.84, mats=None):
    """ヘイロー（チタンの輪。後ろの左右 2 か所と、前の 1 本の支柱でサバイバルセルに付く）。戻り値はリスト"""
    MM = 0.001
    ti = _mk(mats, "titanium", (0.45, 0.45, 0.47), metal=1.0, rough=0.3)
    _, zr = tub_section(rear_y / MM)
    _, zf = tub_section(front_y / MM)
    zr, zf = zr * MM - 0.01, zf * MM - 0.01
    span = rear_y - front_y
    pts = [(-half_w, rear_y, zr), (-half_w * 0.98, rear_y - span * 0.15, top_z - 0.06),
           (-half_w * 0.85, rear_y - span * 0.55, top_z - 0.01), (-half_w * 0.45, front_y + span * 0.08, top_z),
           (0, front_y + 0.02, top_z + 0.005)]
    pts = pts + [(-x, yy, zz) for x, yy, zz in reversed(pts[:-1])]
    ring = qm.tube(name, pts, radius=0.023, seg=12, material=ti)
    pillar = qm.sweep(f"{name}_Pillar", [(0, front_y + 0.02, top_z), (0, front_y - 0.02, (top_z + zf) / 2), (0, front_y - 0.04, zf)],
                      [(-0.012, -0.022), (0.012, -0.022), (0.012, 0.022), (-0.012, 0.022)], up=(0, -1, 0.3), material=ti)
    mounts = [qm.box(f"{name}_Mount{t}", (0.05, 0.08, 0.02), origin="bottom", location=(s * half_w, rear_y, zr - 0.005), material=ti)
              for s, t in ((-1, "L"), (1, "R"))]
    return [ring, pillar] + mounts


def seat(name: str = "Seat", path=None, width: float = 0.38, side_h: float = 0.09, mats=None):
    """ドライバーごとに型を取るシート（座面から背もたれまでの U 字の殻、厚み 10mm）。
    path は座面の中心線の点 [(y, z), ...]（前から背もたれの上へ、メートル）。戻り値 [シート]"""
    path = path or [(1.30, 0.090), (1.45, 0.080), (1.58, 0.092), (1.70, 0.20), (1.77, 0.40), (1.81, 0.60)]
    mat = qm.material("F1_SeatCarbon", (0.06, 0.06, 0.07), metal=0.1, rough=0.5)
    secs = []
    for i, (y, z) in enumerate(path):
        a = path[max(i - 1, 0)]
        b = path[min(i + 1, len(path) - 1)]
        t = Vector((0, b[0] - a[0], b[1] - a[1])).normalized()
        n = Vector((1, 0, 0)).cross(t).normalized()          # 座面から体の側（上・前）を向く
        if n.z < 0:
            n = -n
        c = Vector((0, y, z))
        prof = []
        for k in range(9):
            u = -1 + 2 * k / 8
            lift = side_h * (abs(u) ** 4)                    # 両脇が立ち上がる
            prof.append(c + Vector((u * width / 2, 0, 0)) + n * lift)
        secs.append([tuple(p) for p in prof])
    sh = qm.loft(name, secs, closed=False, material=mat)
    qm.solidify(sh, 0.010)
    return [sh]


def harness(name: str = "Harness", buckle=(0, 1.45, 0.26), straps=None, mats=None):
    """6 点式のシートベルト（肩 2・腰 2・股 2 の帯と、中央の回して外すバックル）。
    straps = [(名前, [取り付け点, 途中の点..., バックル側の点], 幅), ...]（メートル）。戻り値はリスト"""
    web = qm.material("F1_Harness", (0.85, 0.12, 0.10), metal=0.0, rough=0.8)
    steel = _mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    bx, by, bz = buckle
    straps = straps or [
        (f"{name}_ShoulderL", [(-0.09, 1.812, 0.60), (-0.10, 1.74, 0.56), (-0.07, 1.57, 0.42), (-0.02, by + 0.01, bz + 0.02)], 0.075),
        (f"{name}_ShoulderR", [(0.09, 1.812, 0.60), (0.10, 1.74, 0.56), (0.07, 1.57, 0.42), (0.02, by + 0.01, bz + 0.02)], 0.075),
        (f"{name}_LapL", [(-0.19, 1.60, 0.16), (-0.15, 1.50, 0.25), (-0.035, by, bz)], 0.075),
        (f"{name}_LapR", [(0.19, 1.60, 0.16), (0.15, 1.50, 0.25), (0.035, by, bz)], 0.075),
        (f"{name}_CrotchL", [(-0.04, 1.42, 0.086), (-0.03, 1.43, 0.18), (-0.012, by - 0.01, bz - 0.03)], 0.05),
        (f"{name}_CrotchR", [(0.04, 1.42, 0.086), (0.03, 1.43, 0.18), (0.012, by - 0.01, bz - 0.03)], 0.05),
    ]
    parts = []
    for nm, pts, w in straps:
        parts.append(qm.sweep(nm, pts, [(-w / 2, -0.0015), (w / 2, -0.0015), (w / 2, 0.0015), (-w / 2, 0.0015)], material=web))
    b = qm.cylinder(f"{name}_Buckle", 0.042, 0.018, seg=24, origin="center", material=steel)
    knob = qm.cylinder(f"{name}_BuckleKnob", 0.018, 0.012, seg=16, location=(0, 0, 0.009), material=steel)
    qm.orient([b, knob], origin=buckle, x_axis=(1, 0, 0), z_axis=(0, -0.5, 0.87))
    return parts + [b, knob]


def headrest(name: str = "Headrest", y0: float = 1.60, y1: float = 1.84, mats=None):
    """ヘッドレスト（コクピットの縁の後ろと左右を囲む、衝撃を吸う発泡材）。戻り値 [ヘッドレスト]"""
    MM = 0.001
    foam = qm.material("F1_Foam", (0.10, 0.10, 0.12), metal=0.0, rough=0.9)
    w, top = tub_section(y1 / MM)
    hw = (w / 2 - 40) * MM
    z = top * MM - 0.005
    path = [(-hw, y0, z), (-hw, y1, z), (hw, y1, z), (hw, y0, z)]
    return [qm.sweep(name, path, [(-0.04, 0), (0.04, 0), (0.04, 0.11), (-0.04, 0.11)], up=(0, 0, 1), material=foam)]


def steering_wheel(name: str = "Wheel", mats=None):
    """ステアリングホイール（本体・左右のグリップ・表示画面・シフトランプ・ボタン・回すスイッチ・
    裏のシフトパドル 2 枚とクラッチパドル 2 枚・クイックリリースのハブ）。
    原点が中心、X が左右、Z が上、+Y がドライバー側。寸法は推定。戻り値はリスト"""
    carbon = _m(mats, "carbon")
    grip = qm.material("F1_Grip", (0.05, 0.05, 0.05), metal=0.0, rough=0.9)
    screen = qm.material("F1_Screen", (0.02, 0.05, 0.08), metal=0.3, rough=0.1)
    led = qm.material("F1_LED", (0.1, 0.8, 0.2), metal=0.0, rough=0.3)
    btn_cols = [qm.material("F1_BtnRed", (0.8, 0.05, 0.05), rough=0.4), qm.material("F1_BtnYellow", (0.9, 0.7, 0.05), rough=0.4),
                qm.material("F1_BtnBlue", (0.05, 0.25, 0.8), rough=0.4), qm.material("F1_BtnWhite", (0.85, 0.85, 0.85), rough=0.4)]
    alu = _mk(mats, "alu", (0.75, 0.76, 0.78), metal=0.9, rough=0.3)
    parts = [body(name, [(-0.018, 0, -0.068, 0.22, 0.13, 0.03), (0.018, 0, -0.072, 0.25, 0.14, 0.03)], carbon, n=3)]
    for s, t in ((-1, "L"), (1, "R")):
        parts.append(qm.tube(f"{name}_Grip{t}", [(s * 0.118, 0, -0.085), (s * 0.140, 0.004, -0.04), (s * 0.145, 0.004, 0.02),
                                                 (s * 0.128, 0, 0.065)], radius=0.022, seg=12, material=grip))
    parts.append(qm.box(f"{name}_Screen", (0.105, 0.006, 0.062), origin="center", location=(0, 0.019, 0.012), material=screen))
    for k in range(10):
        x = -0.054 + 0.012 * k
        parts.append(qm.cylinder(f"{name}_ShiftLight{k + 1}", 0.0035, 0.008, seg=8, axis="Y", location=(x, 0.016, 0.058),
                                 material=led))
    k = 0
    for x in (-0.085, 0.085):
        for z in (0.03, 0.0, -0.03):
            k += 1
            parts.append(qm.cylinder(f"{name}_Button{k}", 0.0075, 0.008, seg=12, axis="Y", location=(x, 0.020, z),
                                     material=btn_cols[k % 4]))
    for x in (-0.035, 0.035):
        k += 1
        parts.append(qm.cylinder(f"{name}_Button{k}", 0.0075, 0.008, seg=12, axis="Y", location=(x, 0.020, -0.038),
                                 material=btn_cols[k % 4]))
    for j, x in enumerate((-0.055, -0.018, 0.018, 0.055)):
        parts.append(qm.cylinder(f"{name}_Rotary{j + 1}", 0.012, 0.016, seg=16, axis="Y", location=(x, 0.022, -0.058) if abs(x) < 0.03 else (x, 0.022, -0.052),
                                 material=alu))
    for s, t in ((-1, "L"), (1, "R")):
        p = qm.box(f"{name}_ShiftPaddle{t}", (0.075, 0.005, 0.045), origin="center", location=(s * 0.075, -0.030, 0.018), material=carbon)
        qm.pivot(p, (s * 0.04, -0.03, 0.018), (0, 0, s * -12))
        c = qm.box(f"{name}_ClutchPaddle{t}", (0.070, 0.005, 0.030), origin="center", location=(s * 0.070, -0.026, -0.040), material=alu)
        qm.pivot(c, (s * 0.04, -0.026, -0.04), (0, 0, s * -8))
        parts += [p, c]
    parts.append(qm.cylinder(f"{name}_PaddleMount", 0.032, 0.012, seg=16, axis="Y", location=(0, -0.024, 0), material=alu))
    parts.append(qm.cylinder(f"{name}_QuickRelease", 0.024, 0.045, seg=16, axis="Y", location=(0, -0.052, 0), material=alu))
    parts.append(qm.cylinder(f"{name}_ReleaseCollar", 0.030, 0.012, seg=16, axis="Y", location=(0, -0.060, 0), material=btn_cols[1]))
    return parts


def steering_column(name: str, points, r: float = 0.011, mats=None):
    """ステアリングコラム（軸と、折れ点ごとのユニバーサルジョイント）。points = [ラック側, 折れ点..., ホイール側]。
    戻り値はリスト"""
    steel = _mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    pts = [Vector(p) for p in points]
    parts = []
    for i, (a, b) in enumerate(zip(pts, pts[1:])):
        d = (b - a).normalized()
        a2 = a + d * (0.018 if i > 0 else 0)
        b2 = b - d * (0.018 if i < len(pts) - 2 else 0)
        parts.append(qm.tube(f"{name}_Shaft{i + 1}", [a2, b2], radius=r, seg=12, material=steel))
        for j, (p, s) in enumerate(((a, 1), (b, -1))):
            if (i == 0 and j == 0) or (i == len(pts) - 2 and j == 1):
                continue
            y = qm.box(f"{name}_Yoke{i + 1}{'AB'[j]}", (0.030, 0.012, 0.020), origin="center", material=steel)
            qm.orient(y, origin=p + d * s * 0.016, x_axis=d.orthogonal() if i % 2 == 0 else d.orthogonal().cross(d), z_axis=d)
            parts.append(y)
    for k, p in enumerate(pts[1:-1]):
        parts.append(qm.quad_sphere(f"{name}_UJoint{k + 1}", 0.020, n=2, location=tuple(p), material=steel))
    return parts


def pedal(name: str, pivot, pad, width: float = 0.07, mats=None):
    """床に軸のあるペダル（腕・足の裏の板・軸の受け）。pivot と pad はメートルの点。戻り値はリスト"""
    alu = _mk(mats, "alu", (0.75, 0.76, 0.78), metal=0.9, rough=0.3)
    ti = _mk(mats, "titanium", (0.45, 0.45, 0.47), metal=1.0, rough=0.3)
    a, b = Vector(pivot), Vector(pad)
    arm = qm.sweep(f"{name}_Arm", [a, b], [(-0.010, -0.007), (0.010, -0.007), (0.010, 0.007), (-0.010, 0.007)], up=(1, 0, 0), material=ti)
    d = (b - a).normalized()
    face = Vector((0, 1, 0.25)).normalized()
    face = (face - d * face.dot(d)).normalized()
    padob = qm.box(f"{name}_Pad", (width, 0.008, 0.09), origin="center", material=alu)
    qm.orient(padob, origin=b + face * 0.004, x_axis=(1, 0, 0), z_axis=d)
    hinge = qm.cylinder(f"{name}_Hinge", 0.012, 0.05, seg=12, axis="X", location=tuple(a), material=alu)
    return [arm, padob, hinge]


def master_cylinder(name: str, front, back, r: float = 0.011, mats=None):
    """ブレーキのマスターシリンダー（本体・リザーバーへの口・押し棒）。front が取り付け側。戻り値はリスト"""
    alu = _mk(mats, "alu", (0.75, 0.76, 0.78), metal=0.9, rough=0.3)
    steel = _mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    a, b = Vector(front), Vector(back)
    d = (b - a).normalized()
    L = (b - a).length
    body_ob = qm.tube(f"{name}_Body", [a, a + d * L * 0.55], radius=r, seg=12, material=alu)
    rod = qm.tube(f"{name}_Rod", [a + d * L * 0.5, b], radius=r * 0.35, seg=8, material=steel)
    port = qm.cylinder(f"{name}_Port", r * 0.45, r * 1.6, seg=8, location=tuple(a + d * L * 0.2 + Vector((0, 0, r * 0.6))), material=alu)
    return [body_ob, rod, port]


def fire_extinguisher(name: str = "Extinguisher", y0: float = 1.00, length: float = 0.30, r: float = 0.05, mats=None):
    """消火器（ボトル・弁・2 本の固定バンド）。床の上、Y 方向に寝かせる。戻り値はリスト"""
    z = _z0() + 0.008 + r
    bottle_mat = qm.material("F1_Bottle", (0.75, 0.08, 0.06), metal=0.4, rough=0.3)
    alu = _mk(mats, "alu", (0.75, 0.76, 0.78), metal=0.9, rough=0.3)
    prof = [(r * 0.5, 0), (r * 0.9, 0.004), (r, 0.02), (r, length - 0.03), (r * 0.8, length - 0.008), (r * 0.35, length)]
    bottle = qm.lathe(name, prof, seg=20, material=bottle_mat)
    valve = qm.cylinder(f"{name}_Valve", r * 0.35, 0.035, seg=12, location=(0, 0, length - 0.002), material=alu)
    qm.orient([bottle, valve], origin=(0, y0, z), x_axis=(1, 0, 0), z_axis=(0, 1, 0))
    straps = []
    for k, t in enumerate((0.25, 0.75)):
        straps.append(qm.ring(f"{name}_Strap{k + 1}", r + 0.004, r - 0.001, 0.02, seg=20, origin="center",
                              location=(0, y0 + length * t, z), material=alu))
        qm.pivot(straps[-1], (0, y0 + length * t, z), (90, 0, 0))
    return [bottle, valve] + straps


def side_impact(name: str, p_in, p_out, size=(0.09, 0.06), mats=None):
    """側面衝撃吸収構造（サバイバルセルの横から外へ伸びる、楕円断面の筒）。戻り値 [筒]"""
    w, h = size
    prof = [(w / 2 * math.cos(a), h / 2 * math.sin(a)) for a in (2 * math.pi * k / 16 for k in range(16))]
    return [qm.sweep(name, [p_in, p_out], prof, up=(0, 0, 1), scale=[1.0, 0.85], material=_m(mats, "carbon"))]


def fuel_cell(name: str = "FuelCell", y0: float = 1.88, y1: float = 2.24, half_w: float = 0.32, z0: float = 0.175,
              z1: float = 0.64, mats=None):
    """燃料タンク（ゴム袋の燃料セル・上の点検ふた・底の集油槽とポンプ）。戻り値はリスト"""
    bag = qm.material("F1_FuelBag", (0.35, 0.33, 0.25), metal=0.0, rough=0.8)
    alu = _mk(mats, "alu", (0.75, 0.76, 0.78), metal=0.9, rough=0.3)
    h = z1 - z0
    st = [(y0, 0, z0 + 0.01, half_w * 2 - 0.04, h - 0.02, 0.06), (y0 + 0.02, 0, z0, half_w * 2, h, 0.07),
          (y1 - 0.02, 0, z0, half_w * 2, h, 0.07), (y1, 0, z0 + 0.01, half_w * 2 - 0.04, h - 0.02, 0.06)]
    cell = body(name, st, bag, n=3)
    ym = (y0 + y1) / 2
    hatch = qm.cylinder(f"{name}_Hatch", 0.07, 0.010, seg=24, location=(0, ym, z1 - 0.002), material=alu)
    pump = qm.cylinder(f"{name}_Pump", 0.04, 0.12, seg=16, location=(0, ym, z0 + 0.003), material=alu)
    parts = [cell, hatch, pump]
    if HOLLOW:
        # 袋は厚み 3mm のゴム。中に、底の集油槽（コレクター）とその中のメインポンプ、左右の隅から集油槽へ送るリフトポンプ、
        # 燃料の流量計（FIA の指定品・超音波式。タンクの中に付ける）、フィルター、燃料の量の計測棒。配置と寸法は推定
        w = 0.003
        inner = body("_fci", [(y0 + w, 0, z0 + 0.01 + w, half_w * 2 - 0.04 - 2 * w, h - 0.02 - 2 * w, 0.06),
                              (y0 + 0.02 + w, 0, z0 + w, half_w * 2 - 2 * w, h - 2 * w, 0.07),
                              (y1 - 0.02 - w, 0, z0 + w, half_w * 2 - 2 * w, h - 2 * w, 0.07),
                              (y1 - w, 0, z0 + 0.01 + w, half_w * 2 - 0.04 - 2 * w, h - 0.02 - 2 * w, 0.06)], None, n=3)
        qm.cut(cell, [inner, qm.cylinder("_fch", 0.06, 0.02, seg=24, location=(0, ym, z1 - 0.012))])
        col = qm.box(f"{name}_Collector", (0.24, 0.18, 0.10), origin="bottom", location=(0, ym, z0 + w), material=alu)
        qm.cut(col, [qm.box("_coli", (0.236, 0.176, 0.10), origin="bottom", location=(0, ym, z0 + w + 0.002)),
                     qm.cylinder("_colp", 0.012, 0.03, seg=12, axis="X", location=(0.12, ym, z0 + 0.02)),
                     qm.cylinder("_colq", 0.012, 0.03, seg=12, axis="X", location=(-0.12, ym, z0 + 0.02))])
        parts.append(col)
        for s_, tg in ((-1, "L"), (1, "R")):
            lp = qm.cylinder(f"{name}_LiftPump{tg}", 0.016, 0.050, seg=16, axis="X", location=(s_ * (half_w - 0.06), ym, z0 + w + 0.018), material=alu)
            ln = qm.tube(f"{name}_LiftLine{tg}", [(s_ * (half_w - 0.085), ym, z0 + 0.021), (s_ * 0.105, ym, z0 + 0.021)], radius=0.006, seg=10,
                         material=qm.material("F1_PipeFuel", (0.55, 0.12, 0.10), metal=0.0, rough=0.6))
            parts += [lp, ln]
        fm = qm.cylinder(f"{name}_FlowMeter", 0.018, 0.090, seg=16, axis="Y", location=(0.07, ym, z0 + w + 0.120), material=alu)
        fl = qm.cylinder(f"{name}_Filter", 0.020, 0.060, seg=16, axis="Y", location=(-0.07, ym, z0 + w + 0.120), material=alu)
        lvl = qm.cylinder(f"{name}_LevelSensor", 0.006, h - 0.06, seg=12, location=(-0.16, ym + 0.12, z0 + w), material=alu)
        cross = qm.tube(f"{name}_FeedLine", [(-0.07, ym + 0.030, z0 + 0.123), (-0.07, ym + 0.05, z0 + 0.123), (0.07, ym + 0.05, z0 + 0.123),
                                              (0.07, ym + 0.045, z0 + 0.123)], radius=0.006, seg=10,
                        material=qm.material("F1_PipeFuel", (0.55, 0.12, 0.10), metal=0.0, rough=0.6))
        out = qm.tube(f"{name}_OutLine", [(0.07, ym - 0.045, z0 + 0.123), (0.07, ym - 0.08, z0 + 0.13), (0.25, y1 - 0.06, z1 - 0.09),
                                            (0.25, y1 - 0.04, z1 - 0.08)], radius=0.006, seg=10,
                      material=qm.material("F1_PipeFuel", (0.55, 0.12, 0.10), metal=0.0, rough=0.6))
        parts += [fm, fl, lvl, cross, out]
    return parts


def energy_store(name: str = "ES", y0: float = 1.88, y1: float = 2.24, width: float = 0.56, z0: float = 0.073,
                 h: float = 0.10, mats=None):
    """エネルギーストア（リチウムイオン電池の箱。上面の冷却板、前後の高電圧コネクター）。戻り値はリスト"""
    case = qm.material("F1_ESCase", (0.12, 0.13, 0.15), metal=0.5, rough=0.4)
    orange = qm.material("F1_HV", (0.95, 0.45, 0.05), metal=0.0, rough=0.5)
    alu = _mk(mats, "alu", (0.75, 0.76, 0.78), metal=0.9, rough=0.3)
    L = y1 - y0
    box = qm.box(name, (width, L, h), segs=(4, 4, 1), origin="bottom", location=(0, (y0 + y1) / 2, z0), material=case, bevel=0.006)
    plate_ob = qm.box(f"{name}_CoolingPlate", (width * 0.9, L * 0.9, 0.006), origin="bottom", location=(0, (y0 + y1) / 2, z0 + h),
                      material=alu)
    parts = [box, plate_ob]
    for k, x in enumerate((-width * 0.3, width * 0.3)):
        parts.append(qm.cylinder(f"{name}_HVConnector{k + 1}", 0.018, 0.03, seg=12, axis="Y", location=(x, y1 + 0.012, z0 + h * 0.5),
                                 material=orange))
    if HOLLOW:
        # 中：4 つのモジュール（それぞれ薄い板状の電池セルを並べ、両端の押さえ板、上の銅のバスバー、電池を見張る基板）と、
        # モジュールをつなぐ太いバスバー。セルの形（板状）と数・並べ方は推定（公表されていない）
        w_ = 0.0075
        qm.cut(box, [qm.box("_esi", (width - 2 * w_, L - 2 * w_, h - 2 * w_), origin="bottom", location=(0, (y0 + y1) / 2, z0 + w_))])
        cell_m = qm.material("F1_Cell", (0.55, 0.58, 0.62), metal=0.6, rough=0.4)
        cu = qm.material("F1_Copper", (0.80, 0.45, 0.20), metal=1.0, rough=0.3)
        pcb = qm.material("F1_PCB", (0.05, 0.35, 0.12), metal=0.1, rough=0.6)
        nmod = 4
        gap = 0.006
        mod_l = (L - 2 * w_ - gap * (nmod + 1)) / nmod
        ch = h - 2 * w_ - 0.024
        pitch = 0.0062
        ncell = int((width - 2 * w_ - 0.030) / pitch)
        cell_me = fasten.proto_mesh(f"_escell_{round(mod_l, 4)}_{round(ch, 4)}",
                                    lambda nm: qm.box(nm, (pitch - 0.0007, mod_l - 0.004, ch), origin="bottom", material=cell_m))
        for m in range(nmod):
            ym = y0 + w_ + gap + mod_l / 2 + m * (mod_l + gap)
            for c in range(ncell):
                x = -(ncell - 1) * pitch / 2 + c * pitch
                parts.append(fasten.place(f"{name}_Module{m + 1}_Cell{c + 1}", cell_me, fasten.frame((x, ym, z0 + w_ + 0.004), (0, 0, 1), (1, 0, 0)),
                                          "cell"))
            for e, sx in enumerate((-1, 1)):
                parts.append(qm.box(f"{name}_Module{m + 1}_EndPlate{e + 1}", (0.008, mod_l, ch + 0.004), origin="bottom",
                                    location=(sx * ((ncell * pitch) / 2 + 0.005), ym, z0 + w_ + 0.002), material=alu))
            parts.append(qm.box(f"{name}_Module{m + 1}_Busbar", (ncell * pitch, 0.012, 0.002), origin="bottom",
                                location=(0, ym, z0 + w_ + 0.004 + ch), material=cu))
            parts.append(qm.box(f"{name}_Module{m + 1}_BMS", (ncell * pitch * 0.6, mod_l * 0.5, 0.0016), origin="bottom",
                                location=(0, ym + mod_l * 0.2, z0 + w_ + 0.004 + ch + 0.002), material=pcb))
        parts.append(qm.box(f"{name}_MainBusbar", (0.010, L - 2 * w_ - 0.01, 0.003), origin="bottom",
                            location=(width * 0.3, (y0 + y1) / 2, z0 + w_ + 0.004 + ch + 0.002), material=cu))
    return parts


def control_electronics(name: str = "CE", center=(0.16, 2.33, 0.073), size=(0.18, 0.14, 0.16), mats=None):
    """制御用の電子機器（パワーユニットのインバーターなどの箱。冷却の口とコネクター）。center は底面の中心。戻り値はリスト"""
    case = qm.material("F1_CECase", (0.15, 0.15, 0.17), metal=0.6, rough=0.35)
    orange = qm.material("F1_HV", (0.95, 0.45, 0.05), metal=0.0, rough=0.5)
    alu = _mk(mats, "alu", (0.75, 0.76, 0.78), metal=0.9, rough=0.3)
    cx, cy, cz = center
    w, d, h = size
    parts = [qm.box(name, size, segs=(2, 2, 2), origin="bottom", location=center, material=case, bevel=0.005)]
    for k in range(3):
        parts.append(qm.box(f"{name}_Fin{k + 1}", (w * 0.9, 0.004, h * 0.25), origin="bottom",
                            location=(cx, cy - d / 2 + d * (k + 1) / 4, cz + h), material=alu))
    parts.append(qm.cylinder(f"{name}_HVConnector", 0.016, 0.03, seg=12, axis="X", location=(cx - w / 2 - 0.012, cy, cz + h * 0.5),
                             material=orange))
    parts.append(qm.cylinder(f"{name}_CoolPort", 0.010, 0.03, seg=10, axis="Y", location=(cx + w * 0.25, cy + d / 2 + 0.012, cz + h * 0.7),
                             material=alu))
    if HOLLOW:
        # 中：水冷の板の上に、MGU-K を回すインバーターのパワーモジュール 3 つ（三相）、直流のコンデンサー、
        # 三相のバスバー、低い電圧（12〜24V）を作る DC-DC コンバーター、上に制御の基板。配置と寸法は推定
        w_ = 0.0065
        qm.cut(parts[0], [qm.box("_cei", (w - 2 * w_, d - 2 * w_, h - 2 * w_), origin="bottom", location=(cx, cy, cz + w_))])
        cu = qm.material("F1_Copper", (0.80, 0.45, 0.20), metal=1.0, rough=0.3)
        pcb = qm.material("F1_PCB", (0.05, 0.35, 0.12), metal=0.1, rough=0.6)
        dark = qm.material("F1_Module", (0.10, 0.10, 0.11), metal=0.2, rough=0.5)
        z = cz + w_
        parts.append(qm.box(f"{name}_ColdPlate", (w - 2 * w_ - 0.002, d - 2 * w_ - 0.002, 0.010), origin="bottom", location=(cx, cy, z), material=alu))
        z += 0.010
        for k in range(3):
            parts.append(qm.box(f"{name}_PowerModule{k + 1}", (0.040, 0.060, 0.012), origin="bottom",
                                location=(cx - w / 2 + 0.030 + k * 0.045, cy - 0.020, z), material=dark))
            parts.append(qm.box(f"{name}_PhaseBusbar{k + 1}", (0.006, 0.050, 0.003), origin="bottom",
                                location=(cx - w / 2 + 0.030 + k * 0.045, cy + 0.030, z + 0.004), material=cu))
        parts.append(qm.cylinder(f"{name}_DCLink", 0.020, 0.050, seg=20, location=(cx + w * 0.30, cy + 0.030, z), material=dark))
        parts.append(qm.box(f"{name}_DCDC", (0.040, 0.040, 0.030), origin="bottom", location=(cx + w * 0.28, cy - 0.035, z), material=dark))
        for k, zz in enumerate((z + 0.060, z + 0.095)):
            parts.append(qm.box(f"{name}_Board{k + 1}", (w - 2 * w_ - 0.010, d - 2 * w_ - 0.010, 0.0016), origin="bottom",
                                location=(cx, cy, zz), material=pcb))
    return parts


# ---------------------------------------------------------------- V6 エンジン
def v6_point(bank: int, t: float, u: float, y: float, crank_z: float = None):
    """V6 のバンク（-1 = 左、1 = 右）の座標系の点 → 車の座標（すべてミリ）。t = シリンダーの軸に沿った距離（クランク軸から）、
    u = 軸に直角な向き（+ が V の内側）"""
    cz = LAYOUT["crank_z"] if crank_z is None else crank_z
    a = math.radians(V6["vee"] / 2)
    d = Vector((bank * math.sin(a), 0, math.cos(a)))
    inner = Vector((-bank * math.cos(a), 0, math.sin(a)))
    return Vector((0, y, cz)) + d * t + inner * u


def v6_cylinders(y_front: float = None):
    """シリンダーの (バンク, 番号 0〜2, y) の一覧（ミリ）。右のバンクは stagger だけ後ろにずれる"""
    yf = LAYOUT["engine_front"] if y_front is None else y_front
    y0 = yf + 40 + 45 + V6["bore"] / 2
    return [(bank, i, y0 + V6["pitch"] * i + (V6["stagger"] if bank > 0 else 0)) for bank in (-1, 1) for i in range(3)]


def _bank_box(name, bank, t0, t1, w, y0, y1, material, segs=(1, 1, 1), bevel=None):
    MM = 0.001
    a = math.radians(V6["vee"] / 2)
    d = Vector((bank * math.sin(a), 0, math.cos(a)))
    ob = qm.box(name, (w * MM, (y1 - y0) * MM, (t1 - t0) * MM), segs=segs, origin="bottom", material=material, bevel=bevel)
    qm.orient(ob, origin=v6_point(bank, t0, 0, (y0 + y1) / 2) * MM, x_axis=Vector((0, 1, 0)).cross(d), z_axis=d)
    return ob


def v6_engine(name: str = "Engine", mats=None):
    """1.6L V6 90° エンジンの外観（クランクケース・オイルパン・左右のシリンダーブロック・ヘッド・カムカバー・
    前のカバー・後ろの板・点火コイル・ウォーターポンプ・燃料の高圧ポンプ・スカベンジポンプ・エンジンの取り付けボルト）。
    位置は LAYOUT（engine_front から gearbox_y0 まで、クランク軸の高さ crank_z）。戻り値はリスト"""
    MM = 0.001
    alu = qm.material("F1_EngineAlu", (0.55, 0.56, 0.58), metal=0.8, rough=0.45)
    cover_mat = qm.material("F1_CamCover", (0.08, 0.08, 0.09), metal=0.3, rough=0.4)
    steel = _mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    coil = qm.material("F1_Coil", (0.10, 0.10, 0.10), metal=0.1, rough=0.5)
    yf, yr, cz = LAYOUT["engine_front"], LAYOUT["gearbox_y0"], LAYOUT["crank_z"]
    yb0, yb1 = yf + 40, yr - 30                       # ブロックの前後
    parts = []
    st = [(yb0 * MM, 0, (cz - 95) * MM, 0.26, 0.155, 0.03), (yb1 * MM, 0, (cz - 95) * MM, 0.26, 0.155, 0.03)]
    parts.append(body(f"{name}_Crankcase", st, alu, n=3))
    st = [((yb0 + 15) * MM, 0, (cz - 150) * MM, 0.21, 0.07, 0.02), ((yb1 - 15) * MM, 0, (cz - 150) * MM, 0.21, 0.07, 0.02)]
    parts.append(body(f"{name}_Sump", st, alu, n=2))
    cyl = v6_cylinders()
    for bank, tag in ((-1, "L"), (1, "R")):
        ys = [y for b, i, y in cyl if b == bank]
        y0, y1 = ys[0] - V6["bore"] / 2 - 30, ys[-1] + V6["bore"] / 2 + 30
        y1 = min(y1, yb1)
        parts.append(_bank_box(f"{name}_Block{tag}", bank, 40, V6["deck"], V6["block_w"], y0, y1, alu, segs=(2, 6, 2)))
        parts.append(_bank_box(f"{name}_Head{tag}", bank, V6["deck"], V6["deck"] + V6["head"], V6["head_w"], y0 - 5, y1 + 5, alu,
                               segs=(2, 6, 2)))
        # カムカバー（丸みのある箱）
        tc = V6["deck"] + V6["head"]
        a = math.radians(V6["vee"] / 2)
        d = Vector((bank * math.sin(a), 0, math.cos(a)))
        cv = body(f"{name}_CamCover{tag}", [((y0 - 0) * MM, 0, 0, (V6["head_w"] - 14) * MM, V6["cover"] * MM, 0.02),
                                             ((y1 + 0) * MM, 0, 0, (V6["head_w"] - 14) * MM, V6["cover"] * MM, 0.02)], cover_mat, n=3)
        qm.orient(cv, origin=v6_point(bank, tc - 2, 0, 0) * MM, x_axis=Vector((0, 1, 0)).cross(d), z_axis=d)
        parts.append(cv)
        # 点火コイル（シリンダーごと）と、カムカバーのボルト
        for i, y in enumerate(ys):
            c = qm.cylinder(f"{name}_Coil{tag}{i + 1}", 0.013, 0.045, seg=12, material=coil)
            qm.orient(c, origin=v6_point(bank, tc + V6["cover"] - 6, 0, y) * MM, x_axis=(0, 1, 0), z_axis=d)
            parts.append(c)
        k = 0
        for y in (y0 + 15, (y0 + y1) / 2, y1 - 15):
            for u in (-(V6["head_w"] - 14) / 2 + 9, (V6["head_w"] - 14) / 2 - 9):
                k += 1
                b = qm.cylinder(f"{name}_CoverBolt{tag}{k}", 0.0045, 0.006, seg=8, material=steel)
                qm.orient(b, origin=v6_point(bank, tc + V6["cover"] - 8, u, y) * MM, x_axis=(0, 1, 0), z_axis=d)
                parts.append(b)
        # 前のカバー（バンクの前面。ブロックの前端まで）
        parts.append(_bank_box(f"{name}_FrontCover{tag}", bank, 40, tc + 40, 150, yf, y0, alu))
        parts.append(_bank_box(f"{name}_RearPlate{tag}", bank, 40, tc, V6["head_w"], yb1, yr, alu))
        # ウォーターポンプ（前のカバーの外寄り、前向き）
        wp = qm.cylinder(f"{name}_WaterPump{tag}", 0.040, 0.030, seg=16, axis="Y",
                         location=tuple(v6_point(bank, 130, -40, yf - 15) * MM), material=alu)
        parts.append(wp)
    st = [(yf * MM, 0, (cz - 95) * MM, 0.26, 0.155, 0.03), (yb0 * MM, 0, (cz - 95) * MM, 0.26, 0.155, 0.03)]
    parts.append(body(f"{name}_FrontCoverLower", st, alu, n=3))
    st = [(yb1 * MM, 0, (cz - 95) * MM, 0.26, 0.155, 0.03), (yr * MM, 0, (cz - 95) * MM, 0.26, 0.155, 0.03)]
    parts.append(body(f"{name}_RearPlateLower", st, alu, n=3))
    hp = qm.cylinder(f"{name}_FuelPumpHP", 0.022, 0.035, seg=12, axis="Y", location=tuple(v6_point(1, 250, 0, yf - 17) * MM), material=steel)
    parts.append(hp)
    sc = qm.cylinder(f"{name}_ScavengePump", 0.028, (yb1 - yb0 - 60) * MM, seg=12, axis="Y",
                     location=(0.118, (yb0 + yb1) / 2 * MM, (cz - 120) * MM), material=alu)
    parts.append(sc)
    for k, (x, z) in enumerate(((-0.11, cz - 70), (0.11, cz - 70), (-0.11, cz + 20), (0.11, cz + 20))):
        parts.append(qm.cylinder(f"{name}_MountStud{k + 1}", 0.008, (yf - LAYOUT["tub"][-1][0] + 8) * MM, seg=8, axis="Y",
                                 location=(x, (yf + LAYOUT["tub"][-1][0]) / 2 * MM, z * MM), material=steel))
    return parts


def v6_internals(name: str = "Crank", crank_deg: float = 30.0, mats=None):
    """クランクシャフト（主軸・ピン・ウェブ・前のギア 60 歯・モジュール 2.5）、ピストン 6 個、コンロッド 6 本。
    V6 90° の 3 ピン（ピン 1 本に左右のコンロッド 2 本）、ピンは 120° おき。ボア 80・ストローク 53（確認できた値）、
    コンロッドの長さ・ピストンの高さは推定。戻り値はリスト"""
    MM = 0.001
    steel = _mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    ti = _mk(mats, "titanium", (0.45, 0.45, 0.47), metal=1.0, rough=0.3)
    piston_mat = qm.material("F1_Piston", (0.72, 0.72, 0.74), metal=0.85, rough=0.35)
    cz = LAYOUT["crank_z"]
    r = V6["stroke"] / 2
    a = math.radians(V6["vee"] / 2)
    cyl = v6_cylinders()
    parts = []
    throws = []
    for i in range(3):
        yl = [y for b, k, y in cyl if b < 0 and k == i][0]
        yc = yl + V6["stagger"] / 2
        th = math.radians(crank_deg + 120 * i)
        pin = Vector((r * math.sin(th), 0, r * math.cos(th)))
        throws.append((yc, pin))
        parts.append(qm.cylinder(f"{name}_Pin{i + 1}", 0.021, (V6["stagger"] + 26) * MM, seg=16, axis="Y",
                                 location=((pin.x) * MM, yc * MM, (cz + pin.z) * MM), material=steel))
        for s in (-1, 1):
            w = qm.box(f"{name}_Web{i + 1}{'F' if s < 0 else 'R'}", (0.07, 0.012, (r + 62) * MM), origin="bottom", material=steel)
            qm.orient(w, origin=Vector((0, (yc + s * (V6["stagger"] / 2 + 19)) * MM, cz * MM)) - pin.normalized() * 0.040,
                      x_axis=Vector((0, 1, 0)).cross(pin.normalized()), z_axis=pin.normalized())
            parts.append(w)
    ys = [throws[0][0] - 60] + [(throws[i][0] + throws[i + 1][0]) / 2 for i in range(2)] + [throws[2][0] + 60]
    for k, yj in enumerate(ys):
        L = 24 if 0 < k < 3 else 40
        parts.append(qm.cylinder(f"{name}_Main{k + 1}", 0.026, L * MM, seg=16, axis="Y", location=(0, yj * MM, cz * MM), material=steel))
    for k in range(3):
        y_a = ys[k] + (12 if k > 0 else 20)
        y_b = ys[k + 1] - (12 if k + 1 < 3 else 20)
        parts.append(qm.cylinder(f"{name}_Shaft{k + 1}", 0.020, (y_b - y_a) * MM, seg=12, axis="Y",
                                 location=(0, (y_a + y_b) / 2 * MM, cz * MM), material=steel))
    parts.append(qm.gear(f"{name}_Gear", 60, 0.0025, 0.014, bore=0.02, material=steel))
    qm.orient(parts[-1], origin=(0, (LAYOUT["engine_front"] + 12) * MM, cz * MM), x_axis=(1, 0, 0), z_axis=(0, 1, 0))
    nose_y0, nose_y1 = LAYOUT["engine_front"] + 12, ys[0] - 20
    parts.append(qm.cylinder(f"{name}_Nose", 0.020, (nose_y1 - nose_y0) * MM, seg=12, axis="Y",
                             location=(0, (nose_y0 + nose_y1) / 2 * MM, cz * MM), material=steel))
    for bank, i, y in cyl:
        tag = f"{'L' if bank < 0 else 'R'}{i + 1}"
        yc, pin = throws[i]
        d = Vector((bank * math.sin(a), 0, math.cos(a)))
        along = pin.dot(d)
        perp = (pin - d * along).length
        s = along + math.sqrt(V6["rod"] ** 2 - perp ** 2)            # ピストンピンの位置（クランク軸から）
        p_pin = Vector((0, y, cz)) + d * s
        p_big = Vector((pin.x, y, cz + pin.z))
        rod = qm.sweep(f"{name}_Rod{tag}", [p_big * MM + (p_pin - p_big).normalized() * 0.026, p_pin * MM - (p_pin - p_big).normalized() * 0.011],
                       [(-0.009, -0.006), (0.009, -0.006), (0.009, 0.006), (-0.009, 0.006)], up=(0, 1, 0), material=ti)
        big = qm.ring(f"{name}_RodBig{tag}", 0.030, 0.021, 0.012, seg=16, origin="center", material=ti)
        qm.orient(big, origin=p_big * MM, x_axis=(1, 0, 0), z_axis=(0, 1, 0))
        small = qm.ring(f"{name}_RodSmall{tag}", 0.014, 0.0095, 0.012, seg=12, origin="center", material=ti)
        qm.orient(small, origin=p_pin * MM, x_axis=(1, 0, 0), z_axis=(0, 1, 0))
        pis = qm.lathe(f"{name}_Piston{tag}", [((V6["bore"] / 2 - 0.5) * MM, -V6["comp_h"] * MM), ((V6["bore"] / 2 - 0.5) * MM, V6["comp_h"] * MM)],
                       seg=24, material=piston_mat)
        gp = qm.cylinder(f"{name}_GudgeonPin{tag}", 0.0095, 0.060, seg=10, axis="X", material=steel)
        qm.orient([pis, gp], origin=p_pin * MM, x_axis=(0, 1, 0), z_axis=d)
        parts += [rod, big, small, pis, gp]
    return parts


def intake(name: str = "Intake", mats=None):
    """吸気（シリンダーごとの吸気トランペット 6 本と、それを覆うプレナム、前のスロットル）。V の内側に置く。戻り値はリスト"""
    MM = 0.001
    carbon = _m(mats, "carbon")
    alu = _mk(mats, "alu", (0.75, 0.76, 0.78), metal=0.9, rough=0.3)
    yf, cz = LAYOUT["engine_front"], LAYOUT["crank_z"]
    parts = []
    tc = V6["deck"] + V6["head"] * 0.5
    for bank, i, y in v6_cylinders():
        tag = f"{'L' if bank < 0 else 'R'}{i + 1}"
        port = v6_point(bank, tc, V6["head_w"] / 2 - 3, y)
        up = (Vector((-bank * 0.707, 0, 0.707)) + Vector((0, 0, 1))).normalized()
        tr = qm.lathe(f"{name}_Trumpet{tag}", [(0.021, 0), (0.021, 0.04), (0.023, 0.075), (0.031, 0.095), (0.034, 0.100)],
                      seg=16, cap=False, material=alu)
        qm.solidify(tr, 0.002)
        qm.orient(tr, origin=port * MM, x_axis=(0, 1, 0), z_axis=up)
        parts.append(tr)
        flange = qm.box(f"{name}_PortFlange{tag}", (0.056, 0.056, 0.008), origin="center", material=alu)
        qm.orient(flange, origin=(port + up * 2) * MM, x_axis=(0, 1, 0), z_axis=up)
        parts.append(flange)
    ys = [y for _, _, y in v6_cylinders()]
    y0, y1 = min(ys) - 55, max(ys) + 50
    st = [(y0 * MM, 0, (cz + 270) * MM, 0.22, 0.12, 0.04), ((y0 + 30) * MM, 0, (cz + 265) * MM, 0.25, 0.135, 0.05),
          ((y1 - 30) * MM, 0, (cz + 265) * MM, 0.25, 0.135, 0.05), (y1 * MM, 0, (cz + 270) * MM, 0.22, 0.12, 0.04)]
    parts.append(body(f"{name}_Plenum", st, carbon, n=3))
    th = qm.cylinder(f"{name}_Throttle", 0.045, 0.045, seg=20, axis="Y", location=(0, (y0 - 18) * MM, (cz + 330) * MM), material=alu)
    parts.append(th)
    if HOLLOW:      # プレナムは厚み 3mm の殻、トランペットの上端はその中。スロットルは筒と、中の蝶形の弁と軸
        inner = body("_pi", [((y0 + 3) * MM, 0, (cz + 273) * MM, 0.214, 0.114, 0.037), ((y0 + 30) * MM, 0, (cz + 268) * MM, 0.244, 0.129, 0.047),
                             ((y1 - 30) * MM, 0, (cz + 268) * MM, 0.244, 0.129, 0.047), ((y1 - 3) * MM, 0, (cz + 273) * MM, 0.214, 0.114, 0.037)], None, n=3)
        qm.cut(parts[-2], [inner, qm.cylinder("_pin", 0.040, 0.03, seg=20, axis="Y", location=(0, y0 * MM, (cz + 330) * MM))])
        qm.cut(th, [qm.cylinder("_thi", 0.040, 0.06, seg=20, axis="Y", location=(0, (y0 - 18) * MM, (cz + 330) * MM))])
        fly = qm.cylinder(f"{name}_ThrottleButterfly", 0.0395, 0.002, seg=20, origin="center", location=(0, (y0 - 18) * MM, (cz + 330) * MM), material=alu)
        qm.pivot(fly, (0, (y0 - 18) * MM, (cz + 330) * MM), (60, 0, 0))
        shaft = qm.cylinder(f"{name}_ThrottleShaft", 0.004, 0.10, seg=10, axis="X", location=(0, (y0 - 18) * MM, (cz + 330) * MM), material=alu)
        parts += [fly, shaft]
    return parts


def exhaust(name: str = "Exhaust", turbine_in=None, mats=None):
    """排気（シリンダーごとのエキゾーストマニホールド 3 本 × 左右、集合部、タービンへの管、テールパイプ）。
    排気口はヘッドの外側（V の外）。turbine_in はタービンの入口の点（ミリ、左右で ±x）。戻り値はリスト"""
    MM = 0.001
    inconel = qm.material("F1_Inconel", (0.42, 0.36, 0.30), metal=0.9, rough=0.4)
    yr = LAYOUT["gearbox_y0"]
    tin = Vector(turbine_in or (80, 3060, 600))
    parts = []
    tc = V6["deck"] + V6["head"] * 0.5
    for bank, tag in ((-1, "L"), (1, "R")):
        cx = bank * 300
        cz = LAYOUT["crank_z"] + 45
        coll0 = Vector((cx, yr - 20, cz))
        for b, i, y in v6_cylinders():
            if b != bank:
                continue
            port = v6_point(bank, tc, -(V6["head_w"] / 2 - 3), y)
            out = (v6_point(bank, tc, -1000, y) - v6_point(bank, tc, 0, y)).normalized()
            p1 = port + out * 45
            p2 = Vector((cx + bank * 8 * (i - 1), y, cz + 20 + 14 * (2 - i)))       # 道すじが後ろへだけ進むように（折り返すと管がこわれる）
            pts = [port, p1, p2, Vector((cx + bank * 10 * (i - 1), max(coll0.y - 40, y + 18), cz + 12 * (i - 1))),
                   coll0 + Vector((bank * 12 * (i - 1), 2, 10 * (i - 1)))]
            parts.append(qm.tube(f"{name}_Primary{tag}{i + 1}", [p * MM for p in pts], radius=0.019, seg=12, material=inconel))
            hollow(parts[-1], [p * MM for p in pts], 0.019, 0.0012)
            fl = qm.box(f"{name}_Flange{tag}{i + 1}", (0.05, 0.05, 0.008), origin="center", material=inconel)
            qm.orient(fl, origin=port * MM, x_axis=(0, 1, 0), z_axis=out)
            parts.append(fl)
        col = qm.lathe(f"{name}_Collector{tag}", [(0.042, 0), (0.040, 0.03), (0.028, 0.075)], seg=16, material=inconel)
        if HOLLOW:
            qm.cut(col, [qm.lathe("_ci", [(0.0405, -0.002), (0.0385, 0.03), (0.0265, 0.077)], seg=16)])
        qm.orient(col, origin=coll0 * MM, x_axis=(1, 0, 0), z_axis=(0, 1, 0))
        parts.append(col)
        t_in = Vector((bank * abs(tin.x), tin.y, tin.z))
        sec = [coll0 + Vector((0, 70, 0)), Vector((bank * 240, yr + 110, LAYOUT["crank_z"] + 180)), Vector((bank * 170, tin.y - 60, tin.z - 40)), t_in]
        parts.append(qm.tube(f"{name}_ToTurbo{tag}", [p * MM for p in sec], radius=0.026, seg=12, material=inconel))
        hollow(parts[-1], [p * MM for p in sec], 0.026, 0.0015)
    return parts


def turbocharger(name: str = "Turbo", mats=None):
    """ターボチャージャー（前がコンプレッサー、後ろがタービン、間の軸受ハウジング）。軸 Z、中心が原点、
    コンプレッサーが -Z 側。コンプレッサーの出口は +X へ、タービンの入口は左右から。戻り値はリスト"""
    alu = _mk(mats, "alu", (0.75, 0.76, 0.78), metal=0.9, rough=0.3)
    inconel = qm.material("F1_Inconel", (0.42, 0.36, 0.30), metal=0.9, rough=0.4)
    steel = _mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    comp = qm.lathe(f"{name}_Compressor", [(0.040, -0.150), (0.044, -0.110), (0.060, -0.085), (0.098, -0.075), (0.105, -0.055),
                                            (0.092, -0.035), (0.045, -0.030)], seg=32, material=alu)
    chra = qm.lathe(f"{name}_Bearing", [(0.042, -0.034), (0.048, -0.020), (0.048, 0.020), (0.042, 0.034)], seg=24, material=steel)
    turb = qm.lathe(f"{name}_Turbine", [(0.045, 0.030), (0.090, 0.036), (0.102, 0.058), (0.092, 0.082), (0.058, 0.092),
                                         (0.050, 0.140)], seg=32, material=inconel)
    out = qm.cylinder(f"{name}_CompOutlet", 0.034, 0.080, seg=16, axis="X", location=(0.080, 0.045, -0.060), material=alu)
    parts = [comp, chra, turb, out]
    for s, t in ((-1, "L"), (1, "R")):
        parts.append(qm.cylinder(f"{name}_TurbineInlet{t}", 0.030, 0.050, seg=16, axis="X", location=(s * 0.095, 0, 0.060), material=inconel))
    if HOLLOW:      # ハウジングの中（渦巻き・吸い口・排気の出口）と、羽根車 2 つ・軸・軸受
        qm.cut(comp, [qm.lathe("_cv", [(0.036, -0.155), (0.040, -0.110), (0.052, -0.082), (0.090, -0.070), (0.096, -0.055), (0.085, -0.040),
                                         (0.020, -0.036)], seg=32),
                      qm.cylinder("_co", 0.029, 0.09, seg=16, axis="X", location=(0.080, 0.045, -0.060))])
        qm.cut(out, [qm.cylinder("_coi", 0.029, 0.09, seg=16, axis="X", location=(0.080, 0.045, -0.060))])
        qm.cut(turb, [qm.lathe("_tv", [(0.020, 0.034), (0.085, 0.040), (0.095, 0.058), (0.086, 0.078), (0.054, 0.088), (0.045, 0.145)], seg=32)])
        for p_ in parts[-2:]:
            qm.cut(p_, [qm.cylinder("_ti", 0.025, 0.06, seg=16, axis="X", location=(p_.location.x, 0, 0.060))])
        qm.cut(chra, [qm.cylinder("_bi", 0.022, 0.07, seg=24, origin="center")])
        wheel_c = qm.lathe(f"{name}_CompressorWheel", [(0.012, -0.112), (0.020, -0.100), (0.050, -0.076), (0.050, -0.070), (0.012, -0.068)],
                           seg=32, material=alu)
        wheel_t = qm.lathe(f"{name}_TurbineWheel", [(0.012, 0.040), (0.046, 0.044), (0.046, 0.050), (0.022, 0.075), (0.012, 0.082)],
                           seg=32, material=inconel)
        blades = []
        for k in range(10):
            for nm_, z0, z1, rr in (("CompressorBlade", -0.110, -0.072, 0.046), ("TurbineBlade", 0.044, 0.078, 0.042)):
                b = qm.box(f"{name}_{nm_}{k + 1}", (rr - 0.014, 0.0015, z1 - z0), origin="bottom", location=((rr + 0.014) / 2, 0, z0),
                           material=alu if nm_.startswith("Comp") else inconel)
                qm.pivot(b, (0, 0, 0), (0, 0, 36 * k))
                blades.append(b)
        shaft = qm.cylinder(f"{name}_Shaft", 0.008, 0.20, seg=16, origin="center", material=steel)
        brgs = [qm.ring(f"{name}_ShaftBearing{k + 1}", 0.020, 0.008, 0.012, seg=24, origin="center", location=(0, 0, z), material=steel)
                for k, z in enumerate((-0.018, 0.018))]
        parts += [wheel_c, wheel_t, shaft] + blades + brgs
    return parts


def mgu_k(name: str = "MGUK", mats=None):
    """MGU-K（運動エネルギーを回収・放出するモーター発電機。本体・冷却の口・高電圧の端子・前の駆動ギア 40 歯・モジュール 2.5）。
    軸 Z、後ろの端が z=0、前（ギア側）が -Z。2026 年は最大 350kW。寸法は推定。戻り値はリスト"""
    case = qm.material("F1_MGUK", (0.20, 0.21, 0.24), metal=0.7, rough=0.35)
    orange = qm.material("F1_HV", (0.95, 0.45, 0.05), metal=0.0, rough=0.5)
    steel = _mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    alu = _mk(mats, "alu", (0.75, 0.76, 0.78), metal=0.9, rough=0.3)
    body_ob = qm.lathe(name, [(0.060, 0.0), (0.075, -0.010), (0.075, -0.160), (0.066, -0.175)], seg=32, material=case)
    rings = [qm.ring(f"{name}_Rib{k + 1}", 0.079, 0.074, 0.008, seg=32, location=(0, 0, -0.040 - 0.045 * k), material=case) for k in range(3)]
    shaft = qm.cylinder(f"{name}_Shaft", 0.012, 0.050, seg=12, location=(0, 0, -0.205), material=steel)
    gear = qm.gear(f"{name}_Gear", 40, 0.0025, 0.014, bore=0.012, location=(0, 0, -0.199), material=steel)
    hv = qm.cylinder(f"{name}_HVTerminal", 0.016, 0.030, seg=12, axis="X", location=(-0.082, 0, -0.080), material=orange)
    cool = [qm.cylinder(f"{name}_CoolPort{k + 1}", 0.008, 0.025, seg=10, location=(0, 0.03 * (2 * k - 1), -0.002), material=alu)
            for k in range(2)]
    parts = [body_ob] + rings + [shaft, gear, hv] + cool
    if HOLLOW:      # ケースの中：固定子（コイルの入る溝つきの鉄心）・回転子（磁石）・軸・前後の軸受
        qm.cut(body_ob, [qm.cylinder("_mi", 0.068, 0.161, seg=32, location=(0, 0, -0.168))])
        stator = qm.ring(f"{name}_Stator", 0.068, 0.046, 0.12, seg=32, location=(0, 0, -0.145), material=qm.material("F1_Lamination", (0.30, 0.30, 0.33), metal=0.8, rough=0.4))
        slots = [qm.box(f"_sl{k}", (0.010, 0.006, 0.13), origin="bottom", location=(0.049, 0, -0.150)) for k in range(12)]
        for k, sl in enumerate(slots):
            qm.pivot(sl, (0, 0, 0), (0, 0, 30 * k))
        qm.cut(stator, slots)
        windings = []
        for k in range(12):
            w = qm.box(f"{name}_Winding{k + 1}", (0.009, 0.005, 0.12), origin="bottom", location=(0.0495, 0, -0.145),
                       material=qm.material("F1_Copper", (0.80, 0.45, 0.20), metal=1.0, rough=0.3))
            qm.pivot(w, (0, 0, 0), (0, 0, 30 * k))
            windings.append(w)
        rotor = qm.ring(f"{name}_Rotor", 0.044, 0.014, 0.115, seg=32, location=(0, 0, -0.1425), material=qm.material("F1_Magnet", (0.25, 0.25, 0.28), metal=0.7, rough=0.3))
        rshaft = qm.cylinder(f"{name}_RotorShaft", 0.014, 0.178, seg=16, location=(0, 0, -0.176), material=steel)
        brgs = [qm.ring(f"{name}_Bearing{k + 1}", 0.026, 0.014, 0.010, seg=24, location=(0, 0, z), material=steel) for k, z in enumerate((-0.168, -0.012))]
        parts += [stator, rotor, rshaft] + windings + brgs
    return parts


def airbox(name: str = "Airbox", stations=None, wall: float = 0.0025, mats=None):
    """エアボックス（ドライバーの頭の上、ロールフープの吸気口から、燃料タンクとエンジンの上を通って、ターボの吸い口へ向かう吸気の管）。
    stations = [(y, 下端 z, 幅, 高さ, 角の半径), ...]（メートル、前から後ろへ）。中空（HOLLOW のとき）。戻り値 [管]"""
    st = stations or [(1.880, 0.785, 0.200, 0.160, 0.050), (2.100, 0.728, 0.210, 0.145, 0.055), (2.400, 0.697, 0.190, 0.125, 0.055),
                      (2.600, 0.703, 0.110, 0.100, 0.045), (2.705, 0.705, 0.092, 0.090, 0.044)]
    carbon = _m(mats, "carbon")
    duct = body(name, [(y, 0, z, w, h, r) for y, z, w, h, r in st], carbon, n=4)
    if HOLLOW:
        inner = [(st[0][0] - 0.02, 0, st[0][1] + wall, st[0][2] - 2 * wall, st[0][3] - 2 * wall, st[0][4] - wall)]
        inner += [(y, 0, z + wall, w - 2 * wall, h - 2 * wall, r - wall) for y, z, w, h, r in st]
        inner.append((st[-1][0] + 0.02,) + inner[-1][1:])
        qm.cut(duct, [body("_abi", inner, None, n=4)])
    return [duct]


def radiator(name: str, length: float = 0.50, height: float = 0.36, thickness: float = 0.05, mats=None):
    """ラジエーター・インタークーラー・オイルクーラーのコア（細かい格子）と前後のタンク、入口・出口の口。
    原点がコアの中心、Y が長さ、Z が高さ、X が厚み（空気の流れ）。入口は後ろのタンクの上、出口は前のタンクの下。戻り値はリスト"""
    core_m = qm.material("F1_RadCore", (0.62, 0.60, 0.55), metal=0.8, rough=0.5)
    alu = _mk(mats, "alu", (0.75, 0.76, 0.78), metal=0.9, rough=0.3)
    core = qm.box(name, (thickness, length, height), segs=(1, max(4, int(length / 0.02)), max(4, int(height / 0.02))), origin="center",
                  material=core_m)
    parts = [core]
    for s, t in ((-1, "Front"), (1, "Rear")):
        parts.append(qm.box(f"{name}_Tank{t}", (thickness + 0.012, 0.035, height + 0.01), origin="center",
                            location=(0, s * (length / 2 + 0.0175), 0), material=alu, bevel=0.004))
    parts.append(qm.cylinder(f"{name}_Inlet", 0.020, 0.04, seg=12, location=(0, length / 2 + 0.0175, height / 2), material=alu))
    parts.append(qm.cylinder(f"{name}_Outlet", 0.020, 0.04, seg=12, origin="top", location=(0, -length / 2 - 0.0175, -height / 2),
                             material=alu))
    if HOLLOW:
        # コアの中：前後のタンクの間を渡す平たいチューブ（冷やす液や空気が通る）と、チューブの間の波形のフィン（風が通る）。
        # コアの上下は側板だけ残す。タンクも中を空にする。チューブの間隔（10mm）とフィンの波の間隔は推定
        qm.cut(core, [qm.box("_cc", (thickness + 0.01, length + 0.01, height - 0.006), origin="center")])
        for k, t in enumerate(("Front", "Rear")):
            tk = parts[1 + k]
            s = -1 if t == "Front" else 1
            qm.cut(tk, [qm.box("_tk", (thickness + 0.004, 0.027, height + 0.002), origin="center", location=(0, s * (length / 2 + 0.0175), 0))])
        pitch = 0.010
        n = max(2, int((height - 0.006) / pitch))
        pitch = (height - 0.006) / n
        tube_t = 0.0022
        z0 = -height / 2 + 0.003
        tube_me = fasten.proto_mesh(f"_radtube_{round(thickness, 4)}_{round(length, 4)}",
                                    lambda nm: qm.box(nm, (thickness * 0.92, length + 0.004, tube_t), origin="center", material=alu))
        fh = pitch - tube_t - 0.0004
        wave = 0.010
        nz = max(2, int(length / wave))
        path = []
        for i in range(nz * 2 + 1):
            yy = -length / 2 + length * i / (nz * 2)
            path.append((0, yy, (fh / 2 - 0.0003) * (1 if i % 2 else -1)))
        fin_me = fasten.proto_mesh(f"_radfin_{round(thickness, 4)}_{round(length, 4)}_{round(fh, 4)}",
                                   lambda nm: qm.sweep(nm, path, [(-0.0002, -thickness * 0.45), (0.0002, -thickness * 0.45),
                                                                  (0.0002, thickness * 0.45), (-0.0002, thickness * 0.45)],
                                                       up=(1, 0, 0), material=core_m))
        for k in range(n + 1):
            zt = z0 + pitch * k
            if k < n + 1 and 0 < k < n:
                parts.append(fasten.place(f"{name}_Tube{k}", tube_me, fasten.frame((0, 0, zt), (0, 0, 1), (1, 0, 0)), "core"))
            if k < n:
                parts.append(fasten.place(f"{name}_Fin{k + 1}", fin_me, fasten.frame((0, 0, zt + pitch / 2), (0, 0, 1), (1, 0, 0)), "core"))
    return parts


def oil_tank(name: str = "OilTank", y0: float = 2.25, y1: float = 2.415, half_w: float = 0.14, z0: float = 0.30, z1: float = 0.60,
             mats=None):
    """オイルタンク（燃料タンクとエンジンの間。給油口・ブリーザー）。戻り値はリスト"""
    alu = _mk(mats, "alu", (0.75, 0.76, 0.78), metal=0.9, rough=0.3)
    tank_m = qm.material("F1_OilTank", (0.30, 0.30, 0.32), metal=0.7, rough=0.4)
    st = [(y0, 0, z0, half_w * 2, z1 - z0, 0.04), (y1, 0, z0, half_w * 2, z1 - z0, 0.04)]
    tank = body(name, st, tank_m, n=3)
    cap = qm.cylinder(f"{name}_Filler", 0.025, 0.02, seg=16, location=(-half_w * 0.5, (y0 + y1) / 2, z1 - 0.002), material=alu)
    breather = qm.cylinder(f"{name}_Breather", 0.010, 0.04, seg=10, location=(half_w * 0.5, (y0 + y1) / 2, z1 - 0.002), material=alu)
    return [tank, cap, breather]


def pipe(name: str, points, r: float = 0.019, kind: str = "hose", mats=None):
    """配管（冷却水・オイル・燃料・吸気・高電圧ケーブル）。points はメートルの点。両端に締め付けの輪。戻り値はリスト"""
    cols = {"hose": ((0.05, 0.05, 0.06), 0.0, 0.7), "water": ((0.10, 0.18, 0.45), 0.0, 0.6), "oil": ((0.45, 0.30, 0.08), 0.0, 0.6),
            "fuel": ((0.55, 0.45, 0.05), 0.0, 0.6), "air": ((0.05, 0.05, 0.06), 0.1, 0.5), "hv": ((0.95, 0.45, 0.05), 0.0, 0.5),
            "brake": ((0.55, 0.55, 0.57), 0.8, 0.45), "wire": ((0.05, 0.05, 0.05), 0.0, 0.7), "hydraulic": ((0.60, 0.58, 0.52), 0.8, 0.4), "loom": ((0.04, 0.04, 0.05), 0.0, 0.8),
            "extinguisher": ((0.70, 0.70, 0.72), 0.9, 0.3)}
    c, metal, rough = cols.get(kind, cols["hose"])
    m = qm.material(f"F1_Pipe{kind.capitalize()}", c, metal=metal, rough=rough)
    steel = _mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    pts = [Vector(p) for p in points]
    parts = [qm.tube(name, pts, radius=r, seg=12, material=m)]
    hollow(parts[0], pts, r, max(0.0008, r * 0.12))
    for k, (p, q) in enumerate(((pts[0], pts[1]), (pts[-1], pts[-2]))):
        d = (q - p).normalized()
        cl = qm.ring(f"{name}_Clamp{k + 1}", r + 0.003, r - 0.001, 0.008, seg=12, origin="center", material=steel)
        qm.orient(cl, origin=p + d * 0.02, x_axis=d.orthogonal(), z_axis=d)
        parts.append(cl)
    return parts



# ---------------------------------------------------------------- エンジンの細部（動弁系・点火・燃料噴射）
# 確認できた事実: 1 気筒 4 バルブ・DOHC、空気ばね（ニューマチック）のバルブスプリング、直噴（1 気筒 1 本、最大 500bar）。
# 推定: バルブの傾き・径、カムの位置・形、プラグとインジェクターの寸法と向き


def _bank_frame(bank):
    a = math.radians(V6["vee"] / 2)
    d = Vector((bank * math.sin(a), 0, math.cos(a)))
    inner = Vector((-bank * math.cos(a), 0, math.sin(a)))
    return d, inner


def _bank_dir(bank, dt, du):
    d, inner = _bank_frame(bank)
    return (d * dt + inner * du).normalized()


VALVE = {"in_r": 14.5, "ex_r": 12.5, "in_u": 16.0, "ex_u": -18.0, "dy": 15.0, "tilt": 12.0, "len": 96.0}


def v6_valvetrain(name: str = "Valve", mats=None):
    """動弁系（吸気 2・排気 2 のバルブ、空気ばね、タペット、左右のバンクに 2 本ずつのカムシャフトとカムのギア）。
    カムのギア（36 歯・モジュール 1.5）は前のカバーの中、y = engine_front + 42 の面に並ぶ（v6_gear_train がそこまで回す）。
    バルブは V の内側（吸気）と外側（排気）へ VALVE["tilt"] 度ずつ傾ける。戻り値はリスト"""
    MM = 0.001
    steel = _mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    ti = _mk(mats, "titanium", (0.45, 0.45, 0.47), metal=1.0, rough=0.3)
    cam_m = qm.material("F1_CamSteel", (0.55, 0.53, 0.50), metal=0.95, rough=0.25)
    deck = V6["deck"]
    tl = math.radians(VALVE["tilt"])
    parts = []
    cyl = v6_cylinders()
    for bank, tag in ((-1, "L"), (1, "R")):
        ys = [y for b, i, y in cyl if b == bank]
        for kind, r_v, u0, s in (("In", VALVE["in_r"], VALVE["in_u"], 1), ("Ex", VALVE["ex_r"], VALVE["ex_u"], -1)):
            ax = _bank_dir(bank, math.cos(tl), s * math.sin(tl))
            cam_t = deck + 2 + (VALVE["len"] + 16) * math.cos(tl)
            cam_u = u0 + s * (VALVE["len"] + 16) * math.sin(tl)
            for i, y in enumerate(ys):
                for j, dy in enumerate((-VALVE["dy"], VALVE["dy"])):
                    nm = f"{name}_{tag}{i + 1}{kind}{'ab'[j]}"
                    base = v6_point(bank, deck + 2, u0, y + dy) * MM
                    v = qm.lathe(nm, [(r_v * MM, 0), (r_v * MM, 0.0015), ((r_v - 4) * MM, 0.004), (0.003, 0.009), (0.003, VALVE["len"] * MM)],
                                 seg=16, material=ti if kind == "In" else steel)
                    spring = qm.cylinder(f"{nm}_AirSpring", 0.011, 0.024, seg=16, location=(0, 0, 0.062), material=steel)
                    tappet = qm.cylinder(f"{nm}_Tappet", 0.0115, 0.010, seg=16, location=(0, 0, 0.087), material=steel)
                    qm.orient([v, spring, tappet], origin=base, x_axis=(0, 1, 0), z_axis=ax)
                    parts += [v, spring, tappet]
            # カムシャフト（Y 方向）と、バルブごとのカム
            y0, y1 = LAYOUT["engine_front"] + 40, min(ys[-1] + 70, LAYOUT["gearbox_y0"] - 30)
            c0 = v6_point(bank, cam_t, cam_u, y0) * MM
            c1 = v6_point(bank, cam_t, cam_u, y1) * MM
            parts.append(qm.tube(f"Cam_{tag}{kind}", [c0, c1], radius=0.012, seg=16, material=cam_m))
            d, inner = _bank_frame(bank)
            for i, y in enumerate(ys):
                for j, dy in enumerate((-VALVE["dy"], VALVE["dy"])):
                    ph = math.radians(120 * i + (0 if kind == "In" else 100) + 15 * j + (60 if bank > 0 else 0))
                    prof = []
                    for k in range(24):
                        a = 2 * math.pi * k / 24
                        rr = 16 + 9 * max(0.0, math.cos(a - ph)) ** 3
                        prof.append((rr * math.cos(a), rr * math.sin(a)))
                    ctr = v6_point(bank, cam_t, cam_u, y + dy)
                    secs = [[tuple((ctr + Vector((0, yy, 0)) - ax * 0 + d * pt + inner * pu) * MM) for pt, pu in prof] for yy in (-6, 6)]
                    parts.append(qm.loft(f"Cam_{tag}{kind}Lobe{i + 1}{'ab'[j]}", secs, material=cam_m))
            g = qm.gear(f"Cam_{tag}{kind}Gear", 36, 0.0015, 0.010, bore=0.008, material=cam_m)
            qm.orient(g, origin=v6_point(bank, cam_t, cam_u, LAYOUT["engine_front"] + 42) * MM, x_axis=(1, 0, 0), z_axis=(0, 1, 0))
            parts.append(g)
    return parts


def v6_ignition(name: str = "Plug", mats=None):
    """点火プラグ（シリンダーの真上、カムカバーの点火コイルの下まで）と、直噴のインジェクター（吸気側から斜めに）、
    左右のバンクの燃料レール。戻り値はリスト"""
    MM = 0.001
    steel = _mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    ceramic = qm.material("F1_Ceramic", (0.92, 0.92, 0.90), metal=0.0, rough=0.4)
    black = qm.material("F1_Connector", (0.08, 0.08, 0.09), metal=0.1, rough=0.6)
    deck = V6["deck"]
    tc = deck + V6["head"] + V6["cover"] - 6
    parts = []
    cyl = v6_cylinders()
    for bank, tag in ((-1, "L"), (1, "R")):
        d, inner = _bank_frame(bank)
        ys = [y for b, i, y in cyl if b == bank]
        for i, y in enumerate(ys):
            plug = qm.lathe(f"{name}_{tag}{i + 1}", [(0.005, 0), (0.007, 0.004), (0.007, 0.060), (0.010, 0.062), (0.010, 0.078),
                                                      (0.006, 0.082), (0.006, (tc - deck - 1) * MM)], seg=12, material=steel)
            insul = qm.cylinder(f"{name}_{tag}{i + 1}Insulator", 0.0065, (tc - deck - 85) * MM, seg=12, location=(0, 0, 0.080), material=ceramic)
            qm.orient([plug, insul], origin=v6_point(bank, deck + 1, 0, y) * MM, x_axis=(0, 1, 0), z_axis=d)
            parts += [plug, insul]
            tip = v6_point(bank, deck + 6, 34, y)
            top = v6_point(bank, deck + 30, 92, y)
            ax = (top - tip).normalized()
            inj = qm.lathe(f"Injector_{tag}{i + 1}", [(0.003, 0), (0.0045, 0.006), (0.0065, 0.012), (0.0065, 0.050),
                                                       (0.009, 0.052), (0.009, (top - tip).length * MM)], seg=12, material=steel)
            con = qm.box(f"Injector_{tag}{i + 1}Connector", (0.014, 0.010, 0.012), origin="bottom", material=black)
            qm.orient(inj, origin=tip * MM, x_axis=(0, 1, 0), z_axis=ax)
            qm.orient(con, origin=(top - ax * 4) * MM, x_axis=(0, 1, 0), z_axis=ax)
            parts += [inj, con]
        r0 = v6_point(bank, deck + 30, 100, ys[0] - 40) * MM
        r1 = v6_point(bank, deck + 30, 100, ys[-1] + 25) * MM
        parts.append(qm.tube(f"FuelRail_{tag}", [r0, r1], radius=0.008, seg=12, material=steel))
    return parts


# ---------------------------------------------------------------- 小さな部品（シャシー）


def tether(name: str, p0, p1, mats=None):
    """ホイールテザー（車体とアップライトをつなぐ繊維のケーブル。サスペンションのアームの中を通す）。両端に金具。戻り値はリスト"""
    m = qm.material("F1_Tether", (0.85, 0.70, 0.10), metal=0.0, rough=0.8)
    alu = _mk(mats, "alu", (0.75, 0.76, 0.78), metal=0.9, rough=0.3)
    a, b = Vector(p0), Vector(p1)
    d = (b - a).normalized()
    parts = [qm.tube(name, [a, b], radius=0.004, seg=8, material=m)]
    for k, p in enumerate((a, b)):
        e = qm.ring(f"{name}_End{k + 1}", 0.008, 0.0035, 0.006, seg=12, origin="center", material=alu)
        qm.orient(e, origin=p, x_axis=d, z_axis=d.orthogonal())
        parts.append(e)
    return parts


def small_box(name: str, center, size, color=(0.15, 0.15, 0.17), connectors: int = 2, electronics: bool = True, mats=None):
    """電子機器などの小さな箱（角を丸め、前の面にコネクター）。center は底面の中心（メートル）。
    HOLLOW かつ electronics=True なら、中を空にして基板 2 枚と支柱を入れる（弁の箱は electronics=False）。戻り値はリスト"""
    case = qm.material(f"F1_Box{name[:3]}", color, metal=0.5, rough=0.4)
    black = qm.material("F1_Connector", (0.08, 0.08, 0.09), metal=0.1, rough=0.6)
    cx, cy, cz = center
    w, d, h = size
    parts = [qm.box(name, size, segs=(2, 2, 2), origin="bottom", location=center, material=case, bevel=min(size) * 0.08)]
    for k in range(connectors):
        x = cx - w / 2 + w * (k + 1) / (connectors + 1)
        parts.append(qm.cylinder(f"{name}_Connector{k + 1}", min(0.010, h * 0.25), 0.016, seg=12, axis="Y",
                                 location=(x, cy - d / 2 - 0.006, cz + h / 2), material=black))
    if HOLLOW and electronics:
        w_ = min(size) * 0.08 + 0.0015                    # 角の丸みより厚く（中の空洞が角から突き抜けないように）
        qm.cut(parts[0], [qm.box("_sbi", (w - 2 * w_, d - 2 * w_, h - 2 * w_), origin="bottom", location=(cx, cy, cz + w_))])
        pcb = qm.material("F1_PCB", (0.05, 0.35, 0.12), metal=0.1, rough=0.6)
        chip = qm.material("F1_Chip", (0.06, 0.06, 0.07), metal=0.2, rough=0.4)
        levels = (cz + w_ + h * 0.25, cz + w_ + h * 0.6)
        for k, zz in enumerate(levels):
            parts.append(qm.box(f"{name}_Board{k + 1}", (w - 2 * w_ - 0.004, d - 2 * w_ - 0.004, 0.0016), origin="bottom",
                                location=(cx, cy, zz), material=pcb))
            parts.append(qm.box(f"{name}_Board{k + 1}_Chip", (w * 0.3, d * 0.3, 0.003), origin="bottom", location=(cx, cy, zz + 0.0016), material=chip))
        for k, (sx, sy) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1))):
            parts.append(qm.cylinder(f"{name}_Standoff{k + 1}", 0.0025, levels[1] - cz - w_, seg=8,
                                     location=(cx + sx * (w / 2 - w_ - 0.006), cy + sy * (d / 2 - w_ - 0.006), cz + w_), material=chip))
    return parts


def coupling(name: str, location, axis=(-1, 0, 0), r: float = 0.022, mats=None):
    """配管の口（燃料を入れ・抜く口、給水口など）。フランジと、ふた付きの筒。axis は外向き。戻り値はリスト"""
    alu = _mk(mats, "alu", (0.75, 0.76, 0.78), metal=0.9, rough=0.3)
    red = qm.material("F1_CapRed", (0.75, 0.08, 0.06), metal=0.3, rough=0.4)
    fl = qm.cylinder(f"{name}_Flange", r * 1.7, 0.006, seg=16, location=(0, 0, -0.003), material=alu)
    body_ob = qm.cylinder(name, r, 0.030, seg=16, material=alu)
    cap = qm.cylinder(f"{name}_Cap", r * 1.1, 0.010, seg=16, location=(0, 0, 0.030), material=red)
    ax = Vector(axis).normalized()
    qm.orient([fl, body_ob, cap], origin=location, x_axis=ax.orthogonal(), z_axis=ax)
    return [fl, body_ob, cap]


def nozzle(name: str, location, direction, mats=None):
    """消火器のノズル（先が細くなる小さな筒）。direction へ吹き出す。戻り値 [ノズル]"""
    alu = _mk(mats, "alu", (0.75, 0.76, 0.78), metal=0.9, rough=0.3)
    n = qm.lathe(name, [(0.008, 0), (0.008, 0.012), (0.005, 0.022), (0.003, 0.026)], seg=12, material=alu)
    dd = Vector(direction).normalized()
    qm.orient(n, origin=location, x_axis=dd.orthogonal(), z_axis=dd)
    return [n]


def drink_system(name: str = "Drink", bag=(0.27, 1.50, 0.075), tube=None, mats=None):
    """ドリンクの装置（シートの横の袋、電動ポンプ、ヘルメットへの管）。bag は袋の底面の中心。戻り値はリスト"""
    bag_m = qm.material("F1_DrinkBag", (0.55, 0.75, 0.85), metal=0.0, rough=0.5)
    pump_m = qm.material("F1_Pump", (0.12, 0.12, 0.13), metal=0.5, rough=0.4)
    tube_m = qm.material("F1_DrinkTube", (0.15, 0.35, 0.75), metal=0.0, rough=0.5)
    bx, by, bz = bag
    b = qm.box(name, (0.06, 0.20, 0.12), segs=(1, 2, 2), origin="bottom", location=bag, material=bag_m, bevel=0.02)
    pump = qm.cylinder(f"{name}_Pump", 0.016, 0.05, seg=12, axis="Y", location=(bx, by + 0.12, bz + 0.03), material=pump_m)
    tube = tube or [(bx, by + 0.145, bz + 0.03), (bx - 0.02, by + 0.20, bz + 0.20), (bx - 0.04, by + 0.30, bz + 0.50), (bx - 0.05, by + 0.32, bz + 0.62)]
    t = qm.tube(f"{name}_Tube", tube, radius=0.004, seg=8, material=tube_m)
    return [b, pump, t]


# ---------------------------------------------------------------- 中くらいの部品


def header_tank(name: str = "HeaderTank", location=(0, 0, 0), size=(0.12, 0.08, 0.09), mats=None):
    """冷却水のヘッダータンク（膨張タンク）。圧力キャップ付き。location は底面の中心。戻り値はリスト"""
    alu = _mk(mats, "alu", (0.75, 0.76, 0.78), metal=0.9, rough=0.3)
    x, y, z = location
    t = qm.box(name, size, segs=(2, 2, 2), origin="bottom", location=location, material=alu, bevel=0.012)
    cap = qm.cylinder(f"{name}_Cap", 0.018, 0.015, seg=16, location=(x - size[0] * 0.25, y, z + size[2] - 0.002),
                      material=qm.material("F1_CapRed", (0.75, 0.08, 0.06), metal=0.3, rough=0.4))
    return [t, cap]


def wastegate(name: str = "Wastegate", location=(0, 0, 0), mats=None):
    """ウェイストゲート（タービンへの排気の一部を逃がす弁。弁の本体と、上の空気圧のアクチュエーター）。
    location は弁の下端（排気管の上）。戻り値はリスト"""
    inconel = qm.material("F1_Inconel", (0.42, 0.36, 0.30), metal=0.9, rough=0.4)
    alu = _mk(mats, "alu", (0.75, 0.76, 0.78), metal=0.9, rough=0.3)
    x, y, z = location
    body_ob = qm.cylinder(name, 0.026, 0.040, seg=16, location=(x, y, z - 0.010), material=inconel)
    act = qm.lathe(f"{name}_Actuator", [(0.012, 0), (0.030, 0.008), (0.030, 0.030), (0.012, 0.036)], seg=20,
                   location=(x, y, z + 0.030), material=alu)
    return [body_ob, act]


def accumulator(name: str, p0, p1, r: float = 0.030, mats=None):
    """油圧のアキュムレーター（両端の丸い筒。片側に油の口）。p0 から p1 へ。戻り値はリスト"""
    m = qm.material("F1_Accumulator", (0.65, 0.12, 0.10), metal=0.6, rough=0.35)
    alu = _mk(mats, "alu", (0.75, 0.76, 0.78), metal=0.9, rough=0.3)
    a, b = Vector(p0), Vector(p1)
    L = (b - a).length
    prof = [(r * 0.35, 0), (r * 0.8, r * 0.15), (r, r * 0.5), (r, L - r * 0.5), (r * 0.8, L - r * 0.15), (r * 0.35, L)]
    body_ob = qm.lathe(name, prof, seg=20, material=m)
    port = qm.cylinder(f"{name}_Port", r * 0.3, 0.015, seg=10, location=(0, 0, -0.013), material=alu)
    d = (b - a).normalized()
    qm.orient([body_ob, port], origin=a, x_axis=d.orthogonal(), z_axis=d)
    return [body_ob, port]


def hydraulic_pump(name: str, location, axis=(0, -1, 0), mats=None):
    """油圧ポンプ（エンジンに付き、ギアで回る）。本体・ふた・吸い込みと吐き出しの口。axis は前（ふた）の向き。戻り値はリスト"""
    alu = _mk(mats, "alu", (0.75, 0.76, 0.78), metal=0.9, rough=0.3)
    dark = qm.material("F1_PumpDark", (0.25, 0.25, 0.27), metal=0.7, rough=0.4)
    body_ob = qm.cylinder(name, 0.028, 0.040, seg=16, material=dark)
    lid = qm.cylinder(f"{name}_Lid", 0.022, 0.010, seg=16, location=(0, 0, 0.040), material=alu)
    ports = [qm.cylinder(f"{name}_Port{k + 1}", 0.007, 0.018, seg=10, axis="X", location=(s * 0.034, 0, 0.020), material=alu)
             for k, s in enumerate((-1, 1))]
    ax = Vector(axis).normalized()
    qm.orient([body_ob, lid] + ports, origin=location, x_axis=ax.orthogonal(), z_axis=ax)
    return [body_ob, lid] + ports


def valve_block(name: str, center, size=(0.08, 0.10, 0.08), solenoids: int = 6, mats=None):
    """油圧の制御弁のブロック（変速・クラッチ・デフなどの油圧を切り替える）。上面にソレノイド弁。center は底面の中心。戻り値はリスト"""
    alu = _mk(mats, "alu", (0.75, 0.76, 0.78), metal=0.9, rough=0.3)
    sol = qm.material("F1_Solenoid", (0.10, 0.10, 0.11), metal=0.4, rough=0.5)
    cx, cy, cz = center
    w, d, h = size
    parts = [qm.box(name, size, segs=(2, 3, 2), origin="bottom", location=center, material=alu, bevel=0.004)]
    for k in range(solenoids):
        x = cx - w * 0.25 + w * 0.5 * (k % 2)
        y = cy - d / 2 + d * (k // 2 + 0.5) / ((solenoids + 1) // 2)
        parts.append(qm.cylinder(f"{name}_Solenoid{k + 1}", 0.009, 0.030, seg=12, location=(x, y, cz + h - 0.002), material=sol))
    return parts



# ---------------------------------------------------------------- ノーズの衝撃吸収構造・プランク・センサー
# 確認できた事実: プランク（スキッドブロック）は厚さ 10mm、レース後に 9mm 未満にすり減ってはいけない。
#   すり減りは直径 50mm の穴で測り、穴のまわりにチタンのスキッドを付けてよい。
#   センサー: 車高のレーザー、タイヤの空気圧（FIA が決めた装置、ホイールの中）、ノーズのピトー管など。
# 推定: プランクの幅・長さ、ノーズの形と長さ、センサーの位置と大きさ


def nose_crash(name: str = "NoseCrash", y0: float = -0.35, length: float = 0.62, mats=None):
    """ノーズの衝撃吸収構造（前の隔壁から前へ伸びる、先細りのカーボンの筒）と、隔壁に留めるフランジ。戻り値はリスト"""
    z0 = _z0()
    carbon = _m(mats, "carbon")
    y1 = y0 - length
    st = [(y1, 0, z0 + 0.16, 0.12, 0.10, 0.04), (y1 + length * 0.3, 0, z0 + 0.12, 0.17, 0.17, 0.05),
          (y1 + length * 0.7, 0, z0 + 0.06, 0.24, 0.27, 0.06), (y0 - 0.012, 0, z0 + 0.02, 0.28, 0.33, 0.06)]
    shell = body(name, st, carbon, n=3)
    fl = body(f"{name}_Flange", [(y0 - 0.012, 0, z0 + 0.005, 0.30, 0.355, 0.06), (y0 + 0.0, 0, z0 + 0.005, 0.30, 0.355, 0.06)], carbon, n=3)
    return [shell, fl]


def pitot(name: str = "Pitot", tip=(0, -1.0, 0.25), length: float = 0.12, mats=None):
    """ピトー管（前向きの細い管と、根もとの台座）。tip は台座の前の面。戻り値はリスト"""
    ti = _mk(mats, "titanium", (0.45, 0.45, 0.47), metal=1.0, rough=0.3)
    x, y, z = tip
    base = qm.box(f"{name}_Base", (0.02, 0.03, 0.012), origin="bottom", location=(x, y + 0.012, z - 0.006), material=ti)
    tube = qm.lathe(name, [(0.003, 0), (0.003, length * 0.8), (0.0045, length * 0.85), (0.0045, length)], seg=10, material=ti)
    qm.orient(tube, origin=(x, y + 0.002, z), x_axis=(1, 0, 0), z_axis=(0, -1, 0))
    return [base, tube]


def plank(name: str = "Plank", y0: float = 0.30, y1: float = 3.10, width: float = 0.30, thickness: float = 0.010,
          holes=None, mats=None):
    """プランク（フロアの下の中央に付く板。すり減りで車高の下限を守らせる）。下面が z = plank_z - thickness。
    holes はすり減りを測る穴の y の一覧。穴のまわりにチタンのスキッド（直径 50mm の穴の縁）。戻り値はリスト"""
    z_top = EST["plank_z"]
    m = qm.material("F1_Plank", (0.45, 0.33, 0.20), metal=0.0, rough=0.8)
    ti = _mk(mats, "titanium", (0.45, 0.45, 0.47), metal=1.0, rough=0.3)
    L = y1 - y0
    p = qm.box(name, (width, L, thickness), segs=(2, max(4, int(L / 0.1)), 1), origin="bottom",
               location=(0, (y0 + y1) / 2, z_top - thickness), material=m, bevel=0.003)
    parts = [p]
    holes = holes or [y0 + L * t for t in (0.15, 0.40, 0.65, 0.90)]
    for k, y in enumerate(holes):
        parts.append(qm.ring(f"{name}_Skid{k + 1}", 0.040, 0.025, thickness + 0.0004, seg=24, origin="bottom",
                             location=(0, y, z_top - thickness - 0.0002), material=ti))
    return parts


def ride_height_sensor(name: str, location, mats=None):
    """車高のレーザーセンサー（下向きの小さな箱と、窓）。location は上面の中心。戻り値はリスト"""
    case = qm.material("F1_Sensor", (0.10, 0.10, 0.12), metal=0.5, rough=0.4)
    glass = qm.material("F1_SensorWindow", (0.6, 0.1, 0.1), metal=0.2, rough=0.1)
    x, y, z = location
    b = qm.box(name, (0.030, 0.040, 0.022), origin="top", location=location, material=case, bevel=0.003)
    w = qm.cylinder(f"{name}_Window", 0.007, 0.002, seg=12, origin="top", location=(x, y, z - 0.0215), material=glass)
    return [b, w]




# ---------------------------------------------------------------- 残りの部品（ギア列・ブレーキダクト・アンテナ・レインライト など）


def mesh_point(c1, c2, d1, d2, side: int = 1):
    """2 つの円の交点（ギアをかみ合わせる位置を求める）。c1・c2 は (x, z)、d1・d2 はそれぞれからの距離。
    side で 2 つの交点のどちらかを選ぶ。届かないときは c1 から c2 の向きへ d1 の点を返す"""
    a, b = Vector(c1), Vector(c2)
    d = (b - a).length
    u = (b - a) / d
    x = (d1 ** 2 - d2 ** 2 + d ** 2) / (2 * d)
    h = math.sqrt(max(d1 ** 2 - x ** 2, 0.0))
    return a + u * x + Vector((u.y, -u.x)) * h * side


def v6_gear_train(name: str = "GearTrain", mats=None):
    """前のカバーの中のギア列（クランクのギア 60 歯 → アイドラー 2 枚 → 頭の複合ギア → カムのギア 2 枚、左右のバンク）。
    大きいギアはモジュール 2.5、カムまわりは 1.5。歯数と位置は推定。戻り値はリスト"""
    MM = 0.001
    steel = _mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    yf, cz = LAYOUT["engine_front"], LAYOUT["crank_z"]
    y_big, y_cam = yf + 30, yf + 42
    tl = math.radians(VALVE["tilt"])
    cam_t = V6["deck"] + 2 + (VALVE["len"] + 16) * math.cos(tl)
    parts = []

    def put(nm, teeth, module, x, z, y, width=0.010):
        g = qm.gear(nm, teeth, module, width, bore=0.006, material=steel)
        qm.orient(g, origin=(x * MM, y * MM, z * MM), x_axis=(1, 0, 0), z_axis=(0, 1, 0))
        parts.append(g)
        return g

    put(f"{name}_Crank", 60, 0.0025, 0, cz, y_big)
    for bank, tag in ((-1, "L"), (1, "R")):
        ci = v6_point(bank, cam_t, VALVE["in_u"] + (VALVE["len"] + 16) * math.sin(tl), 0)
        ce = v6_point(bank, cam_t, VALVE["ex_u"] - (VALVE["len"] + 16) * math.sin(tl), 0)
        mid = (ci + ce) / 2
        r_cam = 1.5 * 36 / 2
        r_mid = (ci - ce).length / 2 - r_cam                      # カムのギア 2 枚の間の小さなギア
        t_mid = max(8, round(2 * r_mid / 1.5))
        put(f"{name}_{tag}HeadSmall", t_mid, 0.0015, mid.x, mid.z, y_cam)
        C0, Cb = Vector((0, cz)), Vector((mid.x, mid.z))
        r0, r1, r2, rb = 75.0, 42.5, 42.5, 40.0                    # クランク 60 歯、アイドラー 34 歯 ×2、複合ギアの大 32 歯
        dir_ = (Cb - C0).normalized()
        I1 = C0 + dir_ * (r0 + r1)
        I2 = mesh_point(I1, Cb, r1 + r2, r2 + rb, side=bank)
        put(f"{name}_{tag}Idler1", 34, 0.0025, I1.x, I1.y, y_big)
        put(f"{name}_{tag}Idler2", 34, 0.0025, I2.x, I2.y, y_big)
        put(f"{name}_{tag}HeadBig", 32, 0.0025, mid.x, mid.z, y_big)
        for nm, p in (("Idler1", I1), ("Idler2", I2), ("Head", Cb)):
            parts.append(qm.cylinder(f"{name}_{tag}{nm}Shaft", 0.006, (y_cam - y_big + 12) * MM, seg=10, axis="Y",
                                     location=(p.x * MM, (y_big + y_cam) / 2 * MM + 0.004, p.y * MM), material=steel))
    return parts


def gear_cover(name: str, circles, y0: float, y1: float, margin: float = 0.008, n: int = 32, mats=None):
    """ギアを覆うカバー（いくつかの円を包む形を、Y 方向に厚みを付けて作る）。circles = [(x, z, 半径), ...]（メートル）。戻り値 [カバー]"""
    mag = _mk(mats, "magnesium", (0.32, 0.32, 0.34), 0.6, 0.5)
    pts = []
    for x, z, r in circles:
        for k in range(64):
            a = 2 * math.pi * k / 64
            pts.append((x + (r + margin) * math.cos(a), z + (r + margin) * math.sin(a)))
    pts = sorted(set(pts))
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
    hull = lower[:-1] + upper[:-1]
    # 周の長さで等間隔に n 点へ置き直す（断面の点数をそろえ、ふたの格子をきれいにする）
    L = [0.0]
    for a, b in zip(hull, hull[1:] + hull[:1]):
        L.append(L[-1] + math.dist(a, b))
    out, j = [], 0
    for k in range(n):
        t = L[-1] * k / n
        while L[j + 1] < t:
            j += 1
        a, b = hull[j], hull[(j + 1) % len(hull)]
        f = (t - L[j]) / max(L[j + 1] - L[j], 1e-9)
        out.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
    secs = [[(x, y, z) for x, z in out] for y in (y0, y1)]
    return [qm.loft(name, secs, material=mag)]


def brake_duct(name: str, disc_center, out, cal_dir, front: bool = True, mats=None):
    """ブレーキダクト（ディスクを囲む筒の、キャリパーを除いた部分と、前下の空気の取り入れ口）。
    disc_center はディスクの中心、out はホイールの外向き、cal_dir はキャリパーの向き。戻り値はリスト"""
    carbon = _m(mats, "carbon")
    D, T = BRAKE["front" if front else "rear"]
    rd, w = D / 2 + 0.026, 0.070
    c, o = Vector(disc_center), Vector(out).normalized()
    ex = Vector((0, 1, 0))
    ey = o.cross(ex)                                   # orient(x=Y, z=out) と同じ座標系
    cd = Vector(cal_dir)
    a_cal = math.atan2(cd.dot(ey), cd.dot(ex))
    gap = math.radians(42)
    secs = []
    for zz in (-w / 2, w / 2):
        ring = []
        for k in range(25):
            a = a_cal + gap + (2 * math.pi - 2 * gap) * k / 24
            ring.append(tuple(c + ex * (rd * math.cos(a)) + ey * (rd * math.sin(a)) + o * zz))
        secs.append(ring)
    drum = qm.loft(name, secs, closed=False, material=carbon)
    qm.solidify(drum, 0.003)
    edge = c + ex * (rd * -0.92) + Vector((0, 0, -rd * 0.40))
    path = [c - o * 0.17 + Vector((0, -0.150, -0.085)), c - o * 0.07 + Vector((0, -0.165, -0.082)), edge - o * 0.005]
    prof = [(x, z) for x, z in rrect(0.060, 0.040, 0.012, 2)]
    scoop = qm.sweep(f"{name}_Scoop", path, prof, up=(0, 0, 1), material=carbon)
    return [drum, scoop]


def antenna(name: str = "Antenna", base=(0, 0.75, 0.60), mats=None):
    """テレメトリーのアンテナ（台座と、後ろへ傾いた板）。base は台座の底面の中心。戻り値はリスト"""
    black = qm.material("F1_Connector", (0.08, 0.08, 0.09), metal=0.1, rough=0.6)
    x, y, z = base
    b = qm.box(f"{name}_Base", (0.03, 0.05, 0.008), origin="bottom", location=base, material=black)
    blade = plate(name, [(y - 0.02, z + 0.006), (y + 0.02, z + 0.006), (y + 0.05, z + 0.075), (y + 0.035, z + 0.075)], 0.004,
                  axis="X", at=x, material=black)
    return [b, blade]


def rain_light(name: str = "RainLight", center=(0, 3.96, 0.355), size=(0.10, 0.02, 0.04), mats=None):
    """レインライト（後ろの衝撃吸収構造の後端に付く赤いライト）。center は中心。戻り値はリスト"""
    red = _m(mats, "light") or qm.material("F1_Light", (0.9, 0.1, 0.1), rough=0.2)
    black = qm.material("F1_Connector", (0.08, 0.08, 0.09), metal=0.1, rough=0.6)
    x, y, z = center
    housing = qm.box(f"{name}_Housing", (size[0] + 0.01, size[1], size[2] + 0.01), origin="center", location=(x, y - 0.004, z),
                     material=black, bevel=0.003)
    lens = qm.box(name, size, origin="center", location=(x, y + 0.004, z), material=red, bevel=0.003)
    return [housing, lens]


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
- f1.gearbox(y0=2.90) / f1.crash_structure(y0=3.55)   ギアボックスのケースとフランジ / 後ろの衝撃吸収構造
- f1.driveshaft(name, p_in, p_out) / f1.anti_roll_bar(name, center, half)   等速ジョイントとブーツ付きのドライブシャフト / アンチロールバー
- ギアボックスの中身（軸 Z・原点に作るので qm.orient で据える）: f1.clutch()（多板クラッチ）、f1.dog_hub(name)（ドッグハブ）、
  f1.shift_barrel(tracks=[...])（シフトドラム）、f1.selector_fork(name, shaft_r, barrel_at)（フォーク）、f1.differential()（デフ）。
  歯車は qm.gear / qm.bevel_gear、軸受は qm.ball_bearing、空転するギアの下は f1.needle_bearing(name, r_in, r_out, width)

シャシー全体（車体を除く。位置は f1.LAYOUT のミリの値。図鑑の作例 skills/bpy-modeling/examples/f1_chassis_catalog_mm.py）
- f1.survival_cell() / f1.tub_section(y_mm) → (幅, 上端 z)   足もとからエンジンの前までの殻・上ぶた・隔壁・ダッシュボードの梁
- f1.roll_hoop(y, top_z) / f1.halo_frame(rear_y, front_y, half_w, top_z) / f1.side_impact(name, p_in, p_out) / f1.airbox()（ロールフープの吸気口からターボへ）
- コクピット: f1.seat(path=[(y, z)...]) / f1.harness(buckle) / f1.headrest(y0, y1) /
  f1.steering_wheel()（原点・+Y がドライバー側）/ f1.steering_column(name, [点...]) / f1.pedal(name, pivot, pad) /
  f1.master_cylinder(name, front, back) / f1.fire_extinguisher(y0)
- 燃料・電気: f1.fuel_cell(y0, y1) / f1.energy_store(y0, y1) / f1.control_electronics(center) / f1.oil_tank()
- パワーユニット: f1.v6_engine()（外観）/ f1.v6_internals(crank_deg)（クランク・ピストン・コンロッド）/ f1.intake() /
  f1.exhaust(turbine_in) / f1.turbocharger()（軸 Z・原点）/ f1.mgu_k()（軸 Z・原点）。
  f1.V6（ボア 80・ストローク 53・バンク角 90 は確認できた値、ほかは推定）、f1.v6_point(bank, t, u, y) でバンクの座標から車の座標へ
- エンジンの細部: f1.v6_valvetrain()（バルブ・空気ばね・タペット・カムシャフト）/ f1.v6_ignition()（点火プラグ・インジェクター・燃料レール）
- 小物: f1.tether(name, p0, p1)（ホイールテザー）/ f1.coupling(name, location, axis) / f1.nozzle(name, location, direction) /
  f1.drink_system() / f1.small_box(name, center, size)（ECU・無線・ADR などの箱）/ f1.header_tank(location) / f1.wastegate(location)
- 油圧: f1.hydraulic_pump(name, location, axis) / f1.accumulator(name, p0, p1) / f1.valve_block(name, center)
- ノーズ・プランク・センサー: f1.nose_crash(y0, length) / f1.pitot(tip) / f1.plank(y0, y1, width)（厚さ 10mm）/ f1.ride_height_sensor(name, location)
- 残りの部品: f1.v6_gear_train()（前のカバーの中のギア列）/ f1.gear_cover(name, [(x, z, r)...], y0, y1) / f1.brake_duct(name, disc_center, out, cal_dir) /
  f1.antenna(base) / f1.rain_light(center) / f1.mesh_point(c1, c2, d1, d2)（ギアをかみ合わせる位置）
- f1.HOLLOW = True にすると、管・排気管・プレナム・スロットル・ターボ（羽根車まで）・MGU-K（固定子・回転子まで）を中が空の実物どおりに作る
  （ブーリアン。qm.cad() と一緒に）。f1.hollow(ob, points, r, wall) で、自分で作った管も中空に
- 実物どおりの V6（ブーリアンを使うので qm.cad() と一緒に。f1_engine.py）: f1.v6_engine_real(crank_deg) で全部、または
  f1.v6_block()（ブロックとベッドプレート）/ f1.v6_heads() / f1.v6_head_gaskets() / f1.v6_cam_covers() / f1.v6_front_cover() /
  f1.v6_sump() / f1.v6_crankshaft() / f1.v6_conrods() / f1.v6_pistons() / f1.v6_valves() / f1.v6_camshafts() / f1.v6_studs() /
  f1.v6_plugs_injectors() / f1.v6_pumps()
- 冷却・配管: f1.radiator(name, length, height)（原点・Y が長さ）/ f1.pipe(name, [点...], r, kind="water"|"oil"|"fuel"|"air"|"hv"|"brake"|"hydraulic"|"loom"|"extinguisher")。ブレーキ・油圧・配線の束も pipe で

寸法: f1.SPEC（2026 年規定で確認できた値）、f1.EST（推定値）、f1.BRAKE（ディスクの直径・厚み）。変えたいときは f1.EST["height"] = 0.93 のように上書きしてから作る
"""


def sensor(name: str, pos, axis, kind: str = "probe", size: float = 1.0, mats=None):
    """センサー（本体と、配線をつなぐコネクター）。pos は取り付け面の点、axis は外向き（本体はそちらへ出る）。
    kind: "probe"（ねじ込みの棒：温度・圧力・ラムダ）、"block"（箱：速度・位置・加速度）、"patch"（貼るもの：ひずみ）、
    "pot"（ダンパーに沿う直線のポテンショメーター。axis は伸びる向き、size は長さ[m]）。
    戻り値 (部品のリスト, コネクターの先の点)"""
    p, a = Vector(pos), Vector(axis).normalized()
    blk = qm.material("F1_Sensor", (0.12, 0.12, 0.13), metal=0.3, rough=0.5)
    steel = _mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
    con_m = qm.material("F1_Connector", (0.08, 0.08, 0.09), metal=0.1, rough=0.6)
    parts = []
    if kind == "probe":
        hexp = qm.nut(f"{name}", 0.010 * size, s=0.014 * size, m=0.008 * size, material=steel)
        hexp.matrix_world = fasten.frame(p, a)
        body_ = qm.cylinder(f"{name}_Body", 0.006 * size, 0.020 * size, seg=12, material=blk)
        body_.matrix_world = fasten.frame(p + a * 0.008 * size, a)
        parts += [hexp, body_]
        tip = p + a * 0.028 * size
    elif kind == "pot":
        body_ = qm.cylinder(f"{name}", 0.007, size, seg=12, material=blk)
        body_.matrix_world = fasten.frame(p, a)
        parts.append(body_)
        tip = p + a.orthogonal().normalized() * 0.008
    elif kind == "patch":
        body_ = qm.box(f"{name}", (0.012, 0.018, 0.002), origin="bottom", material=blk)
        body_.matrix_world = fasten.frame(p, a)
        parts.append(body_)
        tip = p + a * 0.002
    else:
        body_ = qm.box(f"{name}", (0.022 * size, 0.016 * size, 0.014 * size), origin="bottom", material=blk)
        body_.matrix_world = fasten.frame(p, a)
        parts.append(body_)
        tip = p + a * 0.014 * size
    con = qm.cylinder(f"{name}_Connector", 0.0055, 0.012, seg=12, material=con_m)
    con.matrix_world = fasten.frame(tip, a)
    parts.append(con)
    return parts, tip + a * 0.012


def wire_to(name: str, start, loom_points, r: float = 0.0018, mats=None):
    """センサーのコネクター start から、配線の束（loom_points の折れ線）のいちばん近い点まで、細い線を引く。
    戻り値は [線]（束に届く所で終わる）"""
    from mathutils.geometry import intersect_point_line
    st = Vector(start)
    best = None
    for a, b in zip(loom_points, loom_points[1:]):
        a, b = Vector(a), Vector(b)
        q, t = intersect_point_line(st, a, b)
        t = min(1.0, max(0.0, t))
        q = a + (b - a) * t
        d = (q - st).length
        if best is None or d < best[0]:
            best = (d, q)
    q = best[1]
    mid = st + (q - st) * 0.5
    mid.z = max(mid.z, min(st.z, q.z))
    pts = [st, st + (mid - st) * 0.3, mid, q]
    m = qm.material("F1_PipeWire", (0.05, 0.05, 0.05), metal=0.0, rough=0.7)
    return [qm.tube(name, pts, radius=r, seg=8, material=m)]


# 実物どおりの部品の分け方で作る V6 エンジン（ブーリアンを使う。f1_engine.py）
from f1_engine import *  # noqa: E402,F401,F403

# 留め具（ボルト・ナット・座金・スペーサー）とクレビス（f1_fasten.py）。f1.fasten.xxx で使う
import f1_fasten as fasten  # noqa: E402,F401
