"""
f1_engine — F1 の V6 エンジンを、実物と同じ部品の分け方で作る（f1 から f1.v6_block() のように使う）

鋳物（ブロック・ヘッド・カバー・オイルパン）はブーリアンで、実物どおりの穴・通路・空洞をあける。
使うスクリプトでは qm.cad() を呼ぶ（面に多角形が混ざるため）。

確認できた事実: V6・バンク角 90°・ボア 80mm・ストローク 53mm、1 気筒 4 バルブ・DOHC・空気ばね、直噴（1 気筒 1 本）。
推定: そのほかの寸法すべて（ブロックの肉厚、ポートの形、軸受の幅、コンロッドの長さ、ボルトの位置など）。

座標: f1 と同じ（前 = -Y、上 = Z、メートル）。寸法はミリで考え、MM を掛ける。
バンクの座標: t = シリンダーの軸に沿った距離（クランク軸から）、u = 軸に直角な向き（+ が V の内側）。
"""
from __future__ import annotations

import math

import qm
from mathutils import Vector

import f1

__all__ = ["v6_frame", "v6_mains", "v6_block", "v6_heads", "v6_head_gaskets", "v6_cam_covers", "v6_front_cover",
           "v6_sump", "v6_crankshaft", "v6_conrods", "v6_pistons", "v6_valves", "v6_camshafts", "v6_studs",
           "v6_plugs_injectors", "v6_pumps", "water_pump_point", "v6_oil_jets", "v6_engine_real", "HEAD_TOP", "GEAR_PLANES",
           "accessory_layout", "hp_pump_y"]

MM = 0.001


def _V6():
    return f1.V6


def _L():
    return f1.LAYOUT


def v6_frame(bank: int):
    """バンクの向き (d, inner)。d = シリンダーの軸（クランクから外へ）、inner = V の内側"""
    a = math.radians(_V6()["vee"] / 2)
    return Vector((bank * math.sin(a), 0, math.cos(a))), Vector((-bank * math.cos(a), 0, math.sin(a)))


def _bank_place(objs, bank: int):
    """バンクの局所座標（x = u（左）/ -u（右）、y = 車の Y、z = t、ミリではなくメートル。原点はクランク軸の高さ）で作った部品を据える"""
    d, inner = v6_frame(bank)
    return qm.orient(objs, origin=(0, 0, _L()["crank_z"] * MM), x_axis=inner * (-bank), z_axis=d)


def _lx(bank: int, u: float) -> float:
    """バンクの u を、局所座標の x に"""
    return -bank * u


def _cyl(name, r, t0, t1, x=0.0, y=0.0, seg=32, material=None):
    """局所座標の Z（シリンダーの軸）に沿った円柱（ミリで指定）"""
    return qm.cylinder(name, r * MM, (t1 - t0) * MM, seg=seg, location=(x * MM, y * MM, t0 * MM), material=material)


def _cyl_y(name, r, y0, y1, x=0.0, z=0.0, seg=32, material=None):
    """Y 方向の円柱（ミリ）"""
    return qm.cylinder(name, r * MM, (y1 - y0) * MM, seg=seg, axis="Y", location=(x * MM, (y0 + y1) / 2 * MM, z * MM),
                       material=material)


def _cyl_axis(name, r, p0, p1, seg=24, material=None):
    """2 点（ミリの Vector）を結ぶ円柱"""
    a, b = Vector(p0), Vector(p1)
    c = qm.cylinder(name, r * MM, (b - a).length * MM, seg=seg, material=material)
    dd = (b - a).normalized()
    qm.orient(c, origin=a * MM, x_axis=dd.orthogonal(), z_axis=dd)
    return c


def _box(name, x0, x1, y0, y1, z0, z1, material=None, bevel=None):
    """角の座標（ミリ）で箱"""
    return qm.box(name, ((x1 - x0) * MM, (y1 - y0) * MM, (z1 - z0) * MM), origin="bottom",
                  location=((x0 + x1) / 2 * MM, (y0 + y1) / 2 * MM, z0 * MM), material=material, bevel=bevel)


def v6_mains():
    """主軸受の y（ミリ）と、クランクピンの中心の y（3 つ）"""
    st = _V6()["stagger"]
    cyl = f1.v6_cylinders()
    yc = [[y for b, k, y in cyl if b < 0 and k == i][0] + st / 2 for i in range(3)]
    return [yc[0] - 60, (yc[0] + yc[1]) / 2, (yc[1] + yc[2]) / 2, yc[2] + 48], yc


def _mats(mats):
    return {
        "alu": qm.material("F1_EngineAlu", (0.55, 0.56, 0.58), metal=0.8, rough=0.45),
        "cover": qm.material("F1_CamCover", (0.08, 0.08, 0.09), metal=0.3, rough=0.4),
        "steel": f1._mk(mats, "steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3),
        "forged": qm.material("F1_Forged", (0.50, 0.50, 0.52), metal=0.95, rough=0.35),
        "ti": f1._mk(mats, "titanium", (0.45, 0.45, 0.47), metal=1.0, rough=0.3),
        "piston": qm.material("F1_Piston", (0.72, 0.72, 0.74), metal=0.85, rough=0.35),
        "bearing": qm.material("F1_BearingShell", (0.78, 0.62, 0.38), metal=0.9, rough=0.3),
        "gasket": qm.material("F1_Gasket", (0.35, 0.36, 0.38), metal=0.8, rough=0.5),
        "ring": qm.material("F1_PistonRing", (0.25, 0.25, 0.27), metal=0.9, rough=0.3),
    }


# ================================================================ ブロック（とベッドプレート）


def v6_block(mats=None):
    """シリンダーブロック（クランクケースと左右のバンクが一体の鋳物）と、クランクの中心で分けた下半分のベッドプレート。
    ブーリアンで、ボア・オープンデッキのウォータージャケット・クランク室・主軸受の穴・オイルギャラリーと分岐・
    ヘッドスタッドの穴・ベッドプレートのボルト穴・オイルの落とし口をあける。戻り値 [ブロック, ベッドプレート, メインボルト...]"""
    m = _mats(mats)
    V6, L = _V6(), _L()
    cz = L["crank_z"]
    yf, yr = L["engine_front"], L["gearbox_y0"]
    yb0, yb1 = yf + 40, yr
    mains, yc = v6_mains()
    # 外形：クランクケース（Y 方向の胴）＋左右のバンク
    # クランクの中心は基準面の 90mm 上（規定）なので、クランクケースはクランクの下に 78mm しか取れない（その下はフロア）
    st = [(yb0 * MM, 0, (cz - 78) * MM, 0.26, 0.143, 0.03), (yb1 * MM, 0, (cz - 78) * MM, 0.26, 0.143, 0.03)]
    block = f1.body("Engine_Block", st, m["alu"], n=3)
    banks = []
    for bank in (-1, 1):
        b = qm.box(f"_bank{bank}", (V6["block_w"] * MM, (yb1 - yb0) * MM, (V6["deck"] - 40) * MM), origin="bottom",
                   location=(0, (yb0 + yb1) / 2 * MM, 40 * MM))
        banks.append(_bank_place(b, bank)[0])
    qm.union(block, banks)
    cyl = f1.v6_cylinders()
    edges = [(yb0, mains[0] - 12)] + [(mains[k] + 12, mains[k + 1] - 12) for k in range(3)]
    bolt_pos = [(x, ym) for ym in mains for x in (-48, 48)]

    def cutters():
        """穴・通路・空洞の形（上下の半分それぞれに使うので、呼ぶたびに作る）"""
        cut = []
        for bank in (-1, 1):
            for b_, i, y in cyl:
                if b_ != bank:
                    continue
                bore = _bank_place([_cyl(f"_bore{bank}{i}", V6["bore"] / 2, 48, V6["deck"] + 2, y=y, seg=48)], bank)
                jack = qm.ring(f"_jacket{bank}{i}", 50.5 * MM, 44.0 * MM, (V6["deck"] + 2 - 96) * MM, seg=48,
                               location=(0, y * MM, 96 * MM))
                cut += bore + _bank_place([jack], bank)
            ys_ = [y for b_, i, y in cyl if b_ == bank]
            for k, ysd in enumerate([y - 48 for y in ys_] + [ys_[-1] + 48]):
                for u in (-52, 52):
                    cut += _bank_place([_cyl(f"_stud{bank}{k}{u}", 5.5, V6["deck"] - 70, V6["deck"] + 2, x=_lx(bank, u), y=ysd, seg=16)], bank)
        # クランク室（主軸受の隔壁の間）、オイルの落とし口、主軸受の穴
        for k, (y0, y1) in enumerate(edges[1:]):
            cut.append(_box(f"_bay{k}", -122, 122, y0, y1, cz - 72, cz + 65))
        cut.append(_box("_bayfront", -100, 100, yb0 + 8, mains[0] - 12, cz - 60, cz + 50))
        cut.append(_cyl_y("_mainbore", 30, yb0 - 5, yb1 + 5, z=cz, seg=48))
        # オイルギャラリー（V の谷の中を前後に）と、主軸受への分岐
        cut.append(_cyl_y("_gallery", 6, yb0 + 10, yb1 - 10, z=cz + 75, seg=16))
        for k, ym in enumerate(mains):
            cut.append(_cyl_axis(f"_feed{k}", 3, Vector((0, ym, cz + 75)), Vector((0, ym, cz + 20)), seg=12))
        # ベッドプレートを留めるボルトの穴（主軸受の左右）
        for k, (x, ym) in enumerate(bolt_pos):
            cut.append(_cyl(f"_mbolt{k}", 5.2, cz - 85, cz + 35, x=x, y=ym, seg=16))
        return cut
    # 先にクランクの中心の高さで上下に分け（下がベッドプレート）、それぞれに穴をあける
    # （穴をあけたあとで分けると、ブーリアンが失敗することがあるため。分ける面は主軸受の穴の頂点を避けて 0.05mm ずらす）
    bed = qm.copy(block, "Engine_Bedplate")
    qm.intersect(block, _box("_upper", -400, 400, yb0 - 10, yb1 + 10, cz + 0.05, cz + 600))
    qm.intersect(bed, _box("_lower", -400, 400, yb0 - 10, yb1 + 10, cz - 200, cz + 0.05))
    qm.cut(block, cutters())
    qm.cut(bed, cutters())
    parts = [block, bed]
    for k, (x, ym) in enumerate(bolt_pos):
        b = qm.bolt(f"Engine_MainBolt{k + 1}", "M10", 0.125, material=m["steel"])
        qm.orient(b, origin=(x * MM, ym * MM, (cz - 78) * MM), x_axis=(1, 0, 0), z_axis=(0, 0, -1))
        parts.append(b)
    return parts


# ================================================================ ヘッド


def _valve_axes(bank):
    """吸気・排気のバルブの軸（バンクの局所座標の向き）と、カムの位置 (t, u)"""
    Vv = f1.VALVE
    tl = math.radians(Vv["tilt"])
    out = {}
    for kind, u0, s in (("In", Vv["in_u"], 1), ("Ex", Vv["ex_u"], -1)):
        ax_t, ax_u = math.cos(tl), s * math.sin(tl)
        cam_t = _V6()["deck"] + 2 + (Vv["len"] + 16) * math.cos(tl)
        cam_u = u0 + s * (Vv["len"] + 16) * math.sin(tl)
        out[kind] = {"u0": u0, "ax": (ax_t, ax_u), "cam": (cam_t, cam_u), "r": Vv["in_r"] if kind == "In" else Vv["ex_r"]}
    return out


def _lp(bank, t, u, y):
    """バンクの (t, u, y)（ミリ）→ 局所座標の Vector（ミリ）"""
    return Vector((_lx(bank, u), y, t))


HEAD_TOP = 287.0

# 前のギアの面（エンジンの前の面からの距離 mm。ギアの前の面）：A = MGU-K と補機（ウォーターポンプ・スカベンジ・油圧ポンプ）、
# B = カムを回すアイドラーと頭の複合ギアの大、C = 頭の複合ギアの小とカムのギア（ヘッドの前の面 = 40 より手前）。推定
GEAR_PLANES = {"A": 2, "B": 17, "C": 30}


def accessory_layout():
    """前のギアの面 A の補機のギアの中心 (x, z)（mm）と歯数（モジュール 2.5）。クランクのギア 60 歯から、左右のウォーターポンプ（30 歯）、
    右のウォーターポンプからスカベンジポンプ（18 歯）、スカベンジポンプから油圧ポンプ（18 歯）へ。位置は推定"""
    cz = _L()["crank_z"]
    m = 2.5
    out = {}
    rw = m * (60 + 30) / 2
    for bank, tg in ((-1, "L"), (1, "R")):
        a = math.radians(-10)
        out[f"WaterPump{tg}"] = (Vector((bank * rw * math.cos(a), cz + rw * math.sin(a))), 30)
    w = out["WaterPumpR"][0]
    rs = m * (30 + 18) / 2
    a = math.radians(-10)
    out["Scavenge"] = (w + Vector((rs * math.cos(a), rs * math.sin(a))), 18)
    rh = m * (18 + 18) / 2
    a = math.radians(70)
    out["HydPump"] = (out["Scavenge"][0] + Vector((rh * math.cos(a), rh * math.sin(a))), 18)
    return out


def v6_heads(mats=None):
    """左右のシリンダーヘッド（鋳物）。ブーリアンで、燃焼室（ペントルーフ）・吸気と排気のポート・バルブガイドとばねの穴・
    プラグとインジェクターの穴・ウォータージャケット（ポートのまわりを避けて）とデッキの通水穴・ヘッドスタッドの穴・
    カムの溝とカムジャーナルの受けをあける。カムキャップは別の部品。戻り値はリスト"""
    m = _mats(mats)
    V6, L = _V6(), _L()
    deck = V6["deck"]
    yr = L["gearbox_y0"]
    yb0 = L["engine_front"] + 40
    cyl = f1.v6_cylinders()
    parts = []
    for bank, tag in ((-1, "L"), (1, "R")):
        ax = _valve_axes(bank)
        ys = [y for b, i, y in cyl if b == bank]
        hy0, hy1 = yb0, yr
        head = _box(f"Engine_Head{tag}", -75, 75, hy0, hy1, deck, HEAD_TOP, material=m["alu"])
        # ジャーナルの受け（カムの溝を掘ったあとに残す部分）を先に決める
        journals = [hy0 + 14] + [y + 48 for y in ys[:-1]] + [ys[-1] + 48]
        cut = []
        for i, y in enumerate(ys):
            # 燃焼室：浅いペントルーフ（回転体で近似）
            ch = qm.lathe(f"_ch{i}", [(39.5 * MM, -2 * MM), (39.5 * MM, 2 * MM), (34 * MM, 7 * MM), (20 * MM, 11 * MM), (6 * MM, 12.5 * MM)],
                          seg=40, location=(0, y * MM, deck * MM))
            cut.append(ch)
            for kind, a in ax.items():
                at, au = a["ax"]
                side = 1 if kind == "In" else -1
                for dy in (-f1.VALVE["dy"], f1.VALVE["dy"]):
                    seat = Vector((_lx(bank, a["u0"]), y + dy, deck + 2))
                    axv = Vector((_lx(bank, au), 0, at))
                    # ポート：弁の座から上へ、曲がって V の内側（吸気）か外側（排気）の面へ
                    r = a["r"] - 1.5
                    pts = [seat - axv * 3, seat + axv * 14,
                           Vector((_lx(bank, a["u0"] + side * 14), y + dy * 0.7, deck + 34)),
                           Vector((_lx(bank, side * 50), y + dy * 0.45, deck + 52)),
                           Vector((_lx(bank, side * 82), y + dy * 0.4, deck + 58))]
                    port = qm.tube(f"_port{kind}{i}{dy}", [p * MM for p in pts], radius=r * MM, seg=20)
                    cut.append(port)
                    # バルブガイドの穴と、空気ばねの穴
                    cut.append(_cyl_axis(f"_guide{kind}{i}{dy}", 3.6, seat + axv * 20, seat + axv * 120, seg=12))
                    cut.append(_cyl_axis(f"_spring{kind}{i}{dy}", 13.5, seat + axv * 58, seat + axv * 140, seg=24))
            # プラグの穴（真上）とインジェクターの穴（吸気側から斜め）
            cut.append(_cyl(f"_plug{i}", 7.2, deck + 5, HEAD_TOP + 5, y=y, seg=20))
            tip, top = _lp(bank, deck + 6, 34, y), _lp(bank, deck + 34, 96, y)
            cut.append(_cyl_axis(f"_inj{i}", 6.8, tip, top, seg=16))
            # デッキの通水穴（ブロックのジャケットから、ヘッドのジャケットへ）
            for k, (u, dy) in enumerate(((47, -36), (-47, -36), (47, 36), (-47, 36))):
                cut.append(_cyl(f"_xfer{i}{k}", 4, deck - 2, deck + 30, x=_lx(bank, u), y=y + dy, seg=12))
        # ヘッドスタッドの穴（ナットの座ぐり付き）
        for k, ysd in enumerate([y - 48 for y in ys] + [ys[-1] + 48]):
            for u in (-52, 52):
                cut.append(_cyl(f"_hs{k}{u}", 5.5, deck - 2, HEAD_TOP + 2, x=_lx(bank, u), y=ysd, seg=16))
        # ウォータージャケット：シリンダーの間と前後の端の部屋（バルブ・ポート・プラグ・スタッドを避ける）を、
        # 下の通水穴の高さでつなぐ
        zones = [ys[0] - 63] + [y + 33 for y in ys]

        def ubox(nm, u0, u1, y0, y1, t0, t1):
            xa, xb = sorted((_lx(bank, u0), _lx(bank, u1)))
            return _box(nm, xa, xb, max(y0, hy0 + 10), min(y1, hy1 - 10), t0, t1)
        for k, z0 in enumerate(zones):
            cut.append(ubox(f"_hj{k}", -42, 42, z0, z0 + 30, deck + 26, deck + 66))
            for s_ in (-1, 1):     # 低い通路で、両側の通水穴（u = ±47）の上をつなぐ
                cut.append(ubox(f"_hjo{k}{s_}", s_ * 34, s_ * 62, z0 - 6, z0 + 36, deck + 26, deck + 34))
        # カムの溝（カムが回る所）。ジャーナルの受けは残す
        for kind, a in ax.items():
            ct, cu = a["cam"]
            x0, x1 = sorted((_lx(bank, cu - 28), _lx(bank, cu + 28)))
            prev = hy0 + 22
            for jy in journals[1:] + [hy1 - 8]:
                y_end = min(jy - 9, hy1 - 8)
                if y_end > prev:
                    cut.append(_box(f"_trough{kind}{jy}", x0, x1, prev, y_end, ct - 27, HEAD_TOP + 5))
                prev = jy + 9
            cut.append(_cyl_y(f"_journal{kind}", 12.8, hy0 - 5, hy1 + 5, x=_lx(bank, cu), z=ct, seg=32))
        qm.cut(head, cut)
        _bank_place([head], bank)
        parts.append(head)
        # カムキャップ（ジャーナルを上から押さえる、2 本のボルト）
        for kind, a in ax.items():
            ct, cu = a["cam"]
            for j, jy in enumerate(journals[1:]):
                cap = _box(f"Engine_CamCap{tag}{kind}{j + 1}", _lx(bank, cu) - 22, _lx(bank, cu) + 22, jy - 8, jy + 8, ct, ct + 15,
                           material=m["alu"])
                qm.cut(cap, [_cyl_y(f"_cj{j}", 12.8, jy - 10, jy + 10, x=_lx(bank, cu), z=ct, seg=24)])
                bolts = []
                for s in (-1, 1):
                    b = qm.bolt(f"Engine_CamCapBolt{tag}{kind}{j + 1}{'ab'[s > 0]}", "M6", 0.025, material=m["steel"])
                    qm._place(b, ((_lx(bank, cu) + s * 16) * MM, jy * MM, (ct + 15) * MM))
                    bolts.append(b)
                _bank_place([cap] + bolts, bank)
                parts += [cap] + bolts
    return parts


def v6_head_gaskets(mats=None):
    """ヘッドガスケット（金属の積層板、ボア・通水穴・スタッドの穴を抜く）。左右 2 枚"""
    m = _mats(mats)
    V6, L = _V6(), _L()
    deck = V6["deck"]
    yb0, yr = L["engine_front"] + 40, L["gearbox_y0"]
    parts = []
    for bank, tag in ((-1, "L"), (1, "R")):
        ys = [y for b, i, y in f1.v6_cylinders() if b == bank]
        g = _box(f"Engine_HeadGasket{tag}", -62, 62, yb0 + 4, yr - 14, deck - 0.6, deck + 0.6, material=m["gasket"])
        cut = []
        for i, y in enumerate(ys):
            cut.append(_cyl(f"_gb{i}", 41, deck - 2, deck + 2, y=y, seg=40))
            for k, (u, dy) in enumerate(((47, -30), (-47, -30), (47, 30), (-47, 30))):
                cut.append(_cyl(f"_gx{i}{k}", 4.5, deck - 2, deck + 2, x=_lx(bank, u), y=y + dy, seg=12))
        for k, ysd in enumerate([y - 48 for y in ys] + [ys[-1] + 48]):
            for u in (-52, 52):
                cut.append(_cyl(f"_gs{k}{u}", 6, deck - 2, deck + 2, x=_lx(bank, u), y=ysd, seg=12))
        qm.cut(g, cut)
        parts += _bank_place([g], bank)
    return parts


def v6_cam_covers(mats=None):
    """カムカバー（中が空の殻。点火コイルの穴と、まわりのボルト）。左右"""
    m = _mats(mats)
    V6, L = _V6(), _L()
    yb0, yr = L["engine_front"] + 40, L["gearbox_y0"]
    parts = []
    for bank, tag in ((-1, "L"), (1, "R")):
        ys = [y for b, i, y in f1.v6_cylinders() if b == bank]
        h0, h1 = HEAD_TOP, HEAD_TOP + 52
        st = [(yb0 * MM, 0, h0 * MM, 0.140, (h1 - h0) * MM, 0.022), ((yr - 10) * MM, 0, h0 * MM, 0.140, (h1 - h0) * MM, 0.022)]
        cov = f1.body(f"Engine_CamCover{tag}", st, m["cover"], n=3)
        inner = f1.body("_cci", [((yb0 + 4) * MM, 0, (h0 - 2) * MM, 0.132, (h1 - h0 - 2) * MM, 0.018),
                                 ((yr - 14) * MM, 0, (h0 - 2) * MM, 0.132, (h1 - h0 - 2) * MM, 0.018)], None, n=3)
        cut = [inner] + [_cyl(f"_coil{i}", 14, h0 - 5, h1 + 5, y=y, seg=24) for i, y in enumerate(ys)]
        qm.cut(cov, cut)
        bolts = []
        n = 8                                         # ふちのボルト（左右 8 本ずつ、カバーの縁の肉の中を通してヘッドへ）
        for k in range(n):
            y = yb0 + 18 + (yr - 10 - 18 - (yb0 + 18)) * k / (n - 1)
            for x in (-64, 64):
                bolts += f1.fasten.fasten(f"Engine_CamCoverBolt{tag}{k + 1}{'ab'[x > 0]}", (x * MM, y * MM, (h0 + 6) * MM), (0, 0, -1),
                                          0.006, "M6", nut=False, washer=False, mat="steel")
        for i, y in enumerate(ys):                    # 点火コイルを留めるボルト（1 本ずつ）
            bolts += f1.fasten.fasten(f"Engine_CoilBolt{tag}{i + 1}", (22 * MM, y * MM, h1 * MM), (0, 0, -1), 0.004, "M5",
                                      nut=False, washer=True, mat="steel")
        coils = []
        for i, y in enumerate(ys):
            c = qm.cylinder(f"Engine_Coil{tag}{i + 1}", 0.0135, 0.075, seg=16, location=(0, y * MM, (HEAD_TOP + 2) * MM),
                            material=qm.material("F1_Coil", (0.10, 0.10, 0.10), metal=0.1, rough=0.5))
            coils.append(c)
        parts += _bank_place([cov] + bolts + coils, bank)
    return parts


def v6_front_cover(mats=None):
    """前のカバー（ギア列を覆う、中が空の殻。後ろはブロックへ開く）。戻り値 [カバー]"""
    m = _mats(mats)
    V6, L = _V6(), _L()
    cz, yf = L["crank_z"], L["engine_front"]
    yb0 = yf + 40
    lower = f1.body("Engine_FrontCover", [(yf * MM, 0, (cz - 78) * MM, 0.26, 0.143, 0.03), (yb0 * MM, 0, (cz - 78) * MM, 0.26, 0.143, 0.03)],
                    m["alu"], n=3)
    ups = []
    for bank in (-1, 1):
        b = qm.box(f"_fcu{bank}", (0.150, (yb0 - yf) * MM, (HEAD_TOP + 50 - 40) * MM), origin="bottom",
                   location=(0, (yf + yb0) / 2 * MM, 40 * MM))
        ups += _bank_place([b], bank)
    qm.union(lower, ups)
    inner = f1.body("_fci", [((yf + 4) * MM, 0, (cz - 72) * MM, 0.248, 0.131, 0.026), ((yb0 + 2) * MM, 0, (cz - 72) * MM, 0.248, 0.131, 0.026)],
                    None, n=3)
    inu = []
    for bank in (-1, 1):
        b = qm.box(f"_fci{bank}", (0.138, (yb0 - yf - 2) * MM, (HEAD_TOP + 44 - 46) * MM), origin="bottom",
                   location=(0, (yf + 4 + yb0 + 2) / 2 * MM, 46 * MM))
        inu += _bank_place([b], bank)
    qm.union(inner, inu)
    qm.cut(lower, [inner, _cyl_y("_seal", 22, yf - 5, yf + 6, z=cz, seg=32)])
    return [lower]


def v6_sump(mats=None):
    """ドライサンプのスカベンジの吸い口 3 本（クランク室の底から、右の横のスカベンジポンプへ）。
    クランクが低い（基準面の 90mm 上）ので、クランクの下にオイルパンを置く余地はなく、クランク室の底から直接吸う"""
    m = _mats(mats)
    L = _L()
    cz = L["crank_z"]
    mains, yc = v6_mains()
    picks = []
    for k, y in enumerate(yc):
        picks.append(qm.tube(f"Engine_SumpPickup{k + 1}", [(0.04, y * MM, (cz - 68) * MM), (0.09, y * MM, (cz - 64) * MM),
                                                            (0.125, y * MM, (cz - 45) * MM), (0.145, y * MM, (cz - 32) * MM)],
                             radius=0.006, seg=10, material=m["steel"]))
    return picks


# ================================================================ 回る部品


def _web_outline(pin_ang: float, r_main=34.0, r_pin=28.0, r_cw=58.0, stroke=53.0, n=40):
    """クランクのウェブの輪郭（主軸のまわり・ピンのまわり・反対側のカウンターウェイトを包む形、XZ のミリ）"""
    pts = []
    for k in range(48):
        a = 2 * math.pi * k / 48
        pts.append((r_main * math.cos(a), r_main * math.sin(a)))
        pc = (stroke / 2 * math.sin(pin_ang), stroke / 2 * math.cos(pin_ang))
        pts.append((pc[0] + r_pin * math.cos(a), pc[1] + r_pin * math.sin(a)))
    opp = pin_ang + math.pi
    for k in range(25):
        a = opp - math.radians(70) + math.radians(140) * k / 24
        pts.append((r_cw * math.sin(a), r_cw * math.cos(a)))
    pts = sorted(set((round(x, 4), round(y, 4)) for x, y in pts))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    hull = lo[:-1] + up[:-1]
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
    return out


def v6_crankshaft(crank_deg: float = 30.0, mats=None):
    """クランクシャフト（1 本の鍛造品：主軸 4・ピン 3・カウンターウェイト付きのウェブ 6・前の軸・後ろのフランジ・
    主軸からピンへの油穴）と、主軸受のメタル（上下 2 枚 × 4）。戻り値はリスト"""
    m = _mats(mats)
    V6, L = _V6(), _L()
    cz, yf, yr = L["crank_z"], L["engine_front"], L["gearbox_y0"]
    r = V6["stroke"] / 2
    mains, yc = v6_mains()
    pin_l = V6["stagger"] + 32
    pieces = []
    for i, y in enumerate(yc):
        ang = math.radians(crank_deg + 120 * i)
        px, pz = r * math.sin(ang), r * math.cos(ang)
        pieces.append(_cyl_y(f"_pin{i}", 21, y - pin_l / 2 - 1, y + pin_l / 2 + 1, x=px, z=cz + pz, seg=32))
        for s in (-1, 1):
            y0 = y + s * pin_l / 2
            y1 = y0 + s * 14
            outline = _web_outline(ang)
            secs = [[(x * MM, yy * MM, (cz + z) * MM) for x, z in outline] for yy in sorted((y0, y1))]
            pieces.append(qm.loft(f"_web{i}{s}", secs))
    jr = [(mains[0] - 20, yc[0] - pin_l / 2 - 13), (yc[0] + pin_l / 2 + 13, yc[1] - pin_l / 2 - 13),
          (yc[1] + pin_l / 2 + 13, yc[2] - pin_l / 2 - 13), (yc[2] + pin_l / 2 + 13, yr - 12)]
    for k, (y0, y1) in enumerate(jr):
        pieces.append(_cyl_y(f"_main{k}", 26, y0 - 1, y1 + 1, z=cz, seg=40))
    pieces.append(_cyl_y("_nose", 20, yf + 1, mains[0] - 19, z=cz, seg=32))
    pieces.append(_cyl_y("_flange", 45, yr - 12, yr + 5, z=cz, seg=48))      # 後ろの端のつば（ブロックの後ろの壁の穴を通り、フライホイールを留める）
    crank = pieces[0]
    crank.name = "Crank_Shaft"
    crank.data.materials.append(m["forged"])
    qm.union(crank, pieces[1:])
    # 油穴：主軸の表面から、となりのピンへ斜めに
    holes = []
    for i, y in enumerate(yc):
        ang = math.radians(crank_deg + 120 * i)
        pin = Vector((r * math.sin(ang), y, cz + r * math.cos(ang)))
        ym = mains[i] + 6
        holes.append(_cyl_axis(f"_oil{i}", 3, Vector((0, ym, cz)) - (pin - Vector((0, ym, cz))).normalized() * 30, pin, seg=12))
    qm.cut(crank, holes)
    parts = [crank]
    g = qm.gear("Crank_Gear", 60, 0.0025, 0.014, bore=0.02, material=m["steel"])     # MGU-K と補機を回すギア（前の軸の先）
    qm.orient(g, origin=(0, (yf + GEAR_PLANES["A"]) * MM, cz * MM), x_axis=(1, 0, 0), z_axis=(0, 1, 0))
    parts.append(g)
    for k, ym in enumerate(mains):
        w = 22 if 0 < k < 3 else 26
        for half, tag in ((1, "Upper"), (-1, "Lower")):
            sh = qm.ring(f"Crank_MainShell{k + 1}{tag}", 30 * MM, 26 * MM, w * MM, seg=40, origin="center")
            qm.orient(sh, origin=(0, ym * MM, cz * MM), x_axis=(1, 0, 0), z_axis=(0, 1, 0))
            qm.intersect(sh, _box("_half", -40, 40, ym - 20, ym + 20, cz if half > 0 else cz - 40, cz + 40 if half > 0 else cz))
            sh.data.materials.clear()
            sh.data.materials.append(m["bearing"])
            parts.append(sh)
    return parts


def _rod_frame(bank, i, crank_deg):
    V6, L = _V6(), _L()
    cz = L["crank_z"]
    r = V6["stroke"] / 2
    mains, yc = v6_mains()
    y = [yy for b, k, yy in f1.v6_cylinders() if b == bank and k == i][0]
    ang = math.radians(crank_deg + 120 * i)
    pin = Vector((r * math.sin(ang), 0, r * math.cos(ang)))
    d, inner = v6_frame(bank)
    along = pin.dot(d)
    perp = (pin - d * along).length
    s = along + math.sqrt(V6["rod"] ** 2 - perp ** 2)
    p_big = Vector((pin.x, y, cz + pin.z))
    p_pin = Vector((0, y, cz)) + d * s
    return p_big, p_pin, d, y


def v6_conrods(crank_deg: float = 30.0, mats=None):
    """コンロッド 6 本（I 断面の本体と、別体のキャップ、ボルト 2 本、大端のメタル上下、小端のブッシュ）"""
    m = _mats(mats)
    parts = []
    for bank, tg in ((-1, "L"), (1, "R")):
        for i in range(3):
            tag = f"{tg}{i + 1}"
            pb, pp, d, y = _rod_frame(bank, i, crank_deg)
            ax = (pp - pb).normalized()
            L = (pp - pb).length
            side = Vector((0, 1, 0)).cross(ax).normalized()       # 回る面の中で、軸に直角
            w = 16.0
            # 局所座標で作る：Z = 大端 → 小端、X = side、Y = クランク軸の向き
            shank = f1.body("_shank", [(-w / 2 * MM, 0, 0, 0.026, L * MM, 0.003), (w / 2 * MM, 0, 0, 0.026, L * MM, 0.003)], None, n=1)
            # body は Y に沿って断面を並べ、断面は XZ。ここでは X = 幅、Z = 長さ（0 〜 L）、Y = 厚み
            qm.cut(shank, [_box("_pk1", -9, 9, -w / 2 - 1, -w / 2 + 3.5, 30, L - 18), _box("_pk2", -9, 9, w / 2 - 3.5, w / 2 + 1, 30, L - 18)])
            big = _cyl_y("_bigeye", 34, -w / 2, w / 2, seg=40)
            small = _cyl_y("_smalleye", 13.5, -w / 2 + 1, w / 2 - 1, z=L, seg=32)
            rod = shank
            rod.name = f"Crank_Rod{tag}"
            rod.data.materials.append(m["ti"])
            qm.union(rod, [big, small])
            bolt_x = 26.5
            qm.cut(rod, [_cyl_y("_bigbore", 23, -w, w, seg=40), _cyl_y("_smallbore", 10.5, -w, w, z=L, seg=24),
                         _cyl("_bh1", 3.6, -40, 22, x=-bolt_x, seg=12), _cyl("_bh2", 3.6, -40, 22, x=bolt_x, seg=12)])
            cap = qm.copy(rod, f"Crank_RodCap{tag}")
            qm.intersect(rod, _box("_rk", -60, 60, -20, 20, 0, L + 30))
            qm.intersect(cap, _box("_ck", -60, 60, -20, 20, -60, 0))
            objs = [rod, cap]
            for k, s in enumerate((-1, 1)):
                b = qm.bolt(f"Crank_RodBolt{tag}{'ab'[k]}", "M8", 0.042, material=m["steel"])
                qm.orient(b, origin=(s * bolt_x * MM, 0, -24 * MM), x_axis=(1, 0, 0), z_axis=(0, 0, -1))
                objs.append(b)
            for half, ht in ((1, "Upper"), (-1, "Lower")):
                sh = qm.ring(f"Crank_RodShell{tag}{ht}", 23 * MM, 21 * MM, (w - 1) * MM, seg=32, origin="center")
                qm.orient(sh, origin=(0, 0, 0), x_axis=(1, 0, 0), z_axis=(0, 1, 0))
                qm.intersect(sh, _box("_h", -30, 30, -10, 10, 0 if half > 0 else -30, 30 if half > 0 else 0))
                sh.data.materials.clear()
                sh.data.materials.append(m["bearing"])
                objs.append(sh)
            bush = qm.ring(f"Crank_RodBush{tag}", 10.5 * MM, 9.6 * MM, (w - 2) * MM, seg=24, origin="center", material=m["bearing"])
            qm.orient(bush, origin=(0, 0, L * MM), x_axis=(1, 0, 0), z_axis=(0, 1, 0))
            objs.append(bush)
            # 据える：局所 Z → ax、局所 Y → 車の Y、原点 → 大端の中心
            qm.orient(objs, origin=pb * MM, x_axis=side, z_axis=ax)
            parts += objs
    return parts


def v6_pistons(crank_deg: float = 30.0, mats=None):
    """ピストン 6 個（リングの溝・ピンの穴・裏の空洞・頂面のバルブの逃げ）、ピストンリング 3 本ずつ（合い口付き）、
    ピストンピン（中空）とサークリップ 2 個ずつ"""
    m = _mats(mats)
    V6 = _V6()
    R = V6["bore"] / 2 - 0.4
    ch = V6["comp_h"]
    parts = []
    grooves = [(ch - 4.5, 1.2), (ch - 8.0, 1.2), (ch - 12.0, 2.5)]     # (溝の上端からの位置, 幅)
    for bank, tg in ((-1, "L"), (1, "R")):
        d, inner = v6_frame(bank)
        for i in range(3):
            tag = f"{tg}{i + 1}"
            pb, pp, d_, y = _rod_frame(bank, i, crank_deg)
            prof = [(R * 0.98, -ch)]
            z = -ch + 2
            prof.append((R, z))
            for top, w in sorted(grooves):
                prof += [(R, top - w), (R - 3.2, top - w), (R - 3.2, top), (R, top)]
            prof += [(R, ch - 0.8), (R - 0.8, ch), (0.001, ch)]
            prof = [(r_ * MM, z_ * MM) for r_, z_ in prof]
            pis = qm.lathe(f"Crank_Piston{tag}", prof, seg=48, material=m["piston"])
            cut = [qm.lathe("_under", [(R * 0.82 * MM, -ch * MM - 0.001), (R * 0.82 * MM, (ch - 9) * MM), (R * 0.5 * MM, (ch - 6) * MM)],
                            seg=40, cap=True)]
            cut.append(qm.cylinder("_pinbore", 9.6 * MM, (R * 2 + 4) * MM, seg=24, axis="X"))
            # 頂面のバルブの逃げ。ピストンの局所座標は X = ピンの向き（車の Y）、Y = u の向き（左は -u、右は +u）
            for k, (u, dy, rr) in enumerate(((16, -15, 15.5), (16, 15, 15.5), (-18, -15, 13.5), (-18, 15, 13.5))):
                cut.append(qm.cylinder(f"_vp{k}", rr * MM, 4 * MM, seg=24, location=(dy * MM, u * bank * MM, (ch - 1.2) * MM)))
            qm.cut(pis, cut)
            objs = [pis]
            for k, (top, w) in enumerate(grooves):
                rg = qm.ring(f"Crank_Ring{tag}{k + 1}", (R + 0.35) * MM, (R - 3.0) * MM, (w - 0.05) * MM, seg=48,
                             location=(0, 0, (top - w + 0.025) * MM), material=m["ring"])
                qm.cut(rg, [_box("_gap", R - 6, R + 3, -0.4, 0.4, top - w - 1, top + 1)])
                objs.append(rg)
            pin = qm.ring(f"Crank_GudgeonPin{tag}", 9.5 * MM, 5.5 * MM, (2 * R - 6) * MM, seg=24, origin="center", material=m["steel"])
            qm.orient(pin, origin=(0, 0, 0), x_axis=(0, 1, 0), z_axis=(1, 0, 0))
            objs.append(pin)
            for k, s in enumerate((-1, 1)):
                c = qm.ring(f"Crank_Circlip{tag}{'ab'[k]}", 10.6 * MM, 8.5 * MM, 1.0 * MM, seg=20, origin="center", material=m["steel"])
                qm.orient(c, origin=(s * (R - 2.5) * MM, 0, 0), x_axis=(0, 1, 0), z_axis=(1, 0, 0))
                objs.append(c)
            # 局所：Z = シリンダーの軸、X = ピンの向き（クランク軸 = Y に平行…ではなく）
            # ピストンピンはクランク軸と平行（車の Y）。局所 X を車の Y に、局所 Z を d に
            qm.orient(objs, origin=pp * MM, x_axis=(0, 1, 0), z_axis=d)
            parts += objs
    return parts


def _lobe_phase(bank, i, kind, j):
    """カムの山の向き（ラジアン。カムの局所の (x, z) 面で +x から）。点火順に合わせた本当のタイミングではなく推定"""
    return math.radians(120 * i + (0 if kind == "In" else 100) + 15 * j + (60 if bank > 0 else 0))


def _lobe_r(an, ph):
    """カムの山の半径（mm）。基礎円 16、揚程 9"""
    return 16 + 9 * max(0.0, math.cos(an - ph)) ** 3


def hp_pump_y():
    """燃料の高圧ポンプを押す 3 つ山のカムの y（右の吸気カムの、前のジャーナルと 1 番シリンダーの山の間。mm）"""
    yb0 = _L()["engine_front"] + 40
    ys = [y for b, i, y in f1.v6_cylinders() if b > 0]
    return (yb0 + 22 + ys[0] - f1.VALVE["dy"] - 6) / 2


def _valve_lift(bank, kind, y, j, i, seat, axv):
    """カムの山がタペットを押し下げる量（mm）。山の形とタペットの上の面から求める（バンクの局所座標、mm）"""
    a = _valve_axes(bank)[kind]
    ct, cu = a["cam"]
    cx = _lx(bank, cu)
    n = axv.normalized()
    top = seat + n * 97.0
    ph = _lobe_phase(bank, i, kind, j)
    pen = 0.0
    for k in range(180):
        an = 2 * math.pi * k / 180
        rr = _lobe_r(an, ph)
        q = Vector((cx + rr * math.cos(an), top.y, ct + rr * math.sin(an)))
        pen = max(pen, (top - q).dot(n))
    return pen


def v6_valves(mats=None):
    """バルブ 24 本（チューリップ形）、弁座、バルブガイド、空気ばねのシリンダーとピストン、コッター、タペット（中空のカップ）"""
    m = _mats(mats)
    V6 = _V6()
    deck = V6["deck"]
    Vv = f1.VALVE
    parts = []
    for bank, tg in ((-1, "L"), (1, "R")):
        ax = _valve_axes(bank)
        ys = [y for b, i, y in f1.v6_cylinders() if b == bank]
        for i, y in enumerate(ys):
            for kind, a in ax.items():
                at, au = a["ax"]
                axv = Vector((_lx(bank, au), 0, at))
                r = a["r"]
                for j, dy in enumerate((-Vv["dy"], Vv["dy"])):
                    nm = f"Valve_{tg}{i + 1}{kind}{'ab'[j]}"
                    seat = Vector((_lx(bank, a["u0"]), y + dy, deck + 2))
                    prof = [(r * MM, 0), (r * MM, 1.2 * MM), ((r - 1.8) * MM, 3.0 * MM), (5 * MM, 9 * MM), (3.4 * MM, 16 * MM),
                            (3.0 * MM, 24 * MM), (3.0 * MM, Vv["len"] * MM - 0.004), (2.6 * MM, Vv["len"] * MM)]
                    objs = [qm.lathe(nm, prof, seg=24, material=m["ti"] if kind == "In" else m["steel"])]
                    objs.append(qm.ring(f"{nm}_Seat", (r + 2.5) * MM, (r - 2.2) * MM, 4 * MM, seg=32, location=(0, 0, -1.5 * MM), material=m["steel"]))
                    objs.append(qm.ring(f"{nm}_Guide", 6.0 * MM, 3.15 * MM, 38 * MM, seg=16, location=(0, 0, 24 * MM), material=m["bearing"]))
                    objs.append(qm.ring(f"{nm}_SpringCyl", 13.0 * MM, 11.5 * MM, 26 * MM, seg=24, location=(0, 0, 60 * MM), material=m["alu"]))
                    objs.append(qm.cylinder(f"{nm}_SpringPiston", 11.4 * MM, 6 * MM, seg=24, location=(0, 0, 80 * MM), material=m["steel"]))
                    objs.append(qm.lathe(f"{nm}_Collet", [(3.0 * MM, 86 * MM), (5.0 * MM, 86 * MM), (4.0 * MM, 92 * MM), (3.0 * MM, 92 * MM)],
                                         seg=16, closed=True, material=m["steel"]))
                    tap = qm.lathe(f"{nm}_Tappet", [(11.4 * MM, 86.5 * MM), (11.4 * MM, 97 * MM)], seg=32, material=m["steel"])
                    qm.cut(tap, [qm.cylinder("_tc", 10.2 * MM, 9 * MM, seg=32, location=(0, 0, 86 * MM))])
                    objs.append(tap)
                    # カムの山がタペットを押している分だけ、バルブ・コッター・ばねのピストン・タペットを下げる（バルブが開く）
                    lift = _valve_lift(bank, kind, y + dy, j, i, seat, axv)
                    if lift > 0.05:
                        for o in (objs[0], objs[4], objs[5], objs[6]):
                            o.location.z -= lift * MM
                    qm.orient(objs, origin=seat * MM, x_axis=Vector((0, 1, 0)), z_axis=axv)
                    parts += _bank_place(objs, bank)
    return parts


def v6_camshafts(mats=None):
    """カムシャフト 4 本（1 本の部品：軸・ジャーナル・バルブごとのカム。中は油の通る穴）"""
    cam_m = qm.material("F1_CamSteel", (0.55, 0.53, 0.50), metal=0.95, rough=0.25)
    L = _L()
    yf, yr = L["engine_front"], L["gearbox_y0"]
    yb0 = yf + 40
    Vv = f1.VALVE
    parts = []
    for bank, tg in ((-1, "L"), (1, "R")):
        ax = _valve_axes(bank)
        ys = [y for b, i, y in f1.v6_cylinders() if b == bank]
        journals = [y + 48 for y in ys[:-1]] + [ys[-1] + 48]
        for kind, a in ax.items():
            ct, cu = a["cam"]
            x = _lx(bank, cu)
            shaft = _cyl_y(f"Cam_{tg}{kind}", 10, yf + 30, yr - 18, x=x, z=ct, seg=24, material=cam_m)
            pieces = [_cyl_y(f"_j{k}", 12.5, jy - 7, jy + 7, x=x, z=ct, seg=32) for k, jy in enumerate(journals)]
            pieces.append(_cyl_y("_jf", 12.5, yb0 + 8, yb0 + 22, x=x, z=ct, seg=32))
            for i, y in enumerate(ys):
                for j, dy in enumerate((-Vv["dy"], Vv["dy"])):
                    ph = _lobe_phase(bank, i, kind, j)
                    prof = []
                    for k in range(32):
                        an = 2 * math.pi * k / 32
                        rr = _lobe_r(an, ph)
                        prof.append((x + rr * math.cos(an), ct + rr * math.sin(an)))
                    secs = [[(px * MM, (y + dy + yy) * MM, pz * MM) for px, pz in prof] for yy in (-6, 6)]
                    pieces.append(qm.loft(f"_lobe{i}{j}", secs))
            if bank > 0 and kind == "In":          # 燃料の高圧ポンプを押す 3 つ山のカム
                yp = hp_pump_y()
                prof = [(x + (17 + 6 * max(0.0, math.cos(3 * (2 * math.pi * k / 48))) ** 2) * math.cos(2 * math.pi * k / 48),
                         ct + (17 + 6 * max(0.0, math.cos(3 * (2 * math.pi * k / 48))) ** 2) * math.sin(2 * math.pi * k / 48)) for k in range(48)]
                pieces.append(qm.loft("_trilobe", [[(px * MM, (yp + yy) * MM, pz * MM) for px, pz in prof] for yy in (-5, 5)]))
            qm.union(shaft, pieces)
            qm.cut(shaft, [_cyl_y("_oil", 4, yf + 20, yr, x=x, z=ct, seg=16)])
            g = qm.gear(f"Cam_{tg}{kind}Gear", 36, 0.0015, 0.010, bore=0.008, material=cam_m)    # ギア列（f1.v6_gear_train）から回る
            qm.orient(g, origin=(x * MM, (yf + GEAR_PLANES["C"]) * MM, ct * MM), x_axis=(1, 0, 0), z_axis=(0, 1, 0))
            parts += _bank_place([shaft, g], bank)
    return parts


def v6_studs(mats=None):
    """ヘッドスタッド（ブロックにねじ込み、ヘッドを通してナットで締める）。左右 8 本ずつ"""
    m = _mats(mats)
    V6 = _V6()
    deck = V6["deck"]
    parts = []
    for bank, tg in ((-1, "L"), (1, "R")):
        ys = [y for b, i, y in f1.v6_cylinders() if b == bank]
        objs = []
        for k, ysd in enumerate([y - 48 for y in ys] + [ys[-1] + 48]):
            for j, u in enumerate((-52, 52)):
                nm = f"Engine_HeadStud{tg}{k + 1}{'ab'[j]}"
                objs.append(_cyl(nm, 5, deck - 65, HEAD_TOP + 9, x=_lx(bank, u), y=ysd, seg=12, material=m["steel"]))
                n = qm.nut(f"{nm}_Nut", "M10", material=m["steel"])
                qm._place(n, (_lx(bank, u) * MM, ysd * MM, HEAD_TOP * MM))
                objs.append(n)
        parts += _bank_place(objs, bank)
    return parts


def v6_plugs_injectors(mats=None):
    """点火プラグ（燃焼室からコイルの下まで）とインジェクター（吸気側から斜めに）、左右の燃料レール"""
    m = _mats(mats)
    V6 = _V6()
    deck = V6["deck"]
    ceramic = qm.material("F1_Ceramic", (0.92, 0.92, 0.90), metal=0.0, rough=0.4)
    parts = []
    for bank, tg in ((-1, "L"), (1, "R")):
        ys = [y for b, i, y in f1.v6_cylinders() if b == bank]
        objs = []
        for i, y in enumerate(ys):
            objs.append(qm.lathe(f"Plug_{tg}{i + 1}", [(0.005, 0), (0.007, 0.004), (0.007, 0.060), (0.010, 0.062), (0.010, 0.078),
                                                         (0.006, 0.082), (0.006, (HEAD_TOP - deck - 2) * MM)], seg=16,
                                 location=(0, y * MM, (deck + 4) * MM), material=m["steel"]))
            objs.append(qm.cylinder(f"Plug_{tg}{i + 1}Insulator", 0.0065, (HEAD_TOP + 10 - deck - 85) * MM, seg=16,
                                    location=(0, y * MM, (deck + 84) * MM), material=ceramic))
            tip, top = _lp(bank, deck + 7, 34, y), _lp(bank, deck + 34, 96, y)
            axv = (top - tip).normalized()
            inj = qm.lathe(f"Injector_{tg}{i + 1}", [(0.003, 0), (0.0045, 0.006), (0.0065, 0.012), (0.0065, 0.050), (0.009, 0.052),
                                                      ((0.009), ((top - tip).length + 6) * MM)], seg=16, material=m["steel"])
            qm.orient(inj, origin=tip * MM, x_axis=Vector((0, 1, 0)), z_axis=axv)
            objs.append(inj)
        r0, r1 = _lp(bank, deck + 37, 104, ys[0] - 40), _lp(bank, deck + 37, 104, ys[-1] + 25)
        rail = qm.tube(f"FuelRail_{tg}", [r0 * MM, r1 * MM], radius=0.008, seg=16, material=m["steel"])
        qm.cut(rail, [qm.tube("_rb", [(r0 - Vector((0, 5, 0))) * MM, (r1 + Vector((0, 5, 0))) * MM], radius=0.005, seg=12)])
        objs.append(rail)
        parts += _bank_place(objs, bank)
    return parts


def water_pump_point(bank: int):
    """ウォーターポンプの中心と、外向き（吸い口の向き）（ミリ）。前のカバーの下の左右の角。軸は Y で、ギアの面 A でクランクのギアから回る"""
    c2 = accessory_layout()[f"WaterPump{'L' if bank < 0 else 'R'}"][0]
    yf = _L()["engine_front"]
    return Vector((c2.x, yf + 34, c2.y)), Vector((bank, 0, 0))


def _gear_on_shaft(name, teeth, x, z, y0, y1, mats_steel, plane="A"):
    """ギアの面にギア（モジュール 2.5、幅 14mm）と、そこから y1 までの軸（ミリ）"""
    yf = _L()["engine_front"]
    yp = yf + GEAR_PLANES[plane]
    g = qm.gear(f"{name}_Gear", teeth, 0.0025, 0.014, bore=0.012, material=mats_steel)
    qm.orient(g, origin=(x * MM, yp * MM, z * MM), x_axis=(1, 0, 0), z_axis=(0, 1, 0))
    sh = _cyl_y(f"{name}_DriveShaft", 6, yp - 1, y1, x=x, z=z, seg=16, material=mats_steel)
    return [g, sh]


def v6_pumps(mats=None):
    """ポンプ：前のカバーの下の左右の角のウォーターポンプ 2 個（渦巻きのハウジング・羽根車。ギアの面 A でクランクのギアから回る）、
    クランクケースの右の横のオイルポンプ（スカベンジ 3 段と圧送 1 段。右のウォーターポンプのギアから回る）、
    燃料の高圧ポンプ（右の吸気カムの 3 つ山のカムでプランジャーを押す）。位置と寸法は推定"""
    m = _mats(mats)
    L = _L()
    cz, yf, yr = L["crank_z"], L["engine_front"], L["gearbox_y0"]
    yb0 = yf + 40
    lay = accessory_layout()
    parts = []
    for bank, tg in ((-1, "L"), (1, "R")):
        c, out = water_pump_point(bank)
        h = qm.lathe(f"Engine_WaterPump{tg}", [(0.010, -0.006), (0.034, -0.006), (0.036, 0.0), (0.034, 0.006), (0.010, 0.006)], seg=32,
                     closed=True, material=m["alu"])
        qm.cut(h, [qm.lathe("_wpi", [(0.012, -0.0045), (0.032, -0.0045), (0.032, 0.0045), (0.012, 0.0045)], seg=32, closed=True)])
        imp = [qm.cylinder(f"Engine_WaterPump{tg}_Impeller", 0.028, 0.0015, seg=32, origin="center", location=(0, 0, -0.002), material=m["steel"])]
        for k in range(8):
            v = qm.box(f"Engine_WaterPump{tg}_Vane{k + 1}", (0.016, 0.0015, 0.005), origin="center", location=(0.019, 0, 0.0015), material=m["steel"])
            qm.pivot(v, (0, 0, 0), (0, 0, 45 * k + 20))
            imp.append(v)
        objs = [h] + imp
        qm.orient(objs, origin=c * MM, x_axis=(1, 0, 0), z_axis=(0, 1, 0))
        inlet = qm.cylinder(f"Engine_WaterPump{tg}_Inlet", 0.013, 0.022, seg=16, axis="X",
                            location=tuple((c + out * 45) * MM), material=m["alu"])
        parts += objs + [inlet]
        parts += _gear_on_shaft(f"Engine_WaterPump{tg}", lay[f"WaterPump{tg}"][1], c.x, c.z, 0, yf + 40, m["steel"])
    # オイルポンプ：ハウジング（中空）と 3 段のロータ、軸。前の端は、ギアの面 A のギアで右のウォーターポンプのギアから回る
    sc = lay["Scavenge"][0]
    sx, sz = sc.x, sc.y
    mains, yc = v6_mains()
    y_start = min(yf + 95, min(yc) - 8 - 14)
    hs = _cyl_y("Engine_ScavengePump", 26, y_start, yr - 30, x=sx, z=sz, seg=32, material=m["alu"])
    qm.cut(hs, [_cyl_y("_spb", 21, y_start + 6, yr - 36, x=sx, z=sz, seg=32)])
    parts.append(hs)
    for k, y in enumerate(yc):
        g = qm.gear(f"Engine_ScavengeRotor{k + 1}", 6, 0.006, 0.016, bore=0.004, material=m["steel"])
        qm.orient(g, origin=(sx * MM, (y - 8) * MM, sz * MM), x_axis=(1, 0, 0), z_axis=(0, 1, 0))
        ring_ = qm.ring(f"Engine_ScavengeRotor{k + 1}_Outer", 0.0205, 0.0175, 0.016, seg=32, material=m["steel"])
        qm.orient(ring_, origin=(sx * MM, (y - 8) * MM, sz * MM), x_axis=(1, 0, 0), z_axis=(0, 1, 0))
        parts += [g, ring_]
    parts.append(_cyl_y("Engine_ScavengeShaft", 4, y_start + 2, yr - 32, x=sx, z=sz, seg=12, material=m["steel"]))
    parts += _gear_on_shaft("Engine_ScavengePump", lay["Scavenge"][1], sx, sz, 0, y_start + 1, m["steel"])
    # 燃料の高圧ポンプ：右の吸気カムの 3 つ山のカムの上（V の側へ 45° 傾けて）。カムカバーを通って V の中へ出る
    a = _valve_axes(1)["In"]
    ct, cu = a["cam"]
    yp = hp_pump_y()
    cam_c = Vector((_lx(1, cu), yp, ct))
    n = Vector((_lx(1, 1.0), 0, 1.0)).normalized()                       # 上と V の側の間
    base = cam_c + n * 23.5
    body = _cyl_axis("Engine_FuelPumpHP", 15, base + n * 12, base + n * 62, seg=24, material=m["steel"])
    plunger = _cyl_axis("Engine_FuelPumpHP_Plunger", 5, base - n * 0.5, base + n * 14, seg=16, material=m["steel"])
    side = Vector((0, 1, 0))
    inlet = _cyl_axis("Engine_FuelPumpHP_Inlet", 5, base + n * 40 + side * 14, base + n * 40 + side * 26, seg=12, material=m["steel"])
    outlet = _cyl_axis("Engine_FuelPumpHP_Outlet", 4, base + n * 52 - side * 14, base + n * 52 - side * 24, seg=12, material=m["steel"])
    parts += _bank_place([body, plunger, inlet, outlet], 1)
    return parts


def v6_oil_jets(mats=None):
    """ピストンを下から冷やすオイルジェット 6 本（クランク室の壁の取り付け台から、ピストンの裏へ向けた細い管）"""
    m = _mats(mats)
    parts = []
    for bank, tg in ((-1, "L"), (1, "R")):
        objs = []
        for i, y in enumerate([y for b, k, y in f1.v6_cylinders() if b == bank]):
            base = Vector((_lx(bank, -50), y + 22, 52))           # シリンダーの下の端の壁（バンクの外寄り）。クランクのおもりが回る範囲の外
            tip = Vector((_lx(bank, -32), y + 14, 66))
            objs.append(_box(f"Engine_OilJet{tg}{i + 1}_Mount", base.x - 6, base.x + 6, base.y - 6, base.y + 6, base.z - 8, base.z, material=m["steel"]))
            tube = qm.tube(f"Engine_OilJet{tg}{i + 1}", [base * MM, (base + Vector((0, -4, 10))) * MM, tip * MM], radius=0.0025, seg=10,
                           material=m["steel"])
            f1.hollow(tube, [base * MM, (base + Vector((0, -4, 10))) * MM, tip * MM], 0.0025, 0.0007)
            objs.append(tube)
        parts += _bank_place(objs, bank)
    return parts


def v6_engine_real(crank_deg: float = 30.0, mats=None):
    """V6 エンジンを実物どおりの部品で組み立てる（ブロック・ベッドプレート・ヘッド・ガスケット・カバー・オイルパン・
    クランク・コンロッド・ピストン・バルブ・カム・スタッド・プラグ・インジェクター・ポンプ）。戻り値は部品のリスト"""
    parts = []
    for fn in (v6_block, v6_heads, v6_head_gaskets, v6_cam_covers, v6_front_cover, v6_sump, v6_studs, v6_plugs_injectors, v6_pumps,
               v6_valves, v6_camshafts, v6_oil_jets):
        parts += fn(mats=mats)
    # ブロックとベッドプレートの後ろの壁に、クランクの後ろのつば（半径 45mm）を通す穴
    yr = _L()["gearbox_y0"]
    for nm in ("Engine_Block", "Engine_Bedplate"):
        ob = [o for o in parts if o.name == nm]
        if ob:
            qm.cut(ob[0], [_cyl_y("_rear_seal", 48, yr - 15, yr + 2, z=_L()["crank_z"], seg=48)])
    parts += v6_crankshaft(crank_deg, mats=mats)
    parts += v6_conrods(crank_deg, mats=mats)
    parts += v6_pistons(crank_deg, mats=mats)
    return parts
