"""
bpy モデラー（ローカルサーバー）

Blender（GUI なし、pip の bpy）をこのプロセスの中で動かし、Claude Code などの AI から
MCP で操作させる。API キーは使わない。AI の利用は、AI を動かしているアプリ側の契約で行う。

  AI がスクリプトを送る → Blender で実行 → トポロジー検査 → 結果を AI に返す
  → AI が結果（数値と画像）を見て直す、を AI 自身が繰り返す

ブラウザのビューアー（three.js）には、AI が実行した結果がそのまま出る。

起動:
  python server.py             ビューアー http://127.0.0.1:8000 と、AI の接続先 http://127.0.0.1:8000/mcp
  python server.py --stdio     Claude Desktop など、MCP サーバーを自分で起動するアプリ向け
                               （ビューアーは同じく http://127.0.0.1:8000）
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import os
import re
import shutil
import signal
import sys
import threading
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# ---------------------------------------------------------------- 起動オプション
ap = argparse.ArgumentParser(description="bpy モデラー（AI に操作させるローカルサーバー）")
ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
ap.add_argument("--stdio", action="store_true", help="MCP を標準入出力で受ける（Claude Desktop 向け）")
ap.add_argument("--out", default=os.environ.get("BPY_MODELER_OUT", str(ROOT / "output")), help="結果を保存するフォルダ")
ap.add_argument("--timeout", type=float, default=float(os.environ.get("BPY_MODELER_TIMEOUT", "60")),
                help="スクリプト1回の制限時間（秒、macOS / Linux のみ）")
ARGS = ap.parse_args()

if ARGS.stdio:
    # MCP の通信は標準出力を使う。Blender が標準出力に書くログで通信が壊れないよう、
    # 元の標準出力は MCP 専用に取り分け、以降の出力（Blender の C 側のログを含む）は標準エラーへ流す
    _mcp_fd = os.dup(1)
    os.dup2(2, 1)
    sys.stdout = io.TextIOWrapper(os.fdopen(_mcp_fd, "wb"), encoding="utf-8", write_through=True)

import bpy  # noqa: E402  （addon_utils などは bpy を読み込んだ後でないと import できない）
import addon_utils  # noqa: E402
import bmesh  # noqa: E402
import mathutils  # noqa: E402
import qm  # noqa: E402  （四角ポリゴン主体のモデリング用の関数。スクリプトの中で qm として使える）
import f1  # noqa: E402  （F1 マシンの部品。スクリプトの中で f1 として使える）
import uvicorn  # noqa: E402
from mcp.server.mcpserver import Image, MCPServer  # noqa: E402
from starlette.applications import Starlette  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import FileResponse, JSONResponse, Response  # noqa: E402
from starlette.routing import Route  # noqa: E402

OUT = Path(ARGS.out).resolve()
RUNS_DIR = OUT / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)
FORMATS = ("glb", "fbx", "obj", "stl")
TEX_DIR = Path(os.environ.get("BPY_MODELER_TEXTURES", str(ROOT / "textures"))).resolve()
TEX_EXT = (".png", ".jpg", ".jpeg", ".tga", ".bmp", ".tif", ".tiff", ".webp")
# 起動時に作るサンプルのテクスチャと、1枚が何メートル分か（マテリアルの "tile" で上書きできる）
SAMPLE_TILES = {"Brick": 1.0, "Concrete": 2.0, "Wood": 1.0, "UVGrid": 1.0}
TRI_LIMIT = 0.10      # 三角ポリゴンの割合がこれを超えたら問題として返す
FACE_LIMIT = 300_000  # 面がこれより多ければ問題として返す

# 実行の履歴は output/runs/ のファイルが正本。同じフォルダを使う bpy モデラーが複数動いていても
# （Claude Desktop が起動したものと start.bat で起動したもの、など）、どれのビューアーにも全部の結果が出る
_RUN_CACHE: dict[str, dict] = {}
VIEWER = {"url": None, "shared": False}  # 実際に見られるビューアーの URL
STATE = {"scene_run": None}  # いまシーンに入っている実行の番号
LOCK = threading.Lock()


# ================================================================ Blender 側

def log(*a) -> None:
    print(*a, file=sys.stderr, flush=True)


def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for mod in ("io_scene_gltf2", "io_scene_fbx"):
        try:
            addon_utils.enable(mod, default_set=True)
        except Exception:
            pass


class ScriptTimeout(Exception):
    pass


def run_code(code: str) -> tuple[bool, str]:
    """スクリプトを実行し、(成功したか, 出力とエラー) を返す"""
    ns = {"__name__": "__gen__", "bpy": bpy, "bmesh": bmesh, "mathutils": mathutils, "math": math, "qm": qm, "f1": f1,
          "Vector": mathutils.Vector, "Matrix": mathutils.Matrix}
    buf = io.StringIO()
    use_alarm = hasattr(signal, "setitimer") and threading.current_thread() is threading.main_thread() and ARGS.timeout > 0
    if use_alarm:
        def on_alarm(*_):
            raise ScriptTimeout(f"{ARGS.timeout:g} 秒たっても終わらないので止めました（無限ループや重すぎる処理の可能性）")
        old = signal.signal(signal.SIGALRM, on_alarm)
        signal.setitimer(signal.ITIMER_REAL, ARGS.timeout)
    try:
        with contextlib.redirect_stdout(buf):
            exec(compile(code, "<script>", "exec"), ns)
        ok = True
    except BaseException as e:  # noqa: BLE001  SystemExit なども AI に返す
        if isinstance(e, KeyboardInterrupt):
            raise
        buf.write(traceback.format_exc())
        ok = False
    finally:
        if use_alarm:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old)
    try:  # 編集モードのまま終わっていたら戻す
        obj = bpy.context.view_layer.objects.active
        if obj and obj.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass
    return ok, buf.getvalue()


GEOM: dict = {}  # 最後に調べたシーンの、オブジェクトごとの形（接触の判定用。BVH と頂点の見本）


def inspect_scene() -> tuple[dict, list[dict], list[float]]:
    """モディファイア適用後の見た目でトポロジーを数える。(合計, オブジェクトごと, ワイヤー用の辺)"""
    from mathutils.bvhtree import BVHTree
    GEOM.clear()
    keys = ("verts", "faces", "quads", "tris", "ngons", "bad_edges", "flipped_edges", "boundary_edges",
            "loose_verts", "loose_edges", "dup_verts", "degenerate", "inward")
    total = dict(objects=0, **{k: 0 for k in keys})
    per: list[dict] = []
    wire: list[float] = []
    dg = bpy.context.evaluated_depsgraph_get()
    for o in bpy.context.scene.objects:
        if o.type != "MESH":
            continue
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.transform(o.matrix_world)
        q = {k: 0 for k in keys}
        q["name"] = o.name
        q["verts"] = len(bm.verts)
        q["faces"] = len(bm.faces)
        size = max((max(v.co[i] for v in bm.verts) - min(v.co[i] for v in bm.verts)) for i in range(3)) if bm.verts else 1.0
        eps = max(size, 1e-6) * 1e-5
        for f in bm.faces:
            n = len(f.verts)
            q["tris" if n == 3 else "quads" if n == 4 else "ngons"] += 1
            if f.calc_area() < eps * eps:
                q["degenerate"] += 1
        for e in bm.edges:
            k = len(e.link_faces)
            if k > 2:
                q["bad_edges"] += 1
            elif k == 1:
                q["boundary_edges"] += 1
            elif k == 0:
                q["loose_edges"] += 1
            elif e.link_loops[0].vert == e.link_loops[1].vert:
                q["flipped_edges"] += 1  # となりの面と回り方が同じ ＝ 片方が裏返っている
            if len(wire) < 6 * 400_000:
                for v in e.verts:  # Blender(Z 上) → three.js(Y 上)
                    wire += (v.co.x, v.co.z, -v.co.y)
        q["loose_verts"] = sum(1 for v in bm.verts if not v.link_edges)
        if bm.verts:  # ワールド座標での外接箱（寸法と配置の確認用）
            q["min"] = [round(min(v.co[i] for v in bm.verts), 4) for i in range(3)]
            q["max"] = [round(max(v.co[i] for v in bm.verts), 4) for i in range(3)]
            if bm.faces:
                step = max(1, len(bm.verts) // 3000)
                GEOM[o.name] = (BVHTree.FromBMesh(bm), [v.co.copy() for v in bm.verts[::step]])
        if bm.verts:
            doubles = bmesh.ops.find_doubles(bm, verts=bm.verts, dist=eps)["targetmap"]
            q["dup_verts"] = len(doubles)
        closed = bm.faces and not q["boundary_edges"] and not q["bad_edges"] and not q["flipped_edges"]
        if closed and bm.calc_volume(signed=True) < 0:
            q["inward"] = 1  # 閉じているのに体積が負 ＝ 法線が内向き
        bm.free()
        ev.to_mesh_clear()
        total["objects"] += 1
        for k in keys:
            total[k] += q[k]
        per.append(q)
    return total, per, wire


def layout_problems(per: list[dict]) -> list[str]:
    """形のおかしさ（沈み・浮き・宣言した寸法との差）を見つける"""
    per = [p for p in per if "min" in p]
    if not per:
        return []
    exp = json.loads(bpy.context.scene.get("qm_expect", "[]"))
    may_float = {e["target"] for e in exp if e.get("floating")}
    lo = [min(p["min"][i] for p in per) for i in range(3)]
    hi = [max(p["max"][i] for p in per) for i in range(3)]
    diag = math.dist(lo, hi)
    tol = max(0.005, diag * 0.01)
    out = []
    if "*" not in may_float:
        if lo[2] < -tol:
            out.append(f"全体の底が地面（z=0）より {-lo[2]:.3f}m 下にある。接地するものは底面を z=0 に置く")
        elif lo[2] > tol:
            out.append(f"全体が地面（z=0）から {lo[2]:.3f}m 浮いている。接地するものは底面を z=0 に置く")

    def box_gap(a, b):
        return math.sqrt(sum(max(0.0, a["min"][i] - b["max"][i], b["min"][i] - a["max"][i]) ** 2 for i in range(3)))

    def inside(a, b):  # a の外接箱が b の外接箱の中にすっぽり入っている
        return all(a["min"][i] >= b["min"][i] - tol and a["max"][i] <= b["max"][i] + tol for i in range(3))

    def gap(a, b):
        """実際の面どうしの距離（面が交わっていれば 0）。外接箱が離れていればその距離"""
        g = box_gap(a, b)
        ga, gb = GEOM.get(a["name"]), GEOM.get(b["name"])
        if g > tol or not ga or not gb:
            return g
        if ga[0].overlap(gb[0]) or inside(a, b) or inside(b, a):
            return 0.0
        d = min((gb[0].find_nearest(v)[3] for v in ga[1]), default=g)
        d = min([d] + [ga[0].find_nearest(v)[3] for v in gb[1]])
        return d if d is not None else g

    floating = []
    if len(per) > 1:
        for p in per:
            if p["name"] in may_float:
                continue
            # "*" を浮かせてよいとしたときは地面を数えず、ほかの部品とつながっているかだけを見る
            d = math.inf if "*" in may_float else max(0.0, p["min"][2])
            for o in per:
                if d <= tol:
                    break
                if o is not p:
                    d = min(d, gap(p, o))
            if d > tol:
                floating.append(f"{p['name']}（いちばん近い物まで {d:.3f}m）")
    if floating:
        out.append("地面にもほかの部品にも接していない部品がある: " + "、".join(floating[:6])
                   + "。位置や回転の軸（pivot の point）を確かめる。わざと浮かせるなら qm.expect(名前, floating=True)")
    for e in exp:
        if not e.get("size"):
            continue
        if e["target"] == "*":
            got, label = [hi[i] - lo[i] for i in range(3)], "全体"
        else:
            hit = [p for p in per if p["name"] == e["target"]]
            if not hit:
                out.append(f"qm.expect の対象「{e['target']}」というオブジェクトがない")
                continue
            got, label = [hit[0]["max"][i] - hit[0]["min"][i] for i in range(3)], e["target"]
        bad = []
        for axis, want, have in zip("XYZ", e["size"], got):
            if want is not None and abs(have - want) > max(0.005, abs(want) * e.get("tol", 0.03)):
                bad.append(f"{axis} {have:.3f}m（宣言 {want:.3f}m）")
        if bad:
            out.append(f"{label} の寸法が宣言と違う: " + "、".join(bad))
    return out


def resolve_catalog(per: list[dict]) -> list[dict]:
    """qm.catalog で登録された項目を、実際のオブジェクト名と外形の寸法に直す"""
    items = json.loads(bpy.context.scene.get("qm_catalog", "[]"))
    names = [p["name"] for p in per]
    out = []
    for it in items:
        pats = it.get("parts") or []
        objs = [n for n in names if any(n == p or n.startswith(p) for p in pats)]
        boxes = [p for p in per if p["name"] in objs and "min" in p]
        size = None
        if boxes:
            lo = [min(b["min"][i] for b in boxes) for i in range(3)]
            hi = [max(b["max"][i] for b in boxes) for i in range(3)]
            size = {"min": lo, "max": hi}
        labels = []
        for pre, text in (it.get("labels") or {}).items():
            hit = [n for n in objs if n == pre or n.startswith(pre)]
            if hit:
                labels.append({"prefix": pre, "text": text, "objects": hit})
        out.append({**it, "objects": objs, "box": size, "labels": labels})
    return out


def problems_of(q: dict, per: list[dict]) -> list[str]:
    def where(key: str) -> str:
        names = [p["name"] for p in per if p[key]]
        return f"（{', '.join(names[:6])}{' ほか' if len(names) > 6 else ''}）" if names else ""

    p = []
    if q["objects"] == 0 or q["faces"] == 0:
        p.append("メッシュがひとつもない")
    if q["ngons"]:
        p.append(f"Nゴン（5角形以上）が {q['ngons']} 枚ある{where('ngons')}。四角形に分割する")
    if q["faces"] and q["tris"] / q["faces"] > TRI_LIMIT:
        p.append(f"三角ポリゴンが {q['tris']} 枚（全体の {q['tris'] * 100 // q['faces']}%）ある{where('tris')}。できるだけ四角形にする")
    if q["bad_edges"]:
        p.append(f"3枚以上の面が共有している辺（非多様体）が {q['bad_edges']} 本ある{where('bad_edges')}")
    if q["flipped_edges"]:
        p.append(f"となりの面と向きが逆になっている辺が {q['flipped_edges']} 本ある{where('flipped_edges')}。"
                 "bmesh.ops.recalc_face_normals で向きをそろえる")
    if q["inward"]:
        p.append(f"法線が内向きのオブジェクトがある{where('inward')}。bmesh.ops.recalc_face_normals か面の反転で外向きにする")
    if q["dup_verts"]:
        p.append(f"同じ位置に重なった頂点が {q['dup_verts']} 個ある{where('dup_verts')}。共有するか bmesh.ops.remove_doubles でまとめる")
    if q["degenerate"]:
        p.append(f"面積がほぼゼロのつぶれた面が {q['degenerate']} 枚ある{where('degenerate')}")
    if q["loose_verts"] or q["loose_edges"]:
        p.append(f"面につながっていない頂点 {q['loose_verts']} 個・辺 {q['loose_edges']} 本がある"
                 f"{where('loose_verts') or where('loose_edges')}")
    if q["faces"] > FACE_LIMIT:
        p.append(f"面が {q['faces']:,} 枚と多すぎる。{FACE_LIMIT:,} 枚以下にする（サブディビジョンのレベルを下げる）")
    try:
        p += layout_problems(per)
    except Exception as e:  # 検査の失敗で実行全体を落とさない
        p.append(f"配置の検査に失敗: {e}")
    return p


def export_all(folder: Path) -> list[str]:
    errs = []
    if not any(o.type == "MESH" for o in bpy.context.scene.objects):
        return errs
    jobs = {
        "glb": lambda p: bpy.ops.export_scene.gltf(filepath=p, export_format="GLB", export_apply=True),
        # センチ単位で頂点に焼き込み、Maya / Unity で拡大率 1・回転 0 のまま正しい大きさになるようにする
        "fbx": lambda p: bpy.ops.export_scene.fbx(filepath=p, use_mesh_modifiers=True, object_types={"MESH"},
                                                  apply_scale_options="FBX_SCALE_NONE", apply_unit_scale=True,
                                                  bake_space_transform=True,
                                                  add_leaf_bones=False, bake_anim=False,
                                                  path_mode="COPY", embed_textures=True),  # テクスチャは FBX に埋め込む
        # OBJ はテクスチャを埋め込めないので、MTL と画像を同じフォルダに書き、まとめて zip にする
        "obj": lambda p: bpy.ops.wm.obj_export(filepath=p, apply_modifiers=True, export_materials=True, path_mode="COPY"),
        # STL は単位を持たないので、CAD で一般的なミリとして書く（1 = 1mm、Z が上）
        "stl": lambda p: bpy.ops.wm.stl_export(filepath=p, global_scale=1000.0, apply_modifiers=True, ascii_format=False),
    }
    for fmt, fn in jobs.items():
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                fn(str(folder / f"model.{fmt}"))
        except Exception as e:
            errs.append(f"{fmt.upper()} の書き出しに失敗: {e}")
    obj = folder / "model.obj"
    if obj.exists():
        import zipfile
        with zipfile.ZipFile(folder / "model_obj.zip", "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(folder.iterdir()):
                if f.name in ("model.obj", "model.mtl") or f.suffix.lower() in TEX_EXT:
                    z.write(f, f.name)
    return errs


# ---------------------------------------------------------------- マテリアルとテクスチャ

def _periodic_noise(np, rng, n: int, sigma: float, sigma_v: float | None = None):
    """つなぎ目なく繰り返せるなめらかなノイズ（0〜1）。sigma_v を大きくすると縦に流れる筋になる"""
    sv = sigma if sigma_v is None else sigma_v
    f = np.fft.fft2(rng.standard_normal((n, n)))
    kv, ku = np.fft.fftfreq(n)[:, None] ** 2, np.fft.fftfreq(n)[None, :] ** 2
    a = np.real(np.fft.ifft2(f * np.exp(-2 * math.pi ** 2 * (sigma ** 2 * ku + sv ** 2 * kv))))
    return (a - a.min()) / (a.max() - a.min() + 1e-9)


def make_sample_textures() -> None:
    """textures フォルダに、なければサンプルのテクスチャを作る（つなぎ目なく繰り返せる 512px）"""
    import numpy as np
    TEX_DIR.mkdir(parents=True, exist_ok=True)
    n = 512
    rng = np.random.default_rng(7)
    u = np.arange(n)[None, :].repeat(n, 0) / n   # 横 0〜1
    v = np.arange(n)[:, None].repeat(n, 1) / n   # 縦 0〜1（下から）

    def save(name, rgb):
        path = TEX_DIR / f"{name}.png"
        if path.exists():
            return
        img = bpy.data.images.new(f"_{name}", n, n, alpha=False)
        img.pixels = np.dstack([np.clip(rgb, 0, 1), np.ones((n, n))]).astype(np.float32).ravel()
        img.filepath_raw, img.file_format = str(path), "PNG"
        img.save()
        bpy.data.images.remove(img)

    # レンガ（1m 角に 13 段 × 4 個、半分ずらし、目地 1cm）
    rows, cols = 13, 4
    r = np.floor(v * rows).astype(int)
    uu = (u + (r % 2) * 0.5 / cols) % 1.0
    c = np.floor(uu * cols).astype(int)
    mortar = ((v * rows) % 1.0 < 0.13) | ((uu * cols) % 1.0 < 0.035)
    tone = rng.uniform(-0.08, 0.08, (rows, cols))[r % rows, c % cols]
    grain = _periodic_noise(np, rng, n, 2.0) - 0.5
    brick = np.dstack([0.56 + tone, 0.27 + tone * 0.6, 0.19 + tone * 0.4]) + grain[..., None] * 0.08
    save("Brick", np.where(mortar[..., None], np.array([0.72, 0.70, 0.66]) + grain[..., None] * 0.05, brick))

    # コンクリート（2m 角。大きなむらと細かい粒）
    big, fine = _periodic_noise(np, rng, n, 40.0), _periodic_noise(np, rng, n, 1.0)
    g = 0.52 + (big - 0.5) * 0.12 + (fine - 0.5) * 0.10
    save("Concrete", np.dstack([g, g * 0.99, g * 0.96]))

    # 木目（1m 角に板 5 枚。木目は板の長さ方向＝縦に流れる。板ごとに色を少し変える）
    planks = 5
    pk = np.floor(u * planks).astype(int)
    x = (u * planks) % 1.0                                   # 板の中の横位置
    warp = _periodic_noise(np, rng, n, 30.0, 90.0) - 0.5     # 木目のゆるいうねり
    grain = 0.5 + 0.5 * np.sin(2 * math.pi * (x * 7 + warp * 1.5 + pk * 0.37))
    streak = _periodic_noise(np, rng, n, 0.7, 25.0) - 0.5    # 縦に伸びた細い筋
    shade = rng.uniform(-0.06, 0.06, planks)[pk % planks]
    seam = x < 0.012
    base = 0.45 + shade + grain ** 3 * -0.10 + streak * 0.10
    wood = np.dstack([base * 1.18, base * 0.82, base * 0.52])
    save("Wood", np.where(seam[..., None], wood * 0.55, wood))

    # 確認用のグリッド（8 × 8 マス。列で色、行で明るさが変わるので向きと伸びが分かる）
    cu, cv = np.floor(u * 8), np.floor(v * 8)
    hue = cu / 8
    k_ = (np.dstack([hue * 6, hue * 6 + 4, hue * 6 + 2]) % 6)
    col = 1 - np.clip(np.minimum(k_, 4 - k_), 0, 1)
    col = 0.35 + col * 0.45 * (0.6 + 0.4 * ((cu + cv) % 2))[..., None] + (cv / 8)[..., None] * 0.15
    line = ((u * 8) % 1.0 < 0.02) | ((v * 8) % 1.0 < 0.02)
    save("UVGrid", np.where(line[..., None], 0.95, col))


def texture_files() -> dict[str, Path]:
    if not TEX_DIR.exists():
        return {}
    return {f.stem.lower(): f for f in sorted(TEX_DIR.iterdir()) if f.suffix.lower() in TEX_EXT}


def _base(name: str) -> str:
    return re.sub(r"\.\d{3}$", "", name)  # Blender が付ける ".001" を外す


def prepare_materials() -> list[dict]:
    """マテリアル名と同じ名前の画像を貼り、UV がなければ箱投影で作る。マテリアルの一覧を返す"""
    texs = texture_files()
    info: dict[str, dict] = {}
    tiles: dict[str, float] = {}
    for mat in bpy.data.materials:
        if mat.name.startswith("_") or mat.users == 0:
            continue
        path = texs.get(_base(mat.name).lower())
        if mat.node_tree is None:
            _use_nodes(mat)
        nt = mat.node_tree
        bsdf = next((nd for nd in nt.nodes if nd.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None:
            bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
            outn = next((nd for nd in nt.nodes if nd.type == "OUTPUT_MATERIAL"), None) or nt.nodes.new("ShaderNodeOutputMaterial")
            nt.links.new(bsdf.outputs[0], outn.inputs["Surface"])
        base = bsdf.inputs["Base Color"]
        gray = (0.8, 0.8, 0.8)
        # 色を mat.diffuse_color（ビューポートの色）にだけ入れた場合も、書き出しに色が乗るようにする
        if not base.is_linked and all(abs(a - b) < 1e-4 for a, b in zip(base.default_value[:3], gray)) \
                and any(abs(a - b) > 1e-4 for a, b in zip(mat.diffuse_color[:3], gray)):
            base.default_value = tuple(mat.diffuse_color)
        texture = None
        if base.is_linked:
            texture = "（スクリプトで設定済み）"
        elif path:
            tex = nt.nodes.new("ShaderNodeTexImage")
            tex.image = bpy.data.images.load(str(path), check_existing=True)
            nt.links.new(tex.outputs["Color"], base)
            texture = path.name
        tile = float(mat.get("tile", SAMPLE_TILES.get(path.stem if path else "", 1.0)))
        tiles[mat.name] = tile
        info[mat.name] = {"name": mat.name, "texture": texture, "tile": tile,
                          "color": [round(x, 3) for x in base.default_value[:3]]}

    done = set()
    for o in bpy.context.scene.objects:
        if o.type != "MESH" or o.data.name in done:
            continue
        done.add(o.data.name)
        if o.data.get("keep_uv") and o.data.uv_layers:
            continue  # スクリプトで作った UV を使う
        box_uv(o, [tiles.get(s.material.name, 1.0) if s.material else 1.0 for s in o.material_slots])
    return list(info.values())


def box_uv(o, slot_tiles: list[float]) -> None:
    """面の向きに合わせて X / Y / Z のいずれかから投影した UV を、実寸（メートル ÷ tile）で作る"""
    me = o.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    bm = bmesh.new()
    bm.from_mesh(me)
    uv = bm.loops.layers.uv.verify()
    mw = o.matrix_world
    nm = mw.to_3x3().inverted_safe().transposed()
    for f in bm.faces:
        nrm = (nm @ f.normal).normalized()
        tile = slot_tiles[f.material_index] if f.material_index < len(slot_tiles) else 1.0
        tile = tile if tile > 0 else 1.0
        ax = max(range(3), key=lambda i: abs(nrm[i]))
        for lp in f.loops:
            p = mw @ lp.vert.co
            if ax == 0:
                uu, vv = (p.y if nrm.x > 0 else -p.y), p.z
            elif ax == 1:
                uu, vv = (-p.x if nrm.y > 0 else p.x), p.z
            else:
                uu, vv = p.x, (p.y if nrm.z > 0 else -p.y)
            lp[uv].uv = (uu / tile, vv / tile)
    bm.to_mesh(me)
    bm.free()


# ---------------------------------------------------------------- 画像（AI が形を目で確かめる用）

VIEWS = {  # 視線の向き（カメラ → 被写体）
    "persp": (-1.0, 1.25, -0.8),
    "front": (0.0, 1.0, 0.0),      # 正面（-Y 側から）
    "back": (0.0, -1.0, 0.0),      # 背面（+Y 側から）
    "side": (-1.0, 0.0, 0.0),      # 右（+X 側から）
    "left": (1.0, 0.0, 0.0),       # 左（-X 側から）
    "top": (0.0, 0.0, -1.0),       # 真上
    "bottom": (0.0, 0.0, 1.0),     # 真下
}


def _nice(x: float) -> float:
    """1・2・5 × 10^n のうち、x 以上でいちばん近い値（グリッドの間隔）"""
    e = 10 ** math.floor(math.log10(max(x, 1e-9)))
    for k in (1, 2, 5, 10):
        if k * e >= x:
            return k * e
    return 10 * e


def _axis_label(v) -> str:
    i = max(range(3), key=lambda k: abs(v[k]))
    return ("+" if v[i] > 0 else "-") + "XYZ"[i]


def _use_nodes(idblock) -> None:
    """Blender 5 では use_nodes が非推奨（常に有効）。古い版のために、あるときだけ設定する"""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        if hasattr(idblock, "use_nodes"):
            idblock.use_nodes = True


def render_views(views: list[str], size: int, look: str = "clay", wire: bool = True, ortho: bool = False,
                 grid: float | None = None) -> tuple[bytes, list[str]]:
    """Cycles（CPU）で絵を描き、(PNG のバイト列, 視点ごとの説明) を返す。複数の視点は横に並べる。
    look="clay" は粘土色、"material" はマテリアルとテクスチャのまま。wire でポリゴンの辺を重ねる。
    ortho=True なら遠近のない正投影で、白地に寸法のグリッド（間隔 grid メートル、省略時は自動）を引いた図面風にする"""
    import numpy as np

    sc = bpy.context.scene
    meshes = [o for o in sc.objects if o.type == "MESH"]
    if not meshes:
        raise RuntimeError("シーンにメッシュがありません")
    temp: list = []
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in meshes:
        ev = o.evaluated_get(dg)
        pts += [o.matrix_world @ v.co for v in ev.data.vertices]
    lo = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    center, radius = (lo + hi) / 2, max((hi - lo).length / 2, 1e-3)

    def material(name, color, rough=0.6):
        m = bpy.data.materials.new(name)
        _use_nodes(m)
        bsdf = m.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (*color, 1)
        bsdf.inputs["Roughness"].default_value = rough
        temp.append(m)
        return m

    clay, edge = material("_clay", (0.62, 0.64, 0.68)), material("_edge", (0.03, 0.035, 0.045), 0.9)
    old_mats = {}
    for o in meshes:  # 本体は粘土色に（look="clay" のとき）、辺はワイヤーフレームの複製で描く
        if look == "clay":
            old_mats[o.name] = len(o.material_slots)
            if not o.material_slots:
                o.data.materials.append(None)
            for slot in o.material_slots:
                slot.link = "OBJECT"
                slot.material = clay
        if not wire:
            continue
        wm = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
        wo = bpy.data.objects.new("_wire", wm)
        wo.matrix_world = o.matrix_world
        sc.collection.objects.link(wo)
        mod = wo.modifiers.new("w", "WIREFRAME")
        mod.thickness = radius * 3.2 / size  # 画面上でおよそ 1.5 ピクセル
        mod.use_replace = True
        mod.use_even_offset = False
        wm.materials.clear()
        wm.materials.append(edge)
        temp += [wo, wm]
    world = bpy.data.worlds.new("_world")
    _use_nodes(world)
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.22, 0.23, 0.26, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
    sun_d = bpy.data.lights.new("_sun", "SUN")
    sun_d.energy = 3.0
    sun = bpy.data.objects.new("_sun", sun_d)
    sun.rotation_euler = (math.radians(50), 0, math.radians(30))
    sc.collection.objects.link(sun)
    cam_d = bpy.data.cameras.new("_cam")
    cam_d.lens = 50
    if ortho:
        cam_d.type = "ORTHO"
    cam = bpy.data.objects.new("_cam", cam_d)
    sc.collection.objects.link(cam)
    temp += [world, sun, sun_d, cam, cam_d]
    old = (sc.world, sc.camera, sc.render.engine, sc.render.resolution_x, sc.render.resolution_y, sc.render.filepath)
    sc.world, sc.camera = world, cam
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 12
    sc.cycles.use_denoising = False
    sc.render.resolution_x = sc.render.resolution_y = size
    sc.render.film_transparent = bool(ortho)
    tiles, notes = [], []
    tmp = OUT / "_render.png"
    try:
        for name in views:
            d = mathutils.Vector(VIEWS[name]).normalized()
            dist = radius / math.tan(cam_d.angle / 2) * 1.15
            cam.location = center - d * dist
            # 真上からは向きが決まらないので、画面の上が +Y（奥）になるよう直接指定する
            if name == "top":
                cam.rotation_euler = (0, 0, 0)
            elif name == "bottom":
                cam.rotation_euler = (math.pi, 0, 0)
            else:
                cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
            cam_d.clip_start, cam_d.clip_end = dist / 100, dist * 10
            rot = cam.rotation_euler.to_matrix()
            right, up = rot.col[0], rot.col[1]
            if ortho:
                corners = [mathutils.Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
                ext = max(max(c.dot(right) for c in corners) - min(c.dot(right) for c in corners),
                          max(c.dot(up) for c in corners) - min(c.dot(up) for c in corners))
                cam_d.ortho_scale = max(ext * 1.08, 1e-3)
            sc.render.filepath = str(tmp)
            with contextlib.redirect_stdout(io.StringIO()):
                bpy.ops.render.render(write_still=True)
            img = bpy.data.images.load(str(tmp))
            arr = np.array(img.pixels[:], dtype=np.float32).reshape(size, size, 4)
            bpy.data.images.remove(img)
            if ortho:
                arr, note = _drawing_sheet(np, arr, name, size, cam_d.ortho_scale, center, right, up, grid)
                notes.append(note)
            tiles.append(arr)
    finally:
        sc.world, sc.camera, sc.render.engine, sc.render.resolution_x, sc.render.resolution_y, sc.render.filepath = old
        for o in meshes:
            if o.name in old_mats:
                for slot in o.material_slots:
                    slot.material = None
                    slot.link = "DATA"
                if not old_mats[o.name]:
                    o.data.materials.clear()
        for t in temp:
            coll = {bpy.types.Object: bpy.data.objects, bpy.types.Mesh: bpy.data.meshes, bpy.types.Material: bpy.data.materials,
                    bpy.types.World: bpy.data.worlds, bpy.types.Camera: bpy.data.cameras}.get(type(t))
            if coll is None and isinstance(t, bpy.types.Light):
                coll = bpy.data.lights
            with contextlib.suppress(Exception):
                coll.remove(t)
    # 横に並べて1枚の PNG にする（pixels は下から上の順）
    if ortho:  # 図と図の間に白い余白
        gap = np.ones((size, 6, 4), dtype=np.float32)
        tiles = [t for k, tile in enumerate(tiles) for t in ((gap, tile) if k else (tile,))]
    sheet = np.concatenate(tiles, axis=1)
    h, w = sheet.shape[:2]
    out = bpy.data.images.new("_sheet", w, h, alpha=False)
    out.pixels = sheet.ravel()
    out.filepath_raw = str(tmp)
    out.file_format = "PNG"
    out.save()
    bpy.data.images.remove(out)
    data = tmp.read_bytes()
    tmp.unlink(missing_ok=True)
    return data, notes


def _drawing_sheet(np, arr, name, size, scale, center, right, up, grid):
    """正投影の絵を、白地にグリッドを引いた図面風にする。(画像, 説明) を返す"""
    alpha = arr[..., 3:4]
    paper = np.ones_like(arr)
    out = arr * alpha + paper * (1 - alpha)          # 背景を白に
    out[..., 3] = 1.0
    ppm = size / scale                               # 1 メートルあたりのピクセル数
    g = grid or _nice(scale / 25)
    bg = (alpha[..., 0] < 0.5)
    cr, cu = center.dot(right), center.dot(up)
    for axis_val, coord_c, is_col in ((right, cr, True), (up, cu, False)):
        lo_v = coord_c - scale / 2
        k0, k1 = math.ceil(lo_v / g), math.floor((lo_v + scale) / g)
        for k in range(k0, k1 + 1):
            px = int(round(size / 2 + (k * g - coord_c) * ppm))
            if not 0 <= px < size:
                continue
            if k == 0:
                col = (0.85, 0.30, 0.30)              # 原点を通る線
            elif k % 5 == 0:
                col = (0.55, 0.65, 0.80)              # 太線（5 マスごと）
            else:
                col = (0.84, 0.88, 0.94)
            if is_col:
                m = bg[:, px]
                out[m, px, :3] = col
            else:
                m = bg[px, :]
                out[px, m, :3] = col
    mm = lambda v: f"{v * 1000:g}"
    note = (f"{name}: 右 = {_axis_label(right)}・上 = {_axis_label(up)}、グリッド 1 マス {mm(g)}mm（太線 {mm(5 * g)}mm、"
            f"赤線 = 座標 0）、1px ≒ {scale / size * 1000:.2f}mm、図の中心 = ({mm(round(center.x, 4))}, "
            f"{mm(round(center.y, 4))}, {mm(round(center.z, 4))})mm")
    return out, note


# ================================================================ 実行の記録

def first_comment(code: str) -> str:
    for line in code.splitlines():
        s = line.strip()
        if s.startswith("#"):
            return s.lstrip("#").strip()[:60]
        if s:
            break
    return ""


def runs() -> list[dict]:
    """output/runs/ にある実行の一覧（番号順）。書き終わった meta.json だけを読む"""
    out = []
    for d in RUNS_DIR.iterdir():
        if not (d.is_dir() and d.name.isdigit()):
            continue
        r = _RUN_CACHE.get(d.name)
        if r is None:
            try:
                r = json.loads((d / "meta.json").read_text(encoding="utf-8"))
            except Exception:
                continue  # まだ実行中か、壊れている
            _RUN_CACHE[d.name] = r
        out.append(r)
    return sorted(out, key=lambda r: r["id"])


def get_run(run_id: int | None, ok_only: bool = True) -> dict | None:
    all_runs = runs()
    if run_id is None:
        cands = [r for r in all_runs if r["ok"] or not ok_only]
        return cands[-1] if cands else None
    return next((r for r in all_runs if r["id"] == run_id), None)


def new_run_folder() -> tuple[int, Path]:
    """次の番号のフォルダを作る。ほかの bpy モデラーと同時でも番号がぶつからないよう、作れた番号を使う"""
    run_id = max((int(d.name) for d in RUNS_DIR.iterdir() if d.name.isdigit()), default=0) + 1
    while True:
        folder = RUNS_DIR / f"{run_id:04d}"
        try:
            folder.mkdir()
            return run_id, folder
        except FileExistsError:
            run_id += 1


def ensure_scene(run: dict) -> None:
    """指定の実行の結果がシーンに入っていなければ、スクリプトを実行し直して作る"""
    if STATE["scene_run"] == run["id"]:
        return
    reset_scene()
    ok, _ = run_code((RUNS_DIR / f"{run['id']:04d}" / "script.py").read_text(encoding="utf-8"))
    if not ok:
        STATE["scene_run"] = None
        raise RuntimeError(f"実行 {run['id']} を作り直せませんでした")
    prepare_materials()
    STATE["scene_run"] = run["id"]


def execute(code: str, title: str) -> dict:
    with LOCK:
        run_id, folder = new_run_folder()
        (folder / "script.py").write_text(code, encoding="utf-8")
        t0 = time.time()
        reset_scene()
        ok, out = run_code(code)
        STATE["scene_run"] = None
        run = {"id": run_id, "title": title or first_comment(code) or f"実行 {run_id}", "time": time.strftime("%Y-%m-%d %H:%M:%S"),
               "ok": ok, "output": out[-6000:], "stats": None, "objects": [], "problems": [], "files": [], "materials": [],
               "units": bpy.context.scene.get("qm_units", "cm"), "catalog": []}
        if ok:
            stats, per, wire = inspect_scene()
            (folder / "wire.json").write_text(json.dumps([round(x, 5) for x in wire]), encoding="utf-8")
            try:
                materials, errs = prepare_materials(), []
            except Exception as e:  # テクスチャで失敗しても形は書き出す
                materials, errs = [], [f"マテリアル・テクスチャの準備に失敗: {e}"]
            errs += export_all(folder)
            run["catalog"] = resolve_catalog(per)
            run.update(stats=stats, objects=per, problems=problems_of(stats, per) + errs, materials=materials,
                       files=[f for f in FORMATS if (folder / f"model.{f}").exists()])
            STATE["scene_run"] = run_id
        run["seconds"] = round(time.time() - t0, 2)
        (folder / "meta.json").write_text(json.dumps(run, ensure_ascii=False, indent=1), encoding="utf-8")
        _RUN_CACHE[folder.name] = run
        log(f"[run {run_id}] {'OK' if ok else 'ERROR'} {run['title']}")
        return run


def report(run: dict) -> str:
    lines = [f"実行 {run['id']}「{run['title']}」: {'成功' if run['ok'] else 'エラー'}（{run['seconds']} 秒）"]
    if not run["ok"]:
        lines += ["", "エラー:", run["output"].strip()[-3000:]]
        lines += ["", "直したスクリプト全体を run_script でもう一度実行してください。"]
        return "\n".join(lines)
    s = run["stats"]
    pct = s["quads"] * 100 // s["faces"] if s["faces"] else 0
    lines += ["",
              f"合計: オブジェクト {s['objects']} / 頂点 {s['verts']:,} / 面 {s['faces']:,}"
              f"（四角形 {s['quads']:,} = {pct}%、三角形 {s['tris']:,}、Nゴン {s['ngons']:,}）",
              f"開いている辺 {s['boundary_edges']:,}（穴や板状の部品の縁。意図したものなら問題ない）",
              "", "オブジェクトごと（大きさは 幅X×奥行Y×高さZ）:"]
    if run.get("units") == "mm":
        lines[-1] = "オブジェクトごと（大きさは 幅X×奥行Y×高さZ、範囲はワールド座標。単位ミリ）:"
    for o in run["objects"][:40]:
        extra = [f"{label} {o[k]}" for k, label in (("ngons", "Nゴン"), ("bad_edges", "非多様体"), ("flipped_edges", "逆向きの辺"),
                                                    ("inward", "内向き"), ("dup_verts", "重複頂点"), ("degenerate", "つぶれた面"),
                                                    ("loose_verts", "孤立頂点")) if o[k]]
        if o["boundary_edges"]:
            extra.append(f"開いている辺 {o['boundary_edges']}")
        size = ""
        if "min" in o:
            if run.get("units") == "mm":
                w, d, h = (round((o["max"][i] - o["min"][i]) * 1000, 1) for i in range(3))
                size = (f" ／ {w:g}×{d:g}×{h:g}mm（X {o['min'][0] * 1000:.1f}〜{o['max'][0] * 1000:.1f}、"
                        f"Y {o['min'][1] * 1000:.1f}〜{o['max'][1] * 1000:.1f}、Z {o['min'][2] * 1000:.1f}〜{o['max'][2] * 1000:.1f}mm）")
            else:
                w, d, h = (round((o["max"][i] - o["min"][i]) * 100, 1) for i in range(3))
                size = f" ／ {w:g}×{d:g}×{h:g}cm（高さ {o['min'][2] * 100:.1f}〜{o['max'][2] * 100:.1f}cm）"
        lines.append(f"- {o['name']}: 面 {o['faces']:,}（四角 {o['quads']:,} / 三角 {o['tris']:,}）{size}"
                     + (f" ⚠ {'、'.join(extra)}" if extra else ""))
    if len(run["objects"]) > 40:
        lines.append(f"- ほか {len(run['objects']) - 40} 個")
    if run.get("catalog"):
        lines += ["", f"図鑑の項目: {len(run['catalog'])} 件（ビューアーの「図鑑」で見られる）"]
        for c in run["catalog"][:30]:
            lines.append(f"- {c['title']}（{c['key']}）: 部品 {len(c['objects'])} 個" + ("" if c["objects"] else " ⚠ 該当するオブジェクトがない"))
    mats = run.get("materials") or []
    if mats:
        lines += ["", "マテリアル（UV は面の向きに合わせた箱投影で自動作成。mesh[\"keep_uv\"] = True なら自分の UV を使う）:"]
        for m in mats:
            tex = f"テクスチャ {m['texture']}（1枚 = {m['tile']:g}m）" if m["texture"] else f"色のみ {tuple(m['color'])}"
            lines.append(f"- {m['name']}: {tex}")
    if run["output"].strip():
        lines += ["", "print の出力:", run["output"].strip()[-1500:]]
    if run["problems"]:
        lines += ["", "検査で見つかった問題（形は保ったまま直してください）:"] + [f"- {p}" for p in run["problems"]]
    else:
        lines += ["", "検査（トポロジー・配置・寸法）を通りました。"]
    if VIEWER["url"]:
        lines += ["", f"ビューアー: {VIEWER['url']} に表示しています。形を目で確かめるには render を使ってください。"]
    else:
        lines += ["", "ビューアーは開けていません（ポートが空いていません）。形を目で確かめるには render を使ってください。"]
    return "\n".join(lines)


# ================================================================ MCP（AI の操作口）

GUIDE = """Blender（GUI なし）でメッシュを作るツールです。手作業で丁寧にモデリングしたような、
四角ポリゴン主体のきれいなメッシュを、bpy の Python スクリプトで作ってください。

進め方:
0. 最初に qm_help を読む。箱・円柱・回転体・管・球・穴埋め・回転の軸などは qm の関数で作ると、四角形だけのきれいな面になり、書き間違いも減る
1. run_script にスクリプト全体を渡して実行する（毎回まっさらな空のシーンから実行される）。
   主な部品の寸法は qm.expect("名前", size=(幅, 奥行, 高さ)) で宣言しておくと、サーバーが照合する
2. 返ってくるトポロジーの検査結果を読み、問題があれば形を保ったまま直して、スクリプト全体をもう一度実行する
3. render で絵を見て、頼まれた形になっているかを確かめる。違えば直す（テクスチャは look="material" で見る）。
   寸法や位置合わせは render(views=["front","side","top"], ortho=True) の正投影（ミリのグリッド付き）で確かめる
4. 問題がなくなったら、ユーザーに結果を伝える。保存先を頼まれたら export を使う

実行環境:
- bpy, bmesh, mathutils, math, qm, f1, Vector, Matrix は import 済み。3D ビューや UI はない（F1 は f1_help を読む）
- 単位はメートルで実寸。Z が上。接地するものは原点を底面の中心に置く。
  精密な部品や図面用は qm.units("mm") で報告をミリにし、寸法は「120 * qm.MM」のようにミリで書くとよい
- メッシュは bmesh か bpy.data で直接組み立てる。bpy.ops は 3D ビューがないと動かないものがあるので、
  プリミティブ追加・モディファイア・オブジェクトモードの操作程度にとどめる
- オブジェクトには分かりやすい英語の名前を付ける。ライト・カメラは不要
- ファイルの読み書き、ネットワーク、レンダリングはしない（書き出しはサーバーが自動で行う）

マテリアルとテクスチャ:
- 部品や面ごとに、名前付きのマテリアルを作って割り当てる（obj.data.materials.append(mat) と、面の material_index）
- list_textures にある画像と同じ名前のマテリアル（例: "Brick", "Concrete", "Wood"）には、その画像が自動で貼られる
- 色だけでよい部分は、Principled BSDF の Base Color を設定する（ガラスなら Alpha や Transmission も使ってよい）
- UV は作らなくてよい。サーバーが面の向きに合わせた箱投影で、実寸（メートル）基準の UV を作る。
  1枚の画像が何メートル分かは mat["tile"] = 1.5 のように指定する（サンプルは list_textures に目安がある）
- 自分で UV を作った場合は mesh["keep_uv"] = True を付ける（そのメッシュは自動で作り直さない）
- 貼り具合は render(look="material") で確かめる

トポロジーの品質（最重要）:
- 四角ポリゴン主体にする。Nゴンは作らない。三角形は避けられない箇所（極など）だけ（全体の 10% 未満）
- エッジの流れを形状に沿わせ、間隔はなるべく均等にする
- サブディビジョンで丸めるなら、角を保ちたい所にサポートエッジループを入れる
- 円柱などのフタは Nゴンにせず、四角形のグリッド状か、少なくとも三角ファンにする
- 法線は外向き、重複頂点なし、孤立頂点なし、非多様体なし
- 部品は地面か、ほかの部品に接するように置く（浮いていると検査で指摘される）
- モディファイア（Subdivision Surface, Mirror, Solidify, Bevel など）は使ってよい。
  書き出し時に適用された形が最終結果になるので、面数が膨らみすぎないようにする（目安は合計 5 万面まで）"""

mcp = MCPServer("bpy-modeler", instructions=GUIDE)


@mcp.tool(structured_output=False)
async def run_script(code: str, title: str = "") -> str:
    """bpy の Python スクリプトを、まっさらな空のシーンで実行し、トポロジーの検査結果を返す。
    結果はビューアーに表示され、GLB / FBX / OBJ にも自動で書き出される。
    code: スクリプト全体（bpy, bmesh, mathutils, math は import 済み。Z が上、メートル単位）
    title: この実行の短い説明（省略時はスクリプト1行目のコメント）"""
    return report(execute(code, title))


@mcp.tool(structured_output=False)
async def render(views: list[str] | None = None, size: int = 384, run: int | None = None,
                 look: str = "clay", wire: bool = True, ortho: bool = False, grid_mm: float | None = None) -> list:
    """結果を絵にして見る（粘土色の面に、黒い線でポリゴンの辺を描いたもの）。
    look: "clay"（粘土色。形とトポロジーを見る）か "material"（マテリアルとテクスチャのまま）
    wire: ポリゴンの辺を重ねるか
    ortho: True なら遠近のない正投影で、白地にミリのグリッドを引いた図面風にする（寸法・位置合わせの確認に）
    grid_mm: グリッドの間隔（ミリ。省略時は大きさに合わせて 1・2・5 × 10^n から自動）
    views: "persp"（斜め前）, "front"（正面 -Y 側から）, "back"（背面）, "side"（右 +X 側から）, "left"（左）,
           "top"（真上）, "bottom"（真下）から選ぶ。
           省略時は ["persp", "front", "side"]。複数なら横に並べる
    size: 1視点あたりの大きさ（128〜768 ピクセル）
    run: 何番目の実行を描くか（省略時は最後に成功した実行）"""
    views = views or ["persp", "front", "side"]
    bad = [v for v in views if v not in VIEWS]
    if bad:
        return [f"views に使えるのは {', '.join(VIEWS)} です（{', '.join(bad)} は使えません）"]
    with LOCK:
        target = get_run(run)
        if not target or not target["ok"]:
            return ["描ける実行がありません。先に run_script で形を作ってください"]
        ensure_scene(target)
        png, notes = render_views(views[:4], max(128, min(int(size), 768)), "material" if look == "material" else "clay",
                                  bool(wire), bool(ortho), grid_mm / 1000 if grid_mm else None)
    head = f"実行 {target['id']}「{target['title']}」: 左から {', '.join(views[:4])}" + ("（正投影）" if ortho else "")
    return ["\n".join([head] + notes), Image(data=png, format="png")]


@mcp.tool(structured_output=False)
async def qm_help() -> str:
    """スクリプトの中で使える qm（四角ポリゴン主体のモデリング用の関数）の説明と例。最初に一度読む"""
    return qm.HELP


@mcp.tool(structured_output=False)
async def f1_help() -> str:
    """F1 マシン（2026 年規定）の部品を作る f1 の説明。F1・フォーミュラカーを作るときに読む"""
    return f1.HELP


@mcp.tool(structured_output=False)
async def list_textures() -> str:
    """貼れるテクスチャの一覧。この名前のマテリアルを作ると、その画像が貼られる"""
    texs = texture_files()
    if not texs:
        return f"テクスチャがありません（{TEX_DIR} に画像を置くと使えます）"
    rows = []
    for f in texs.values():
        hint = f"（1枚 = {SAMPLE_TILES[f.stem]:g}m の目安）" if f.stem in SAMPLE_TILES else ""
        rows.append(f"- {f.stem}: {f.name}{hint}")
    return f"マテリアル名に使える名前（大文字小文字は区別しない。置き場所: {TEX_DIR}）:\n" + "\n".join(rows)


@mcp.tool(structured_output=False)
async def list_runs(limit: int = 20) -> str:
    """これまでの実行の一覧（番号・説明・成否・面数・問題の数）"""
    all_runs = runs()
    if not all_runs:
        return "まだ実行がありません"
    rows = []
    for r in all_runs[-limit:]:
        s = r["stats"] or {}
        state = "OK" if r["ok"] and not r["problems"] else ("問題あり" if r["ok"] else "エラー")
        rows.append(f"{r['id']}: {r['title']} ／ {state} ／ 面 {s.get('faces', '-')} ／ {r['time']}")
    return "\n".join(rows)


@mcp.tool(structured_output=False)
async def get_script(run: int | None = None) -> str:
    """指定した実行のスクリプトを返す（省略時は最後に成功した実行）。前の版から作り直すときに使う"""
    r = get_run(run, ok_only=run is None)
    if not r:
        return "その実行は見つかりません"
    return (RUNS_DIR / f"{r['id']:04d}" / "script.py").read_text(encoding="utf-8")


@mcp.tool(structured_output=False)
async def export(directory: str, name: str = "model", formats: list[str] | None = None, run: int | None = None) -> str:
    """書き出したファイルを指定のフォルダにコピーする（ユーザーに保存先を頼まれたとき）。
    directory: 保存先のフォルダ（なければ作る）
    name: ファイル名（拡張子なし）
    formats: "fbx", "obj", "glb" から選ぶ（省略時はすべて）
    run: 何番目の実行か（省略時は最後に成功した実行）"""
    r = get_run(run)
    if not r or not r["ok"]:
        return "書き出せる実行がありません"
    formats = formats or list(FORMATS)
    safe = re.sub(r'[\\/:*?"<>|]+', "_", name).strip() or "model"
    dest = Path(directory).expanduser()
    dest.mkdir(parents=True, exist_ok=True)
    done = []
    folder = RUNS_DIR / f"{r['id']:04d}"
    for f in formats:
        src = folder / f"model.{f}"
        if not src.exists():
            continue
        if f == "obj":  # OBJ は MTL と画像も一緒に置く
            text = src.read_text(encoding="utf-8").replace("mtllib model.mtl", f"mtllib {safe}.mtl")
            (dest / f"{safe}.obj").write_text(text, encoding="utf-8")
            if (folder / "model.mtl").exists():
                shutil.copyfile(folder / "model.mtl", dest / f"{safe}.mtl")
                done.append(str(dest / f"{safe}.mtl"))
            for img in folder.iterdir():
                if img.suffix.lower() in TEX_EXT:
                    shutil.copyfile(img, dest / img.name)
        else:
            shutil.copyfile(src, dest / f"{safe}.{f}")
        done.append(str(dest / f"{safe}.{f}"))
    return "保存しました:\n" + "\n".join(done) if done else "該当するファイルがありません"


# ================================================================ ビューアー（ブラウザ）

def run_public(r: dict) -> dict:
    return {**{k: r[k] for k in ("id", "title", "time", "ok", "stats", "problems", "files", "seconds")},
            "materials": r.get("materials", []), "catalog_count": len(r.get("catalog") or [])}


async def page_catalog(_: Request):
    return FileResponse(ROOT / "static" / "catalog.html", headers={"Cache-Control": "no-store"})


async def page_index(_: Request):
    return FileResponse(ROOT / "static" / "index.html", headers={"Cache-Control": "no-store"})


async def api_runs(_: Request):
    return JSONResponse({"app": "bpy-modeler", "out": str(OUT), "runs": [run_public(r) for r in runs()],
                         "port": ARGS.port, "stdio": ARGS.stdio},
                        headers={"Cache-Control": "no-store"})


async def api_run(req: Request):
    r = get_run(int(req.path_params["run_id"]), ok_only=False)
    if not r:
        return Response(status_code=404)
    code = (RUNS_DIR / f"{r['id']:04d}" / "script.py").read_text(encoding="utf-8")
    return JSONResponse({**r, "code": code, "report": report(r)}, headers={"Cache-Control": "no-store"})


async def api_file(req: Request):
    run_id, name = int(req.path_params["run_id"]), req.path_params["name"]
    if name not in ("wire.json", "model_obj.zip", *(f"model.{f}" for f in FORMATS)):
        return Response(status_code=404)
    f = RUNS_DIR / f"{run_id:04d}" / name
    if not f.exists():
        return Response(status_code=404)
    media = {"glb": "model/gltf-binary", "fbx": "application/octet-stream", "obj": "text/plain", "json": "application/json",
             "zip": "application/zip", "stl": "model/stl"}
    download = name.endswith((".fbx", ".obj", ".zip", ".stl"))
    return FileResponse(f, media_type=media[name.rsplit(".", 1)[1]], filename=f"run{run_id:04d}_{name}" if download else None,
                        headers={"Cache-Control": "no-store"})


async def api_texture(req: Request):
    f = texture_files().get(Path(req.path_params["name"]).stem.lower())
    if not f or f.name != req.path_params["name"]:
        return Response(status_code=404)
    return FileResponse(f)


VIEW_ROUTES = [
    ("/", page_index),
    ("/catalog", page_catalog),
    ("/textures/{name}", api_texture),
    ("/api/runs", api_runs),
    ("/api/runs/{run_id:int}", api_run),
    ("/api/runs/{run_id:int}/{name}", api_file),
]


def port_free(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if os.name != "nt":
            # 直前まで使っていたポート（TIME_WAIT）を「使用中」と誤判定しないように。
            # 待ち受け中のポートには、これを付けても bind できない（Windows では付けると重ねて bind できてしまうので付けない）
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def probe(port: int) -> dict | None:
    """そのポートで動いているのが bpy モデラーなら、その情報を返す"""
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/runs", timeout=1.5) as r:
            data = json.load(r)
        return data if data.get("app") == "bpy-modeler" else None
    except Exception:
        return None


def same_output(info: dict | None) -> bool:
    return bool(info) and Path(info.get("out", "")).resolve() == OUT


def start_viewer_thread(port: int) -> None:
    """ビューアーを別スレッドで動かす（ファイルを配るだけで Blender には触れない）"""
    viewer = Starlette(routes=[Route(p, fn) for p, fn in VIEW_ROUTES])
    server = uvicorn.Server(uvicorn.Config(viewer, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(50):  # 待ち受けが始まるまで待つ（最大5秒）
        if server.started:
            break
        time.sleep(0.1)


def main() -> None:
    try:
        make_sample_textures()
    except Exception as e:
        log(f"サンプルのテクスチャを作れませんでした: {e}")
    reset_scene()
    if ARGS.stdio:
        # ポートが使われていたら、同じ output を見ている bpy モデラーのビューアーに相乗りする。
        # 別のものなら、空いている次のポートで開く
        for port in range(ARGS.port, ARGS.port + 11):
            if port_free(port):
                start_viewer_thread(port)
                VIEWER.update(url=f"http://127.0.0.1:{port}", shared=False)
                break
            if same_output(probe(port)):
                VIEWER.update(url=f"http://127.0.0.1:{port}", shared=True)
                break
        if VIEWER["url"]:
            how = "（すでに動いている bpy モデラーのビューアーに表示）" if VIEWER["shared"] else ""
            log(f"bpy モデラー（stdio）: ビューアー {VIEWER['url']}{how}")
        else:
            log(f"bpy モデラー（stdio）: ポート {ARGS.port}〜{ARGS.port + 10} が空いていないので、ビューアーは開きません")
        mcp.run("stdio")  # Blender はメインスレッドで動く
        return

    url = f"http://127.0.0.1:{ARGS.port}"
    if not port_free(ARGS.port):
        info = probe(ARGS.port)
        if same_output(info):
            log(f"bpy モデラーはすでに動いています（{'Claude Desktop などが起動したもの' if info.get('stdio') else '別の画面で起動したもの'}）。")
            log(f"ビューアーは {url} で見られます。この画面は閉じて構いません。")
            if info.get("stdio"):
                log("Claude Code からも使いたい場合は、Claude Desktop を終了してから起動し直してください。")
        else:
            log(f"ポート {ARGS.port} はほかのプログラムが使っています。--port 8001 のように別の番号で起動してください。")
        sys.exit(1)
    for p, fn in VIEW_ROUTES:
        mcp.custom_route(p, ["GET"])(fn)
    app = mcp.streamable_http_app(host="127.0.0.1")
    VIEWER.update(url=url)
    log(f"bpy モデラー: ビューアー {url} ／ AI の接続先 {url}/mcp")
    # 生成されたコードを実行するサーバーなので、自分の PC からだけ受け付ける
    uvicorn.run(app, host="127.0.0.1", port=ARGS.port, log_level="warning")


if __name__ == "__main__":
    main()
