"""3.1 ツールを1回使って答える（LLM とプログラムの往復）

① 質問とツールの説明を送る → LLM が「このツールを使いたい」と返す
② プログラムがツール（Python の関数）を実行し、結果を会話の履歴に足す
③ 履歴をまるごと送り直す → LLM が結果を読んで答える
第1回 2.3 と同じく、LLM は何も覚えていない。履歴（messages）が増えていく様子を見る。

実行:  uv run session2/3.1_one_round.py
       uv run session2/3.1_one_round.py "好きな質問"
"""
import json
import sys

import ollama

from _common import big_model, heading, run
from _library import TOOLS, call_tool


def main():
    model = big_model()
    question = sys.argv[1] if len(sys.argv) > 1 else "B001 の本は、いま借りられますか？"
    print(f"モデル: {model}\n")

    messages: list = [{"role": "user", "content": question}]

    # ① 質問とツールの説明を送る
    print("■ ① 質問とツールの説明を送る\n")
    show_messages(messages)
    res = ollama.chat(model=model, messages=messages, tools=TOOLS, think=False)
    print(heading("LLM の返事"))
    print(res.message.model_dump_json(exclude_none=True, indent=2))
    messages.append(res.message)   # LLM の返事も履歴に入れる

    if not res.message.tool_calls:
        print("\nLLM はツールを使わずに答えました（往復は起きませんでした）。")
        return

    # ② プログラムがツールを実行し、結果を履歴に足す
    print("\n■ ② プログラムがツールを実行する\n")
    for call in res.message.tool_calls:
        name, args = call.function.name, call.function.arguments
        result = call_tool(name, args)   # ここで初めて Python の関数が動く（中身は _library.py）
        print(f"実行: {name}({json.dumps(args, ensure_ascii=False)})")
        print(f"結果: {result}\n")
        messages.append({"role": "tool", "tool_name": name, "content": result})

    # ③ 履歴をまるごと送り直す
    print("■ ③ 結果も含めた履歴を、まるごと送り直す\n")
    show_messages(messages)
    res = ollama.chat(model=model, messages=messages, tools=TOOLS, think=False)
    print(heading("LLM の答え"))
    if res.message.tool_calls:   # 結果を読んで、さらに別のツールを使いたくなった
        names = ", ".join(c.function.name for c in res.message.tool_calls)
        print(f"LLM は、さらに {names} を使いたいと書いてきました。")
        print("このスクリプトは往復1回で終わります。答えが出るまでくり返すのは 3.2 です。")
    else:
        print((res.message.content or "").strip())


def show_messages(messages: list) -> None:
    """送る messages（会話の履歴）を表示する。"""
    plain = [m if isinstance(m, dict) else m.model_dump(exclude_none=True) for m in messages]
    print(heading(f"送ったデータ（messages：{len(plain)}件）"))
    print(json.dumps(plain, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    run(main)
