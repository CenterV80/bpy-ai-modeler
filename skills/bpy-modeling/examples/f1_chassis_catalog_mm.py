# F1 シャシーの、車体（カウル・ウイング・フロア）を除いたすべての部品と、部品ごとの図鑑。寸法はすべてミリ
# 実在の値: ホイールベース 3,400mm、全幅 1,900mm、タイヤ 前 705×280 / 後ろ 710×375mm、18 インチ、
#           ブレーキディスク 前 328×32 / 後ろ 280×32mm、V6 90°・ボア 80・ストローク 53mm（1.6L）、前進 8 段、
#           エネルギーストアはサバイバルセルの中（ドライバーの後ろ・燃料タンクの下）
# 推定値  : 部品の位置（f1.LAYOUT）と、上に書いた以外の寸法（公表されていない）
# 図鑑    : ビューアーの「図鑑を開く」で、qm.catalog で登録した項目ごとに等角図・三面図・部品表を描く
qm.units("mm")
MM = qm.MM
L = f1.LAYOUT

def P(x, y, z):
    return Vector((x * MM, y * MM, z * MM))

mats = f1.materials()
titan = mats["titanium"]
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
f1.oil_tank("OilTank", 2.25, 2.415, 0.14, 0.30, 0.60, mats=mats)

# =========================================================== パワーユニット
f1.v6_engine("Engine", mats=mats)
f1.v6_internals("Crank", crank_deg=30, mats=mats)
f1.intake("Intake", mats=mats)
TC = P(0, 3060, 610)                                       # ターボの軸の中心
f1.exhaust("Exhaust", turbine_in=(115, 3120, 610), mats=mats)
qm.orient(f1.turbocharger("Turbo", mats=mats), origin=TC, x_axis=(1, 0, 0), z_axis=(0, 1, 0))
qm.box("Turbo_Bracket", (0.04, 0.04, 0.110), origin="bottom", location=(0, 3.06, 0.455), material=titan)
inconel = qm.material("F1_Inconel", (0.42, 0.36, 0.30), metal=0.9, rough=0.4)
qm.tube("Tailpipe", [P(0, 3185, 610), P(0, 3420, 600), P(0, 3760, 560)], radius=0.040, seg=16, material=inconel)
f1.pipe("AirInlet", [P(0, 2918, 610), P(0, 2880, 690), P(0, 2700, 750)], r=0.045, kind="air", mats=mats)
qm.orient(qm.ring("AirInlet_Flange", 0.058, 0.044, 0.010, seg=20, origin="center", material=titan), origin=P(0, 2702, 750),
          x_axis=(1, 0, 0), z_axis=(0, -1, 0.3))

# MGU-K（クランクの前のギアからかみ合う。位置は推定）
steel_k = qm.material("F1_Steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
MG = P(-205, 0, 202)
MG.y = (YF + 12 + 199) * MM
qm.orient(f1.mgu_k("MGUK", mats=mats), origin=MG, x_axis=(1, 0, 0), z_axis=(0, 1, 0))
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
def cooler(name, s, center, length, height, tilt=15):
    a = math.radians(tilt)
    x_ax = Vector((math.cos(a), 0, -s * math.sin(a)))
    z_ax = Vector((s * math.sin(a), 0, math.cos(a)))
    parts = f1.radiator(name, length * MM, height * MM, 0.05, mats=mats)
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
    r_in, r_out = cooler(f"Radiator{tg}", s, (s * 500, 1700, 350), 500, 360)
    wp = f1.v6_point(s, 130, -40, YF - 15)
    out = f1.v6_point(s, 300, -40, YF + 10)
    f1.pipe(f"WaterPipeHot{tg}", [out * MM, P(out.x, YF - 20, out.z), P(s * 330, 2450, 600), P(s * 480, 2150, 640), r_in + Vector((0, 0, 0.03)), r_in - Vector((0, 0, 0.012))],
            r=0.019, kind="water", mats=mats)
    f1.pipe(f"WaterPipeCold{tg}", [r_out + Vector((0, 0, 0.012)), r_out - Vector((0, 0, 0.03)), P(s * 390, 1400, 110), P(s * 390, 2430, 110),
                                   P(s * 200, 2448, 250), P(wp.x, YF - 28, wp.z)], r=0.019, kind="water", mats=mats)

ic_in, ic_out = cooler("Intercooler", 1, (500, 2110, 330), 220, 300)
th_y = min(y for _, _, y in f1.v6_cylinders()) - 55 - 40
f1.pipe("ChargePipe1", [TC + Vector((0.115, -0.060, -0.045)), P(300, 2950, 600), P(430, 2500, 570), ic_in + Vector((0, 0, 0.04)), ic_in - Vector((0, 0, 0.012))],
        r=0.030, kind="air", mats=mats)
f1.pipe("ChargePipe2", [ic_out + Vector((0, 0, 0.012)), ic_out - Vector((0, 0, 0.04)), P(455, 2440, 95), P(300, 2462, 400), P(120, 2468, 600),
                        P(0, 2482, 600), P(0, th_y + 15, CZ + 330)], r=0.030, kind="air", mats=mats)

oc_in, oc_out = cooler("OilCooler", -1, (-500, 2090, 300), 180, 220)
f1.pipe("OilLineFeed", [P(-120, 2330, 470), P(-330, 2330, 480), oc_in + Vector((0, 0, 0.04)), oc_in - Vector((0, 0, 0.012))], r=0.012, kind="oil", mats=mats)
f1.pipe("OilLineReturn", [oc_out + Vector((0, 0, 0.012)), oc_out - Vector((0, 0, 0.05)), P(-445, 2300, 85), P(-200, 2440, 300), P(-100, 2400, 330)],
        r=0.012, kind="oil", mats=mats)

# 燃料・高電圧の配線
hp = f1.v6_point(1, 250, 0, YF - 17)
f1.pipe("FuelLine", [P(250, 2200, 560), P(250, 2440, 560), P(200, 2455, 470), P(hp.x, YF - 33, hp.z)], r=0.008, kind="fuel", mats=mats)
f1.pipe("HVCableK", [P(-168, 2255, 123), P(-250, 2440, 130), P(-320, 2600, 190), MG + Vector((-0.098, -0.080, 0))], r=0.011, kind="hv", mats=mats)
f1.pipe("HVCableCE", [P(168, 2255, 123), P(110, 2300, 150), P(66, 2330, 153)], r=0.011, kind="hv", mats=mats)

# =========================================================== 前の足まわり（左右）
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
    upper, lower, steer = Vector((s * 0.70, 0.0, C.z + 0.165)), Vector((s * 0.72, 0.0, C.z - 0.165)), Vector((s * 0.70, -0.11, C.z + 0.01))
    f1.upright(f"Upright_{tg}", U, upper, lower, steer, axis=OUT, mats=mats)
    cal_in = DC - OUT * (f1.BRAKE["front"][1] / 2 + 0.018) + cal_dir * 0.14
    qm.sweep(f"CaliperBracket_{tg}", [U + cal_dir * 0.06, cal_in], [(-0.010, -0.014), (0.010, -0.014), (0.010, 0.014), (-0.010, 0.014)],
             up=OUT, material=titan)
    f1.wishbone(f"LowerArm_{tg}", (s * 0.17, -0.20, 0.17), (s * 0.17, 0.22, 0.17), lower, mats=mats)
    f1.wishbone(f"UpperArm_{tg}", (s * 0.20, -0.18, 0.43), (s * 0.21, 0.20, 0.44), upper, mats=mats)
    f1.pushrod(f"Pushrod_{tg}", lower + Vector((-s * 0.07, 0.02, 0.03)), (s * 0.17, 0.05, 0.58), mats=mats)
    TOP = 0.505
    qm.box(f"RockerMount_{tg}", (0.05, 0.05, 0.05), location=(s * 0.12, 0.05, TOP - 0.01), material=mats["carbon"])
    f1.rocker(f"Rocker_{tg}", (s * 0.12, 0.05, 0.56), [(s * 0.17, 0.05, 0.58), (s * 0.08, 0.05, 0.62)], normal=(0, 1, 0), mats=mats)
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
    upper, lower, toe = P(s * 690, WB, WZ + 165), P(s * 700, WB, WZ - 160), P(s * 690, WB + 110, WZ + 5)
    f1.upright(f"Upright_R{tag}", U, upper, lower, toe, axis=OUT, mats=mats)
    cal_in = DC - OUT * ((32 / 2 + 18) * MM) + cal_dir * (115 * MM)
    qm.sweep(f"CaliperBracket_R{tag}", [U + cal_dir * (60 * MM), cal_in],
             [(-10 * MM, -14 * MM), (10 * MM, -14 * MM), (10 * MM, 14 * MM), (-10 * MM, 14 * MM)], up=OUT, material=titan)
    f1.driveshaft(f"Driveshaft_R{tag}", P(s * 150, WB, WZ), U + OUT * (25 * MM), mats=mats)
    for nm, y, z in (("LF", 3230, 140), ("LR", 3530, 160), ("UF", 3240, 440), ("UR", 3500, 420)):
        mount(f"Mount_{nm}_R{tag}", s * 140, y, z - 20)
    f1.wishbone(f"LowerArm_R{tag}", P(s * 150, 3230, 140), P(s * 150, 3530, 160), lower, mats=mats)
    f1.wishbone(f"UpperArm_R{tag}", P(s * 150, 3240, 440), P(s * 150, 3500, 420), upper, mats=mats)
    mount(f"Mount_Toe_R{tag}", s * 140, 3510, WZ - 15)
    f1.pushrod(f"ToeLink_R{tag}", P(s * 150, 3510, WZ + 5), toe, mats=mats)
    f1.pushrod(f"Pushrod_R{tag}", lower + Vector((-s * 70 * MM, 20 * MM, 35 * MM)), P(s * 110, 3330, 545), mats=mats)
    mount(f"RockerMount_R{tag}", s * 70, 3330, 485)
    f1.rocker(f"Rocker_R{tag}", P(s * 70, 3330, 530), [P(s * 110, 3330, 545), P(s * 45, 3330, 585)], normal=(0, 1, 0), mats=mats)
    mount(f"DamperMount_R{tag}", s * 45, 3080, 465, h=110)
    f1.damper(f"Damper_R{tag}", P(s * 45, 3095, 580), P(s * 45, 3320, 590), mats=mats)

mount("ARBMount_L", -90, 3240, 480, h=25)
mount("ARBMount_R", 90, 3240, 480, h=25)
f1.anti_roll_bar("AntiRollBar", P(0, 3240, 515), 110 * MM, mats=mats)

# =========================================================== ギアボックスの中身（f1_gearbox_internals_mm.py と同じ配置）
AXLE_Z = 355.0
IN_Z, OUT_Z = AXLE_Z - 85.0, AXLE_Z                  # 入力軸の高さ = クランク軸の高さ（270）
Mg, GW = 2.5, 13.0
PAIRS = [(20, 48), (22, 46), (24, 44), (26, 42), (28, 40), (30, 38), (32, 36), (34, 34)]
steel = qm.material("F1_Steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
gear_mat = qm.material("F1_GearSteel", (0.70, 0.66, 0.58), metal=0.95, rough=0.25)

def place(parts, y, z, x=0.0):
    return qm.orient(parts, origin=P(x, y, z), x_axis=(1, 0, 0), z_axis=(0, 1, 0))

place(f1.clutch("Clutch", d=100 * MM, mats=mats), 2905, IN_Z)
place(qm.lathe("InputShaft", [(16 * MM, 0), (16 * MM, 385 * MM)], seg=16, material=steel), 2915, IN_Z)
place(qm.lathe("OutputShaft", [(18 * MM, 0), (18 * MM, 335 * MM)], seg=16, material=steel), 2975, OUT_Z)
Y0, BLOCK = 2995.0, 56.0
hub_ys = []
for b in range(4):
    yb = Y0 + b * BLOCK
    for k, ys in ((2 * b, yb), (2 * b + 1, yb + 35)):
        zi, zo = PAIRS[k]
        place(qm.gear(f"Gear{k + 1}_In", zi, Mg * MM, GW * MM, bore=16 * MM, material=gear_mat), ys, IN_Z)
        place(qm.gear(f"Gear{k + 1}_Out", zo, Mg * MM, GW * MM, bore=18 * MM, material=gear_mat), ys, OUT_Z)
    hub_ys.append(yb + 24)
    place(f1.dog_hub(f"DogHub{b + 1}", r_in=18 * MM, r_out=32 * MM, width=16 * MM, mats=mats), yb + 24, OUT_Z)
BARREL_X, BARREL_Y0 = 75.0, 2990.0
place(f1.shift_barrel("ShiftBarrel", 225 * MM, 24 * MM, tracks=[(y - BARREL_Y0) * MM for y in hub_ys], mats=mats), BARREL_Y0, OUT_Z, BARREL_X)
for b, y in enumerate(hub_ys):
    place(f1.selector_fork(f"Fork{b + 1}", 32 * MM, (BARREL_X * MM, 0), mats=mats), y, OUT_Z)
place(qm.gear("ReverseIdler", 18, Mg * MM, GW * MM, bore=8 * MM, material=gear_mat), 3222, (IN_Z + OUT_Z) / 2, 58)
place(qm.lathe("ReverseIdlerShaft", [(8 * MM, 0), (8 * MM, 30 * MM)], seg=12, material=steel), 3214, (IN_Z + OUT_Z) / 2, 58)
for nm, y, z, di, do, w in (("Brg_InFront", 2958, IN_Z, 32, 62, 14), ("Brg_InRear", 3288, IN_Z, 32, 62, 14),
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

# =========================================================== 検査
qm.expect("*", floating=True)        # 車体とフロアがないので、全体は地面から浮いてよい（部品どうしのつながりは見る）
qm.expect("Disc_FL", size=(32 * MM, 328 * MM, 328 * MM), tol=0.02)
qm.expect("Disc_RL", size=(32 * MM, 280 * MM, 280 * MM), tol=0.02)

# =========================================================== 図鑑
G1, G2, G3, G4, G5, G6, G7 = "サバイバルセル", "コクピット", "燃料・電気", "パワーユニット", "冷却", "足まわり", "ギアボックス"
qm.catalog("all", "シャシー全体（車体を除く）", "カウル・ウイング・フロアを外した F1 マシンの中身。前輪の軸から後輪の軸まで 3,400mm（2026 年規定の上限）。"
           "部品の位置はすべて推定。", parts=[""],
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
           "バランスバーを介して押す。", parts=["PedalBox", "PedalBrake", "PedalThrottle", "Master", "BalanceBar"],
           labels={"PedalBrake_Pad": "ブレーキペダル", "PedalThrottle_Pad": "アクセルペダル", "Master1_Body": "マスターシリンダー",
                   "BalanceBar": "バランスバー", "PedalThrottle_Sensor": "位置センサー", "PedalBox_Front": "取り付け板"}, group=G2)
qm.catalog("extinguisher", "消火器", "脚の下の床に寝かせたボトル。ノズルへの配管は省略。寸法は推定。", parts=["Extinguisher"],
           labels={"Extinguisher_Valve": "弁", "Extinguisher_Strap1": "固定バンド", "Extinguisher": "ボトル"}, group=G2)
qm.catalog("fuel", "燃料タンク", "ドライバーの背中とエンジンの間にある、ゴム袋の燃料セル。底の集油槽のポンプから、エンジンの高圧ポンプへ送る。",
           parts=["FuelCell", "FuelLine"], labels={"FuelCell": "燃料セル", "FuelCell_Hatch": "点検ふた", "FuelLine": "燃料の配管"}, group=G3)
qm.catalog("es", "エネルギーストアと制御電子機器", "リチウムイオン電池（ES）は、サバイバルセルの中、燃料タンクの下。"
           "制御電子機器（CE）と MGU-K へ高電圧の配線でつながる。寸法は推定。", parts=["ES", "CE", "HVCable"],
           labels={"ES": "エネルギーストア", "ES_CoolingPlate": "冷却板", "CE": "制御電子機器", "HVCableK": "MGU-K への配線"}, group=G3)
qm.catalog("engine", "V6 エンジン（外観）", "1.6L・V 型 6 気筒・バンク角 90°。ボア 80mm・ストローク 53mm。吸気は V の内側、排気は外側。"
           "前のカバーにウォーターポンプと燃料の高圧ポンプ。", parts=["Engine_"],
           labels={"Engine_HeadL": "シリンダーヘッド", "Engine_CamCoverR": "カムカバー", "Engine_BlockL": "シリンダーブロック",
                   "Engine_Crankcase": "クランクケース", "Engine_Sump": "オイルパン", "Engine_WaterPumpR": "ウォーターポンプ",
                   "Engine_CoilR2": "点火コイル", "Engine_ScavengePump": "スカベンジポンプ"}, group=G4)
qm.catalog("crank", "クランクシャフト・ピストン・コンロッド", "3 本のクランクピンを 120° おきに置き、1 本のピンに左右のコンロッド 2 本。"
           "ピストンの直径 80mm（ボア）、行程 53mm。コンロッドの長さは推定。", parts=["Crank_"],
           labels={"Crank_PistonL1": "ピストン", "Crank_RodR2": "コンロッド", "Crank_Pin3": "クランクピン", "Crank_Main1": "主軸",
                   "Crank_Web2F": "ウェブ", "Crank_Gear": "前のギア"}, group=G4)
qm.catalog("intake", "吸気", "ターボで圧縮しインタークーラーで冷やした空気が、スロットルからプレナムへ入り、"
           "シリンダーごとのトランペットで吸い込まれる。", parts=["Intake_", "AirInlet"],
           labels={"Intake_Plenum": "プレナム", "Intake_Throttle": "スロットル", "Intake_TrumpetL2": "吸気トランペット",
                   "AirInlet": "ターボへの吸気管"}, group=G4)
qm.catalog("exhaust", "排気", "左右 3 本ずつの管を集合部でまとめ、ギアボックスの上のタービンへ。出口はテールパイプ 1 本。",
           parts=["Exhaust_", "Tailpipe"], labels={"Exhaust_PrimaryL1": "マニホールド", "Exhaust_CollectorL": "集合部",
                                                   "Exhaust_ToTurboR": "タービンへの管", "Tailpipe": "テールパイプ"}, group=G4)
qm.catalog("turbo", "ターボチャージャー", "排気でタービンを回し、同じ軸のコンプレッサーで吸気を圧縮する。2026 年は MGU-H がなくなった。",
           parts=["Turbo"], labels={"Turbo_Compressor": "コンプレッサー", "Turbo_Turbine": "タービン", "Turbo_Bearing": "軸受ハウジング",
                                     "Turbo_CompOutlet": "圧縮空気の出口", "Turbo_TurbineInletL": "排気の入口"}, group=G4)
qm.catalog("mguk", "MGU-K", "減速で電気を回収し、加速で最大 350kW を足すモーター発電機。クランクの前のギアから、アイドラーを介して回る。"
           "位置・寸法は推定。", parts=["MGUK", "Crank_Gear"],
           labels={"MGUK": "本体", "MGUK_Gear": "駆動ギア", "MGUK_Idler": "アイドラー", "Crank_Gear": "クランクのギア", "MGUK_HVTerminal": "高電圧の端子"}, group=G4)
qm.catalog("cooling", "冷却（ラジエーター・インタークーラー・オイルクーラー）", "サイドポッドの中の熱交換器。左右に冷却水のラジエーター、"
           "右にターボの空気を冷やすインタークーラー、左にオイルクーラー。", parts=["Radiator", "Intercooler", "OilCooler", "WaterPipe", "ChargePipe", "OilLine", "CoolerBracket"],
           labels={"RadiatorL": "ラジエーター", "Intercooler": "インタークーラー", "OilCooler": "オイルクーラー", "WaterPipeHotR": "冷却水（行き）",
                   "WaterPipeColdR": "冷却水（帰り）", "ChargePipe1": "圧縮空気の管", "OilLineFeed": "オイルの管"}, group=G5)
qm.catalog("oiltank", "オイルタンク", "ドライサンプのオイルをためるタンク。燃料タンクとエンジンの間。", parts=["OilTank"],
           labels={"OilTank": "タンク", "OilTank_Filler": "給油口", "OilTank_Breather": "ブリーザー"}, group=G5)
qm.catalog("front_susp", "前のサスペンション", "上下の A アーム、プッシュロッド、ロッカー、ダンパー。ダンパーはサバイバルセルの上に寝かせる。",
           parts=["LowerArm_F", "UpperArm_F", "Pushrod_F", "Rocker_F", "RockerMount_F", "Damper_F", "DamperMount_F", "Upright_F"],
           labels={"LowerArm_FL": "下の A アーム", "UpperArm_FL": "上の A アーム", "Pushrod_FL": "プッシュロッド", "Rocker_FR": "ロッカー",
                   "Damper_FR": "ダンパー", "Upright_FR": "アップライト"}, group=G6)
qm.catalog("front_brake", "前のブレーキ・ハブ・ホイール（左）", "ベンチレーテッドディスク 328×32mm と 6 ピストンキャリパー、ハブとセンターナット、18 インチのホイール。",
           parts=["Disc_FL", "Caliper_FL", "CaliperBracket_FL", "Hub_FL", "Rim_FL", "Upright_FL"],
           labels={"Disc_FL": "ブレーキディスク", "Caliper_FL": "キャリパー", "Hub_FL": "ハブ", "Rim_FL": "ホイール", "Upright_FL": "アップライト"}, group=G6)
qm.catalog("rear_susp", "後ろのサスペンション", "ギアボックスの横の取り付け台から出る A アームとトーリンク、プッシュロッドで動くロッカーとダンパー、アンチロールバー。",
           parts=["LowerArm_R", "UpperArm_R", "ToeLink_R", "Pushrod_R", "Rocker_R", "RockerMount_R", "Damper_R", "DamperMount_R", "Upright_R", "Mount_",
                  "AntiRollBar", "ARBMount"],
           labels={"LowerArm_RL": "下の A アーム", "UpperArm_RL": "上の A アーム", "ToeLink_RL": "トーリンク", "Damper_RR": "ダンパー",
                   "Rocker_RR": "ロッカー", "AntiRollBar": "アンチロールバー", "Upright_RR": "アップライト"}, group=G6)
qm.catalog("rear_brake", "後ろのブレーキ・ドライブシャフト（左）", "ディスク 280×32mm、6 ピストンキャリパー。ドライブシャフトの両端に等速ジョイント。",
           parts=["Disc_RL", "Caliper_RL", "CaliperBracket_RL", "Hub_RL", "Rim_RL", "Upright_RL", "Driveshaft_RL"],
           labels={"Disc_RL": "ブレーキディスク", "Caliper_RL": "キャリパー", "Driveshaft_RL_InnerCV": "等速ジョイント（内）",
                   "Driveshaft_RL_Shaft": "ドライブシャフト", "Rim_RL": "ホイール"}, group=G6)
qm.catalog("tyres", "タイヤ", "前 705×280mm、後ろ 710×375mm（2026 年規定）。18 インチ。", parts=["Tyre_"],
           labels={"Tyre_FL": "前輪", "Tyre_RL": "後輪"}, group=G6)
qm.catalog("gearbox", "ギアボックスのケースと後ろの衝撃吸収構造", "エンジンの後ろに付き、後ろのサスペンションの取り付け台を兼ねる。", parts=["Gearbox", "RearCrash"],
           labels={"Gearbox_Flange": "ベルハウジングのフランジ", "Gearbox": "ケース", "RearCrash": "衝撃吸収構造"}, group=G7)
qm.catalog("clutch", "クラッチ", "カーボンの多板クラッチ。直径およそ 100mm。", parts=["Clutch"],
           labels={"Clutch_Basket": "バスケット", "Clutch_Friction1": "摩擦板", "Clutch_PressurePlate": "押し付け板", "Clutch_Hub": "ハブ"}, group=G7)
qm.catalog("gears", "前進 8 段のギア列", "入力軸と出力軸に 8 組の歯車。ドッグハブ 4 個で 1 組ずつ選ぶ。歯数とモジュールは推定。",
           parts=["InputShaft", "OutputShaft", "Gear1_", "Gear2_", "Gear3_", "Gear4_", "Gear5_", "Gear6_", "Gear7_", "Gear8_", "DogHub", "ReverseIdler", "Brg_In", "Brg_Out"],
           labels={"InputShaft": "入力軸", "OutputShaft": "出力軸", "Gear1_": "1 速", "Gear8_": "8 速", "DogHub2": "ドッグハブ", "ReverseIdler": "リバース"}, group=G7)
qm.catalog("shift", "シフトドラムとフォーク", "ドラムの溝がフォークを動かし、フォークがドッグハブを滑らせる（シームレスシフト）。",
           parts=["ShiftBarrel", "Fork", "DogHub"], labels={"ShiftBarrel_Drum": "シフトドラム", "ShiftBarrel_Actuator": "アクチュエーター",
                                                           "Fork2": "セレクターフォーク", "DogHub3": "ドッグハブ"}, group=G7)
qm.catalog("diff", "かさ歯車とデフ", "出力軸のピニオン（12 歯）とクラウン（36 歯）で 90° 曲げ、デフで左右へ分ける。", parts=["BevelPinion", "CrownWheel", "Diff", "Brg_Diff"],
           labels={"BevelPinion": "ピニオン", "CrownWheel": "クラウンギア", "Diff_Case": "デフケース", "Brg_DiffR": "軸受"}, group=G7)
