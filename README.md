# AIモデル生成（bpy × three.js）

Blender（GUI なし）を持ったローカルサーバーを自分の PC で起動し、Claude Code などの AI に
MCP で操作させて、手作業でモデリングしたような四角ポリゴン主体のメッシュを作るツール。
**Claude の API キーは使いません。** AI は、ふだん使っている Claude Code / Claude Desktop がそのまま担当します。

```
あなた ──「スツールを作って」──▶ AI（Claude Code など）
                                    │  run_script（bpy のスクリプト）
                                    ▼
                         ローカルサーバー（このフォルダ）
                         Blender で実行 → トポロジー検査 → GLB/FBX/OBJ に書き出し
                                    │  検査結果・render の絵
                                    ▼
                         AI が結果を見て直す（エラー・Nゴン・三角形・法線の向き など）
                                    │
                                    ▼
                         ブラウザのビューアー（three.js）に結果がそのまま出る
```

## 入手

```bash
git clone https://github.com/CenterV80/bpy-ai-modeler.git
cd bpy-ai-modeler
```

git を使わない場合は、このページの緑の「Code」ボタン →「Download ZIP」で取得して展開してください。
あとから git で更新できるようにしたいときは、[git の管理下にする](#zip-で取得したフォルダを-git-で更新できるようにする) を見てください。

## セットアップ

`bpy` は Blender のバージョンごとに対応する Python が決まっています。いまの bpy 5.3 は **Python 3.13** 専用です
（PyPI の bpy のページで確認してください）。

いちばん楽なのは [uv](https://docs.astral.sh/uv/) を入れる方法です。Python 3.13 も uv が用意するので、Python を別に入れる必要はありません。

```powershell
# Windows（PowerShell）
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

入れたらターミナルを開き直します。**Windows はこのまま「起動」へ進んでください**（`start.bat` が残りを自動でやります）。
手動で準備する場合は次のとおりです。

```bash
uv venv --python 3.13
source .venv/bin/activate        # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

Windows で `.venv\Scripts\activate` が「このシステムではスクリプトの実行が無効になっている」で止まるときは、
次を一度だけ実行します（自分のユーザーにだけかかる設定です）。

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

有効になると、行の頭に `(bpy-ai-modeler)` のような環境の名前が付きます（uv はフォルダ名を名前にするので `(.venv)` ではありません）。

## 起動

**Windows** は `start.bat` をダブルクリックするだけです。初回は `.venv` の作成と必要なものの
インストール（数分）まで自動で行い、サーバーが立ち上がるとブラウザでビューアーを開きます。
uv か Python 3.13 のどちらかが入っている必要があります。止めるときは黒い画面で Ctrl+C を押します。

それ以外の環境や、手動で起動する場合は、仮想環境を有効にしてから次を実行します。

```bash
python server.py
```

- ビューアー: http://127.0.0.1:8000
- AI の接続先（MCP）: http://127.0.0.1:8000/mcp

## AI をつなぐ

使う AI のアプリによって、つなぎ方が2通りあります。ふだんはどちらか片方で十分です。

| | Claude Code | Claude Desktop |
|---|---|---|
| サーバーを起動するのは | 自分（`start.bat` か `python server.py`） | Claude Desktop（自動） |
| つなぎ方 | `claude mcp add` を一度実行 | `setup_claude_desktop.py` を一度実行 |

> claude.ai の「カスタムコネクタ」からはつなげません。カスタムコネクタは Anthropic のサーバーから接続するので、
> 自分の PC の中（127.0.0.1）には届かないためです。トンネルで外に公開するのは、送られたコードをそのまま実行する
> サーバーなので危険です。やめてください。

### Claude Code

サーバーを起動したまま、一度だけ実行します。Claude Code に「このコマンドを実行して」と頼んでも構いません。

```bash
claude mcp add --transport http bpy-modeler http://127.0.0.1:8000/mcp
```

Claude Code を開き直し、`/mcp` で `bpy-modeler` がつながっているか確認できます。

### Claude Desktop

Claude Desktop がこのサーバーを自分で起動します（`--stdio`）。`start.bat` を動かす必要はありません。

両方を同時に使っても困らないようにしてあります。サーバーが2つ動いていても、結果は同じ `output` フォルダに保存され、
どちらのビューアーにも全部の結果が出ます。後から起動した方は、ポート 8000 が bpy モデラーで使われていれば、そのビューアーに相乗りします。

仮想環境の python で、付属の `setup_claude_desktop.py` を一度だけ実行します。設定ファイル
（`claude_desktop_config.json`）を探して、もとの設定は残したまま bpy-modeler を登録します。書き換える前に `.bak` を作ります。

```powershell
# Windows（このフォルダで）
.venv\Scripts\python.exe setup_claude_desktop.py
```
```bash
# macOS
.venv/bin/python setup_claude_desktop.py
```

そのあと Claude Desktop を**完全に終了して**（タスクトレイのアイコンを右クリック →「終了」）、起動し直します。
10 秒ほど待って http://127.0.0.1:8000 のビューアーが開けば、つながっています。

- 消すときは `setup_claude_desktop.py --remove`
- 設定ファイルが見つからないときは `--config <パス>` で指定します

設定ファイルの場所は、Claude Desktop の版によって違います。

| 版 | 場所 |
|---|---|
| 新しい版（Windows） | `%LOCALAPPDATA%\Claude-Data\claude_<英数字>\claude_desktop_config.json` |
| 以前の版（Windows） | `%APPDATA%\Claude\claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |

手で書く場合は、ファイル全体が `{ … }` **1つ**になるようにしてください。末尾に `{ "mcpServers": … }` を足すと、
ファイル全体が読めなくなって無視されます。もとからある `{ … }` の中に、カンマで区切って `"mcpServers"` を入れます。

```json
{
  "（もとからある設定）": "…",
  "mcpServers": {
    "bpy-modeler": {
      "command": "<このフォルダ>\\.venv\\Scripts\\python.exe",
      "args": ["<このフォルダ>\\server.py", "--stdio"]
    }
  }
}
```

## 使い方

AI に、名前を出して頼みます。寸法や形の特徴を書くほど狙いどおりになります。

```
bpy-modeler で木製のスツールを作って。座面は直径35cmの円形で縁を丸く、脚は4本で少し外に開く。高さ45cm
```

1. AI がスクリプトを書いて `run_script` で実行する。ビューアーの「実行の履歴」に1行増え、モデルが出る
2. 検査で問題があれば、AI が自分で直して実行し直す（履歴に何行か並ぶことがある）
3. AI が `render` で絵を見て、形を確かめる（1 視点に数秒かかる）
4. 気に入ったら「FBX で デスクトップ に保存して」と頼むか、ビューアーの「書き出し」ボタンで保存する

初めてツールを使うときは、AI のアプリが使ってよいかを聞いてきます。「許可」（毎回聞かれたくなければ「常に許可」）を選んでください。
Claude Desktop では、入力欄の「＋」などから開くツール一覧で `bpy-modeler` がオンになっている必要があります。

ビューアーでは「ワイヤー」でポリゴンの辺の流れ、「トポロジー」で四角形の割合などを見られます。
履歴の行を押すと、前の結果に切り替えられます。

## AI が使える道具（MCP ツール）

| ツール | 内容 |
|---|---|
| `run_script` | bpy のスクリプトを空のシーンで実行し、トポロジーの検査結果を返す。結果はビューアーに出て、GLB / FBX / OBJ にも書き出される |
| `render` | 結果を絵にして返す（粘土色の面＋ポリゴンの辺。斜め・正面・横・真上から）。AI が形を目で確かめる |
| `list_runs` | これまでの実行の一覧 |
| `get_script` | 前の実行のスクリプトを取り出す（前の版から作り直すとき） |
| `export` | 書き出したファイルを指定のフォルダにコピーする |

モデリングのルール（四角ポリゴン主体、Z が上、メートル単位など）は、接続したときにサーバーから AI に伝わります（`server.py` の `GUIDE`）。

## トポロジー検査の基準

次のどれかに当てはまると「問題」として AI に返し、直させます（`server.py` の `problems_of()` で変更できます）。

- Nゴン（5角形以上）がある
- 三角ポリゴンが全体の 10% を超える
- 3枚以上の面が共有している辺（非多様体）がある
- となりの面と向きが逆の辺がある／閉じた形なのに法線が内向き
- 同じ位置に重なった頂点がある／面積がほぼゼロの面がある
- 面につながっていない頂点・辺がある
- 面が 30 万枚を超える

開いている辺（穴や板の縁）は、意図した形のこともあるので問題には数えず、オブジェクトごとの数だけを返します。
穴があいていないかは `render` の絵で確かめさせます。

## 起動オプション

| オプション | 既定値 | 内容 |
|---|---|---|
| `--port` | `8000` | ポート（環境変数 `PORT` でも可） |
| `--stdio` | なし | MCP を標準入出力で受ける |
| `--out` | `./output` | 結果の保存先（実行ごとに `runs/0001/` のようなフォルダができる） |
| `--timeout` | `60` | スクリプト1回の制限時間（秒）。macOS / Linux のみ。Windows では効かないので、止まったら Ctrl+C で再起動する |

## うまくいかないとき

| 症状 | 見るところ |
|---|---|
| ビューアーが開かない（Claude Code） | `start.bat` の黒い画面にエラーが出ていないか。「すでに動いています」と出たら、案内された URL を開く |
| ビューアーに結果が出ない | AI に返された結果の最後の「ビューアー: …」の URL を開く（8000 番がほかのプログラムに使われていると、8001 番などで開く） |
| ビューアーが開かない（Claude Desktop） | 設定ファイルが `{ … }` 1つになっているか（`setup_claude_desktop.py` を実行し直すと直る）。Claude Desktop を完全に終了したか |
| Claude Desktop がサーバーを起動しない | ログ `%LOCALAPPDATA%\Claude\logs\mcp.log`（以前の版は `%APPDATA%\Claude\logs`）が空なら、設定ファイルが読まれていない |
| 「bpy-modeler のツールがない」と言われる | ツール一覧で `bpy-modeler` がオンか。Claude Code なら `/mcp` |
| スクリプトが終わらない | macOS / Linux は 60 秒で止まる。Windows は止まらないので、Ctrl+C でサーバーを再起動する |

## この Python 環境について

- `.venv` は普通の Python 3.13 の仮想環境で、その中に pip で `bpy` を入れています。
  `bpy` は Blender 本体を Python のライブラリにしたもの（Blender Foundation が配布）で、画面はありませんが
  モデリング・モディファイア・書き出し・Cycles での描画など、中身は Blender 5.3 と同じです。
- PC にインストールした Blender とは関係ありません。Blender が入っていなくても動きます。
- 作ったモデルを Blender で開くときは、書き出した FBX / OBJ / GLB を読み込みます（`.blend` は作りません）。
- `bpy` を新しい版に上げるときは、対応する Python の版も変わることがあります。PyPI の bpy のページで確認してください。

## ZIP で取得したフォルダを git で更新できるようにする

`.venv` と `output` は git の管理外なので、そのまま残ります。`server.py` などはリポジトリの最新版で上書きされます。

```powershell
git init
git remote add origin https://github.com/CenterV80/bpy-ai-modeler.git
git fetch origin
git checkout -f -B main origin/main
git branch -u origin/main
```

以後は `git pull` で最新になります。

## 注意

- AI が書いたコードを `exec()` でそのまま実行します。`127.0.0.1` でだけ待ち受けているので、外部には公開しないでください。
- `render` は Cycles（CPU）で描きます。GPU がなくても動きますが、1 視点に 1〜数秒かかります。
- 検査も書き出しも、モディファイアを適用した後の形に対して行います。
- FBX はセンチ単位・Y が上で、頂点に寸法を焼き込んで書き出します。Maya や Unity では、拡大率 1・回転 0 のまま正しい大きさになります。
- 実行の履歴は `output/` に残るので、サーバーを再起動しても続きから使えます。

## ライセンス

このリポジトリのコードは [MIT ライセンス](LICENSE) です。

依存しているライブラリはそれぞれのライセンスに従います。特に `bpy`（Blender）は GPL-3.0 です。
このツールと bpy を組み合わせて配布する場合は、GPL の条件にも従ってください（MIT は GPL と両立します）。
