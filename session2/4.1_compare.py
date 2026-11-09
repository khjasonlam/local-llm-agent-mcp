"""4.1 小さいモデルと大きいモデルで、Agent の動き方を比べる

同じ課題を2つのモデルに Agent として解かせ、どのツールをどの順に使ったか、何回往復したか、
最後にどう答えたかを並べる。ツールを選ぶのも、引数を決めるのも LLM なので、モデルによって動きが変わる。

実行:  uv run session2/4.1_compare.py            用意した課題の一覧を表示
       uv run session2/4.1_compare.py 1          用意した課題の1番を解かせる
       uv run session2/4.1_compare.py "好きな課題"
       uv run session2/4.1_compare.py 1 --think  思考ありで解かせる（もっと試す）
"""
import json
import sys
import time

import ollama

from _common import big_model, free_memory, pad, run, small_model
from _library import TOOLS, call_tool, reset

TASKS = [
    "「はじめてのPython」は、いま借りられますか？",
    "AIの本で、いま借りられるものをすべて教えて",
    "「生成AIのしくみ」を借りてください",
]
MAX_STEPS = 6
MAX_TOKENS = 2048   # 1回の返事の上限（思考ありで考えすぎて終わらないとき用）


def main():
    args = [a for a in sys.argv[1:] if a != "--think"]
    think = "--think" in sys.argv[1:]

    if not args:
        print("用意した課題:")
        for i, t in enumerate(TASKS, start=1):
            print(f"  {i}. {t}")
        print('\n使い方: uv run session2/4.1_compare.py 1　（または "好きな課題"）')
        return

    if args[0].isdigit():
        number = int(args[0])
        if not 1 <= number <= len(TASKS):
            sys.exit(f"番号は 1〜{len(TASKS)} で指定してください。")
        task = TASKS[number - 1]
    else:
        task = args[0]
    models = [small_model(), big_model()]
    print(f"課題: {task}")
    print(f"思考: {'あり' if think else 'なし'}\n")

    results = []
    for model in models:
        print("━" * 60)
        print(f"■ {model}\n")
        results.append(solve(model, task, think))
        print()

    print("━" * 60)
    print("■ くらべると")
    for r in results:
        end = "答えた" if r["answered"] else "上限で停止"
        print(f"  {pad(r['model'], 14)} 往復 {r['steps']}回　ツール {len(r['calls'])}回"
              f"（{' → '.join(r['calls']) or 'なし'}）　{r['seconds']:5.1f}秒　{end}")


def solve(model: str, task: str, think: bool) -> dict:
    """1つのモデルに Agent として課題を解かせ、使ったツールと答えを集める。"""
    reset()                    # 貸出の状態を最初に戻す（前のモデルが借りた分を消す）
    free_memory(keep=model)    # もう1つのモデルをメモリから外してから始める
    start = time.perf_counter()
    messages: list = [{"role": "user", "content": task}]
    calls: list[str] = []

    for step in range(1, MAX_STEPS + 1):
        res = ollama.chat(model=model, messages=messages, tools=TOOLS, think=think,
                          options={"num_predict": MAX_TOKENS})
        messages.append(res.message)
        if think and res.message.thinking:
            print(f"  （{step}回目：{len(res.message.thinking)}文字考えた）")

        if not res.message.tool_calls:
            print("  答え: " + ((res.message.content or "").strip() or "（空）").replace("\n", "\n        "))
            return {"model": model, "steps": step, "calls": calls, "answered": True,
                    "seconds": time.perf_counter() - start}

        for call in res.message.tool_calls:
            name, args = call.function.name, call.function.arguments
            result = call_tool(name, args)
            calls.append(name)
            print(f"  {step}回目: {name}({json.dumps(args, ensure_ascii=False)})")
            print(f"        → {result}")
            messages.append({"role": "tool", "tool_name": name, "content": result})

    print(f"  {MAX_STEPS}回往復しても答えが出なかったので、止めました。")
    return {"model": model, "steps": MAX_STEPS, "calls": calls, "answered": False,
            "seconds": time.perf_counter() - start}


if __name__ == "__main__":
    run(main)
