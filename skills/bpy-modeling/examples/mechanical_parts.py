# 部品の寄りの絵（ねじ山付きボルト・ナット・座金・歯車・フランジ・ばね）
steel = qm.material("Steel", (0.62, 0.62, 0.64), metal=0.9, rough=0.3)
brass = qm.material("Brass", (0.85, 0.62, 0.25), metal=1.0, rough=0.3)
qm.box("Base", (0.20, 0.08, 0.004), material=qm.material("Dark", (0.12, 0.12, 0.13), rough=0.6))
Z = 0.004
qm.bolt("Bolt_M12", "M12", length=0.04, thread=True, location=(-0.08, 0, Z + 0.04), material=steel)
qm.washer("Washer_M12", "M12", location=(-0.05, 0, Z), material=steel)
qm.nut("Nut_M12", "M12", location=(-0.05, 0, Z + 0.0022), material=steel)
qm.gear("Gear", teeth=24, module=0.0015, width=0.008, location=(-0.005, 0, Z), material=brass)
qm.flange("Flange", 0.012, 0.03, 0.006, bolts=6, bolt_size="M4", location=(0.05, 0, Z), material=steel)
s = qm.tube("Spring", qm.helix(0.008, 0.006, 6, per_turn=16, z0=Z + 0.0015), radius=0.0015, seg=8, material=steel)
s.location = (0.085, 0, 0)

# 車輪は別に置く（タイヤ・リム・ハブ・スポーク 5 本）
qm.wheel("Wheel", radius=0.05, width=0.03, spokes=5, tire_material=qm.material("Rubber", (0.03, 0.03, 0.03), rough=0.85),
         rim_material=steel, location=(0.0, 0.10, 0.05), rotate=(90, 0, 0))
