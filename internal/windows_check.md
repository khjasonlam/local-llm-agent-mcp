# 第1回教材 Windows 動作確認のお願い

勉強会の前に、Windows で第1回の教材が動くか、どのくらい時間がかかるかを確かめたいです。
30分〜1時間ほど、PCを置いておける時間にお願いします（ほとんどは待ち時間です）。

## 1. 事前準備ページの手順1〜4を済ませる

事前準備ページ: https://claude.ai/artifact/FJ1vs8KyhSSfeNxXNA2idG

Ollama・モデル2つ（`qwen3.5:0.8b` と、メモリに合わせて `qwen3.5:4b` か `qwen3.5:2b`）・uv が入っていれば大丈夫です。

## 2. リポジトリを取ってくる

PowerShell を開き、教材を置きたい場所（例: ドキュメント）で次を実行します。参加者に配る教材に、確認用のスクリプト（`internal/tools/verify.py`）が入った状態で取ってこられます。

```powershell
git clone https://github.com/khjasonlam/local-llm-agent-mcp.git
cd local-llm-agent-mcp
```

2回目以降は、`local-llm-agent-mcp` フォルダで `git pull` を実行すれば最新になります。

## 3. 確認用のスクリプトを実行する

続けて、同じ PowerShell で次を実行します。

```powershell
uv sync
uv run internal/tools/verify.py --quick
```

`[時刻] 完了しました。` と出たら終わりです。途中でエラーが出て止まった場合も、そこまでの結果は残ります。

## 4. 結果を送る

`local-llm-agent-mcp\internal\verify_results\` の中にできたフォルダ（日時の名前）を zip にして、Jason に送ってください。
あわせて、次の3つを教えてください。

- PCの機種、メモリ、GPUの有無（わかる範囲で）
- Windows のバージョン（10 / 11）
- 実行中に気づいたこと（画面の表示が崩れた、PCが重くなった、など）

## 確認したいこと（運営メモ）

- session1 のスクリプト（2.1〜4.1、もっと試すの 2.2・3.3・3.4 を含む）がすべて終了コード 0 で終わるか
- 4.1（比較）が1問あたり何秒かかるか。Mac（M系・4b）では約1分
- 日本語・罫線・棒グラフ（█）が PowerShell で崩れずに表示されるか（送ってもらう結果ファイルとは別に、画面の見え方も聞く）
