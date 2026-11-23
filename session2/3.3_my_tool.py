"""3.3（もっと試す）自分のツールを1つ足す

LLM は今日の日付を知らない（学習したときの文章しか知らない）。
「今日の日付を返す」ツールを足すと、LLM がそのツールを「使える」ようになる。
ただし、使うかどうかは LLM が決める。思考なしでは使わずに答えることも多いので、思考ありとも比べる。
ツールを足す手順は ①関数を書く ②説明を書く ③一覧に足す の3つだけ。

この節では、調べるツール（search_books・check_availability）だけを使い、borrow_book は外す。
本を借りると返却期限の日付が返ってくるので、そこから今日の日付がわかってしまうため。

実行:  uv run session2/3.3_my_tool.py              思考なしで質問する
       uv run session2/3.3_my_tool.py --think      思考ありで、同じ質問をする
       uv run session2/3.3_my_tool.py "好きな質問"
       uv run session2/3.3_my_tool.py --without    自分のツールを外して、同じ質問をする（余裕があれば）
"""
import json
import sys
from datetime import date

import ollama

from _common import big_model, heading, run
from _library import FUNCTIONS, TOOLS, call_tool

MAX_STEPS = 6
MAX_TOKENS = 1024        # 1回の返事の上限（3.2 と同じ）
MAX_TOKENS_THINK = 2048  # 思考ありは考える分だけ長く書くので、上限を大きくする（4.1 と同じ）
WEEKDAYS = "月火水木金土日"

# 調べるツールだけにする（borrow_book を外す）
BASE_TOOLS = [t for t in TOOLS if t["function"]["name"] != "borrow_book"]
BASE_FUNCTIONS = {name: func for name, func in FUNCTIONS.items() if name != "borrow_book"}


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

# ③ 一覧に足す（LLM に渡す説明と、実際に実行する関数の両方）
MY_TOOLS = BASE_TOOLS + [MY_TOOL]
MY_FUNCTIONS = {**BASE_FUNCTIONS, "get_today": get_today}


def main():
    model = big_model()
    args = [a for a in sys.argv[1:] if a not in ("--without", "--think")]
    without = "--without" in sys.argv[1:]
    think = "--think" in sys.argv[1:]
    question = args[0] if args else "B002 の本は、あと何日で返ってきますか？"

    # --without のときは、自分のツールを足す前の一覧を使う
    tools = BASE_TOOLS if without else MY_TOOLS
    functions = BASE_FUNCTIONS if without else MY_FUNCTIONS

    print(f"モデル: {model}")
    print(f"質問: {question}")
    print(f"思考: {'あり' if think else 'なし'}")
    print(f"使えるツール: {', '.join(functions)}\n")

    messages: list = [{"role": "user", "content": question}]
    for step in range(1, MAX_STEPS + 1):
        print(heading(f"{step}回目の往復"))
        res = ollama.chat(model=model, messages=messages, tools=tools, think=think,
                          options={"num_predict": MAX_TOKENS_THINK if think else MAX_TOKENS})
        messages.append(res.message)
        if think and res.message.thinking:
            print(f"（{len(res.message.thinking)}文字考えた）")
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
