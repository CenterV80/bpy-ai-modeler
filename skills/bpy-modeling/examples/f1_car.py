# F1 マシン（2026 年規定の寸法を元に、f1.car で組み立て）
parts = f1.car(livery=(0.85, 0.05, 0.05))
qm.expect("*", size=(f1.SPEC["width"], None, f1.EST["height"]))
qm.expect("Wheel_FL_Tyre", size=(f1.SPEC["front_tyre"][1], f1.SPEC["front_tyre"][0], f1.SPEC["front_tyre"][0]))
qm.expect("Wheel_RL_Tyre", size=(f1.SPEC["rear_tyre"][1], f1.SPEC["rear_tyre"][0], f1.SPEC["rear_tyre"][0]))
