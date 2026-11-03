"""2.3（もっと試す）会話の履歴を送り直していることを確かめる

LLM は前の会話を覚えていない。2回目の質問のときに、1回目のやりとりも含めて送り直しているだけ。
1回目のやりとりを付けて送った場合と、付けずに送った場合で、2回目の答えを比べる。

実行:  uv run session1/2.3_history.py
"""
import json

import ollama

from _common import big_model, run

FIRST = "私の好きな飲み物は、ほうじ茶です。覚えておいてください"
SECOND = "私の好きな飲み物は何でしたか？飲み物の名前だけ答えて"


def ask(model: str, messages: list[dict]) -> str:
    """messages（会話の履歴）を送り、返事を表示して返す。"""
    print("── 送ったデータ（messages）" + "─" * 30)
    print(json.dumps(messages, ensure_ascii=False, indent=2))
    res = ollama.chat(model=model, messages=messages, think=False)
    answer = (res.message.content or "").strip()
    print("── 返事 " + "─" * 46)
    print(answer + "\n")
    return answer


def main():
    model = big_model()
    print(f"モデル: {model}\n")

    print("■ 1回目：好きな飲み物を伝える\n")
    first = [{"role": "user", "content": FIRST}]
    answer = ask(model, first)

    print("■ 2回目（履歴あり）：1回目の質問と返事も一緒に送る\n")
    ask(model, first + [
        {"role": "assistant", "content": answer},  # 1回目の返事も履歴に入れる
        {"role": "user", "content": SECOND},
    ])

    print("■ 2回目（履歴なし）：2回目の質問だけを送る\n")
    ask(model, [{"role": "user", "content": SECOND}])


if __name__ == "__main__":
    run(main)
