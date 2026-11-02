"""04 小さいモデルと大きいモデルの「考え方」を比べる

同じ質問を2つのモデルに投げ、思考ログ（考えている途中の文章）と答えを並べる。

実行:  uv run session1/04_compare.py            用意した質問の一覧を表示
       uv run session1/04_compare.py 1          用意した質問の1番を投げる
       uv run session1/04_compare.py "好きな質問"
       uv run session1/04_compare.py 1 --no-think   思考なしで答えさせる（持ち帰り課題）
"""
import sys
import time

import ollama

from _common import big_model, run, small_model, text_width

QUESTIONS = [
    "英単語 strawberry の中に、r は何個ありますか？",
    "池の睡蓮は毎日2倍に増え、48日目に池全体を覆いました。池の半分を覆ったのは何日目ですか？",
    "本とブックカバーを合わせて1100円です。本はブックカバーより1000円高いです。ブックカバーは何円ですか？",
]
# 考えすぎて終わらないときの上限（トークン数）。小さいモデルは同じ確認を繰り返しがちなので短めにする
MAX_TOKENS = {"small": 2048, "big": 4096}


def main():
    args = [a for a in sys.argv[1:] if a != "--no-think"]
    think = "--no-think" not in sys.argv[1:]

    if not args:
        print("用意した質問:")
        for i, q in enumerate(QUESTIONS, start=1):
            print(f"  {i}. {q}")
        print('\n使い方: uv run session1/04_compare.py 1　（または "好きな質問"）')
        return

    question = QUESTIONS[int(args[0]) - 1] if args[0].isdigit() else args[0]
    models = [(small_model(), MAX_TOKENS["small"]), (big_model(), MAX_TOKENS["big"])]
    print(f"質問: {question}")
    print(f"思考: {'あり' if think else 'なし'}\n")

    results = [ask(model, question, think, limit) for model, limit in models]

    for r in results:
        print("━" * 60)
        print(f"■ {r['model']}")
        if think:
            print("\n［考えていること］")
            print(r["thinking"].strip() or "（なし）")
        print("\n［答え］")
        print(r["answer"].strip() or "（答えを書く前に打ち切りました）")
        if r["cut"]:
            print(f"\n※ {r['limit']}トークンに達したので、途中で打ち切りました")
        print()

    print("━" * 60)
    print("■ くらべると")
    for r in results:
        end = "（打ち切り）" if r["cut"] else ""
        print(f"  {r['model']:<14} 思考 {len(r['thinking']):>5}文字　"
              f"書いたトークン {r['tokens']:>5}　時間 {r['seconds']:5.1f}秒{end}")


def ask(model: str, question: str, think: bool, limit: int) -> dict:
    """1つのモデルに質問し、思考と答えを集める。待っている間は進み具合を表示する。"""
    thinking, answer, tokens, cut = "", "", 0, False
    start = time.perf_counter()
    stream = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": question}],
        think=think,
        stream=True,
        options={"num_predict": limit},
    )
    for chunk in stream:
        thinking += chunk.message.thinking or ""
        answer += chunk.message.content or ""
        if sys.stdout.isatty():  # 画面に出しているときだけ、同じ行を書き換えて進み具合を表示
            status = "答えを書いています" if answer else "考えています"
            line = f"  {model}: {status}… 思考 {len(thinking)}文字 / 答え {len(answer)}文字"
            print("\r" + line + " " * max(0, 70 - text_width(line)), end="", flush=True)
        if chunk.done:
            tokens = chunk.eval_count or 0
            cut = chunk.done_reason == "length"
    if sys.stdout.isatty():
        print()
    return {
        "model": model,
        "thinking": thinking,
        "answer": answer,
        "tokens": tokens,
        "seconds": time.perf_counter() - start,
        "cut": cut,
        "limit": limit,
    }


if __name__ == "__main__":
    run(main)
