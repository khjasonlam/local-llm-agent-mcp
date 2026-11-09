"""3.3（もっと試す）自分のツールを1つ足す

LLM は今日の日付を知らない（学習したときの文章しか知らない）。
「今日の日付を返す」ツールを足すと、日付を使う質問に答えられるようになる。
ツールを足す手順は ①関数を書く ②説明を書く ③一覧に足す の3つだけ。

実行:  uv run session2/3.3_my_tool.py
       uv run session2/3.3_my_tool.py "好きな質問"
       uv run session2/3.3_my_tool.py --without   自分のツールを外して、同じ質問をする
"""
import json
import sys
from datetime import date

import ollama

from _common import big_model, heading, run
from _library import FUNCTIONS, TOOLS, call_tool

MAX_STEPS = 6
WEEKDAYS = "月火水木金土日"


# ① 関数を書く（ふつうの Python の関数）
def get_today() -> dict:
    today = date.today()
    return {"今日": today.isoformat(), "曜日": WEEKDAYS[today.weekday()] + "曜日"}


# ② LLM に渡す説明を書く（引数がないので properties は空）
MY_TOOL = {
    "type": "function",
    "function": {
        "name": "get_today",
        "description": "今日の日付と曜日を調べる",
        "parameters": {"type": "object", "properties": {}},
    },
}


def main():
    model = big_model()
    args = [a for a in sys.argv[1:] if a != "--without"]
    without = "--without" in sys.argv[1:]
    question = args[0] if args else "B003 の本を今日借りたら、返却期限は何月何日ですか？貸出期間は2週間です"

    # ③ 一覧に足す（--without のときは足さない）
    tools = TOOLS if without else TOOLS + [MY_TOOL]
    functions = FUNCTIONS if without else {**FUNCTIONS, "get_today": get_today}

    print(f"モデル: {model}")
    print(f"質問: {question}")
    print(f"使えるツール: {', '.join(functions)}\n")

    messages: list = [{"role": "user", "content": question}]
    for step in range(1, MAX_STEPS + 1):
        print(heading(f"{step}回目の往復"))
        res = ollama.chat(model=model, messages=messages, tools=tools, think=False,
                          options={"num_predict": 1024})
        messages.append(res.message)
        if not res.message.tool_calls:
            print(heading("答え"))
            print((res.message.content or "").strip())
            print(f"\n（参考：本当の今日の日付は {date.today().isoformat()}）")
            return
        for call in res.message.tool_calls:
            name, call_args = call.function.name, call.function.arguments
            result = call_tool(name, call_args, functions)
            print(f"LLM: {name} を {json.dumps(call_args, ensure_ascii=False)} で使いたい")
            print(f"  → 結果: {result}")
            messages.append({"role": "tool", "tool_name": name, "content": result})
        print()

    print(f"{MAX_STEPS}回往復しても答えが出なかったので、止めました。")


if __name__ == "__main__":
    run(main)
