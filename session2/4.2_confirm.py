"""4.2（もっと試す）記録を変えるツールの前に、人の確認を挟む

3.2 の Agent は、LLM が「借りる」と決めたら、そのまま本を借りてしまう。
調べるだけのツールはそのまま実行し、記録を変えるツール（borrow_book）だけは、実行する前に人に y/n で確かめる。
n と答えると、ツールは実行せず「取りやめた」という結果を LLM に返す。

実行:  uv run session2/4.2_confirm.py
       uv run session2/4.2_confirm.py "好きな質問"
"""
import json
import sys

import ollama

from _common import big_model, heading, run
from _library import TOOLS, call_tool

MAX_STEPS = 6
NEED_CONFIRM = {"borrow_book"}   # 実行する前に人の確認が要るツール


def main():
    model = big_model()
    question = sys.argv[1] if len(sys.argv) > 1 else "「やさしい機械学習」を借りたいです。借りられるなら借りてください"
    print(f"モデル: {model}")
    print(f"質問: {question}\n")

    messages: list = [{"role": "user", "content": question}]
    for step in range(1, MAX_STEPS + 1):
        print(heading(f"{step}回目の往復"))
        res = ollama.chat(model=model, messages=messages, tools=TOOLS, think=False,
                          options={"num_predict": 1024})
        messages.append(res.message)
        if not res.message.tool_calls:
            print(heading("答え"))
            print((res.message.content or "").strip())
            return

        for call in res.message.tool_calls:
            name, args = call.function.name, call.function.arguments
            print(f"LLM: {name} を {json.dumps(args, ensure_ascii=False)} で使いたい")
            if name in NEED_CONFIRM and not confirm(f"  {name} を実行してよいですか？ [y/n] "):
                result = json.dumps({"結果": "利用者が取りやめたので、実行しませんでした"}, ensure_ascii=False)
            else:
                result = call_tool(name, args)
            print(f"  → 結果: {result}")
            messages.append({"role": "tool", "tool_name": name, "content": result})
        print()

    print(f"{MAX_STEPS}回往復しても答えが出なかったので、止めました。")


def confirm(prompt: str) -> bool:
    """人に y/n で確かめる。y 以外（何も入力できないときも含む）は「いいえ」とみなす。"""
    try:
        answer = input(prompt)
    except EOFError:   # 入力を受け付けられない実行のしかたのとき
        print("（入力がないので、いいえ とみなします）")
        return False
    return answer.strip().lower() in ("y", "yes", "はい")


if __name__ == "__main__":
    run(main)
