# F1 シャシーの、車体（カウル・ウイング・フロア）を除いたすべての部品と、部品ごとの図鑑。寸法はすべてミリ
# 実在の値: ホイールベース 3,400mm、全幅 1,900mm、タイヤ 前 705×280 / 後ろ 710×375mm、18 インチ、
#           ブレーキディスク 前 328×32 / 後ろ 280×32mm、V6 90°・ボア 80・ストローク 53mm（1.6L）、前進 8 段、
#           エネルギーストアはサバイバルセルの中（ドライバーの後ろ・燃料タンクの下）
# 推定値  : 部品の位置（f1.LAYOUT）と、上に書いた以外の寸法（公表されていない）
# 確認できた事実（細部）: 1 気筒 4 バルブ・DOHC・空気ばね、直噴（1 気筒 1 本・最大 500bar）
#           プランクは厚さ 10mm・すり減りの下限 9mm・測る穴は直径 50mm
# 作り方  : エンジンとギアボックスは実物と同じ部品の分け方（鋳物はブーリアンで穴・通路・空洞をあける）。
#           管・排気管・プレナム・ターボ・MGU-K も中空（f1.HOLLOW）。そのため qm.cad() で四角形の検査を外す
#           継ぎ目はすべてボルト・ナット・座金で留める（f1.fasten。同じ寸法の留め具はメッシュを共有）。
#           箱の中身（燃料セル・電池・インバーター・基板・ラジエーターのコア）とセンサー・配線の枝も作る（中の作りと位置は推定）
# 図鑑    : ビューアーの「図鑑を開く」で、qm.catalog で登録した項目ごとに等角図・三面図・部品表を描く（48 項目）
qm.units("mm")
qm.cad()
f1.HOLLOW = True
MM = qm.MM
L = f1.LAYOUT

def P(x, y, z):
    return Vector((x * MM, y * MM, z * MM))

mats = f1.materials()
titan = mats["titanium"]

YR_TUB = f1.LAYOUT["tub"][-1][0] * MM          # サバイバルセルの後ろの隔壁（= エンジンの前の面）

# 配管・配線は route で引く。サバイバルセルの隔壁や横の壁を通る所に、貫通の継ぎ手（グロメット）を自動で付ける
def route(name, points, r=0.019, kind="hose", mats=None):
    parts = f1.pipe(name, points, r=r, kind=kind, mats=mats)
    pts = [Vector(q) for q in points]
    z0 = f1.EST["plank_z"] + 0.03
    def wall(q):                                         # 壁の外なら正、中なら負
        if not (-0.35 <= q.y <= YR_TUB) or not (z0 < q.z < f1.tub_section(q.y / MM)[1] * MM):
            return None
        return abs(q.x) - f1.tub_section(q.y / MM)[0] / 2 * MM
    hits = []
    for a, b in zip(pts, pts[1:]):
        for yb in (YR_TUB - 0.005, -0.345):              # 後ろと前の隔壁
            if (a.y - yb) * (b.y - yb) < 0:
                q = a + (b - a) * ((yb - a.y) / (b.y - a.y))
                w = wall(Vector((q.x, min(max(q.y, -0.349), YR_TUB - 0.001), q.z)))
                if w is not None and w < 0:
                    hits.append((q, (b - a).normalized()))
        prev = None
        for k in range(41):                              # 横の壁
            q = a + (b - a) * (k / 40)
            w = wall(q)
            if w is not None and prev is not None and (w > 0) != (prev[1] > 0):
                hits.append(((q + prev[0]) / 2, (b - a).normalized()))
            prev = (q, w) if w is not None else None
    for k, (q, d) in enumerate(hits):
        g = qm.ring(f"{name}_Fitting{k + 1}", r + 0.007, r, 0.014, seg=12, origin="center", material=titan)
        qm.orient(g, origin=q, x_axis=d.orthogonal(), z_axis=d)
        parts.append(g)
    return parts

CZ = L["crank_z"]
YF, YGB = L["engine_front"], L["gearbox_y0"]

# =========================================================== サバイバルセル・コクピット
f1.survival_cell("Cell", mats=mats)
f1.roll_hoop("RollHoop", y=1870 * MM, top_z=960 * MM, half_w=200 * MM, mats=mats)
hw1800 = f1.tub_section(1800)[0] / 2
f1.halo_frame("Halo", rear_y=1800 * MM, front_y=1100 * MM, half_w=(hw1800 - 22) * MM, top_z=840 * MM, mats=mats)
f1.headrest("Headrest", 1600 * MM, 1840 * MM, mats=mats)
f1.seat("Seat", [(1.30, 0.080), (1.45, 0.073), (1.58, 0.082), (1.70, 0.20), (1.77, 0.40), (1.81, 0.60)], mats=mats)
f1.harness("Harness", buckle=(0, 1.45, 0.26), mats=mats)

# ステアリングホイールとコラム（ラックのピニオンから、ユニバーサルジョイント 2 つで折れてホイールへ）
RACK = P(0, -110, 300)
f1.steering_rack("Rack", tuple(RACK), mats=mats)
pin_axis = Vector((0, math.sin(math.radians(35)), math.cos(math.radians(35))))
pin_top = RACK + Vector((0.04, 0, 0)) + pin_axis * 0.07
W = P(0, 1200, 500)
UJ1, UJ2 = pin_top + pin_axis * 0.04, P(0, 950, 470)
c_dir = (W - UJ2).normalized()
qm.orient(f1.steering_wheel("Wheel", mats=mats), origin=W, x_axis=(1, 0, 0), z_axis=Vector((1, 0, 0)).cross(c_dir))
f1.steering_column("Column", [pin_top - pin_axis * 0.01, UJ1, UJ2, W - c_dir * 0.068], mats=mats)
cb_z = UJ2.z + (W.z - UJ2.z) * (1.05 - 0.95) / (1.20 - 0.95)
f1.tub_section(1050)
qm.box("Column_Bracket", (0.040, 0.026, f1.tub_section(1050)[1] * MM - 0.045 - cb_z), origin="bottom", location=(0, 1.05, cb_z + 0.012), material=titan)
qm.orient(qm.ring("Column_Bearing", 0.022, 0.012, 0.024, seg=16, origin="center", material=titan), origin=(0, 1.05, cb_z), x_axis=(1, 0, 0), z_axis=c_dir)

# ペダル（床に軸。左がブレーキ、右がアクセル。クラッチはホイールの裏のパドル）
qm.box("PedalBox_Base", (0.30, 0.30, 0.010), origin="bottom", location=(0, 0.56, 0.071), material=titan)
qm.box("PedalBox_Front", (0.24, 0.010, 0.26), origin="bottom", location=(0, 0.425, 0.081), material=titan)
for x, nm in ((-80, "PedalBrake"), (80, "PedalThrottle")):
    f1.pedal(nm, P(x, 640, 95), P(x, 520, 300), mats=mats)
t = (220 - 95) / (300 - 95)
bb = P(-80, 640 - 120 * t, 220)
qm.tube("BalanceBar", [bb + Vector((-0.045, 0, 0)), bb + Vector((0.045, 0, 0))], radius=0.006, seg=10, material=titan)
for k, dx in enumerate((-35, 35)):
    f1.master_cylinder(f"Master{k + 1}", P(-80 + dx, 432, 220), bb + Vector((dx * MM, 0, 0)), mats=mats)
# ブレーキフルードのリザーバー（前後の系統に 1 つずつ。ペダルボックスの前の板の上に。形と位置は推定）
for k, dx in enumerate((-35, 35)):
    rx = -80 + dx
    qm.lathe(f"BrakeReservoir{k + 1}", [(0.012, 0.0), (0.016, 0.004), (0.016, 0.046), (0.012, 0.050)], seg=16,
             material=qm.material("F1_Reservoir", (0.85, 0.85, 0.80), metal=0.0, rough=0.4), location=tuple(P(rx, 405, 342)))
    qm.cylinder(f"BrakeReservoir{k + 1}_Cap", 0.010, 0.008, seg=16, location=tuple(P(rx, 405, 392)), material=titan)
    qm.box(f"BrakeReservoir{k + 1}_Bracket", (0.036, 0.016, 0.004), origin="bottom", location=tuple(P(rx, 412, 338)), material=titan)
    qm.tube(f"BrakeReservoir{k + 1}_Hose", [P(rx, 405, 343), P(rx, 405, 300), P(rx, 437, 260), P(rx, 437, 237)], radius=0.003, seg=8,
            material=qm.material("F1_Hose", (0.10, 0.10, 0.12), metal=0.0, rough=0.7))
qm.cylinder("PedalThrottle_Sensor", 0.016, 0.03, seg=12, axis="X", location=tuple(P(80 + 40, 640, 95)), material=mats["titanium"])

f1.fire_extinguisher("Extinguisher", y0=1.00, length=0.30, r=0.05, mats=mats)

# 側面衝撃吸収構造（サイドポッドの前、上下 2 本ずつ）
for s, tg in ((-1, "L"), (1, "R")):
    hw = f1.tub_section(1300)[0] / 2
    for z, lvl in ((520, "Upper"), (170, "Lower")):
        f1.side_impact(f"SideImpact{lvl}{tg}", P(s * (hw - 15), 1300, z), P(s * 700, 1300, z), mats=mats)

# =========================================================== 燃料・エネルギーストア
FC0, FC1 = L["fuel_cell"]
f1.energy_store("ES", y0=FC0 * MM, y1=FC1 * MM, width=0.56, z0=0.073, h=0.10, mats=mats)
f1.fuel_cell("FuelCell", y0=FC0 * MM, y1=FC1 * MM, half_w=0.32, z0=0.179, z1=0.64, mats=mats)
f1.control_electronics("CE", center=(0.16, 2.33, 0.073), size=(0.18, 0.14, 0.16), mats=mats)
f1.oil_tank("OilTank", 2.25, 2.49, 0.14, 0.30, 0.60, mats=mats)          # 燃料タンクとエンジンの間（隔壁の手前まで）
# オイルフィルター（オイルタンクの左の横に。缶と中のエレメント）
ofc = qm.cylinder("Engine_OilFilter", 0.030, 0.040, seg=32, axis="X", location=(0.160, 2.37, 0.45), material=titan)
qm.cut(ofc, [qm.cylinder("_ofi", 0.0275, 0.040, seg=32, axis="X", location=(0.162, 2.37, 0.45))])
ofe = qm.cylinder("Engine_OilFilter_Element", 0.025, 0.032, seg=32, axis="X", location=(0.160, 2.37, 0.45),
                  material=qm.material("F1_FilterPaper", (0.85, 0.80, 0.55), metal=0.0, rough=0.9))
qm.cut(ofe, [qm.cylinder("_ofc", 0.010, 0.036, seg=24, axis="X", location=(0.160, 2.37, 0.45))])

# =========================================================== パワーユニット
f1.v6_engine_real(30, mats=mats)        # ブロック・ベッドプレート・ヘッド・ガスケット・カバー・オイルパン・クランク・コンロッド・ピストン・バルブ・カム・ポンプ
# エンジンの前の面を、サバイバルセルの後ろの隔壁にボルトで直接留める（エンジンが車体の骨組みを兼ねる）
for k, (x, z) in enumerate(((-0.11, CZ - 70), (0.11, CZ - 70), (-0.11, CZ + 30), (0.11, CZ + 30), (-0.20, CZ + 180), (0.20, CZ + 180))):
    qm.orient(qm.bolt(f"Engine_MountBolt{k + 1}", "M10", 0.040, material=titan), origin=(x, YR_TUB - 0.010, z * MM),
              x_axis=(1, 0, 0), z_axis=(0, -1, 0))
f1.intake("Intake", mats=mats)
TC = P(0, 3060, 610)                                       # ターボの軸の中心
f1.exhaust("Exhaust", turbine_in=(115, 3120, 610), mats=mats)
qm.orient(f1.turbocharger("Turbo", mats=mats), origin=TC, x_axis=(1, 0, 0), z_axis=(0, 1, 0))
qm.box("Turbo_Bracket", (0.04, 0.04, 0.110), origin="bottom", location=(0, 3.06, 0.455), material=titan)
inconel = qm.material("F1_Inconel", (0.42, 0.36, 0.30), metal=0.9, rough=0.4)
qm.tube("Tailpipe", [P(0, 3185, 610), P(0, 3420, 600), P(0, 3760, 560)], radius=0.040, seg=16, material=inconel)
route("AirInlet", [P(0, 2918, 610), P(0, 2880, 690), P(0, 2700, 750)], r=0.045, kind="air", mats=mats)
# エアボックス：ドライバーの頭の上のロールフープの吸気口から、燃料タンクとエンジンの上を通ってターボへ（中空。形は推定）
f1.airbox("Airbox", mats=mats)
qm.orient(qm.ring("AirInlet_Flange", 0.058, 0.044, 0.010, seg=20, origin="center", material=titan), origin=P(0, 2702, 750),
          x_axis=(1, 0, 0), z_axis=(0, -1, 0.3))

# MGU-K：サバイバルセルの中（燃料タンクの後ろ、左下）に置き、隔壁を通る軸のギアで、クランクの前のギアから回す。
# 2026 年は MGU-K をサバイバルセルの中に置くという報道がある（規定の本文は確かめられなかった）。クランクが低いので、エンジンの横の下には置けない
steel_k = qm.material("F1_Steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
MG = P(-190, 0, CZ + 95)
MG.y = (YF + 12 - 199) * MM                            # ギア（MGU-K の前の端）がクランクのギアと同じ面に来るように
qm.orient(f1.mgu_k("MGUK", mats=mats), origin=MG, x_axis=(1, 0, 0), z_axis=(0, -1, 0))
# クランクのギア（60 歯）と MGU-K のギア（40 歯）の間にアイドラー（38 歯）。モジュール 2.5、中心はかみ合う距離の円の交点
rC, rI, rM = 2.5 * 60 / 2, 2.5 * 38 / 2, 2.5 * 40 / 2
C2, M2 = Vector((0, CZ)), Vector((MG.x / MM, MG.z / MM))
dd = (M2 - C2).length
aa = ((rC + rI) ** 2 - (rI + rM) ** 2 + dd ** 2) / (2 * dd)
hh = math.sqrt((rC + rI) ** 2 - aa ** 2)
u = (M2 - C2) / dd
I2 = C2 + u * aa + Vector((u.y, -u.x)) * hh             # 上側の交点
qm.orient(qm.gear("MGUK_Idler", 38, 2.5 * MM, 14 * MM, bore=10 * MM, material=steel_k), origin=P(I2.x, YF + 12, I2.y), x_axis=(1, 0, 0), z_axis=(0, 1, 0))
qm.cylinder("MGUK_IdlerShaft", 0.010, 0.040, seg=12, axis="Y", location=tuple(P(I2.x, YF + 19, I2.y)), material=steel_k)

# =========================================================== 冷却（左右のラジエーター、右のインタークーラー、左のオイルクーラー）
def cooler(name, s, center, length, height, tilt=15, thick=50):
    a = math.radians(tilt)
    x_ax = Vector((math.cos(a), 0, -s * math.sin(a)))
    z_ax = Vector((s * math.sin(a), 0, math.cos(a)))
    parts = f1.radiator(name, length * MM, height * MM, thick * MM, mats=mats)
    qm.orient(parts, origin=P(*center), x_axis=x_ax, z_axis=z_ax)
    def at(ly, lz):
        return P(*center) + Vector((0, ly * MM, 0)) + z_ax * (lz * MM)
    top_in = at(length / 2 + 17.5, height / 2 + 30)
    bot_out = at(-length / 2 - 17.5, -height / 2 - 30)
    hw = f1.tub_section(center[1])[0] / 2
    for k, dy in enumerate((-length * 0.3, length * 0.3)):
        qm.sweep(f"CoolerBracket_{name}{k + 1}", [P(s * (hw - 6), center[1] + dy, center[2]), P(s * (abs(center[0]) - 22), center[1] + dy, center[2])],
                 [(-0.006, -0.012), (0.006, -0.012), (0.006, 0.012), (-0.006, 0.012)], up=(0, 0, 1), material=titan)
    return top_in, bot_out

for s, tg in ((-1, "L"), (1, "R")):
    r_in, r_out = cooler(f"Radiator{tg}", s, (s * 505, 1700, 350), 500, 420, thick=65)     # サイドポッドの高さいっぱい
    wpc, wpo = f1.water_pump_point(s)                 # ブロックの横のウォーターポンプ（中心と外向き）
    wp = wpc + wpo * 25                               # 吸い口
    out = f1.v6_point(s, 300, -40, YF + 20)           # ヘッドの前の上の出口（前のカバーの上）
    route(f"WaterPipeHot{tg}", [out * MM, P(out.x + s * 30, YF + 20, out.z + 40), P(s * 330, YF + 15, 600), P(s * 480, 2150, 640), r_in + Vector((0, 0, 0.03)), r_in - Vector((0, 0, 0.012))],
            r=0.019, kind="water", mats=mats)
    route(f"WaterPipeCold{tg}", [r_out + Vector((0, 0, 0.012)), r_out - Vector((0, 0, 0.03)), r_out - Vector((s * 0.03, 0.03, 0.05)), P(s * 390, 1440, 70), P(s * 390, 2430, 110), P(s * 390, YF + 220, 140),
                                   P(s * 250, wp.y - 10, wp.z - 60), wp * MM + wpo * 0.012, wp * MM - wpo * 0.010], r=0.019, kind="water", mats=mats)

ic_in, ic_out = cooler("Intercooler", 1, (505, 2110, 345), 220, 360, thick=60)
th_y = min(y for _, _, y in f1.v6_cylinders()) - 55 - 40
route("ChargePipe1", [TC + Vector((0.115, -0.060, -0.045)), P(300, 2950, 600), P(430, 2500, 570), ic_in + Vector((0, 0, 0.04)), ic_in - Vector((0, 0, 0.012))],
        r=0.030, kind="air", mats=mats)
route("ChargePipe2", [ic_out + Vector((0, 0, 0.012)), ic_out - Vector((0, 0, 0.04)), P(455, YF + 20, 95), P(300, YF + 20, 400), P(120, YF + 22, 600),
                        P(0, YF + 25, 600), P(0, th_y + 15, CZ + 330)], r=0.030, kind="air", mats=mats)

oc_in, oc_out = cooler("OilCooler", -1, (-505, 2100, 330), 200, 300, thick=55)
route("OilLineFeed", [P(-120, 2330, 470), P(-330, 2330, 480), oc_in + Vector((0, 0, 0.04)), oc_in - Vector((0, 0, 0.012))], r=0.012, kind="oil", mats=mats)
route("OilLineReturn", [oc_out + Vector((0, 0, 0.012)), oc_out - Vector((0, 0, 0.05)), P(-445, 2300, 85), P(-200, 2440, 300), P(-100, 2400, 330)],
        r=0.012, kind="oil", mats=mats)

# 燃料・高電圧の配線
route("FuelLine", [P(250, 2200, 560), P(250, 2470, 590), P(60, YF + 25, 520), P(0, YF + 50, CZ + 200)], r=0.008, kind="fuel", mats=mats)
route("HVCableK", [P(-168, 2255, 123), P(-250, 2330, 150), P(-310, MG.y / MM + 80, MG.z / MM), MG + Vector((-0.098, 0.080, 0))], r=0.011, kind="hv", mats=mats)
route("HVCableCE", [P(168, 2255, 123), P(110, 2300, 150), P(66, 2330, 153)], r=0.011, kind="hv", mats=mats)

# =========================================================== 前の足まわり（左右）
CORNER = {}
D, TWF = f1.SPEC["front_tyre"]
for s, tg in ((-1, "FL"), (1, "FR")):
    C = Vector((s * (f1.SPEC["width"] - TWF) / 2, 0.0, D / 2))
    OUT = Vector((s, 0, 0))
    Mf = C + OUT * (TWF * 0.95 * 0.05)
    DC = Mf - OUT * 0.065
    U = DC - OUT * 0.055
    f1.tyre_and_wheel(f"Tyre_{tg}", True, location=tuple(C), wheel=False, mats=mats)
    qm.orient(f1.rim(f"Rim_{tg}", True, mats=mats), origin=Mf, x_axis=(0, 1, 0), z_axis=OUT)
    qm.orient(f1.hub_and_nut(f"Hub_{tg}", mats=mats), origin=Mf, x_axis=(0, 1, 0), z_axis=OUT)
    qm.orient(f1.brake_disc(f"Disc_{tg}", True, mats=mats), origin=DC, x_axis=(0, 1, 0), z_axis=OUT)
    cal_dir = Vector((0, 0.5, 0.866))
    qm.orient(f1.caliper(f"Caliper_{tg}", True, mats=mats), origin=DC, x_axis=cal_dir, z_axis=OUT)
    f1.brake_duct(f"BrakeDuct_{tg}", DC, OUT, cal_dir, front=True, mats=mats)
    upper, lower, steer = Vector((s * 0.70, 0.0, C.z + 0.165)), Vector((s * 0.72, 0.0, C.z - 0.165)), Vector((s * 0.70, -0.11, C.z + 0.01))
    f1.upright(f"Upright_{tg}", U, upper, lower, steer, axis=OUT, clevis=True, mats=mats)
    zoff, rc = f1.caliper_body_offset(True)
    cal_in = DC - OUT * zoff + cal_dir * rc
    CORNER[tg] = {"cal": cal_in, "lower": lower, "upper": upper, "mid": Mf - OUT * (TWF * 0.95 * 0.05)}
    qm.sweep(f"CaliperBracket_{tg}", [U + cal_dir * 0.06, cal_in], [(-0.010, -0.014), (0.010, -0.014), (0.010, 0.014), (-0.010, 0.014)],
             up=OUT, material=titan)
    f1.wishbone(f"LowerArm_{tg}", (s * 0.17, -0.20, 0.17), (s * 0.17, 0.22, 0.17), lower, mats=mats)
    f1.wishbone(f"UpperArm_{tg}", (s * 0.20, -0.18, 0.43), (s * 0.21, 0.20, 0.44), upper, mats=mats)
    f1.pushrod(f"Pushrod_{tg}", lower + Vector((-s * 0.07, 0.02, 0.03)), (s * 0.17, 0.05, 0.58), mats=mats)
    TOP = 0.505
    f1.rocker(f"Rocker_{tg}", (s * 0.12, 0.05, 0.56), [(s * 0.17, 0.05, 0.58), (s * 0.08, 0.05, 0.62)], normal=(0, 1, 0), clevis=True, mats=mats)
    qm.box(f"DamperMount_{tg}", (0.04, 0.04, 0.10), location=(s * 0.08, -0.27, TOP - 0.01), material=mats["carbon"])
    f1.damper(f"Damper_{tg}", (s * 0.08, -0.25, 0.60), (s * 0.08, 0.04, 0.62), mats=mats)
    f1.pushrod(f"TrackRod_{tg}", (s * 0.20, -0.11, 0.30), steer, mats=mats)

# =========================================================== 後ろ（ギアボックス・ドライブシャフト・足まわり・ブレーキ）
WB = 3400.0
TD, TWR = 710.0, 375.0
WX, WZ = (1900.0 - TWR) / 2, TD / 2
RIM_W = TWR * 0.95
f1.gearbox(y0=YGB * MM, length=660 * MM, mats=mats)
f1.crash_structure("RearCrash", y0=3560 * MM, length=400 * MM, mats=mats)

def mount(name, x, y, z, w=40, d=40, h=40):
    qm.box(name, (w * MM, d * MM, h * MM), origin="bottom", location=P(x, y, z), material=titan)

for side, tag in ((-1, "L"), (1, "R")):
    s = side
    C = P(s * WX, WB, WZ)
    OUT = Vector((s, 0, 0))
    M = C + OUT * (RIM_W * 0.05 * MM)
    DC = M - OUT * (65 * MM)
    U = DC - OUT * (55 * MM)
    f1.tyre_and_wheel(f"Tyre_R{tag}", False, location=tuple(C), wheel=False, mats=mats)
    qm.orient(f1.rim(f"Rim_R{tag}", False, mats=mats), origin=M, x_axis=(0, 1, 0), z_axis=OUT)
    qm.orient(f1.hub_and_nut(f"Hub_R{tag}", mats=mats), origin=M, x_axis=(0, 1, 0), z_axis=OUT)
    qm.orient(f1.brake_disc(f"Disc_R{tag}", False, mats=mats), origin=DC, x_axis=(0, 1, 0), z_axis=OUT)
    cal_dir = Vector((0, -0.5, 0.866))
    qm.orient(f1.caliper(f"Caliper_R{tag}", False, mats=mats), origin=DC, x_axis=cal_dir, z_axis=OUT)
    f1.brake_duct(f"BrakeDuct_R{tag}", DC, OUT, cal_dir, front=False, mats=mats)
    upper, lower, toe = P(s * 690, WB, WZ + 165), P(s * 700, WB, WZ - 160), P(s * 690, WB + 110, WZ + 5)
    f1.upright(f"Upright_R{tag}", U, upper, lower, toe, axis=OUT, clevis=True, mats=mats)
    zoff, rc = f1.caliper_body_offset(False)
    cal_in = DC - OUT * zoff + cal_dir * rc
    CORNER["R" + tag] = {"cal": cal_in, "lower": lower, "upper": upper, "mid": M - OUT * (RIM_W * 0.05 * MM)}
    qm.sweep(f"CaliperBracket_R{tag}", [U + cal_dir * (60 * MM), cal_in],
             [(-10 * MM, -14 * MM), (10 * MM, -14 * MM), (10 * MM, 14 * MM), (-10 * MM, 14 * MM)], up=OUT, material=titan)
    f1.driveshaft(f"Driveshaft_R{tag}", P(s * 150, WB, WZ), U + OUT * (25 * MM), mats=mats)
    f1.wishbone(f"LowerArm_R{tag}", P(s * 150, 3230, 140), P(s * 150, 3530, 160), lower, mats=mats)
    f1.wishbone(f"UpperArm_R{tag}", P(s * 150, 3240, 440), P(s * 150, 3500, 420), upper, mats=mats)
    f1.pushrod(f"ToeLink_R{tag}", P(s * 150, 3510, WZ + 5), toe, mats=mats)
    f1.pushrod(f"Pushrod_R{tag}", lower + Vector((-s * 70 * MM, 20 * MM, 35 * MM)), P(s * 110, 3330, 545), mats=mats)
    f1.rocker(f"Rocker_R{tag}", P(s * 70, 3330, 530), [P(s * 110, 3330, 545), P(s * 45, 3330, 585)], normal=(0, 1, 0), clevis=True, mats=mats)
    mount(f"DamperMount_R{tag}", s * 45, 3080, 465, h=110)
    f1.damper(f"Damper_R{tag}", P(s * 45, 3095, 580), P(s * 45, 3320, 590), mats=mats)

mount("ARBMount_L", -90, 3240, 480, h=25)
mount("ARBMount_R", 90, 3240, 480, h=25)
f1.anti_roll_bar("AntiRollBar", P(0, 3240, 515), 110 * MM, mats=mats)

# =========================================================== ギアボックスの中身（f1_gearbox_internals_mm.py と同じ配置）
AXLE_Z = 355.0
IN_Z, OUT_Z = AXLE_Z - 85.0, AXLE_Z                  # 入力軸 270・出力軸 355（デフは車軸の高さ）
CLUTCH_Z = CZ                                        # クラッチはクランクの高さ（基準面の 90mm 上）。段差のギアで入力軸へ上げる（推定）
Mg, GW = 2.5, 13.0
PAIRS = [(20, 48), (22, 46), (24, 44), (26, 42), (28, 40), (30, 38), (32, 36), (34, 34)]
steel = qm.material("F1_Steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
gear_mat = qm.material("F1_GearSteel", (0.70, 0.66, 0.58), metal=0.95, rough=0.25)

def place(parts, y, z, x=0.0):
    return qm.orient(parts, origin=P(x, y, z), x_axis=(1, 0, 0), z_axis=(0, 1, 0))

place(f1.clutch("Clutch", d=100 * MM, mats=mats), 2905, CLUTCH_Z)
# クラッチを切る、クラッチの軸のまわりの油圧のシリンダー（コンセントリック・スレーブシリンダー）とレリーズベアリング
place(qm.ring("ClutchSlave", 34 * MM, 20 * MM, 4 * MM, seg=32, material=mats["titanium"]), 2943.5, CLUTCH_Z)
place(qm.ring("ClutchSlave_ReleaseBearing", 28 * MM, 18 * MM, 2.5 * MM, seg=32, material=steel), 2941, CLUTCH_Z)
# クラッチの軸と、入力軸へ上げる段差のギア（58 歯 × 2、モジュール 2.5、軸間 145mm）。この仕組みは公表されていないので推定
place(qm.lathe("ClutchShaft", [(16 * MM, 0), (16 * MM, 90 * MM)], seg=16, material=steel), 2900, CLUTCH_Z)
place(qm.gear("DropGear_Clutch", 58, 2.5 * MM, GW * MM, bore=16 * MM, material=gear_mat), 2948, CLUTCH_Z)
place(qm.gear("DropGear_Input", 58, 2.5 * MM, GW * MM, bore=16 * MM, material=gear_mat), 2948, IN_Z)
place(qm.lathe("InputShaft", [(16 * MM, 0), (16 * MM, 354 * MM)], seg=16, material=steel), 2946, IN_Z)
place(qm.lathe("OutputShaft", [(18 * MM, 0), (18 * MM, 335 * MM)], seg=16, material=steel), 2975, OUT_Z)
Y0, BLOCK = 2995.0, 56.0
hub_ys = []
for b in range(4):
    yb = Y0 + b * BLOCK
    for k, ys in ((2 * b, yb), (2 * b + 1, yb + 35)):
        zi, zo = PAIRS[k]
        place(qm.gear(f"Gear{k + 1}_In", zi, Mg * MM, GW * MM, bore=16 * MM, material=gear_mat), ys, IN_Z)
        # 出力軸のギアは空転し（ドッグハブで選んだ段だけが軸に固定される）、軸との間にニードル軸受
        place(qm.gear(f"Gear{k + 1}_Out", zo, Mg * MM, GW * MM, bore=22 * MM, material=gear_mat), ys, OUT_Z)
        place(f1.needle_bearing(f"NeedleBrg{k + 1}", 18 * MM, 22 * MM, (GW - 1) * MM, mats=mats), ys + GW / 2, OUT_Z)
    hub_ys.append(yb + 24)
    place(f1.dog_hub(f"DogHub{b + 1}", r_in=18 * MM, r_out=32 * MM, width=16 * MM, mats=mats), yb + 24, OUT_Z)
BARREL_X, BARREL_Y0 = 75.0, 2990.0
place(f1.shift_barrel("ShiftBarrel", 225 * MM, 24 * MM, tracks=[(y - BARREL_Y0) * MM for y in hub_ys], mats=mats), BARREL_Y0, OUT_Z, BARREL_X)
for b, y in enumerate(hub_ys):
    place(f1.selector_fork(f"Fork{b + 1}", 32 * MM, (BARREL_X * MM, 0), mats=mats), y, OUT_Z)
# セレクターレール（フォークが前後に滑る棒。前後の軸受の壁の間に渡す）
qm.cylinder("SelectorRail", 0.005, (3253 - 2989) * MM, seg=16, axis="Y", location=tuple(P(44, (2989 + 3253) / 2, OUT_Z)), material=steel)
place(qm.gear("ReverseIdler", 18, Mg * MM, GW * MM, bore=8 * MM, material=gear_mat), 3222, (IN_Z + OUT_Z) / 2, 58)
place(qm.lathe("ReverseIdlerShaft", [(8 * MM, 0), (8 * MM, 30 * MM)], seg=12, material=steel), 3214, (IN_Z + OUT_Z) / 2, 58)
for nm, y, z, di, do, w in (("Brg_InFront", 2975, IN_Z, 32, 62, 14), ("Brg_InRear", 3288, IN_Z, 32, 62, 14), ("Brg_ClutchShaft", 2975, CLUTCH_Z, 32, 62, 14),
                            ("Brg_OutFront", 2982, OUT_Z, 36, 72, 14), ("Brg_OutRear", 3260, OUT_Z, 36, 72, 14)):
    place(qm.ball_bearing(nm, di * MM, do * MM, w * MM, balls=10, material=steel), y, z)
FD_M, ZP, ZC = 5.0, 12, 36
gp = math.degrees(math.atan(ZP / ZC))
rp_p, rp_c = FD_M * ZP / 2, FD_M * ZC / 2
place(qm.bevel_gear("BevelPinion", ZP, FD_M * MM, 25 * MM, gp, material=gear_mat), WB - rp_c, OUT_Z)
qm.orient(qm.bevel_gear("CrownWheel", ZC, FD_M * MM, 25 * MM, 90 - gp, material=gear_mat), origin=P(-rp_p, WB, AXLE_Z),
          x_axis=(0, 1, 0), z_axis=(1, 0, 0))
qm.orient(f1.differential("Diff", 60 * MM, 150 * MM, mats=mats), origin=P(0, WB, AXLE_Z), x_axis=(0, 1, 0), z_axis=(1, 0, 0))
for side in (-1, 1):
    qm.orient(qm.ball_bearing(f"Brg_Diff{'L' if side < 0 else 'R'}", 60 * MM, 100 * MM, 18 * MM, balls=12, material=steel),
              origin=P(side * 95, WB, AXLE_Z), x_axis=(0, 1, 0), z_axis=(1, 0, 0))


# =========================================================== 細かい部品
# ---- エンジンの中の動弁系・点火プラグ・インジェクターは、f1.v6_engine_real に含まれる

# ---- ホイールテザー（A アームの中を通す。本数は規定書で確かめられなかったので、上下のアームに 1 本ずつ）
for s, tg in ((-1, "FL"), (1, "FR")):
    f1.tether(f"Tether_{tg}U", (s * 0.20, -0.18, 0.43), CORNER[tg]["upper"], mats=mats)
    f1.tether(f"Tether_{tg}L", (s * 0.17, -0.20, 0.17), CORNER[tg]["lower"], mats=mats)
for s, tg in ((-1, "RL"), (1, "RR")):
    f1.tether(f"Tether_{tg}U", P(s * 150, 3240, 440), CORNER[tg]["upper"], mats=mats)
    f1.tether(f"Tether_{tg}L", P(s * 150, 3230, 140), CORNER[tg]["lower"], mats=mats)

# ---- ブレーキの配管（前の系統はマスターシリンダー 1 から前の左右へ、後ろの系統はマスターシリンダー 2 からブレーキバイワイヤの弁を通って後ろへ）
for s, tg in ((-1, "FL"), (1, "FR")):
    lo = CORNER[tg]["lower"]
    route(f"BrakeLine_{tg}", [P(-115, 440, 220), P(-115, 380, 150), P(s * 60, 100, 110), P(s * 160, -150, 170),
                                lo + Vector((-s * 0.06, -0.02, 0.04)), CORNER[tg]["cal"]], r=0.004, kind="brake", mats=mats)
f1.small_box("BBW", (-0.25, 2.37, 0.073), (0.08, 0.06, 0.05), color=(0.20, 0.22, 0.26), connectors=1, electronics=False, mats=mats)
route("BrakeLine_Rear", [P(-45, 440, 220), P(-45, 380, 150), P(-200, 800, 90), P(-250, 2300, 90), P(-250, 2380, 100)], r=0.004, kind="brake", mats=mats)
for s, tg in ((-1, "RL"), (1, "RR")):
    lo = CORNER[tg]["lower"]
    route(f"BrakeLine_{tg}", [P(-250, 2385, 100), P(s * 200, 2460, 100), P(s * 200, 3150, 100), P(s * 350, 3350, 170),
                                lo + Vector((-s * 0.06, 0.02, 0.04)), CORNER[tg]["cal"]], r=0.004, kind="brake", mats=mats)

# ---- 燃料を入れ・抜く口（左の横。レース中の給油はしない）
hw2100 = f1.tub_section(2100)[0] / 2
f1.coupling("FuelCoupling", P(-(hw2100 + 2), 2100, 480), axis=(-1, 0, 0), mats=mats)
route("FuelFillLine", [P(-(hw2100 - 4), 2100, 480), P(-(hw2100 - 20), 2100, 480), P(-300, 2100, 470)], r=0.012, kind="fuel", mats=mats)

# ---- 消火器の配管とノズル（コクピットの足もとと、エンジンの前へ）
EZ = 0.065 + 0.008 + 0.05
route("ExtLine_Cockpit", [P(0, 1320, EZ / MM), P(40, 1345, 100), P(150, 1200, 90), P(150, 700, 100), P(150, 660, 108)], r=0.004, kind="extinguisher", mats=mats)
f1.nozzle("ExtNozzle_Cockpit", P(150, 660, 108), (0, -1, 0.3), mats=mats)
route("ExtLine_Engine", [P(0, 1320, EZ / MM), P(-40, 1345, 100), P(-230, 1400, 90), P(-300, 1900, 90), P(-300, 2300, 90),
                           P(-300, 2490, 120), P(-215, YF + 25, 160)], r=0.004, kind="extinguisher", mats=mats)
f1.nozzle("ExtNozzle_Engine", P(-215, YF + 25, 160), (0.3, 1, 0.3), mats=mats)

# ---- ドリンクの装置、無線、事故データ記録装置
f1.drink_system("Drink", bag=(0.27, 1.50, 0.073), mats=mats)
f1.small_box("Radio", (0.25, 1.15, 0.073), (0.08, 0.10, 0.05), color=(0.18, 0.18, 0.20), connectors=2, mats=mats)
f1.small_box("ADR", (-0.25, 1.15, 0.073), (0.06, 0.08, 0.04), color=(0.75, 0.55, 0.05), connectors=1, mats=mats)

# ---- 前のアンチロールバーとヒーブダンパー（ロッカーの間。配置は推定）
deck90 = f1.tub_section(90)[1] * MM
f1.anti_roll_bar("FrontARB", (0, 0.09, deck90 + 0.010), 0.10, arm=0.07, mats=mats)
for s, tg in ((-1, "L"), (1, "R")):
    qm.box(f"FrontARB_Mount{tg}", (0.03, 0.03, 0.02), origin="bottom", location=(s * 0.06, 0.09, deck90 - 0.004), material=titan)
    qm.tube(f"ARBLink_F{tg}", [(s * 0.088, 0.09, deck90 + 0.010 + 0.068), (s * 0.11, 0.055, 0.585)], radius=0.005, seg=8, material=titan)
    qm.tube(f"HeaveLink_F{tg}", [(s * 0.07, 0.10, 0.63), (s * 0.085, 0.05, 0.618)], radius=0.005, seg=8, material=titan)
f1.damper("FrontHeave", (-0.07, 0.10, 0.63), (0.07, 0.10, 0.63), body_r=0.018, mats=mats)
f1.damper("RearHeave", P(-60, 3360, 600), P(60, 3360, 600), body_r=0.018, mats=mats)
for s, tg in ((-1, "L"), (1, "R")):
    qm.tube(f"HeaveLink_R{tg}", [P(s * 60, 3360, 600), P(s * 45, 3330, 585)], radius=0.005, seg=8, material=titan)

# ---- ウェイストゲートと、テールパイプへの管
f1.wastegate("Wastegate", (-0.170, 3.060, 0.592), mats=mats)
qm.tube("Wastegate_Pipe", [P(-150, 3070, 600), P(-80, 3250, 625), P(0, 3420, 612)], radius=0.018, seg=12, material=inconel)

# ---- 冷却水のヘッダータンク（後ろの上ぶたの上）と、ギアボックスのオイルクーラー
deck2380 = f1.tub_section(2380)[1] * MM
f1.header_tank("HeaderTank", (-0.20, 2.38, deck2380), mats=mats)
route("HeaderTankHose", [(-0.25, 2.40, deck2380 + 0.03), (-0.30, 2.45, deck2380 + 0.01), (-0.33, (YF + 15) * MM, 0.60)], r=0.008, kind="water", mats=mats)
gbc = f1.radiator("GearboxOilCooler", 0.16, 0.12, 0.04, mats=mats)
qm.orient(gbc, origin=P(-240, 3150, 260), x_axis=(1, 0, 0), z_axis=(0, 0, 1))
qm.sweep("GearboxOilCooler_Bracket", [P(-138, 3150, 260), P(-222, 3150, 260)], [(-0.006, -0.012), (0.006, -0.012), (0.006, 0.012), (-0.006, 0.012)],
         up=(0, 0, 1), material=titan)
route("GearboxOilLine1", [P(-240, 3247, 330), P(-200, 3262, 345), P(-120, 3262, 345)], r=0.006, kind="oil", mats=mats)
route("GearboxOilLine2", [P(-240, 3053, 190), P(-200, 3045, 185), P(-120, 3045, 235)], r=0.006, kind="oil", mats=mats)

# ---- 油圧系（エンジンの前のポンプ → アキュムレーター → ギアボックスの横の制御弁 → シフト・クラッチ、パワーステアリング）
f1.hydraulic_pump("HydPump", P(132, YF + 65, CZ + 40), axis=(1, 0, 0), mats=mats)      # エンジンの右の横（前の面は隔壁に付くため）
f1.accumulator("Accumulator", P(190, 2600, 160), P(190, 2780, 160), mats=mats)
f1.valve_block("ValveBlock", (-0.19, 3.00, 0.34), mats=mats)
route("HydLine_Pump", [P(160, YF + 65, CZ + 40), P(195, YF + 75, CZ + 45), P(190, 2590, 165), P(190, 2596, 160)], r=0.005, kind="hydraulic", mats=mats)
route("HydLine_Supply", [P(190, 2775, 160), P(230, 2860, 120), P(230, 2960, 120), P(-190, 2960, 120), P(-190, 3000, 345)], r=0.005, kind="hydraulic", mats=mats)
route("HydLine_Shift", [P(-150, 3010, 390), P(-60, 2965, 470), P(40, 2965, 360)], r=0.004, kind="hydraulic", mats=mats)
route("HydLine_Clutch", [P(-190, 2960, 360), P(-120, 2930, 250), P(-30, 2945, CLUTCH_Z + 20)], r=0.004, kind="hydraulic", mats=mats)
route("PowerSteeringLine", [P(-200, 3000, 345), P(-320, 2950, 110), P(-330, 2440, 100), P(-320, 1600, 130), P(-280, 1000, 130),
                              P(-150, 100, 170), P(-60, -110, 300)], r=0.005, kind="hydraulic", mats=mats)
f1.small_box("PowerSteering_Valve", (0.04, -0.15, 0.255), (0.05, 0.04, 0.045), color=(0.55, 0.56, 0.58), connectors=1, electronics=False, mats=mats)

# ---- 電装（ECU、配線の束）
f1.small_box("ECU", (-0.42, 1.15, 0.17), (0.12, 0.16, 0.06), color=(0.12, 0.12, 0.14), connectors=3, mats=mats)
hw1150 = f1.tub_section(1150)[0] / 2
qm.box("ECU_Bracket", ((0.36 - hw1150 * MM) + 0.01, 0.03, 0.02), origin="bottom",
       location=(-(hw1150 * MM + 0.36) / 2, 1.15, 0.19), material=titan)
route("Loom_Main", [P(-400, 1150, 220), P(-336, 1180, 300), P(-336, 1500, 400), P(-336, 2440, 400), P(-300, 2480, 470)], r=0.010, kind="loom", mats=mats)
t_top = f1.V6["deck"] + f1.V6["head"] + f1.V6["cover"]           # カムカバーの上面（クランク軸からの距離）
cov = [f1.v6_point(-1, t_top + 10, -45, y) for y in (2560, 2700, 2840)]
route("Loom_Engine", [P(-300, 2480, 470)] + [c * MM for c in cov], r=0.008, kind="loom", mats=mats)
route("Loom_Cockpit", [P(-400, 1150, 220), P(-300, 1080, 400), P(-150, 1060, 520), P(-20, 1050, 540)], r=0.008, kind="loom", mats=mats)

# ---- ノーズの衝撃吸収構造とピトー管、プランク、センサー
f1.nose_crash("NoseCrash", y0=-0.35, length=0.62, mats=mats)
f1.pitot("Pitot", tip=(0, -0.90, 0.33), mats=mats)
f1.plank("Plank", y0=0.30, y1=3.10, width=0.30, mats=mats)
for k, (y, z) in enumerate(((0.5, 0.065), (1.2, 0.065), (1.9, 0.065), (2.7, (CZ - 78) * MM), (3.05, 0.062))):
    qm.cylinder(f"Plank_Mount{k + 1}", 0.012, z - f1.EST["plank_z"] + 0.004, seg=12, location=(0, y, f1.EST["plank_z"] - 0.002), material=titan)
for s, tg in ((-1, "L"), (1, "R")):
    f1.ride_height_sensor(f"RideHeight_F{tg}", (s * 0.07, -0.25, 0.066), mats=mats)
    f1.ride_height_sensor(f"RideHeight_R{tg}", (s * 0.07, 3.15, 0.093), mats=mats)
tpms_m = qm.material("F1_TPMS", (0.85, 0.80, 0.15), metal=0.3, rough=0.4)
for tg in ("FL", "FR", "RL", "RR"):
    c = CORNER[tg]["mid"]
    qm.box(f"TPMS_{tg}", (0.030, 0.020, 0.012), origin="bottom", location=(c.x, c.y, c.z + 0.2236), material=tpms_m)
f1.small_box("IMU", (0, 1.845, 0.073), (0.05, 0.04, 0.03), color=(0.20, 0.35, 0.65), connectors=1, mats=mats)

# =========================================================== 残りの部品
# ---- 前のカバーの中のギア列（クランク → アイドラー 2 枚 → 頭の複合ギア → カム）と、MGU-K のギアのカバー
f1.v6_gear_train("GearTrain", mats=mats)
f1.gear_cover("Engine_GearCover", [(0, CZ * MM, 0.077), (I2.x * MM, I2.y * MM, 0.0495), (MG.x, MG.z, 0.052)],
              (YF + 5) * MM, (YF + 33) * MM, mats=mats)
# ---- 主軸受のメタルとオイルフィルターは、f1.v6_engine_real に含まれる

# ---- 戻りの配管（燃料の戻り、オイルのスカベンジ、エンジンへのオイル、デフの油圧）
rail_f = f1.v6_point(1, f1.V6["deck"] + 37, 104, [y for b, k_, y in f1.v6_cylinders() if b > 0][0] - 35)
route("FuelReturn", [rail_f * MM, P(60, YF + 30, CZ + 300), P(200, 2470, 605), P(200, 2220, 600)], r=0.006, kind="fuel", mats=mats)
route("OilLineScavenge", [P(150, 2575, CZ - 30), P(150, 2470, CZ - 15), P(100, 2430, 330), P(100, 2400, 335)], r=0.008, kind="oil", mats=mats)
route("OilLineFilter", [P(140, 2330, 420), P(160, 2350, 430), P(160, 2365, 445)], r=0.008, kind="oil", mats=mats)        # タンク → フィルター
route("OilLineEngine", [P(180, 2370, 450), P(205, 2480, 300), P(128, YF + 20, CZ + 20)], r=0.008, kind="oil", mats=mats)  # フィルター → エンジン
route("HydLine_Diff", [P(-190, 3020, 360), P(-120, 3300, 400), P(-50, WB, 360)], r=0.004, kind="hydraulic", mats=mats)

# ---- エネルギーストアと制御電子機器の冷却（右の前の小さなクーラー → ES → CE → クーラー）
es_in, es_out = cooler("ESCooler", 1, (440, 1370, 350), 80, 100)
route("ESCoolLine1", [es_out + Vector((0, 0, 0.012)), es_out - Vector((0, 0, 0.03)), P(330, 1400, 120), P(330, 1800, 100), P(220, 1890, 120)],
      r=0.006, kind="water", mats=mats)
route("ESCoolLine2", [P(200, 2235, 120), P(200, 2250, 140), P(200, 2275, 150)], r=0.006, kind="water", mats=mats)
route("ESCoolLine3", [P(205, 2410, 185), P(300, 2400, 120), P(335, 2200, 100), P(335, 1860, 100), P(335, 1500, 160), P(380, 1470, 300),
                      es_in + Vector((0, 0, 0.035)), es_in - Vector((0, 0, 0.012))], r=0.006, kind="water", mats=mats)

# ---- センサーの配線（ECU から車高センサー・ピトー管・慣性センサーへ。後ろの車高センサーとレインライトへ）
route("SensorWire_RHFL", [P(-400, 1150, 200), P(-300, 1050, 100), P(-100, 0, 80), P(-70, -240, 72)], r=0.003, kind="wire", mats=mats)
route("SensorWire_RHFR", [P(-100, 0, 80), P(0, -150, 76), P(70, -240, 72)], r=0.003, kind="wire", mats=mats)
route("SensorWire_Pitot", [P(-400, 1150, 220), P(-300, 1000, 450), P(-150, 0, 460), P(-50, -350, 420), P(0, -800, 340), P(0, -878, 333)],
      r=0.003, kind="wire", mats=mats)
route("SensorWire_IMU", [P(-400, 1150, 190), P(-300, 1250, 90), P(-250, 1750, 90), P(-20, 1845, 90)], r=0.003, kind="wire", mats=mats)
route("SensorWire_Rear", [P(-300, 2480, 470), P(-310, 2495, 120), P(-150, 2560, 70), P(-180, 2880, 80), P(-180, 3100, 100), P(-70, 3150, 90)],
      r=0.003, kind="wire", mats=mats)
route("SensorWire_RHRR", [P(-180, 3100, 100), P(0, 3120, 70), P(70, 3150, 90)], r=0.003, kind="wire", mats=mats)
route("SensorWire_Light", [P(0, 3120, 70), P(0, 3560, 170), P(0, 3940, 340), P(0, 3955, 355)], r=0.003, kind="wire", mats=mats)

# ---- テレメトリーのアンテナ、データロガー、レインライト
f1.antenna("Antenna", base=(0, 0.75, f1.tub_section(750)[1] * MM - 0.002), mats=mats)
f1.small_box("Logger", (0.42, 1.15, 0.17), (0.12, 0.16, 0.06), color=(0.12, 0.14, 0.18), connectors=3, mats=mats)
qm.box("Logger_Bracket", ((0.36 - hw1150 * MM) + 0.01, 0.03, 0.02), origin="bottom", location=((hw1150 * MM + 0.36) / 2, 1.15, 0.19), material=titan)
route("Loom_Logger", [P(400, 1150, 220), P(330, 1150, 300), P(150, 1100, 520), P(20, 1050, 540)], r=0.006, kind="loom", mats=mats)
f1.rain_light("RainLight", center=(0, 3.962, 0.355), size=(0.07, 0.016, 0.035), mats=mats)

# ---- ボルト（エンジンとギアボックスのフランジ、ノーズの取り付け）
k = 0
for x, z in f1.gearbox_flange_bolts():
    k += 1
    qm.orient(qm.bolt(f"Gearbox_Bolt{k}", "M10", 0.04, material=steel), origin=(x, (YGB + 22) * MM, z), x_axis=(1, 0, 0), z_axis=(0, 1, 0))
nz = f1.EST["plank_z"] + 0.03 + 0.005 + 0.355 / 2
for k, (x, z) in enumerate([(s * 0.143, nz + t * 0.10) for s in (-1, 1) for t in (-1, 1)]):
    qm.orient(qm.bolt(f"NoseCrash_Bolt{k + 1}", "M8", 0.03, material=steel), origin=(x, -0.362, z), x_axis=(1, 0, 0), z_axis=(0, -1, 0))

# =========================================================== 留め具（ボルト・ナット・座金・スペーサー・クレビス）
FX = f1.fasten
# ---- サスペンション：ロッドエンドはすべて二股の金具（クレビス）にボルト 1 本で留め、ボールの両側にスペーサー。
#      胴体側の金具はサバイバルセル・ギアボックスへボルト 2 本で留める（カーボンには金属のねじを埋める）
for tg in ("FL", "FR", "RL", "RR"):
    front = tg[0] == "F"
    body = ["Cell"] if front else ["Gearbox"]
    for arm in ("LowerArm", "UpperArm"):
        for e in ("F", "R"):
            FX.rod_end_joint(f"{arm}_{tg}_RodEnd{e}", host=body)
        FX.rod_end_joint(f"{arm}_{tg}_Outer", host=[f"Upright_{tg}_{'Upper' if arm == 'UpperArm' else 'Lower'}Arm"],
                         bolted=False, outward=True, length=0.022)
    FX.rod_end_joint(f"Pushrod_{tg}_RodEndA", host=[f"LowerArm_{tg}_Front", f"LowerArm_{tg}_Rear"], bolted=False)
    FX.rod_end_joint(f"Pushrod_{tg}_RodEndB", host=[f"Rocker_{tg}_Arm1"], bolted=False, outward=True, length=0.024)
    FX.rod_end_joint(f"Damper_{tg}_RodEndA", host=[f"DamperMount_{tg}"])
    FX.rod_end_joint(f"Damper_{tg}_RodEndB", host=[f"Rocker_{tg}_Arm2"], bolted=False, outward=True, length=0.024)
    link = "TrackRod" if front else "ToeLink"
    FX.rod_end_joint(f"{link}_{tg}_RodEndA", host=[f"Rack_Boot{tg[1]}"] if front else body, bolted=not front)
    FX.rod_end_joint(f"{link}_{tg}_RodEndB", host=[f"Upright_{tg}_SteerArm"], bolted=False, outward=True, length=0.022)
    # ロッカーの軸：ハブの針状ころ軸受を、二股の金具と軸のボルトで受ける（金具は胴体へボルト留め）
    rk = bpy.data.objects[f"Rocker_{tg}_Hub"]
    rc_ = sum((qm._mw(rk) @ v.co for v in rk.data.vertices), Vector()) / len(rk.data.vertices)
    FX.joint(f"Rocker_{tg}_Pivot", rc_, (0, 1, 0), 0.012 * 1.6 / 2, 0.020, "M10", host=body, out=(0, 0, -1), spacer=False)
for nm, hosts in (("FrontHeave", ["HeaveLink_FL", "HeaveLink_FR"]), ("RearHeave", ["HeaveLink_RL", "HeaveLink_RR"])):
    for e in ("A", "B"):
        FX.rod_end_joint(f"{nm}_RodEnd{e}", host=hosts, bolted=False)
# ダンパーの台・アンチロールバーの台を胴体へ（ボルト 2 本ずつ、上から）
for nm in ["DamperMount_FL", "DamperMount_FR", "FrontARB_MountL", "FrontARB_MountR"]:
    ob = bpy.data.objects[nm]
    lo_, hi_ = FX.bbox(nm)
    cx, cy = (lo_[0] + hi_[0]) / 2, (lo_[1] + hi_[1]) / 2
    for k, dy in enumerate((-1, 1)):
        q = Vector((cx, cy + dy * (hi_[1] - lo_[1]) * 0.3, lo_[2] + 0.008))
        FX.fasten(f"{nm}_Bolt{k + 1}", q, (0, 0, -1), 0.008 + 0.002, "M6", nut=False, washer=True, drill=("Cell",), insert=True)
for nm in ["DamperMount_RL", "DamperMount_RR", "ARBMount_L", "ARBMount_R"]:
    ob = bpy.data.objects[nm]
    lo_, hi_ = FX.bbox(nm)
    cx, cy = (lo_[0] + hi_[0]) / 2, (lo_[1] + hi_[1]) / 2
    for k, dy in enumerate((-1, 1)):
        FX.fasten(f"{nm}_Bolt{k + 1}", Vector((cx, cy + dy * (hi_[1] - lo_[1]) * 0.3, hi_[2])), (0, 0, -1), hi_[2] - lo_[2] + 0.002, "M6",
                  nut=False, washer=True, drill=("Gearbox",))

# ---- ブレーキとハブ：キャリパーを留めるボルト 2 本、ディスクのベルをハブのつばへ 6 本、ハブのつば
for tg in ("FL", "FR", "RL", "RR"):
    front = tg[0] == "F"
    D_, T_ = f1.BRAKE["front" if front else "rear"]
    s = -1 if tg[1] == "L" else 1
    OUT = Vector((s, 0, 0))
    disc = bpy.data.objects[f"Disc_{tg}"]
    DCw = qm._mw(disc).translation.copy()
    cal_dir = Vector((0, 0.5, 0.866)) if front else Vector((0, -0.5, 0.866))
    zoff, rc = f1.caliper_body_offset(front)
    tang = OUT.cross(cal_dir).normalized()
    q0 = DCw - OUT * (zoff + f1.CALIPER["w"] / 2) + cal_dir * rc
    lugb = qm.box(f"CaliperBracket_{tg}_Lug", (0.075, 0.024, 0.012), origin="center", material=titan)   # キャリパーの内側の面に当てる板
    lugb.matrix_world = FX.frame(q0 - OUT * 0.006, OUT, tang)
    for k, u in enumerate((-1, 1)):
        q = q0 + tang * u * 0.028
        FX.fasten(f"Caliper_{tg}_MountBolt{k + 1}", q - OUT * 0.012, OUT, 0.012 + f1.CALIPER["w"] * 0.6, "M10", nut=False, washer=True)
    fl = qm.ring(f"Hub_{tg}_DiscFlange", 0.062, 0.042, 0.008, seg=24, origin="bottom", material=titan)
    qm.orient(fl, origin=DCw - OUT * 0.011, x_axis=(0, 1, 0), z_axis=OUT)
    FX.bolt_circle(f"Disc_{tg}_BellBolt", DCw + OUT * 0.003, -OUT, 0.053, 6, 0.014, "M6", start=math.pi / 6, nut=True, washer=False,
                   x_axis=(0, 1, 0))

# ---- エンジン：前のカバー・ベッドプレート・ポンプ・吸排気のフランジ・ギア・フライホイールとクラッチ
V6 = f1.V6
HT = f1.HEAD_TOP                                   # ヘッドの上面（クランク軸から）
yb0e = YF + 40
# 前のカバーのふち（クランクケースの下半分と、左右のバンクの上まで。カバーの前の壁からブロックへ通す）
ring_pts = [(-122, CZ - 70), (122, CZ - 70)]
for bank in (1, -1):
    for t, u in ((60, -70), (HT + 40, -70), (HT + 40, 70)) if bank > 0 else ((HT + 40, 70), (HT + 40, -70), (60, -70)):
        q = f1.v6_point(bank, t, u, YF)
        ring_pts.append((q.x, q.z))
pts2 = FX.perimeter(FX.hull2d(ring_pts), 26, inset=6)
for k, q in enumerate(pts2):
    FX.fasten(f"Engine_FrontCoverBolt{k + 1}", (q.x * MM, (YF + 4) * MM, q.y * MM), (0, 1, 0), 0.036, "M6", nut=False, washer=False, mat="steel")
# ベッドプレートとブロック（下から。頭はベッドプレートの座ぐりの中）
for k, y in enumerate([yb0e + 25 + (YGB - 25 - yb0e - 25) * i / 6 for i in range(7)]):
    for j, x in enumerate((-118, 118)):
        FX.fasten(f"Engine_BedplateBolt{k + 1}{'ab'[j]}", P(x, y, CZ - 78 + 7), (0, 0, 1), 0.070, "M8", nut=False, washer=False, mat="steel")
# ウォーターポンプ（ブロックの横に、つばとボルト 3 本）
for bank, tg in ((-1, "L"), (1, "R")):
    wc, wo = f1.water_pump_point(bank)
    fl = qm.ring(f"Engine_WaterPump{tg}_Flange", 0.056, 0.030, 0.006, seg=32, origin="bottom", material=mats["titanium"])
    fl.matrix_world = FX.frame(wc * MM - wo * 0.020, wo, (0, 1, 0))
    FX.bolt_circle(f"Engine_WaterPump{tg}_Bolt", wc * MM - wo * 0.014, -wo, 0.050, 3, 0.006, "M6", start=math.pi / 6, x_axis=(0, 1, 0), mat="steel")
# スカベンジポンプ：前後のふた（ボルト 6 本ずつ）と、圧送の段（オイルを主軸受へ送るロータ。スカベンジの 3 段の後ろ）
sx, sz = 150, CZ - 30
for tg, y, ax in (("Front", yb0e + 20, (0, 1, 0)), ("Rear", YGB - 30, (0, -1, 0))):
    FX.bolt_circle(f"Engine_ScavengePump_{tg}Bolt", P(sx, y, sz), ax, 0.0235, 6, 0.008, "M4", x_axis=(1, 0, 0), mat="steel")
_mains, _yc = f1.v6_mains()
yp = (max(_yc) - 8 + 8 + (YGB - 36)) / 2 + 4
g = qm.gear("Engine_PressureRotor", 6, 0.006, 0.012, bore=0.004, material=steel)
qm.orient(g, origin=P(sx, yp, sz), x_axis=(1, 0, 0), z_axis=(0, 1, 0))
g2 = qm.ring("Engine_PressureRotor_Outer", 0.0205, 0.0175, 0.012, seg=32, material=steel)
qm.orient(g2, origin=P(sx, yp, sz), x_axis=(1, 0, 0), z_axis=(0, 1, 0))
# 燃料の高圧ポンプ（前のカバーにつばとボルト 3 本）
fl = qm.ring("Engine_FuelPumpHP_Flange", 0.032, 0.022, 0.006, seg=24, origin="bottom", material=steel)
fl.matrix_world = FX.frame(P(0, YF + 40, CZ + 200), (0, 1, 0))
FX.bolt_circle("Engine_FuelPumpHP_Bolt", P(0, YF + 46, CZ + 200), (0, -1, 0), 0.027, 3, 0.006 + 0.004, "M5", start=math.pi / 2, x_axis=(1, 0, 0), mat="steel")
# 吸気のポートのつば（2 本ずつ）と、スロットルのつば（4 本）
tc_ = V6["deck"] + V6["head"] * 0.5
for bank, i, y in f1.v6_cylinders():
    tg = f"{'L' if bank < 0 else 'R'}{i + 1}"
    port = f1.v6_point(bank, tc_, V6["head_w"] / 2 - 3, y) * MM
    up = (Vector((-bank * 0.707, 0, 0.707)) + Vector((0, 0, 1))).normalized()
    m_ = FX.frame(port + up * 0.002, up, (0, 1, 0))
    for j, (a, b) in enumerate(((0.020, 0.020), (-0.020, -0.020))):
        FX.fasten(f"Intake_PortFlange{tg}_Bolt{j + 1}", m_ @ Vector((a, b, 0.004)), -up, 0.008, "M6", nut=False, washer=False, mat="steel")
    # 排気のつば：スタッド 2 本とナット
    portx = f1.v6_point(bank, tc_, -(V6["head_w"] / 2 - 3), y) * MM
    outx = (f1.v6_point(bank, tc_, -1000, y) - f1.v6_point(bank, tc_, 0, y)).normalized()
    mx = FX.frame(portx, outx, (0, 1, 0))
    for j, (a, b) in enumerate(((0.018, 0.018), (-0.018, -0.018))):
        FX.stud_nut(f"Exhaust_Flange{tg}_Stud{j + 1}", mx @ Vector((a, b, -0.004)), outx, 0.008, "M8", mat="steel")
ys_all = [y for _, _, y in f1.v6_cylinders()]
ty0 = min(ys_all) - 55
FX.bolt_circle("Intake_Throttle_Bolt", P(0, ty0 - 18 - 22.5, CZ + 330), (0, 1, 0), 0.040, 4, 0.045, "M5", start=math.pi / 4, x_axis=(1, 0, 0), mat="steel")
# 燃料レールの台（2 個ずつ、ボルト 1 本）
for bank, tg in ((-1, "L"), (1, "R")):
    ysb = [y for b, i, y in f1.v6_cylinders() if b == bank]
    d_, inner_ = f1.v6_frame(bank)
    for j, y in enumerate((ysb[0] + 20, ysb[-1] - 20)):
        q = f1.v6_point(bank, V6["deck"] + 37, 104, y) * MM
        down = -d_
        bk = qm.box(f"FuelRail_{tg}_Bracket{j + 1}", (0.016, 0.012, 0.026), origin="center", material=steel)
        bk.matrix_world = FX.frame(q + down * 0.018, down, (0, 1, 0))
        FX.fasten(f"FuelRail_{tg}_Bracket{j + 1}Bolt", q + down * 0.008 + inner_ * 0.0, down, 0.026, "M5", nut=False, washer=True, mat="steel")
# ギア：カムのギア（3 本ずつ）、アイドラーの軸、クランクの前の端
for nm in ("Cam_LInGear", "Cam_LExGear", "Cam_RInGear", "Cam_RExGear"):
    lo_, hi_ = FX.bbox(nm)
    c_ = (lo_ + hi_) / 2
    FX.bolt_circle(f"{nm}_Bolt", Vector((c_.x, lo_.y, c_.z)), (0, 1, 0), 0.010, 3, hi_.y - lo_.y, "M5", x_axis=(1, 0, 0), mat="steel")
for nm in [o.name for o in bpy.context.scene.objects if o.name.startswith("GearTrain_") and o.name.endswith("Shaft")] + ["MGUK_IdlerShaft"]:
    lo_, hi_ = FX.bbox(nm)
    c_ = (lo_ + hi_) / 2
    FX.fasten(f"{nm}_Bolt", Vector((c_.x, lo_.y, c_.z)), (0, 1, 0), 0.010, "M6", nut=False, washer=True, mat="steel")
lo_, hi_ = FX.bbox("Crank_Shaft")
FX.fasten("Crank_NoseBolt", Vector((0, lo_.y, CZ * MM)), (0, 1, 0), 0.012, "M12", nut=False, washer=True, mat="steel")
# フライホイールをクランクの後ろの端へ（6 本）、クラッチのバスケットをフライホイールへ（6 本）
lo_, hi_ = FX.bbox("Clutch_Flywheel")
FX.bolt_circle("Clutch_FlywheelBolt", Vector((0, hi_.y, CZ * MM)), (0, -1, 0), 0.018, 6, hi_.y - lo_.y, "M8", x_axis=(1, 0, 0), mat="steel")
lo_b, hi_b = FX.bbox("Clutch_Basket")
FX.bolt_circle("Clutch_BasketBolt", Vector((0, lo_b.y, CZ * MM)), (0, -1, 0), (hi_b.x - lo_b.x) / 2 * 0.86, 6, 0.006, "M5",
               start=math.pi / 6, x_axis=(1, 0, 0), mat="steel", nut=False)
# MGU-K：前の端のつばを、後ろの隔壁へボルト 6 本で留める
mgf = qm.ring("MGUK_MountFlange", 0.092, 0.062, 0.006, seg=32, origin="bottom", material=titan)
mgf.matrix_world = FX.frame(MG + Vector((0, 0.175 - 0.002, 0)), (0, 1, 0), (1, 0, 0))
FX.bolt_circle("MGUK_MountBolt", MG + Vector((0, 0.175 - 0.002, 0)), (0, 1, 0), 0.084, 6, 0.006 + 0.010, "M6", start=math.pi / 6,
               x_axis=(1, 0, 0), nut=False, washer=True, drill=("Cell_RearBulkhead",))
FX.reserve("Cell_RearBulkhead", MG + Vector((0, 0.15, 0)), MG + Vector((0, 0.23, 0)), 0.016)     # 軸が隔壁を通る穴
# ギアのカバー（MGU-K とクランクのギア）：ふちにボルト
circ = [(0, CZ * MM, 0.077 + 0.008), (I2.x * MM, I2.y * MM, 0.0495 + 0.008), (MG.x, MG.z, 0.052 + 0.008)]
hp = FX.hull2d([(x + r * math.cos(2 * math.pi * k / 48), z + r * math.sin(2 * math.pi * k / 48)) for x, z, r in circ for k in range(48)])
for k, q in enumerate(FX.perimeter(hp, 16, inset=0.005)):
    FX.fasten(f"Engine_GearCoverBolt{k + 1}", (q.x, (YF + 33) * MM, q.y), (0, -1, 0), 0.008, "M5", nut=False, washer=False, mat="steel")
# ターボ：V バンド（タービンの入口 2・コンプレッサーの出口・タービンの出口）と、台のボルト
def turbo_w(x, y, z):                       # ターボの局所座標 → 車（x はそのまま、局所の z が車の +Y、局所の y が車の -Z）
    return TC + Vector((x, z, -y))
FX.vband("Turbo_VbandInL", turbo_w(-0.120, 0, 0.060), (1, 0, 0), 0.030)
FX.vband("Turbo_VbandInR", turbo_w(0.120, 0, 0.060), (1, 0, 0), 0.030)
FX.vband("Turbo_VbandComp", turbo_w(0.118, 0.045, -0.060), (1, 0, 0), 0.034)
FX.vband("Turbo_VbandOut", turbo_w(0, 0, 0.138), (0, 1, 0), 0.050)
for k, dx in enumerate((-0.012, 0.012)):
    FX.fasten(f"Turbo_Bracket_BoltLow{k + 1}", Vector((dx, 3.06, 0.455 + 0.012)), (0, 0, -1), 0.012, "M6", nut=False, washer=True, drill=("Gearbox",))
# 後ろの衝撃吸収構造をギアボックスへ（4 本）。ギアボックスの抜き・入れの栓
lo_, hi_ = FX.bbox("RearCrash")
cy0 = lo_.y
cc = (lo_ + hi_) / 2
for k, (u, v) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1))):
    q = Vector((cc.x + u * (hi_.x - lo_.x) * 0.3, cy0 + 0.012, cc.z + v * (hi_.z - lo_.z) * 0.3))
    FX.fasten(f"RearCrash_Bolt{k + 1}", q, (0, -1, 0), 0.012 + 0.006, "M8", nut=False, washer=True, drill=("Gearbox",))
for nm, start, d_ in (("Gearbox_DrainPlug", Vector((0, 3.25, 0.05)), Vector((0, 0, 1))), ("Gearbox_FillPlug", Vector((0.30, 3.15, 0.33)), Vector((-1, 0, 0)))):
    hit = FX.ray(start, d_, ["Gearbox"], far=0.5)
    if hit:
        FX.fasten(nm, hit[0], d_, 0.008, "M12", nut=False, washer=True, mat="steel")
# ギアボックスのオイルポンプ（ケースの左の横、オイルクーラーの戻りの近く。形と位置は推定）
hit = FX.ray(Vector((-0.40, 3.10, 0.24)), (1, 0, 0), ["Gearbox"], far=0.6)
if hit:
    gpc = hit[0] + Vector((-0.024, 0, 0))
    qm.cylinder("Gearbox_OilPump", 0.024, 0.050, seg=24, axis="Y", location=tuple(gpc), material=mats["titanium"])
    qm.cylinder("Gearbox_OilPump_Drive", 0.008, 0.020, seg=12, axis="X", location=tuple(gpc + Vector((0.020, 0, 0))), material=steel)
    for k, dy in enumerate((-0.018, 0.018)):
        FX.fasten(f"Gearbox_OilPump_Bolt{k + 1}", gpc + Vector((-0.024, dy, 0.016)), (1, 0, 0), 0.010, "M5", nut=False, washer=True, drill=("Gearbox",))

# ---- 冷却器の台（サバイバルセルの側と冷却器の側に 1 本ずつ）
for o in [o.name for o in bpy.context.scene.objects if o.name.startswith("CoolerBracket_") or o.name == "GearboxOilCooler_Bracket"]:
    lo_, hi_ = FX.bbox(o)
    c_ = (lo_ + hi_) / 2
    for j, x in enumerate((lo_.x + 0.010, hi_.x - 0.010)):
        FX.fasten(f"{o}_Bolt{j + 1}", Vector((x, c_.y, hi_.z)), (0, 0, -1), hi_.z - lo_.z, "M6", nut=True, washer=True)

# ---- 油圧・潤滑の足りなかった管：ターボの軸受へのオイル（行きと戻り）、カムカバーからオイルタンクへのブリーザー
route("TurboOilFeed", [P(205, 2480, 300), P(230, 2700, 480), P(150, 2950, 660), P(20, 3050, 670), TC + Vector((0, -0.010, 0.048))], r=0.004, kind="oil", mats=mats)
route("TurboOilDrain", [TC + Vector((0, 0.010, -0.048)), P(0, 3070, 545), P(-60, 2980, 470), P(-150, 2890, CZ - 10), P(-150, 2870, CZ - 30)], r=0.007, kind="oil", mats=mats)
for bank, tg in ((-1, "L"), (1, "R")):
    q = f1.v6_point(bank, HT + 52, -40, 2560) * MM
    route(f"Breather{tg}", [q, q + Vector((0, -0.02, 0.02)), P(bank * 60, 2420, 640), P(70, (2.25 + 2.49) / 2 / MM, 600)], r=0.006, kind="oil", mats=mats)

# ---- サバイバルセル・コクピットの留め具
def bolt_down(name, n=4, host=("Cell",), size="M5", inset=0.2, from_top=True, extra=0.004, insert=True):
    """箱の形の部品を、上の面の隅から下の部品へボルトで留める（n = 2 か 4）"""
    lo_, hi_ = FX.bbox(name)
    xs = [lo_.x + (hi_.x - lo_.x) * inset, hi_.x - (hi_.x - lo_.x) * inset]
    ys = [lo_.y + (hi_.y - lo_.y) * inset, hi_.y - (hi_.y - lo_.y) * inset]
    pts = [(x, y) for x in xs for y in ys] if n == 4 else [(xs[0], ys[0]), (xs[1], ys[1])]
    for k, (x, y) in enumerate(pts):
        FX.fasten(f"{name}_Bolt{k + 1}", Vector((x, y, hi_.z)), (0, 0, -1), hi_.z - lo_.z + extra, size, nut=False, washer=True,
                  drill=host, insert=insert)
# 箱物（床に留める）
for nm in ("Radio", "ADR", "IMU", "BBW", "CE", "PedalBox_Base"):
    bolt_down(nm, 4)
for nm in ("ECU_Bracket", "Logger_Bracket", "Column_Bracket"):
    bolt_down(nm, 2, size="M6")
bolt_down("ValveBlock", 4, host=("Gearbox",), size="M6", insert=False)
bolt_down("HeaderTank", 2, size="M5")
# ペダルボックスの前の板（床の板へ下から 3 本）、ステアリングラック（2 本の帯で前の隔壁の上に。帯 1 つにボルト 2 本）
for k, x in enumerate((-0.08, 0.0, 0.08)):
    FX.fasten(f"PedalBox_Front_Bolt{k + 1}", Vector((x, 0.425, 0.071)), (0, 0, 1), 0.020, "M5", nut=False, washer=False)
for j, x in enumerate((-0.07, 0.07)):
    band = qm.ring(f"Rack_Clamp{j + 1}", 0.026, 0.022, 0.016, seg=24, origin="center", material=titan)
    band.matrix_world = FX.frame(RACK + Vector((x, 0, 0)), (1, 0, 0), (0, 1, 0))
    foot = qm.box(f"Rack_Clamp{j + 1}_Foot", (0.016, 0.060, 0.006), origin="center", material=titan)
    foot.matrix_world = FX.frame(RACK + Vector((x, 0, -0.026)), (0, 0, 1))
    for k, dy in enumerate((-0.022, 0.022)):
        FX.fasten(f"Rack_Clamp{j + 1}_Bolt{k + 1}", RACK + Vector((x, dy, -0.023)), (0, 0, -1), 0.006 + 0.010, "M6", nut=False, washer=True,
                  drill=("Cell",), insert=True)
# 消火器のバンド（両端をボルトで床へ）
for k in (1, 2):
    lo_, hi_ = FX.bbox(f"Extinguisher_Strap{k}")
    for j, x in enumerate((lo_.x + 0.003, hi_.x - 0.003)):
        FX.fasten(f"Extinguisher_Strap{k}_Bolt{j + 1}", Vector((x, (lo_.y + hi_.y) / 2, lo_.z + 0.010)), (0, 0, -1), 0.010, "M5", nut=False,
                  washer=True, drill=("Cell",), insert=True)
# シート（2 本で留める。シートは運転者を乗せたまま外せる）と、シートベルトの取り付け（6 本）
for k, (x, y, z) in enumerate(((0.0, 1.32, 0.080), (0.0, 1.78, 0.38))):
    FX.fasten(f"Seat_Bolt{k + 1}", Vector((x, y, z + 0.006)), (0, 0, -1) if k == 0 else (0, 1, 0), 0.012, "M8", nut=False, washer=True,
              drill=("Cell",), insert=True)
for nm in ("Harness_ShoulderL", "Harness_ShoulderR", "Harness_LapL", "Harness_LapR", "Harness_CrotchL", "Harness_CrotchR"):
    lo_, hi_ = FX.bbox(nm)
    if "Shoulder" in nm:
        q, ax = Vector(((lo_.x + hi_.x) / 2, hi_.y, hi_.z - 0.02)), (0, 1, 0)
    elif "Lap" in nm:
        q, ax = Vector((lo_.x if nm.endswith("L") else hi_.x, (lo_.y + hi_.y) / 2, lo_.z + 0.01)), (-1, 0, 0) if nm.endswith("L") else (1, 0, 0)
    else:
        q, ax = Vector(((lo_.x + hi_.x) / 2, (lo_.y + hi_.y) / 2, lo_.z + 0.006)), (0, 0, -1)
    FX.fasten(f"{nm}_Anchor", q, ax, 0.010, "M8", nut=False, washer=True, drill=("Cell",), insert=True)
# ロールフープ（左右の足を 3 本ずつ）、ヘイロー（後ろの台 2 つを 4 本ずつ、前の柱を 3 本）
lo_, hi_ = FX.bbox("RollHoop")
for s_, tg in ((-1, "L"), (1, "R")):
    for k, dy in enumerate((-0.022, 0.0, 0.022)):
        FX.fasten(f"RollHoop_{tg}Bolt{k + 1}", Vector((s_ * (hi_.x - 0.020), (lo_.y + hi_.y) / 2 + dy, lo_.z + 0.012)), (0, 0, -1), 0.020, "M8",
                  nut=False, washer=True, drill=("Cell",), insert=True)
for tg in ("L", "R"):
    lo_, hi_ = FX.bbox(f"Halo_Mount{tg}")
    for k, (u, v) in enumerate(((0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75))):
        FX.fasten(f"Halo_Mount{tg}_Bolt{k + 1}", Vector((lo_.x + (hi_.x - lo_.x) * u, lo_.y + (hi_.y - lo_.y) * v, hi_.z)), (0, 0, -1),
                  hi_.z - lo_.z + 0.010, "M10", nut=False, washer=True, drill=("Cell",), insert=True)
lo_, hi_ = FX.bbox("Halo_Pillar")
for k, dy in enumerate((-0.030, 0.0, 0.030)):
    FX.fasten(f"Halo_Pillar_Bolt{k + 1}", Vector((0.0, (lo_.y + hi_.y) / 2 + dy, lo_.z + 0.010)), (0, 0, -1), 0.020, "M8", nut=False, washer=True,
              drill=("Cell",), insert=True)
# 側面衝撃吸収構造（根元のつばを 4 本ずつ）
for nm in ("SideImpactUpperL", "SideImpactLowerL", "SideImpactUpperR", "SideImpactLowerR"):
    lo_, hi_ = FX.bbox(nm)
    s_ = -1 if nm.endswith("L") else 1
    xr = hi_.x if s_ < 0 else lo_.x
    fl = qm.box(f"{nm}_Flange", (0.006, 0.110, 0.080), origin="center", location=(xr - s_ * 0.003, (lo_.y + hi_.y) / 2, (lo_.z + hi_.z) / 2),
                material=mats["carbon"])
    for k, (dy, dz) in enumerate(((-0.042, -0.030), (0.042, -0.030), (-0.042, 0.030), (0.042, 0.030))):
        FX.fasten(f"{nm}_Bolt{k + 1}", Vector((xr - s_ * 0.006, (lo_.y + hi_.y) / 2 + dy, (lo_.z + hi_.z) / 2 + dz)), (-s_, 0, 0), 0.006 + 0.008,
                  "M6", nut=False, washer=True, drill=("Cell",), insert=True)
# 燃料タンクの点検ふた（8 本）
lo_, hi_ = FX.bbox("FuelCell_Hatch")
FX.bolt_circle("FuelCell_HatchBolt", Vector(((lo_.x + hi_.x) / 2, (lo_.y + hi_.y) / 2, hi_.z)), (0, 0, -1), 0.060, 8, 0.012, "M4")
# プランクのチタンのスキッド（4 本ずつ、下から）と、プランクの柱（上で 1 本ずつ）
for k in range(1, 5):
    lo_, hi_ = FX.bbox(f"Plank_Skid{k}")
    for j, (u, v) in enumerate(((0.2, 0.2), (0.8, 0.2), (0.2, 0.8), (0.8, 0.8))):
        FX.fasten(f"Plank_Skid{k}_Bolt{j + 1}", Vector((lo_.x + (hi_.x - lo_.x) * u, lo_.y + (hi_.y - lo_.y) * v, lo_.z + 0.003)), (0, 0, 1),
                  0.007, "M5", nut=False, washer=False)
for k in range(1, 6):
    lo_, hi_ = FX.bbox(f"Plank_Mount{k}")
    FX.fasten(f"Plank_Mount{k}_Bolt", Vector(((lo_.x + hi_.x) / 2, (lo_.y + hi_.y) / 2, 0.025 + 0.004)), (0, 0, 1), 0.010 + 0.010, "M8",
              nut=False, washer=False)
# ホイールテザーの端（車体側とアップライト側に 1 本ずつ）
for o in [o.name for o in bpy.context.scene.objects if o.name.startswith("Tether_") and "_End" in o.name]:
    lo_, hi_ = FX.bbox(o)
    FX.fasten(f"{o}_Bolt", Vector(((lo_.x + hi_.x) / 2, (lo_.y + hi_.y) / 2, hi_.z)), (0, 0, -1), hi_.z - lo_.z, "M6", nut=True, washer=True)
# 小物：アンテナの台・ピトー管の台・レインライト・アキュムレーターの帯・油圧ポンプ・ウェイストゲート
for nm, n_, host in (("Antenna_Base", 2, ("Cell",)), ("Pitot_Base", 2, ("NoseCrash",))):
    bolt_down(nm, n_, host=host, size="M4", insert=False)
lo_, hi_ = FX.bbox("RainLight_Housing")
for k, x in enumerate((lo_.x + 0.008, hi_.x - 0.008)):
    FX.fasten(f"RainLight_Bolt{k + 1}", Vector((x, hi_.y, (lo_.z + hi_.z) / 2)), (0, -1, 0), hi_.y - lo_.y + 0.006, "M4", nut=False, washer=False)
lo_, hi_ = FX.bbox("Accumulator")
for k, y in enumerate((lo_.y + 0.04, hi_.y - 0.04)):
    band = qm.ring(f"Accumulator_Strap{k + 1}", (hi_.z - lo_.z) / 2 + 0.003, (hi_.z - lo_.z) / 2, 0.012, seg=24, origin="center", material=titan)
    band.matrix_world = FX.frame(Vector(((lo_.x + hi_.x) / 2, y, (lo_.z + hi_.z) / 2)), (0, 1, 0), (1, 0, 0))
    FX.fasten(f"Accumulator_Strap{k + 1}_Bolt", Vector(((lo_.x + hi_.x) / 2, y, lo_.z - 0.003)), (0, 0, -1), 0.012, "M5", nut=False, washer=True)
lo_, hi_ = FX.bbox("HydPump")
FX.bolt_circle("HydPump_Bolt", Vector((lo_.x, (lo_.y + hi_.y) / 2, (lo_.z + hi_.z) / 2)), (-1, 0, 0), 0.022, 3, 0.010, "M5", x_axis=(0, 1, 0))
FX.vband("Wastegate_Vband", Vector((-0.170, 3.060, 0.584)), (0, 0, 1), 0.026)

# ---- FIA が求める装置（位置は規定の古い版・報道による。2026 年の本文では未確認）
# 衝撃の警告灯：サバイバルセルの上、コクピットの開口の前の中心線の近くに上向き
dz_ = f1.tub_section(1000)[1] * MM
qm.cylinder("MedicalLight", 0.012, 0.010, seg=16, location=(0.06, 1.00, dz_ - 0.004), material=qm.material("F1_MedLight", (0.2, 0.4, 0.95), rough=0.2))
qm.cylinder("MedicalLight_Base", 0.016, 0.004, seg=16, location=(0.06, 1.00, dz_ - 0.006), material=mats["carbon"])
# 運転者を写す高速度カメラ（コクピットの前、アンテナの後ろ。運転者の方を向く）
qm.box("HighSpeedCamera", (0.030, 0.050, 0.025), origin="bottom", location=(-0.05, 0.93, f1.tub_section(930)[1] * MM - 0.002), material=mats["carbon"])
qm.cylinder("HighSpeedCamera_Lens", 0.008, 0.010, seg=16, axis="Y", location=(-0.05, 0.96, f1.tub_section(930)[1] * MM + 0.012),
            material=qm.material("F1_Lens", (0.05, 0.05, 0.08), metal=0.2, rough=0.1))
# ロールフープの、電気の状態を示すランプ（ERS の状態。左右）と、上のテレビカメラの台（T カメラ）
lo_, hi_ = FX.bbox("RollHoop")
for s_, tg in ((-1, "L"), (1, "R")):
    qm.box(f"RollHoop_ERSLight{tg}", (0.020, 0.010, 0.030), origin="center", location=(s_ * 0.060, lo_.y - 0.004, hi_.z - 0.060),
           material=qm.material("F1_ERSLight", (0.1, 0.8, 0.2), rough=0.2))
qm.box("RollHoop_TCam", (0.060, 0.090, 0.030), origin="bottom", location=(0, (lo_.y + hi_.y) / 2, hi_.z - 0.002), material=mats["carbon"])
# 外からの非常スイッチ（電源を切る・消火器を作動させる。ロールフープの近く）と、コクピットの電源スイッチ
for k, (nm, x) in enumerate((("MasterSwitch_External", -0.10), ("Extinguisher_ExternalButton", 0.10))):
    qm.cylinder(nm, 0.012, 0.012, seg=16, axis="Y", location=(x, lo_.y - 0.006, lo_.z + 0.030),
                material=qm.material("F1_Switch", (0.9, 0.75, 0.1) if k else (0.9, 0.1, 0.1), rough=0.3))
qm.box("MasterSwitch_Cockpit", (0.020, 0.012, 0.020), origin="center", location=(0.12, 1.06, f1.tub_section(1060)[1] * MM - 0.04), material=mats["carbon"])
# タイミングのトランスポンダー（ノーズの下の床。位置は推定）
qm.box("Transponder", (0.040, 0.060, 0.015), origin="bottom", location=(0.0, 0.10, f1.EST["plank_z"] + 0.03 - 0.016), material=qm.material("F1_Transponder", (0.9, 0.85, 0.1), rough=0.4))
bolt_down("Transponder", 2, size="M4", insert=False)
# コクピットの側のパッド（膝の横。規定で決まったエネルギー吸収材）とシートを引き上げるベルト
for s_, tg in ((-1, "L"), (1, "R")):
    hw = f1.tub_section(1300)[0] / 2 * MM
    qm.box(f"CockpitPad{tg}", (0.030, 0.40, 0.12), origin="bottom", location=(s_ * (hw - 0.025), 1.25, 0.25),
           material=qm.material("F1_Padding", (0.15, 0.15, 0.17), metal=0.0, rough=0.9))
    qm.tube(f"Seat_LiftStrap{tg}", [(s_ * 0.12, 1.70, 0.40), (s_ * 0.13, 1.72, 0.47), (s_ * 0.12, 1.74, 0.50)], radius=0.004, seg=8,
            material=qm.material("F1_Belt", (0.85, 0.15, 0.1), metal=0.0, rough=0.8))

# ---- 配線の束の枝とセンサー（センサーごとにコネクターと細い線で束へつなぐ。センサーの種類は実車にあるもの、位置は推定）
LOOMS = {}
def loom(name, pts, r=0.007):
    LOOMS[name] = [Vector(q) for q in pts]
    route(name, pts, r=r, kind="loom", mats=mats)
cov_r = [f1.v6_point(1, t_top + 10, -45, y) * MM for y in (2560, 2700, 2840)]
cov_l = [c * MM for c in cov]
LOOMS["Loom_Main"] = [P(-400, 1150, 220), P(-336, 1180, 300), P(-336, 1500, 400), P(-336, 2440, 400), P(-300, 2480, 470)]
LOOMS["Loom_Engine"] = [P(-300, 2480, 470)] + cov_l
LOOMS["Loom_Cockpit"] = [P(-400, 1150, 220), P(-300, 1080, 400), P(-150, 1060, 520), P(-20, 1050, 540)]
LOOMS["SensorWire_RHFL"] = [P(-400, 1150, 200), P(-300, 1050, 100), P(-100, 0, 80), P(-70, -240, 72)]
loom("Loom_EngineR", [P(-300, 2480, 470), P(-120, 2492, 600), P(120, 2492, 600)] + cov_r, r=0.006)
loom("Loom_EngineLow", [P(-300, 2480, 470), P(-335, 2520, 260), P(-335, 2700, 200), P(-260, 2880, 160)], r=0.006)
loom("Loom_Gearbox", [cov_l[-1], P(-150, 2900, 470), P(-190, 3000, 440), P(-80, 3150, 470), P(0, 3300, 440)], r=0.006)
loom("Loom_Front", [P(-150, 1060, 520), P(-150, 500, 470), P(-150, 100, 450), P(0, 0, 450)], r=0.006)
for s_, tg in ((-1, "FL"), (1, "FR")):
    up_ = CORNER[tg]["upper"]
    loom(f"Loom_Corner{tg}", [P(0, 0, 450) if s_ > 0 else P(-150, 100, 450), Vector((s_ * 0.20, -0.17, 0.44)), up_ + Vector((-s_ * 0.06, -0.03, -0.01)),
                              up_ + Vector((-s_ * 0.03, -0.01, -0.06))], r=0.004)
for s_, tg in ((-1, "RL"), (1, "RR")):
    up_ = CORNER[tg]["upper"]
    loom(f"Loom_Corner{tg}", [P(0, 3300, 440), P(s_ * 150, 3250, 450), up_ + Vector((-s_ * 0.06, -0.03, -0.01)), up_ + Vector((-s_ * 0.03, -0.01, -0.06))], r=0.004)

SENS = []
def sens(name, pos, axis, kind="probe", size=1.0):
    parts, tip = f1.sensor(name, pos, axis, kind=kind, size=size, mats=mats)
    best = None
    for nm, pts in LOOMS.items():
        for a, b in zip(pts, pts[1:]):
            from mathutils.geometry import intersect_point_line
            q, t = intersect_point_line(tip, a, b)
            q = a + (b - a) * min(1.0, max(0.0, t))
            d = (q - tip).length
            if best is None or d < best[0]:
                best = (d, nm)
    f1.wire_to(f"{name}_Wire", tip, LOOMS[best[1]], mats=mats)
    SENS.append(name)

# エンジン
sens("Sensor_Crank", P(-125, YGB - 25, CZ), (-1, 0, 0), "block")
for bank, tg in ((-1, "L"), (1, "R")):
    d_, inner_ = f1.v6_frame(bank)
    for j, u in enumerate((35, -35)):
        sens(f"Sensor_Cam{tg}{'IE'[j]}", f1.v6_point(bank, HT + 52, u, YF + 60) * MM, d_, "block", 0.8)
    sens(f"Sensor_Knock{tg}", f1.v6_point(bank, 110, -62, 2700) * MM, -inner_, "block", 0.9)
    sens(f"Sensor_WaterTemp{tg}", f1.v6_point(bank, 285, -62, YF + 70) * MM, -inner_, "probe")
    ysb = [y for b, i, y in f1.v6_cylinders() if b == bank]
    sens(f"Sensor_FuelPressure{tg}", f1.v6_point(bank, V6["deck"] + 45, 104, ysb[-1] + 20) * MM, d_, "probe", 0.8)
    coll = Vector((bank * 300, YGB - 20 + 60, CZ + 45 + 28)) * MM
    sens(f"Sensor_Lambda{tg}", coll, (0, 0, 1), "probe", 1.1)
    for i, y in enumerate(ysb):
        portx = f1.v6_point(bank, tc_, -(V6["head_w"] / 2 - 3), y)
        outx = (f1.v6_point(bank, tc_, -1000, y) - f1.v6_point(bank, tc_, 0, y)).normalized()
        sens(f"Sensor_EGT{tg}{i + 1}", (portx + outx * 30) * MM + Vector((0, 0, 0.019)), (0, 0, 1), "probe", 0.6)
sens("Sensor_OilPressure", P(131, 2565, CZ + 50), (1, 0, 0), "probe")
sens("Sensor_OilTemp", P(131, 2600, CZ + 50), (1, 0, 0), "probe")
sens("Sensor_MAP", P(0, 2700, CZ + 334), (0, 0, 1), "block")
sens("Sensor_IntakeTemp", P(124, 2650, CZ + 300), (1, 0, 0), "probe")
sens("Sensor_Throttle", P(50, ty0 - 18, CZ + 330), (1, 0, 0), "block")
sens("Sensor_TurboSpeed", turbo_w(0, -0.104, -0.068), (0, 0, 1), "block", 0.8)
# ギアボックス
sens("Sensor_GearPosition", P(75, 2984, OUT_Z), (0, -1, 0), "block", 0.9)
hit = FX.ray(Vector((0, 3.25, 0.80)), (0, 0, -1), ["Gearbox"], far=0.6)
if hit:
    sens("Sensor_OutputSpeed", hit[0], (0, 0, 1), "block")
hit = FX.ray(Vector((-0.40, 3.20, 0.30)), (1, 0, 0), ["Gearbox"], far=0.6)
if hit:
    sens("Sensor_GearboxOilTemp", hit[0], (-1, 0, 0), "probe")
sens("Sensor_ClutchPosition", P(-45, 2944, CLUTCH_Z + 30), (0, 0, 1), "block", 0.8)
sens("Sensor_HydPressure", P(220, 2690, 190), (0, 0, 1), "probe")
# 足まわり・ブレーキ・ステアリング
for tg in ("FL", "FR", "RL", "RR"):
    lo_, hi_ = FX.bbox(f"Upright_{tg}_Housing")
    c_ = (lo_ + hi_) / 2
    sens(f"Sensor_WheelSpeed{tg}", c_ + Vector((0, 0, 0.068)), (0, 0, 1), "block", 0.9)
    sens(f"Sensor_BrakeTemp{tg}", c_ + Vector((0, -0.069 if tg[0] == "F" else 0.069, -0.02)), (0, -1 if tg[0] == "F" else 1, 0), "block", 0.8)
    a_, b_ = FX.rod_end_geom(f"Damper_{tg}_RodEndA")[0], FX.rod_end_geom(f"Damper_{tg}_RodEndB")[0]
    dd = (b_ - a_)
    side_ = dd.cross(Vector((0, 0, 1))).normalized()
    sens(f"Sensor_DamperPot{tg}", a_ + dd * 0.08 + side_ * 0.030, dd, "pot", dd.length * 0.6)
    a_, b_ = FX.rod_end_geom(f"Pushrod_{tg}_RodEndA")[0], FX.rod_end_geom(f"Pushrod_{tg}_RodEndB")[0]
    m_ = (a_ + b_) / 2
    sens(f"Sensor_PushrodLoad{tg}", m_ + (b_ - a_).cross(Vector((1, 0, 0))).normalized() * 0.008, (b_ - a_).cross(Vector((1, 0, 0))).normalized(), "patch")
for nm in ("FrontHeave", "RearHeave"):
    a_, b_ = FX.rod_end_geom(f"{nm}_RodEndA")[0], FX.rod_end_geom(f"{nm}_RodEndB")[0]
    sens(f"Sensor_DamperPot{nm}", a_ + (b_ - a_) * 0.1 + Vector((0, 0, 0.026)), b_ - a_, "pot", (b_ - a_).length * 0.6)
for k, x in enumerate((-115, -45)):
    sens(f"Sensor_BrakePressure{k + 1}", P(x, 446, 250), (0, 0, 1), "probe")
sens("Sensor_SteeringAngle", UJ2 + Vector((0, 0.03, 0.020)), (0, 0, 1), "block")
sens("Sensor_BrakePedal", P(-80 - 32, 640, 95), (-1, 0, 0), "block", 0.9)
print("センサー:", len(SENS))

# ---- 予約した穴を、部品ごとにまとめてあける
print("穴をあけた部品:", FX.drill_all())
print("留め具の数:", FX.report())

# =========================================================== 検査
qm.expect("*", floating=True)        # 車体とフロアがないので、全体は地面から浮いてよい（部品どうしのつながりは見る）
qm.expect("Disc_FL", size=(32 * MM, 328 * MM, 328 * MM), tol=0.02)
qm.expect("Disc_RL", size=(32 * MM, 280 * MM, 280 * MM), tol=0.02)

# =========================================================== 図鑑
G1, G2, G3, G4, G5, G6, G7 = "サバイバルセル", "コクピット", "燃料・電気", "パワーユニット", "冷却", "足まわり", "ギアボックス"
qm.catalog("all", "シャシー全体（車体を除く）", "カウル・ウイング・フロアを外した F1 マシンの中身。前輪の軸から後輪の軸まで 3,400mm（2026 年規定の上限）。"
           "クランクの高さは規定（基準面の 90mm 上）。エンジンはサバイバルセルに直接留める。"
           "そのほかの部品の位置は推定（ペダルの前後位置・燃料タンクの大きさ・車高を含む）。", parts=[""],
           labels={"Cell": "サバイバルセル", "Engine_": "V6 エンジン", "Gearbox": "ギアボックス", "RadiatorL": "ラジエーター",
                   "Turbo": "ターボ", "Halo": "ヘイロー", "Tyre_FL": "前輪", "Tyre_RL": "後輪"}, group="全体")
qm.catalog("cell", "サバイバルセル", "ドライバーと燃料タンクを囲むカーボンの殻。コクピットの前後に上ぶた、脚の上にダッシュボードの梁。"
           "後ろの隔壁にエンジンを直接ボルトで留める。", parts=["Cell", "RollHoop", "Halo"],
           labels={"Cell_DashBeam": "ダッシュボードの梁", "Cell_FrontDeck": "前の上ぶた", "Cell_RearDeck": "後ろの上ぶた",
                   "RollHoop": "ロールフープ", "Halo": "ヘイロー", "Cell_RearBulkhead": "後ろの隔壁"}, group=G1)
qm.catalog("side_impact", "側面衝撃吸収構造", "サイドポッドの前で、サバイバルセルの横から外へ伸びる筒。横からの衝突のエネルギーを吸う。",
           parts=["SideImpact", "Cell"], labels={"SideImpactUpperL": "上の筒", "SideImpactLowerL": "下の筒", "Cell": "サバイバルセル"}, group=G1)
qm.catalog("seat", "シートとシートベルト", "ドライバーの体に合わせて型を取るシートと、6 点式のベルト（肩 2・腰 2・股 2）。"
           "ベルトは中央のバックルを回すと一度に外れる。", parts=["Seat", "Harness", "Headrest"],
           labels={"Seat": "シート", "Harness_ShoulderL": "肩のベルト", "Harness_LapR": "腰のベルト", "Harness_CrotchL": "股のベルト",
                   "Harness_Buckle": "バックル", "Headrest": "ヘッドレスト"}, group=G2, view="front-left")
qm.catalog("wheel", "ステアリングホイール", "表示画面・シフトランプ・ボタン・回すスイッチを並べた操作盤（ドライバー側から見た図）。"
           "裏の上にシフトパドル、下にクラッチパドル（側面図に見える）。クイックリリースで外してコクピットから出る。寸法は推定。", parts=["Wheel"],
           labels={"Wheel_Screen": "表示画面", "Wheel_ShiftLight": "シフトランプ", "Wheel_GripL": "グリップ", "Wheel_Rotary": "回すスイッチ",
                   "Wheel_Button": "ボタン"}, group=G2, view="rear")
qm.catalog("steering", "ステアリングコラムとラック", "ホイールの回転を、ユニバーサルジョイント 2 つで折れた軸でラックのピニオンへ伝える。"
           "ラックが左右に動き、トラックロッドがアップライトを向ける。", parts=["Column", "Rack", "TrackRod"],
           labels={"Column_UJoint1": "ユニバーサルジョイント", "Column_Bearing": "コラムの軸受", "Rack_Body": "ラック",
                   "Rack_Pinion": "ピニオン", "TrackRod_FL": "トラックロッド"}, group=G2)
qm.catalog("pedals", "ペダル", "床に軸のある 2 枚のペダル（左がブレーキ、右がアクセル）。ブレーキは前後 2 本のマスターシリンダーを、"
           "バランスバーを介して押す。前後の位置は推定：規定では足は前輪の軸より後ろ、前の隔壁から 300mm 以上後ろ"
           "（後者は報道による）だが、実車のペダルの位置は確かめられなかった。", parts=["PedalBox", "PedalBrake", "PedalThrottle", "Master", "BalanceBar"],
           labels={"PedalBrake_Pad": "ブレーキペダル", "PedalThrottle_Pad": "アクセルペダル", "Master1_Body": "マスターシリンダー",
                   "BalanceBar": "バランスバー", "PedalThrottle_Sensor": "位置センサー", "PedalBox_Front": "取り付け板"}, group=G2)
qm.catalog("extinguisher", "消火器", "脚の下の床に寝かせたボトルから、コクピットの足もとと、エンジンの前のノズルへ配管する。寸法は推定。",
           parts=["Extinguisher", "ExtLine", "ExtNozzle"],
           labels={"Extinguisher_Valve": "弁", "Extinguisher_Strap1": "固定バンド", "Extinguisher": "ボトル", "ExtNozzle_Cockpit": "コクピットのノズル",
                   "ExtNozzle_Engine": "エンジンのノズル"}, group=G2)
qm.catalog("fuel", "燃料タンク", "ドライバーの背中とエンジンの間にある、ゴム袋の燃料セル。底の集油槽のポンプから、エンジンの高圧ポンプへ送る。"
           "大きさ（約 100L）は推定：タンクの容量そのものの規定はなく、2026 年のレースの燃料の量は資料によって 70kg / 110kg と食い違い、確かめられなかった。",
           parts=["FuelCell", "FuelLine", "FuelCoupling", "FuelFillLine", "FuelReturn"], view="front-left",
           labels={"FuelCell": "燃料セル", "FuelCell_Hatch": "点検ふた", "FuelLine": "燃料の配管", "FuelCoupling": "燃料を入れ・抜く口",
                   "FuelReturn": "戻りの配管"}, group=G3)
qm.catalog("es", "エネルギーストアと制御電子機器", "リチウムイオン電池（ES）は、サバイバルセルの中、燃料タンクの下。"
           "制御電子機器（CE）と MGU-K へ高電圧の配線でつながる。右の前の小さなクーラーから、冷却水が ES → CE の順に回る。"
           "中身（ES のセル・モジュール・バスバー、CE のインバーターと DC-DC）は断面図で見られる。寸法と中の作りは推定。", parts=["ES", "CE", "HVCable", "ESCooler", "ESCoolLine"],
           labels={"ES": "エネルギーストア", "ES_CoolingPlate": "冷却板", "CE": "制御電子機器", "HVCableK": "MGU-K への配線",
                   "ESCooler": "ES・CE のクーラー", "ESCoolLine3": "冷却水の管"}, group=G3)
qm.catalog("engine", "V6 エンジン（外観）", "1.6L・V 型 6 気筒・バンク角 90°。ボア 80mm・ストローク 53mm。吸気は V の内側、排気は外側。"
           "クランクの中心は規定で基準面（プランクの上面）の 90mm 上と低く、クランクの下にオイルパンを置く余地はない（クランク室の底から直接吸う）。"
           "ブロックはクランクの中心で上下に分かれ、下がベッドプレート。前の面はサバイバルセルの隔壁に直接留め、"
           "ウォーターポンプはブロックの横、燃料の高圧ポンプは V の谷。", parts=["Engine_"],
           labels={"Engine_HeadL": "シリンダーヘッド", "Engine_CamCoverR": "カムカバー", "Engine_Block": "シリンダーブロック",
                   "Engine_Bedplate": "ベッドプレート", "Engine_SumpPickup1": "スカベンジの吸い口", "Engine_WaterPumpR": "ウォーターポンプ",
                   "Engine_CoilR2": "点火コイル", "Engine_ScavengePump": "スカベンジポンプ",
                   "Engine_GearCover": "ギアのカバー", "Engine_OilFilter": "オイルフィルター"}, group=G4)
qm.catalog("crank", "クランクシャフト・ピストン・コンロッド", "3 本のクランクピンを 120° おきに置き、1 本のピンに左右のコンロッド 2 本。"
           "クランクは 1 本の鍛造品（カウンターウェイト・油穴付き）。コンロッドはキャップとボルト 2 本で大端を締め、メタルをはさむ。"
           "ピストンにはリング 3 本とピン・サークリップ。ピストンの直径 80mm（ボア）、行程 53mm。コンロッドの長さは推定。", parts=["Crank_"],
           labels={"Crank_PistonL1": "ピストン", "Crank_RingL1": "ピストンリング", "Crank_RodR2": "コンロッド", "Crank_RodCapR2": "キャップ",
                   "Crank_Shaft": "クランクシャフト", "Crank_MainShell2Upper": "主軸受のメタル", "Crank_Gear": "前のギア"}, group=G4)
qm.catalog("intake", "吸気", "ドライバーの頭の上の吸気口からエアボックスを通ってターボへ。圧縮しインタークーラーで冷やした空気が、スロットルからプレナムへ入り、"
           "シリンダーごとのトランペットで吸い込まれる。", parts=["Intake_", "AirInlet", "Airbox"],
           labels={"Intake_Plenum": "プレナム", "Intake_Throttle": "スロットル", "Intake_TrumpetL2": "吸気トランペット",
                   "AirInlet": "ターボへの吸気管", "Airbox": "エアボックス"}, group=G4)
qm.catalog("exhaust", "排気", "左右 3 本ずつの管を集合部でまとめ、ギアボックスの上のタービンへ。出口はテールパイプ 1 本。",
           parts=["Exhaust_", "Tailpipe"], labels={"Exhaust_PrimaryL1": "マニホールド", "Exhaust_CollectorL": "集合部",
                                                   "Exhaust_ToTurboR": "タービンへの管", "Tailpipe": "テールパイプ"}, group=G4)
qm.catalog("turbo", "ターボチャージャー", "排気でタービンを回し、同じ軸のコンプレッサーで吸気を圧縮する。2026 年は MGU-H がなくなった。"
           "管との継ぎ目は V バンドクランプで締める。軸受へはエンジンからオイルを送り、下から戻す（管の道すじは推定）。",
           parts=["Turbo", "Wastegate"], labels={"Wastegate": "ウェイストゲート", "Turbo_Compressor": "コンプレッサー", "Turbo_Turbine": "タービン", "Turbo_Bearing": "軸受ハウジング",
                                     "Turbo_CompOutlet": "圧縮空気の出口", "Turbo_TurbineInletL": "排気の入口",
                                     "Turbo_VbandInL": "V バンド", "TurboOilFeed": "オイル（行き）", "TurboOilDrain": "オイル（戻り）"}, group=G4)
qm.catalog("mguk", "MGU-K", "減速で電気を回収し、加速で最大 350kW を足すモーター発電機。サバイバルセルの中（燃料タンクの後ろ）に置き、"
           "隔壁を通る軸のギアで、クランクの前のギアからアイドラーを介して回る。セルの中に置くのは 2026 年の報道による（規定の本文は未確認）。寸法は推定。",
           parts=["MGUK", "Crank_Gear"],
           labels={"MGUK": "本体", "MGUK_Gear": "駆動ギア", "MGUK_Idler": "アイドラー", "Crank_Gear": "クランクのギア", "MGUK_HVTerminal": "高電圧の端子"}, group=G4)
qm.catalog("cooling", "冷却（ラジエーター・インタークーラー・オイルクーラー）", "サイドポッドの中の熱交換器。左右に冷却水のラジエーター、"
           "右にターボの空気を冷やすインタークーラー、左にオイルクーラー。", parts=["Radiator", "Intercooler", "OilCooler", "WaterPipe", "ChargePipe", "OilLine", "CoolerBracket", "HeaderTank"],
           labels={"RadiatorL": "ラジエーター", "Intercooler": "インタークーラー", "OilCooler": "オイルクーラー", "WaterPipeHotR": "冷却水（行き）",
                   "WaterPipeColdR": "冷却水（帰り）", "ChargePipe1": "圧縮空気の管", "OilLineFeed": "オイルの管", "HeaderTank": "ヘッダータンク"}, group=G5)
qm.catalog("oiltank", "オイルタンク", "ドライサンプのオイルをためるタンク。燃料タンクとエンジンの間。", parts=["OilTank"],
           labels={"OilTank": "タンク", "OilTank_Filler": "給油口", "OilTank_Breather": "ブリーザー"}, group=G5)
qm.catalog("front_susp", "前のサスペンション", "上下の A アーム、プッシュロッド、ロッカー、ダンパー。ダンパーはサバイバルセルの上に寝かせる。"
           "ロッドエンドはすべて二股の金具（クレビス）にボルト 1 本で留め、ボールの両側にスペーサー。胴体側の金具はボルト 2 本でサバイバルセルへ。",
           parts=["LowerArm_F", "UpperArm_F", "Pushrod_F", "Rocker_F", "Damper_F", "DamperMount_F", "Upright_F"],
           labels={"LowerArm_FL": "下の A アーム", "UpperArm_FL": "上の A アーム", "Pushrod_FL": "プッシュロッド", "Rocker_FR": "ロッカー", "LowerArm_FL_RodEndF_Clevis_Lug1": "クレビス",
                   "Damper_FR": "ダンパー", "Upright_FR": "アップライト"}, group=G6)
qm.catalog("front_brake", "前のブレーキ・ハブ・ホイール（右を内側から）", "ベンチレーテッドディスク 328×32mm と一体型の 6 ピストンキャリパー、ハブとセンターナット、18 インチのホイール。"
           "キャリパーのピストンが、裏板つきのパッドをディスクへ押す（2026 年は 6 か 8 ピストンを選べ、8 ピストンはパッド 4 枚。図は 6 ピストン・パッド 2 枚）。"
           "ハブはアップライトの中の玉軸受 2 個で回り、ディスクはボビンでベルに、ベルはハブのつばにボルトで留める。パッドの厚み・軸受・ボビンの数は推定。",
           parts=["Disc_FR", "Caliper_FR", "CaliperBracket_FR", "Hub_FR", "Rim_FR", "Upright_FR", "BrakeDuct_FR"],
           labels={"Disc_FR": "ブレーキディスク", "Caliper_FR": "キャリパー", "Caliper_FR_PadIn": "パッド", "Hub_FR": "ハブ", "Rim_FR": "ホイール",
                   "Upright_FR_BrgOut": "ハブの軸受", "Disc_FR_Bobbin1": "ボビン", "BrakeDuct_FR_Scoop": "ブレーキダクト"}, group=G6, view="front-left")
qm.catalog("rear_susp", "後ろのサスペンション", "ギアボックスの横の取り付け台から出る A アームとトーリンク、プッシュロッドで動くロッカーとダンパー、アンチロールバー。",
           parts=["LowerArm_R", "UpperArm_R", "ToeLink_R", "Pushrod_R", "Rocker_R", "Damper_R", "DamperMount_R", "Upright_R",
                  "AntiRollBar", "ARBMount", "RearHeave", "HeaveLink_R"],
           labels={"LowerArm_RL": "下の A アーム", "UpperArm_RL": "上の A アーム", "ToeLink_RL": "トーリンク", "Damper_RR": "ダンパー",
                   "Rocker_RR": "ロッカー", "AntiRollBar": "アンチロールバー", "RearHeave": "ヒーブダンパー", "Upright_RR": "アップライト"}, group=G6)
qm.catalog("rear_brake", "後ろのブレーキ・ドライブシャフト（左）", "ディスク 280×32mm、6 ピストンキャリパー。ドライブシャフトの両端に等速ジョイント。",
           parts=["Disc_RL", "Caliper_RL", "CaliperBracket_RL", "Hub_RL", "Rim_RL", "Upright_RL", "Driveshaft_RL", "BrakeDuct_RL"],
           labels={"Disc_RL": "ブレーキディスク", "Caliper_RL": "キャリパー", "Driveshaft_RL_InnerCV": "等速ジョイント（内）",
                   "Driveshaft_RL_Shaft": "ドライブシャフト", "Rim_RL": "ホイール", "BrakeDuct_RL_Scoop": "ブレーキダクト"}, group=G6)
qm.catalog("tyres", "タイヤ", "前 705×280mm、後ろ 710×375mm（2026 年規定）。18 インチ。", parts=["Tyre_"],
           labels={"Tyre_FL": "前輪", "Tyre_RL": "後輪"}, group=G6)
qm.catalog("gearbox", "ギアボックスのケースと後ろの衝撃吸収構造", "エンジンの後ろに付き、後ろのサスペンションの取り付け台を兼ねる。左の横にギアボックスのオイルクーラー。",
           parts=["Gearbox", "RearCrash", "RainLight"],
           labels={"Gearbox_Flange": "ベルハウジングのフランジ", "Gearbox": "ケース", "RearCrash": "衝撃吸収構造", "GearboxOilCooler": "オイルクーラー", "RainLight": "レインライト",
                   "Gearbox_Bolt1": "フランジのボルト"}, group=G7, view="front-left")
qm.catalog("clutch", "クラッチ", "カーボンの多板クラッチ。直径およそ 100mm。クランクの高さにあり、軸のまわりの油圧のシリンダーで切る。"
           "段差のギア（推定）で、上の入力軸へ回す。", parts=["Clutch", "DropGear"],
           labels={"Clutch_Basket": "バスケット", "Clutch_Friction1": "摩擦板", "Clutch_PressurePlate": "押し付け板", "Clutch_Hub": "ハブ",
                   "ClutchSlave": "スレーブシリンダー", "DropGear_Input": "段差のギア"}, group=G7)
qm.catalog("gears", "前進 8 段のギア列", "入力軸と出力軸に 8 組の歯車。ドッグハブ 4 個で 1 組ずつ選ぶ。歯数とモジュールは推定。",
           parts=["InputShaft", "OutputShaft", "Gear1_", "Gear2_", "Gear3_", "Gear4_", "Gear5_", "Gear6_", "Gear7_", "Gear8_", "DogHub", "ReverseIdler", "Brg_In", "Brg_Out", "NeedleBrg"],
           labels={"InputShaft": "入力軸", "OutputShaft": "出力軸", "Gear1_": "1 速", "Gear8_": "8 速", "DogHub2": "ドッグハブ", "ReverseIdler": "リバース",
                   "NeedleBrg3": "ニードル軸受"}, group=G7)
qm.catalog("shift", "シフトドラムとフォーク", "ドラムの溝がフォークを動かし、フォークがドッグハブを滑らせる（シームレスシフト）。",
           parts=["ShiftBarrel", "Fork", "DogHub", "SelectorRail"], labels={"SelectorRail": "セレクターレール", "ShiftBarrel_Drum": "シフトドラム", "ShiftBarrel_Actuator": "アクチュエーター",
                                                           "Fork2": "セレクターフォーク", "DogHub3": "ドッグハブ"}, group=G7)
qm.catalog("diff", "かさ歯車とデフ", "出力軸のピニオン（12 歯）とクラウン（36 歯）で 90° 曲げ、デフで左右へ分ける。", parts=["BevelPinion", "CrownWheel", "Diff", "Brg_Diff"],
           labels={"BevelPinion": "ピニオン", "CrownWheel": "クラウンギア", "Diff_Case": "デフケース", "Brg_DiffR": "軸受"}, group=G7)

G8 = "細かい部品"
qm.catalog("valvetrain", "動弁系（左バンク）", "1 気筒に吸気 2・排気 2 のバルブ。バンクごとに吸気と排気のカムシャフト（DOHC）。"
           "バルブは金属のばねではなく空気ばねで閉じる。傾き・径・カムの形は推定。", parts=["Valve_L", "Cam_L"],
           labels={"Valve_L1Ina": "吸気バルブ", "Valve_L1Exa": "排気バルブ", "Valve_L2Ina_SpringCyl": "空気ばね", "Valve_L3Exb_Tappet": "タペット",
                   "Cam_LIn": "吸気のカムシャフト", "Cam_LEx": "排気のカムシャフト", "Cam_LInGear": "カムのギア"}, group=G4)
qm.catalog("ignition", "点火プラグとインジェクター", "点火プラグはシリンダーの真上。燃料は 1 気筒 1 本のインジェクターで、シリンダーへ直接噴く（最大 500bar）。"
           "左右のバンクの燃料レールから配る。", parts=["Plug_", "Injector_", "FuelRail_", "Engine_Coil"],
           labels={"Plug_L1": "点火プラグ", "Plug_L1Insulator": "がいし", "Injector_R2": "インジェクター", "FuelRail_R": "燃料レール",
                   "Engine_CoilL3": "点火コイル"}, group=G4)
qm.catalog("tethers", "ホイールテザー", "事故でタイヤが外れて飛ばないよう、車体とアップライトをつなぐ繊維のケーブル。サスペンションのアームの中を通す。"
           "本数は規定書で確かめられなかったので、図では上下のアームに 1 本ずつ。", parts=["Tether_"],
           labels={"Tether_FLU": "前・上", "Tether_FLL": "前・下", "Tether_RRU": "後ろ・上", "Tether_RRL": "後ろ・下"}, group=G6, context=["Cell", "Upright_", "Rim_", "Gearbox"])
qm.catalog("brake_lines", "ブレーキの配管", "前後 2 系統。前はマスターシリンダーから前の左右のキャリパーへ。"
           "後ろはブレーキバイワイヤの弁を通して後ろの左右へ。", parts=["BrakeLine", "BBW", "Master", "PedalBrake"],
           labels={"BrakeLine_FL": "前の配管", "BrakeLine_Rear": "後ろの系統", "BBW": "ブレーキバイワイヤの弁", "Master1": "マスターシリンダー",
                   "BrakeLine_RR": "後ろの配管"}, group=G6, context=["Cell", "Upright_", "Caliper_", "Gearbox"])
qm.catalog("arb_heave", "前のアンチロールバーとヒーブダンパー", "左右のロッカーをつなぐねじり棒（ロール）と、上下の動きだけを受ける 3 本目のダンパー（ヒーブ）。"
           "配置は推定。", parts=["FrontARB", "FrontHeave", "ARBLink_F", "HeaveLink_F", "Rocker_F"],
           labels={"FrontARB": "アンチロールバー", "FrontHeave": "ヒーブダンパー", "ARBLink_FL": "リンク", "Rocker_FR": "ロッカー"}, group=G6)
qm.catalog("drink", "ドリンクの装置・無線・記録装置", "シートの横の袋から、電動ポンプでヘルメットへ飲み物を送る。"
           "無線の箱と、事故のときの加速度を残す記録装置（ADR）。寸法は推定。", parts=["Drink", "Radio", "ADR"],
           labels={"Drink": "ドリンクの袋", "Drink_Pump": "ポンプ", "Drink_Tube": "ヘルメットへの管", "Radio": "無線", "ADR": "事故データ記録装置"}, group=G2)
qm.catalog("hydraulics", "油圧系", "エンジンの前のポンプで油圧を作り、アキュムレーターにためる。ギアボックスの横の制御弁から、"
           "シフト・クラッチと、ラックのパワーステアリングへ送る。配置は推定。", parts=["HydPump", "HydLine", "Accumulator", "ValveBlock", "PowerSteering"],
           labels={"HydPump": "油圧ポンプ", "Accumulator": "アキュムレーター", "ValveBlock": "制御弁", "PowerSteeringLine": "パワーステアリングへ",
                   "PowerSteering_Valve": "パワーステアリングの弁", "HydLine_Shift": "シフトへ"}, group=G7, context=["Cell", "Gearbox", "Engine_Crankcase", "Engine_Block", "Engine_Head", "Rack"])
qm.catalog("electronics", "電装（ECU と配線）", "車の制御をする ECU は左のサイドポッドの前。配線の束（幹と枝）でエンジンの両バンク・下、ギアボックス、"
           "前後の 4 輪、ステアリングホイールへ。箱の中は基板 2 枚（推定）。",
           parts=["ECU", "Loom", "Logger", "Antenna", "SensorWire"], labels={"ECU": "ECU", "Logger": "データロガー", "Antenna": "アンテナ", "Loom_Main": "配線の束", "Loom_Engine": "エンジンへ",
                   "SensorWire_Pitot": "センサーの配線"}, group=G3, context=["Cell", "Engine_Crankcase", "Engine_Block", "Engine_Head", "Engine_CamCover", "Column"])
qm.catalog("nose", "ノーズの衝撃吸収構造", "前の隔壁に留める、先細りのカーボンの筒。正面からの衝突のエネルギーを吸う。上にピトー管。"
           "形と長さは推定。", parts=["NoseCrash", "Pitot", "Cell_FrontBulkhead"],
           labels={"NoseCrash": "衝撃吸収構造", "NoseCrash_Flange": "取り付けのフランジ", "Pitot": "ピトー管", "Cell_FrontBulkhead": "前の隔壁"}, group=G1)
qm.catalog("plank", "プランク", "フロアの下の中央に付く板。厚さ 10mm で、レースの後に 9mm 未満にすり減っていると失格になる。"
           "すり減りは直径 50mm の穴で測り、穴のまわりにチタンのスキッド。フロアを外しているので、取り付けは柱で示した。幅と長さは推定。",
           parts=["Plank"], labels={"Plank": "プランク", "Plank_Skid1": "チタンのスキッド", "Plank_Mount3": "取り付けの柱"}, group=G1)
qm.catalog("sensors", "センサー", "車の状態を測るセンサーと、配線の束への細い線。エンジン（クランク・カムの回転、ノッキング、水温・油温・油圧、"
           "燃料の圧力、吸気の圧力と温度、スロットル、排気の温度 6・ラムダ 2、ターボの回転）、ギアボックス（ギアの位置・出力の回転・油温・クラッチ）、"
           "足まわり（車輪の回転・ブレーキの温度・ダンパーの伸び縮み・プッシュロッドの力）、ブレーキの圧力、舵角、ペダル、車高、空気圧、ピトー管、慣性。"
           "どれも実車にある種類だが、位置と形は推定（実車には数百のセンサーがある）。",
           parts=["Sensor_", "RideHeight", "TPMS", "Pitot", "IMU"],
           labels={"Sensor_Crank": "クランクの回転", "Sensor_LambdaR": "ラムダ", "Sensor_EGTL2": "排気の温度", "Sensor_DamperPotFR": "ダンパーの伸び縮み",
                   "Sensor_WheelSpeedRL": "車輪の回転", "Sensor_BrakePressure1": "ブレーキの圧力", "RideHeight_FL": "車高", "Pitot": "ピトー管",
                   "Sensor_GearPosition": "ギアの位置"}, group=G3, context=["Cell", "NoseCrash", "Engine_Block", "Engine_Head", "Gearbox", "Upright_", "Damper_"])
qm.catalog("gear_train", "エンジンの前のギア列", "クランクの前のギアから、アイドラー 2 枚で頭の複合ギアへ回し、吸気・排気のカムを回す（左右のバンク）。"
           "手前の面では、別のアイドラーで MGU-K を回す。歯数と位置は推定。",
           parts=["GearTrain", "Crank_Gear", "MGUK_Gear", "MGUK_Idler", "Cam_LInGear", "Cam_LExGear", "Cam_RInGear", "Cam_RExGear"],
           labels={"GearTrain_Crank": "クランクのギア（カム用）", "GearTrain_LIdler1": "アイドラー", "GearTrain_RHeadBig": "頭の複合ギア",
                   "Cam_RInGear": "カムのギア", "MGUK_Gear": "MGU-K のギア", "Crank_Gear": "クランクのギア（MGU-K 用）"}, group=G4)

# ---- 断面図（qm.catalog の section。小さい部品の切り口ほど上に描かれるので、ケースやブロックの中の部品が見える）
G9 = "断面図"
yL2 = [y for b, k, y in f1.v6_cylinders() if b < 0 and k == 1][0]
qm.catalog("sec_engine", "エンジンの断面（左の 2 番シリンダー）", "左の 2 番シリンダーの中心で、前から見た断面。V の内側に吸気（トランペットとプレナム）、"
           "外側に排気。クランク・コンロッド・ピストン・バルブ・カム・プラグの切り口が、ブロックとヘッドの上に重なる。"
           "ブロックは中の詰まった立体で作っているので、シリンダーの穴は描かれない。",
           parts=["Engine_", "Crank_", "Valve_", "Cam_", "Plug_", "Injector_", "FuelRail_", "Intake_", "Exhaust_Primary", "Exhaust_Flange"],
           labels={"Crank_PistonL2": "ピストン", "Crank_RodL2": "コンロッド", "Valve_L2Ina": "吸気バルブ", "Cam_LEx": "排気のカム",
                   "Intake_Plenum": "プレナム", "Engine_HeadR": "シリンダーヘッド", "Engine_Bedplate": "ベッドプレート"},
           group=G9, section=("Y", yL2 * MM))
qm.catalog("sec_gearbox", "ギアボックスの断面（中心）", "車の中心（X = 0）で縦に切った断面。クラッチから入力軸・出力軸の 8 組の歯車、"
           "かさ歯車でデフへ。ケースは中の詰まった立体で作っているので、切り口の上に中の部品が重なる。",
           parts=["Gearbox", "Clutch", "InputShaft", "OutputShaft", "Gear1_", "Gear2_", "Gear3_", "Gear4_", "Gear5_", "Gear6_", "Gear7_", "Gear8_",
                  "DogHub", "BevelPinion", "CrownWheel", "Diff", "Brg_", "NeedleBrg", "ClutchSlave", "DropGear"],
           labels={"Clutch_Basket": "クラッチ", "DropGear_Clutch": "段差のギア", "InputShaft": "入力軸", "OutputShaft": "出力軸", "Gear1_Out": "1 速", "CrownWheel": "クラウンギア",
                   "Diff_Case": "デフ", "Gearbox": "ケース"}, group=G9, section=("X", 0.0))
qm.catalog("sec_brake", "前のブレーキの断面（キャリパーの中心）", "右前のキャリパーの中心（車軸の 70mm 前）で切り、前から見た断面。ディスクを両側からパッドがはさみ、"
           "その外にピストンと、キャリパーの一体の本体。上でディスクをまたぐのがブリッジで、パッドを止めるピンが通る。パッドの厚みは推定。",
           parts=["Disc_FR", "Caliper_FR", "CaliperBracket_FR", "Hub_FR", "Upright_FR", "Rim_FR"],
           labels={"Disc_FR": "ディスク", "Caliper_FR_PadIn": "パッド", "Caliper_FR_PistonIn2": "ピストン", "Caliper_FR": "キャリパー",
                   "Caliper_FR_PadPin": "パッドのピン", "Upright_FR_Housing": "アップライト"}, group=G9, section=("Y", f1.caliper_body_offset(True)[1] * 0.5))
qm.catalog("sec_fuel", "燃料タンクの断面（中身）", "燃料セルの前後の中央で切り、前から見た断面。袋は厚み 3mm のゴム。底の集油槽（コレクター）にメインポンプ、"
           "左右の隅のリフトポンプが燃料を集油槽へ送る。上に燃料の流量計（FIA の指定品・超音波式。タンクの中に付けるという報道による）とフィルター。"
           "中の部品の形と配置は推定。", parts=["FuelCell"],
           labels={"FuelCell": "燃料セル（袋）", "FuelCell_Collector": "集油槽", "FuelCell_Pump": "メインポンプ", "FuelCell_LiftPumpL": "リフトポンプ",
                   "FuelCell_FlowMeter": "流量計", "FuelCell_Filter": "フィルター", "FuelCell_LevelSensor": "量の計測棒"},
           group=G9, section=("Y", (FC0 + FC1) / 2 * MM))
qm.catalog("fia", "FIA が求める装置", "事故の衝撃を知らせる警告灯（コクピットの前、上向き）、運転者を写す高速度カメラ、ロールフープの電気の状態のランプ、"
           "外から電源を切るスイッチと消火器のボタン、タイミングのトランスポンダー、コクピットの膝の横のパッド、シートを引き上げるベルト。"
           "位置は規定の古い版や報道によるもので、2026 年の本文では確かめていない（トランスポンダーの位置は推定）。12V の電池は持たない"
           "（制御電子機器が 12〜24V も作る）。",
           parts=["MedicalLight", "HighSpeedCamera", "RollHoop_ERSLight", "RollHoop_TCam", "MasterSwitch", "Extinguisher_ExternalButton", "Transponder",
                  "CockpitPad", "Seat_LiftStrap"],
           labels={"MedicalLight": "衝撃の警告灯", "HighSpeedCamera": "高速度カメラ", "RollHoop_ERSLightL": "電気の状態のランプ", "RollHoop_TCam": "T カメラの台",
                   "MasterSwitch_External": "非常スイッチ", "Extinguisher_ExternalButton": "消火器のボタン", "Transponder": "トランスポンダー",
                   "CockpitPadL": "膝の横のパッド"}, group=G2, context=["Cell", "RollHoop", "Halo", "Seat"])
qm.catalog("sec_ce", "制御電子機器の断面", "制御電子機器（CE）の前後の中央で切った断面。水冷の板の上に、MGU-K を回すインバーターのパワーモジュール 3 つ、"
           "直流のコンデンサー、12〜24V を作る DC-DC コンバーター、上に制御の基板 2 枚。配置と寸法は推定。", parts=["CE"],
           labels={"CE": "ケース", "CE_ColdPlate": "水冷の板", "CE_PowerModule2": "パワーモジュール", "CE_DCLink": "コンデンサー",
                   "CE_DCDC": "DC-DC", "CE_Board1": "基板"}, group=G9, section=("Y", 2.31))
qm.catalog("sec_radiator", "ラジエーターのコアの断面", "左のラジエーターを高さの中ほどで水平に切った断面。前後のタンクの間に平たいチューブが段に並び、"
           "その間を波形のフィンが埋める（ここでは波形のフィンの切り口が見える）。チューブとフィンの間隔は推定。", parts=["RadiatorL"],
           labels={"RadiatorL": "側板", "RadiatorL_TankFront": "前のタンク", "RadiatorL_TankRear": "後ろのタンク", "RadiatorL_Fin21": "フィン",
                   "RadiatorL_Tube21": "チューブ"}, group=G9, section=("Z", 0.352))
qm.catalog("sec_chassis", "シャシーの断面（燃料タンクの位置）", "Y = 2,000mm で切り、前から見た断面。サバイバルセルの殻の中に燃料セルと、その下のエネルギーストア。"
           "左右のサイドポッドにインタークーラーとオイルクーラー。",
           parts=["Cell", "FuelCell", "ES", "Intercooler", "OilCooler", "RollHoop", "Halo", "Plank", "Headrest"],
           labels={"Cell": "サバイバルセル", "FuelCell": "燃料セル", "ES": "エネルギーストア", "Intercooler": "インタークーラー",
                   "OilCooler": "オイルクーラー", "Plank": "プランク"}, group=G9, section=("Y", 2.0))
