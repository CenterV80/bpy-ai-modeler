"""
Claude Desktop の設定ファイル（claude_desktop_config.json）に bpy-modeler を登録する。

  python setup_claude_desktop.py            設定ファイルを探して登録する
  python setup_claude_desktop.py --config <パス>   設定ファイルを指定する
  python setup_claude_desktop.py --remove   登録を消す

・この仮想環境の python と、このフォルダの server.py を、--stdio 付きで登録する
・もとからある設定はそのまま残す。書き換える前に .bak を作る
・手で追記して { … } が2つ並んでしまったファイルも、1つにまとめて直す
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import sys
from pathlib import Path

NAME = "bpy-modeler"
HERE = Path(__file__).resolve().parent


def candidates() -> list[Path]:
    """Claude Desktop が使う設定ファイルの候補（新しい版の置き場所を先に）"""
    out: list[Path] = []
    local, roaming = os.environ.get("LOCALAPPDATA"), os.environ.get("APPDATA")
    if local:
        # 新しい版: %LOCALAPPDATA%\Claude-Data\claude_<英数字>\claude_desktop_config.json
        out += [Path(p) for p in glob.glob(os.path.join(local, "Claude-Data", "*", "claude_desktop_config.json"))]
        out += [Path(p) for p in glob.glob(os.path.join(local, "Packages", "Claude_*", "LocalCache", "Roaming", "Claude",
                                                         "claude_desktop_config.json"))]
    if roaming:
        out.append(Path(roaming, "Claude", "claude_desktop_config.json"))
    home = Path.home()
    out.append(home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json")  # macOS
    return out


def load(path: Path) -> dict:
    """JSON を読む。{ … } が複数並んでいたら、順に重ねて1つにする"""
    text = path.read_text(encoding="utf-8-sig") if path.exists() else ""
    if not text.strip():
        return {}
    dec, pos, merged = json.JSONDecoder(), 0, {}
    while pos < len(text):
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos >= len(text):
            break
        obj, pos = dec.raw_decode(text, pos)
        if not isinstance(obj, dict):
            raise ValueError("設定ファイルの一番外側が { } ではありません")
        servers = {**merged.get("mcpServers", {}), **obj.get("mcpServers", {})}
        merged.update(obj)
        if servers:
            merged["mcpServers"] = servers
    return merged


def main() -> int:
    ap = argparse.ArgumentParser(description="Claude Desktop に bpy-modeler を登録する")
    ap.add_argument("--config", help="claude_desktop_config.json のパス（省略時は自動で探す）")
    ap.add_argument("--remove", action="store_true", help="登録を消す")
    args = ap.parse_args()

    if args.config:
        path = Path(args.config).expanduser()
    else:
        found = [p for p in candidates() if p.exists()]
        if not found:
            print("claude_desktop_config.json が見つかりませんでした。")
            print("Claude Desktop を一度起動してから、もう一度実行するか、--config でパスを指定してください。")
            return 1
        path = max(found, key=lambda p: p.stat().st_mtime)  # いちばん最近使われたもの
        if len(found) > 1:
            print("候補が複数ありました。いちばん最近更新されたものを使います:")
            for p in found:
                print(("  * " if p == path else "    ") + str(p))

    try:
        cfg = load(path)
    except ValueError as e:
        print(f"設定ファイルを読めませんでした: {path}\n  {e}")
        return 1

    servers = cfg.setdefault("mcpServers", {})
    if args.remove:
        if servers.pop(NAME, None) is None:
            print(f"{NAME} は登録されていません: {path}")
            return 0
        if not servers:
            cfg.pop("mcpServers")
    else:
        servers[NAME] = {"command": sys.executable, "args": [str(HERE / "server.py"), "--stdio"]}

    if path.exists():
        shutil.copyfile(path, path.with_name(path.name + ".bak"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"{'消しました' if args.remove else '登録しました'}: {path}")
    if path.with_name(path.name + ".bak").exists():
        print(f"  元のファイル: {path.name}.bak")
    if not args.remove:
        print(f"  python : {sys.executable}")
        print(f"  server : {HERE / 'server.py'} --stdio")
    print("Claude Desktop を完全に終了して（タスクトレイのアイコンを右クリック →「終了」）、起動し直してください。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
