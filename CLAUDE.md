# CLAUDE.md

社内勉強会「ローカルLLM・Agent・MCP」のハンズオン教材リポジトリ（公開リポジトリ）。
受講者は Python 経験がまちまちで、各自の個人 PC（Windows / Mac 混在、メモリ 8GB〜）で動かす。
目的は「コードを書けるようになる」ことではなく「中で何が起きているか説明できる」こと。

## 構成

| パス | 内容 | 配布 zip に入るか |
| --- | --- | --- |
| `session1/` | 第1回「ローカルLLMの中をのぞく」のスクリプト。`_common.py` は共通処理、`assets/` はサンプル画像・PDF | 入る |
| `README.md` / `pyproject.toml` / `uv.lock` | 参加者向けの入口と依存関係 | 入る |
| `internal/tools/make_zip.py` | 配布 zip を作る（標準ライブラリのみ） | 入らない |
| `internal/tools/verify.py` | 運営用。教材を実機でまとめて実行し、結果を `internal/verify_results/<日時>/` に保存 | 入らない |
| `internal/check_guide.md` | 運営メンバー向けの動作確認手順（verify.py の使い方） | 入らない |
| `internal/tools/make_backup_pdf.py` | ページの HTML から PDF 控えを作る（`uv run --with playwright` で実行）。ページを直したら控えも作り直す | 入らない |
| `internal/backup/` | 当日資料・事前準備ページの PDF 控え（Artifact が開けないとき用） | 入らない |
| `internal/archive/` | 過去の下書き（Agent・MCP の図書貸出ワークブック等）。gitignore 済み。第2回・第3回の素材 | 入らない |

当日の手順書・事前準備ページは Claude Artifact で公開しており、このリポジトリには無い（README からリンク）。
第2回（Agent）・第3回（MCP、可能であれば）は未作成。

## コマンド

```bash
uv sync                                   # 依存関係を入れる
uv run session1/2.1_api.py                # スクリプトの実行（参加者と同じ形。リポジトリのルートから）
uv run internal/tools/verify.py --quick   # 実機での一括確認（約10分。--quick なしで約20分）
uv run internal/tools/make_zip.py         # dist/llm-agent-mcp-handson.zip を手元で作る（確認用）
```

- 実行には Ollama の起動と、モデル `qwen3.5:0.8b` ＋ `qwen3.5:4b` か `qwen3.5:2b` が必要。自動テストや CI での実行は無く、確認は verify.py を実機で回す。
- `pyproject.toml` の依存を変えたら `uv lock` で `uv.lock` も更新してコミットする。

## 配布の仕組み

- `main` に push すると `.github/workflows/release-zip.yml` が `make_zip.py` で zip を作り、リリース `handson` に差し替える。README の配布リンク（`releases/latest/download/...`）は常にこれを指す。
- zip の中身は `make_zip.py` の `PUBLIC` で決まる。`internal/` は `.gitattributes` の `export-ignore` で GitHub の Source code zip からも外している。
- push した時点で参加者に配られる。配布物（`session1/`・README・pyproject・uv.lock）を壊す変更は push 前に確認する。

## 新しい回（session2/ など）を足すときに更新する場所

1. `internal/tools/make_zip.py` の `PUBLIC`
2. `.github/workflows/release-zip.yml` の `paths`
3. `pyproject.toml` の `[tool.pyright] extraPaths`（`_common` を見つけるため）と、必要なら依存
4. `README.md` の「中身」表と「資料」表
5. `internal/tools/verify.py`（今は第1回だけを確認している）と `internal/check_guide.md`

## スクリプトの書き方（session1 の慣習）

- ファイル名は当日資料の節番号に合わせる（`2.1_api.py`、`4.1_compare.py`）。番号を変えるときは、docstring 内の相互参照（「4.1 で見る」など）、verify.py のスクリプト一覧、当日資料の Artifact もそろえる。
- 先頭の docstring は「節番号＋タイトル → 何を見るスクリプトかの説明 → `実行:` の例」の形。任意の節はタイトルに「（もっと試す）」を付ける。
- 既定の入力を持ち、`sys.argv[1]` で好きな質問に差し替えられるようにする。
- モデル名は直書きせず `_common.big_model()` / `small_model()` を使う（未導入なら事前準備の手順を案内して終了する）。
- `if __name__ == "__main__": run(main)` で包む。`run()` が「Ollama に接続できない」などをわかりやすい日本語で表示する。
- 表示は日本語。区切りは `── 見出し ───`、全角を含む列そろえは `_common.pad()` / `text_width()`、確率の棒は `bar()`、トークン表示は `show_token()` を使う。
- コメントと画面表示は、プログラミング経験が少ない人が読む前提で平易な日本語にする（専門用語は言い換えるか一言説明する）。1ファイルで完結し、上から読めば流れがわかる構成にする。
- `requires-python = ">=3.10"`。3.11 以降の機能（`tomllib`、`ExceptionGroup` など）は使わない。
- Windows の PowerShell でも動くようにする（パスは `pathlib`、文字コード・罫線・█ の表示崩れに注意）。
- 型チェックは Pyright の standard（エディタで警告が出ない状態を保つ）。

## 守ること

- 使うモデルは PC の中だけで動くもの（`qwen3.5:0.8b`、`qwen3.5:4b`、`qwen3.5:2b`）。名前に `cloud` が付くモデルは使わない・勧めない。
- 教材に入れる入力・サンプルはダミーだけ（業務データ・実在の人物の情報は入れない）。`assets/sample.pdf` も架空の社内図書館の案内。
- モデル名は `_common.py`、`verify.py`、`README.md`、`check_guide.md` に重複して書かれている。変えるときは全部そろえる。
- 公開リポジトリなので、社名・社内システム名・個人情報を書かない。
- 受講者にリポジトリ（GitHub のページ）は見せない。当日資料・事前準備ページからリポジトリへのリンクを張らず、受講者に必要な説明はページ自体か配布 zip の README に書く（zip のダウンロードリンクだけは例外）。

## コミット

- メッセージは英語、`docs:` / `feat:` / `fix:` / `chore:` / `ci:` の接頭辞＋小文字始まりの命令形。本文には「なぜ」を書く。
