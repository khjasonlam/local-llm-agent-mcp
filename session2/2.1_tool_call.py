"""2.1 LLM が「ツールを使いたい」と書いてくるのを見る

質問と一緒に「ツールの説明」（架空の社内図書館の、本を探す・貸出状況を調べる・借りる）を送る。
LLM はツールを実行しない。「このツールを、この引数で使いたい」と書いて返してくるだけ。それをそのまま表示する。

実行:  uv run session2/2.1_tool_call.py
       uv run session2/2.1_tool_call.py "好きな質問"
       uv run session2/2.1_tool_call.py "こんにちは"     ツールが要らない質問（もっと試す）
"""
import json
import sys

import ollama

from _common import big_model, heading, run
from _library import TOOLS


def main():
    model = big_model()
    question = sys.argv[1] if len(sys.argv) > 1 else "Pythonの本を探して"

    # Ollama に送るデータ。第1回の 2.1 に「tools」（ツールの説明）が増えただけ
    request = {
        "model": model,
        "messages": [
            {"role": "user", "content": question},
        ],
        "tools": TOOLS,   # 使えるツールの説明（中身は _library.py）
        "think": False,   # 思考はオフ（4.1 で比べる）
    }

    print(heading("送ったデータ"))
    print(json.dumps(request, ensure_ascii=False, indent=2))

    res = ollama.chat(**request)

    print("\n" + heading("返ってきたデータ（message の部分）"))
    print(res.message.model_dump_json(exclude_none=True, indent=2))

    print("\n" + heading("つまり"))
    if res.message.tool_calls:
        for call in res.message.tool_calls:
            args = json.dumps(call.function.arguments, ensure_ascii=False)
            print(f"LLM は「{call.function.name} を {args} で使いたい」と書いてきました。")
        print("ただし、まだ何も実行されていません。実行するのはプログラムの役目です（3.1 で作ります）。")
    else:
        print("LLM はツールを使わずに、直接答えました:")
        print((res.message.content or "").strip())


if __name__ == "__main__":
    run(main)
