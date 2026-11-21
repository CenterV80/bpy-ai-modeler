# F1 シャシーの後ろ（ギアボックス・クラッシュストラクチャー・ドライブシャフト・後輪の足まわり・ブレーキ）。寸法はすべてミリ
# 実在の値: ホイールベース 3,400mm（2026 年規定の上限）、全幅 1,900mm、後輪タイヤ 710×375mm、18 インチ、
#           リアのブレーキディスク 280×32mm、6 ピストンキャリパー
# 推定値  : ギアボックス・アーム・ダンパーなどの寸法と取り付け点（公表されていない）
qm.cad()        # キャリパーは一体の本体にピストンの穴を掘る（ブーリアン）ので、四角形の検査を外す
qm.units("mm")
MM = qm.MM

def P(x, y, z):                      # ミリの座標 → メートルの Vector
    return Vector((x * MM, y * MM, z * MM))

WB = 3400.0                          # 後輪の軸の Y
TD, TW = 710.0, 375.0                # 後輪タイヤ 直径・幅
WX = (1900.0 - TW) / 2               # ホイール中心の X（= 762.5）
WZ = TD / 2                          # ホイール中心の Z（= 355）
RIM_W = TW * 0.95
SHOW_TYRE = False                    # 図面ではタイヤを外して中を見せる

mats = f1.materials()
f1.gearbox(y0=2900 * MM, length=660 * MM, mats=mats)
f1.crash_structure(y0=3560 * MM, length=400 * MM, mats=mats)

def mount(name, x, y, z, w=40, d=40, h=40):
    qm.box(name, (w * MM, d * MM, h * MM), origin="bottom", location=P(x, y, z), material=mats["titanium"])

for side, tag in ((-1, "L"), (1, "R")):
    s = side
    C = P(s * WX, WB, WZ)                                   # ホイールの中心
    OUT = Vector((s, 0, 0))                                 # 外向き
    M = C + OUT * (RIM_W * 0.05 * MM)                       # ホイールの取り付け面
    DC = M - OUT * (65 * MM)                                # ブレーキディスクの中心
    U = DC - OUT * (55 * MM)                                # アップライトの軸受

    if SHOW_TYRE:
        f1.tyre_and_wheel(f"Tyre_R{tag}", False, location=tuple(C), wheel=False, mats=mats)
    qm.orient(f1.rim(f"Rim_R{tag}", False, mats=mats), origin=M, x_axis=(0, 1, 0), z_axis=OUT)
    qm.orient(f1.hub_and_nut(f"Hub_R{tag}", mats=mats), origin=M, x_axis=(0, 1, 0), z_axis=OUT)
    qm.orient(f1.brake_disc(f"Disc_R{tag}", False, mats=mats), origin=DC, x_axis=(0, 1, 0), z_axis=OUT)
    cal_dir = Vector((0, -0.5, 0.866))                      # キャリパーは前上
    qm.orient(f1.caliper(f"Caliper_R{tag}", False, mats=mats), origin=DC, x_axis=cal_dir, z_axis=OUT)

    upper, lower, toe = P(s * 690, WB, WZ + 165), P(s * 700, WB, WZ - 160), P(s * 690, WB + 110, WZ + 5)
    f1.upright(f"Upright_R{tag}", U, upper, lower, toe, axis=OUT, mats=mats)
    cal_in = DC - OUT * ((32 / 2 + 18) * MM) + cal_dir * (115 * MM)
    qm.sweep(f"CaliperBracket_R{tag}", [U + cal_dir * (60 * MM), cal_in],
             [(-10 * MM, -14 * MM), (10 * MM, -14 * MM), (10 * MM, 14 * MM), (-10 * MM, 14 * MM)], up=OUT, material=mats["titanium"])

    # ドライブシャフト（ギアボックスの横から、アップライトの軸受の中へ）
    f1.driveshaft(f"Driveshaft_R{tag}", P(s * 150, WB, WZ), U + OUT * (25 * MM), mats=mats)

    # A アーム（胴体側はギアボックスの横の取り付け台）
    for nm, y, z in (("LF", 3230, 140), ("LR", 3530, 160), ("UF", 3240, 440), ("UR", 3500, 420)):
        mount(f"Mount_{nm}_R{tag}", s * 140, y, z - 20)
    f1.wishbone(f"LowerArm_R{tag}", P(s * 150, 3230, 140), P(s * 150, 3530, 160), lower, mats=mats)
    f1.wishbone(f"UpperArm_R{tag}", P(s * 150, 3240, 440), P(s * 150, 3500, 420), upper, mats=mats)
    mount(f"Mount_Toe_R{tag}", s * 140, 3510, WZ - 15)
    f1.pushrod(f"ToeLink_R{tag}", P(s * 150, 3510, WZ + 5), toe, mats=mats)

    # プッシュロッド → ロッカー → ダンパー（ギアボックスの上に前向きに寝かせる）
    f1.pushrod(f"Pushrod_R{tag}", lower + Vector((-s * 70 * MM, 20 * MM, 35 * MM)), P(s * 110, 3330, 545), mats=mats)
    mount(f"RockerMount_R{tag}", s * 70, 3330, 485)
    f1.rocker(f"Rocker_R{tag}", P(s * 70, 3330, 530), [P(s * 110, 3330, 545), P(s * 45, 3330, 585)], normal=(0, 1, 0), mats=mats)
    mount(f"DamperMount_R{tag}", s * 45, 3080, 465, h=110)
    f1.damper(f"Damper_R{tag}", P(s * 45, 3095, 580), P(s * 45, 3320, 590), mats=mats)

# アンチロールバー（ギアボックスの上、左右の取り付け台に載せる）
mount("ARBMount_L", -90, 3240, 480, h=25)
mount("ARBMount_R", 90, 3240, 480, h=25)
f1.anti_roll_bar("AntiRollBar", P(0, 3240, 515), 110 * MM, mats=mats)

qm.expect("Disc_RL", size=(32 * MM, 280 * MM, 280 * MM), tol=0.02)
qm.expect("Disc_RR", size=(32 * MM, 280 * MM, 280 * MM), tol=0.02)
qm.expect("Rim_RL_Barrel", size=(RIM_W * MM, None, None), tol=0.02)
if not SHOW_TYRE:
    qm.expect("*", floating=True)    # タイヤを外しているので、全体は地面から浮いてよい（部品どうしのつながりは見る）
