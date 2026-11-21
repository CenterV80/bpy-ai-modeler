# F1 ギアボックスの中身（クラッチ・入出力軸・前進 8 段・ドッグハブ・フォーク・シフトドラム・かさ歯車・デフ・軸受）。寸法はすべてミリ
# 確認できた事実: 前進 8 段、シームレスシフト（シフトドラムとフォーク）、カーボン多板クラッチ（直径およそ 100mm）、
#                 最終減速はかさ歯車で差動制限付きのデフへ
# 推定値      : 軸間距離 85mm、歯車の幅 13mm、モジュール 2.5、歯数、最終減速比 3.0、軸受・デフ・ケースの寸法
qm.units("mm")
MM = qm.MM

def P(x, y, z):
    return Vector((x * MM, y * MM, z * MM))

SHOW_CASE = True                     # True なら半透明のケースも置く
WB, AXLE_Z = 3400.0, 355.0           # 後輪の軸の Y と高さ（ドライブシャフトの出口）
IN_Z, OUT_Z = AXLE_Z - 85.0, AXLE_Z  # 入力軸・出力軸の高さ（軸間 85mm）
M = 2.5                              # 前進ギアのモジュール [mm]
PAIRS = [(20, 48), (22, 46), (24, 44), (26, 42), (28, 40), (30, 38), (32, 36), (34, 34)]   # 1〜8 速（入力:出力、和 68 → 軸間 85）
GW = 13.0                            # 歯車の幅
Y_AXIS = (0, 1, 0)

mats = f1.materials()
steel = qm.material("F1_Steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
gear_mat = qm.material("F1_GearSteel", (0.70, 0.66, 0.58), metal=0.95, rough=0.25)

def place(parts, y, z, x=0.0):
    """軸 Z で作った部品を、Y 方向の軸の上に据える（部品の z=0 が y の位置）"""
    return qm.orient(parts, origin=P(x, y, z), x_axis=(1, 0, 0), z_axis=Y_AXIS)

# ---- クラッチと入力軸
place(f1.clutch("Clutch", d=100 * MM, mats=mats), 2905, IN_Z)
place(qm.lathe("InputShaft", [(16 * MM, 0), (16 * MM, 385 * MM)], seg=16, material=steel), 2915, IN_Z)
# ---- 出力軸
place(qm.lathe("OutputShaft", [(18 * MM, 0), (18 * MM, 335 * MM)], seg=16, material=steel), 2975, OUT_Z)

# ---- 前進 8 段：2 段ずつ 1 つのドッグハブの両側に並べる
Y0, BLOCK = 2995.0, 56.0
hub_ys = []
for b in range(4):
    yb = Y0 + b * BLOCK
    for k, ys in ((2 * b, yb), (2 * b + 1, yb + 35)):
        zi, zo = PAIRS[k]
        place(qm.gear(f"Gear{k + 1}_In", zi, M * MM, GW * MM, bore=16 * MM, material=gear_mat), ys, IN_Z)
        place(qm.gear(f"Gear{k + 1}_Out", zo, M * MM, GW * MM, bore=18 * MM, material=gear_mat), ys, OUT_Z)
    hub_y = yb + 24
    hub_ys.append(hub_y)
    place(f1.dog_hub(f"DogHub{b + 1}", r_in=18 * MM, r_out=32 * MM, width=16 * MM, mats=mats), hub_y, OUT_Z)

# ---- シフトドラムとフォーク（ドラムは出力軸の横、+X 側）
BARREL_X, BARREL_Y0 = 75.0, 2990.0
place(f1.shift_barrel("ShiftBarrel", 225 * MM, 24 * MM, tracks=[(y - BARREL_Y0) * MM for y in hub_ys], mats=mats), BARREL_Y0, OUT_Z, BARREL_X)
for b, y in enumerate(hub_ys):
    place(f1.selector_fork(f"Fork{b + 1}", 32 * MM, (BARREL_X * MM, 0), mats=mats), y, OUT_Z)

# ---- リバースのアイドラー（入力軸と出力軸の間、+X 側）
place(qm.gear("ReverseIdler", 18, M * MM, GW * MM, bore=8 * MM, material=gear_mat), 3222, (IN_Z + OUT_Z) / 2, 58)
place(qm.lathe("ReverseIdlerShaft", [(8 * MM, 0), (8 * MM, 30 * MM)], seg=12, material=steel), 3214, (IN_Z + OUT_Z) / 2, 58)

# ---- 軸受（入力軸と出力軸の前後）
for nm, y, z, di, do, w in (("Brg_InFront", 2958, IN_Z, 32, 62, 14), ("Brg_InRear", 3288, IN_Z, 32, 62, 14),
                            ("Brg_OutFront", 2982, OUT_Z, 36, 72, 14), ("Brg_OutRear", 3260, OUT_Z, 36, 72, 14)):
    place(qm.ball_bearing(nm, di * MM, do * MM, w * MM, balls=10, material=steel), y, z)

# ---- かさ歯車（出力軸の先のピニオン 12 歯と、デフのクラウン 36 歯。軸どうしは (0, WB, AXLE_Z) で交わる）
FD_M, ZP, ZC = 5.0, 12, 36
gp = math.degrees(math.atan(ZP / ZC))
rp_p, rp_c = FD_M * ZP / 2, FD_M * ZC / 2      # 30mm / 90mm
place(qm.bevel_gear("BevelPinion", ZP, FD_M * MM, 25 * MM, gp, material=gear_mat), WB - rp_c, OUT_Z)
qm.orient(qm.bevel_gear("CrownWheel", ZC, FD_M * MM, 25 * MM, 90 - gp, material=gear_mat), origin=P(-rp_p, WB, AXLE_Z),
          x_axis=(0, 1, 0), z_axis=(1, 0, 0))

# ---- デフ（車軸の向き = X）と、その軸受
qm.orient(f1.differential("Diff", 60 * MM, 150 * MM, mats=mats), origin=P(0, WB, AXLE_Z), x_axis=(0, 1, 0), z_axis=(1, 0, 0))
for side in (-1, 1):
    qm.orient(qm.ball_bearing(f"Brg_Diff{'L' if side < 0 else 'R'}", 60 * MM, 100 * MM, 18 * MM, balls=12, material=steel),
              origin=P(side * 95, WB, AXLE_Z), x_axis=(0, 1, 0), z_axis=(1, 0, 0))

# ---- ケース（半透明。中身を見るため）
if SHOW_CASE:
    glass = qm.material("CaseGlass", (0.55, 0.6, 0.66), rough=0.15, alpha=0.18)
    f1.gearbox(y0=2900 * MM, length=660 * MM, mats={"carbon": glass, "magnesium": glass})

qm.expect("*", floating=True)        # ギアボックス単体なので、地面には置かない
qm.expect("Clutch_Friction1", size=(100 * MM, 3 * MM, 100 * MM), tol=0.02)
qm.expect("Gear1_Out", size=(M * (48 + 2) * MM, GW * MM, M * (48 + 2) * MM), tol=0.03)
