"""3.2 Agent：ツールを使い終わるまで往復をくり返す

3.1 の往復を、LLM がツールを使わなくなる（＝答えを書く）までくり返す。これが Agent の正体。
「探す → 借りられるか調べる → 借りる」のように、何をどの順で使うかは LLM が決める。
決めた手順で動くのではないので、くり返しの回数に上限を設けておく。

実行:  uv run session2/3.2_agent_loop.py
       uv run session2/3.2_agent_loop.py "好きな質問"
"""
import json
import sys

import ollama

from _common import big_model, heading, run
from _library import TOOLS, call_tool

MAX_STEPS = 6   # 往復の上限。LLM が同じツールを使い続けても、ここで止める


def main():
    model = big_model()
    question = sys.argv[1] if len(sys.argv) > 1 else "「AIエージェント入門」を借りたいです。借りられるなら借りてください"
    print(f"モデル: {model}")
    print(f"質問: {question}\n")

    messages: list = [{"role": "user", "content": question}]

    for step in range(1, MAX_STEPS + 1):
        print(heading(f"{step}回目の往復（履歴 {len(messages)}件を送る）"))
        res = ollama.chat(model=model, messages=messages, tools=TOOLS, think=False,
                          options={"num_predict": 1024})
        messages.append(res.message)

        # ツールを使いたいと書いてこなければ、それが最終的な答え
        if not res.message.tool_calls:
            print("LLM: ツールは使わず、答えを書きました\n")
            print(heading("答え"))
            print((res.message.content or "").strip())
            return

        # ツールを使いたいと書いてきたら、プログラムが実行して結果を履歴に足す
        for call in res.message.tool_calls:
            name, args = call.function.name, call.function.arguments
            result = call_tool(name, args)
            print(f"LLM: {name} を {json.dumps(args, ensure_ascii=False)} で使いたい")
            print(f"  → プログラムが実行した結果: {result}")
            messages.append({"role": "tool", "tool_name": name, "content": result})
        print()

    print(f"{MAX_STEPS}回往復しても答えが出なかったので、止めました。")


if __name__ == "__main__":
    run(main)
