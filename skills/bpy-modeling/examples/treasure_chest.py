# 宝箱（木の箱とかまぼこ型のふた、鉄の帯、錠前、ふたを 35° 開けて中に金貨の山）
W, D, H = 0.90, 0.55, 0.42          # 本体の幅（X）・奥行（Y）・高さ（Z）
R = D / 2                           # ふたの半径
T, BW = 0.012, 0.06                 # 鉄の帯の厚み・幅

wood = qm.material("Wood", tile=0.6)                      # 板 1 枚 ≒ 12cm
iron = qm.material("Iron", (0.06, 0.06, 0.065), metal=0.85, rough=0.45)
gold = qm.material("Gold", (1.0, 0.70, 0.22), metal=1.0, rough=0.25)

body = qm.box("Body", (W, D, H), material=wood, bevel=0.012)

# ふた：半円の断面（円弧 12 分割＋底 6 分割 = 18 点）を X 方向に 10 分割で並べる。両端は qm が四角形でふさぐ
section = qm.arc(R, 180, 0, 12) + [(R - 2 * R * i / 6, 0.0) for i in range(1, 6)]
lid = qm.loft("Lid", [[(-W / 2 + W * k / 10, y, H + z) for y, z in section] for k in range(11)], material=wood)

# 鉄の帯：本体は前・上・後ろに U 字、ふたは円弧に沿って。断面は 厚み T × 幅 BW
band = [(-T / 2, -BW / 2), (T / 2, -BW / 2), (T / 2, BW / 2), (-T / 2, BW / 2)]
lid_parts = [lid]
for side, cx in (("L", -0.28), ("R", 0.28)):
    o = R + T / 2
    qm.sweep(f"Band_Body_{side}", [(cx, -D / 2 - T / 2, 0), (cx, -D / 2 - T / 2, H), (cx, D / 2 + T / 2, H), (cx, D / 2 + T / 2, 0)],
             band, up=(1, 0, 0), material=iron)
    lid_parts.append(qm.sweep(f"Band_Lid_{side}", [(cx, y, H + z) for y, z in qm.arc(R + T / 2, 180, 0, 12)],
                              band, up=(1, 0, 0), material=iron))

qm.box("Lock", (0.09, 0.02, 0.11), origin="center", location=(0, -D / 2 - 0.01, H - 0.05), material=gold, bevel=0.006)
qm.quad_sphere("Gold_Pile", (W - 0.1, D - 0.1, 0.2), n=6, location=(0, 0, H), material=gold)

# ふたを、奥の上の辺（蝶番）を軸に開ける
qm.pivot(lid_parts, point=(0, D / 2, H), rotate=(-35, 0, 0))

qm.expect("Body", size=(W, D, H))
qm.expect("*", size=(None, None, None))
