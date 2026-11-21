# F1 の左前の足まわり（モノコック・A アーム上下・プッシュロッド・ロッカー・ダンパー・ステアリング・アップライト・ブレーキ・ハブ・ホイール・タイヤ）
qm.cad()        # キャリパーは一体の本体にピストンの穴を掘る（ブーリアン）ので、四角形の検査を外す
D, W = f1.SPEC["front_tyre"]
C = Vector((-(f1.SPEC["width"] - W) / 2, 0.0, D / 2))   # 左前のホイールの中心
OUT = Vector((-1, 0, 0))                                 # ホイールの外向き
w = W * 0.95
M = C + OUT * (w * 0.05)                                 # ホイールの取り付け面
DC = M - OUT * 0.065                                     # ブレーキディスクの中心
U = DC - OUT * 0.055                                     # アップライトの軸受

tub = f1.tub()
f1.tyre_and_wheel("Tyre_FL", True, location=tuple(C), wheel=False)
qm.orient(f1.rim("Rim_FL", True), origin=M, x_axis=(0, 1, 0), z_axis=OUT)
qm.orient(f1.hub_and_nut("Hub_FL"), origin=M, x_axis=(0, 1, 0), z_axis=OUT)
qm.orient(f1.brake_disc("Disc_FL", True), origin=DC, x_axis=(0, 1, 0), z_axis=OUT)
cal_dir = Vector((0, 0.5, 0.866))
qm.orient(f1.caliper("Caliper_FL", True), origin=DC, x_axis=cal_dir, z_axis=OUT)

upper, lower, steer = Vector((-0.70, 0.0, C.z + 0.165)), Vector((-0.72, 0.0, C.z - 0.165)), Vector((-0.70, -0.11, C.z + 0.01))
f1.upright("Upright_FL", U, upper, lower, steer, axis=OUT)
# キャリパーの取り付けブラケット（アップライトの軸受からキャリパーの内側の本体へ）
cal_in = DC + OUT * (f1.BRAKE["front"][1] / 2 + 0.018) * -1 + cal_dir * 0.14
qm.sweep("CaliperBracket_FL", [U + cal_dir * 0.06, cal_in], [(-0.010, -0.014), (0.010, -0.014), (0.010, 0.014), (-0.010, 0.014)],
         up=OUT, material=qm.material("F1_Titanium", (0.45, 0.45, 0.47), metal=1.0, rough=0.3))

f1.wishbone("LowerArm_FL", (-0.17, -0.20, 0.17), (-0.17, 0.22, 0.17), lower)
f1.wishbone("UpperArm_FL", (-0.20, -0.18, 0.43), (-0.21, 0.20, 0.44), upper)
f1.pushrod("Pushrod_FL", lower + Vector((0.07, 0.02, 0.03)), (-0.17, 0.05, 0.58))

# ロッカーとダンパー（モノコックの上に寝かせる）
TOP = 0.505
qm.box("RockerMount_FL", (0.05, 0.05, 0.05), location=(-0.12, 0.05, TOP - 0.01), material=f1.materials()["carbon"])
f1.rocker("Rocker_FL", (-0.12, 0.05, 0.56), [(-0.17, 0.05, 0.58), (-0.08, 0.05, 0.62)], normal=(0, 1, 0))
qm.box("DamperMount_FL", (0.04, 0.04, 0.10), location=(-0.08, -0.27, TOP - 0.01), material=f1.materials()["carbon"])
f1.damper("Damper_FL", (-0.08, -0.25, 0.60), (-0.08, 0.04, 0.62))

# ステアリングラックとトラックロッド
f1.steering_rack("Rack", (0.0, -0.11, 0.30))
f1.pushrod("TrackRod_FL", (-0.20, -0.11, 0.30), steer)

qm.expect("Disc_FL", size=(f1.BRAKE["front"][1], f1.BRAKE["front"][0], f1.BRAKE["front"][0]), tol=0.02)
