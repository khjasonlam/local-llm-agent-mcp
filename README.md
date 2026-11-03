# ローカルLLM・Agent・MCP 勉強会 教材

自分のPCでLLMを動かし、中で何が起きているかをのぞいてみるハンズオン勉強会の教材です。
コードを書けるようになることより、「AIがどう動いているかを説明できる」ことを目指します。

## 資料

| 資料 | 内容 |
| --- | --- |
| [事前準備](https://claude.ai/artifact/FJ1vs8KyhSSfeNxXNA2idG) | Ollama・モデル・uv のインストール（勉強会の前に） |
| [第1回 ローカルLLMの中をのぞく](https://claude.ai/artifact/D5nYfU1itV7aNyWARmBqam) | 当日の手順と持ち帰り課題 |

## 教材の取り方

[llm-agent-mcp-handson.zip](https://github.com/khjasonlam/local-llm-agent-mcp/releases/latest/download/llm-agent-mcp-handson.zip) をダウンロードして展開し、展開したフォルダで次を実行します。

```bash
uv sync
```

## 中身

| フォルダ | 内容 |
| --- | --- |
| `session1/` | 第1回：ローカルLLMを動かしてみよう（次の単語の予測・思考の比較） |

スクリプトは、展開したフォルダから `uv run session1/2.1_api.py` のように実行します。

## 注意

- 入力するのは、勉強会で用意した質問や、ダミーの内容だけにしてください。業務データや実在の人物の情報は入れないでください。
- 使うモデルは、PCの中だけで動くもの（`qwen3.5:0.8b`、`qwen3.5:4b` または `qwen3.5:2b`）です。名前に `cloud` が付くモデルは、PCの外にデータが送られるので使わないでください。
