"""02 次に来るトークンの候補を見る

書きかけの文を渡し、LLM が「次に何を書くか」の候補と確率を表示する。
LLM は、この候補の中から1つを選んで書き足すことを繰り返している。

実行:  uv run session1/02_next_token.py
       uv run session1/02_next_token.py "書きかけの文"
"""
import math
import sys

import ollama

from _common import bar, big_model, pad, run, show_token

TOP_N = 10  # 表示する候補の数（最大20）


def main():
    text = sys.argv[1] if len(sys.argv) > 1 else "日本の首都は"
    model = big_model()

    res = ollama.generate(
        model=model,
        prompt=text,
        raw=True,                 # 会話の形にせず、文の続きをそのまま書かせる
        options={"num_predict": 1},  # 1トークンだけ書く
        logprobs=True,            # 確率を返してもらう
        top_logprobs=TOP_N,       # 候補を上位 TOP_N 個まで
    )

    if not res.logprobs:
        sys.exit("確率が返ってきませんでした。Ollama を最新版に更新してください。")
    step = res.logprobs[0]
    print(f"モデル: {model}")
    print(f"入力　: {text}")
    print(f"\n次に来る候補（上位{TOP_N}個）")
    total = 0.0
    for cand in step.top_logprobs or []:
        p = math.exp(cand.logprob)  # logprob（対数）を確率に戻す
        total += p
        print(f"  {pad(show_token(cand.token), 16)} {pad(bar(p), 31)} {p * 100:5.1f}%")
    print(f"\n上位{TOP_N}個の合計: {total * 100:.1f}%（残りは、ほかの何万もの候補）")
    print(f"実際に選ばれたのは: {show_token(step.token)}")


if __name__ == "__main__":
    run(main)
