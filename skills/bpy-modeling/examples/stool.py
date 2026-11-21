# 木製スツール（座面は直径35cmで縁を丸く、脚4本は少し外に開く、貫で補強。高さ45cm）
H, R, T = 0.45, 0.175, 0.035
wood = qm.material("Wood", tile=0.5)

# 座面：縁を丸めた断面を回す（フタは qm が四角形の格子でふさぐ）
qm.lathe("Seat", [(R - 0.012, H - T), (R - 0.004, H - T + 0.002), (R, H - T + 0.01), (R, H - 0.01),
                  (R - 0.004, H - 0.002), (R - 0.012, H)], seg=32, material=wood)

# 脚：床では外側、上では内側。先細りの管
top, foot = 0.11, 0.15
legs = []
for name, sx, sy in (("Leg_FR", 1, -1), ("Leg_FL", -1, -1), ("Leg_BR", 1, 1), ("Leg_BL", -1, 1)):
    pts = [(sx * (foot + (top - foot) * t) / 2 ** 0.5, sy * (foot + (top - foot) * t) / 2 ** 0.5, (H - T) * t) for t in (0, 0.25, 0.5, 0.75, 1)]
    legs.append(qm.tube(name, pts, radius=[0.016, 0.0153, 0.0145, 0.0138, 0.013], seg=8, material=wood))

# 貫：前後は 15cm、左右は 19cm の高さ（交差しないよう段違い）
def leg_off(z):
    return (foot + (top - foot) * z / (H - T)) / 2 ** 0.5
for name, z, axis, sgn in (("Rung_F", 0.15, "X", -1), ("Rung_B", 0.15, "X", 1), ("Rung_R", 0.19, "Y", 1), ("Rung_L", 0.19, "Y", -1)):
    d = leg_off(z)
    loc = (0, sgn * d, z) if axis == "X" else (sgn * d, 0, z)
    qm.cylinder(name, 0.008, 2 * d, seg=8, rows=6, axis=axis, location=loc, material=wood)

qm.expect("*", size=(None, None, H))
qm.expect("Seat", size=(2 * R, 2 * R, T))
