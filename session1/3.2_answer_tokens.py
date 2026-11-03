"""3.2 答え全体を、1トークンずつ見る

短い答えを書かせ、書いたトークンごとに「選ばれたもの・その確率・ほかの候補」を並べる。
迷わず書いた所と、迷った所がわかる。

実行:  uv run session1/3.2_answer_tokens.py
       uv run session1/3.2_answer_tokens.py "好きな質問"
       uv run session1/3.2_answer_tokens.py --temperature 0   くじ引きをしない。何度実行しても同じ答えになる（もっと試す）
"""
import math
import sys

import ollama

from _common import big_model, pad, run, show_token

OTHERS = 3        # ほかの候補をいくつ表示するか
HESITATED = 0.5   # 確率がこれより低いトークンを「迷った」とする


def main():
    args = sys.argv[1:]
    # --temperature 数字 で、くじ引きの度合いを変えられる（0 にすると、くじ引きをしない）
    temperature = None
    if "--temperature" in args:
        i = args.index("--temperature")
        try:
            temperature = float(args[i + 1])
        except (IndexError, ValueError):
            sys.exit("--temperature のあとに数字を付けてください（例: --temperature 0）")
        del args[i:i + 2]
    question = args[0] if args else "新しいカフェの名前を1つ考えて。名前だけ答えて"
    model = big_model()

    res = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": question}],
        think=False,
        logprobs=True,
        top_logprobs=OTHERS + 1,
        options={} if temperature is None else {"temperature": temperature},
    )

    print(f"モデル: {model}")
    print(f"質問　: {question}")
    if temperature is not None:
        print(f"温度　: {temperature:g}（くじ引きの度合い。0 はくじ引きなし）")
    print(f"答え　: {res.message.content}\n")
    print(f"  {'#':>3}  {pad('選ばれた', 16)} {'確率':>6}   ほかの候補")
    hesitated = 0
    for i, step in enumerate(res.logprobs or [], start=1):
        p = math.exp(step.logprob)
        others = [c for c in (step.top_logprobs or []) if c.token != step.token][:OTHERS]
        others_text = "　".join(f"{show_token(c.token)} {math.exp(c.logprob) * 100:.0f}%" for c in others)
        mark = "  ← 迷った" if p < HESITATED else ""
        hesitated += p < HESITATED
        print(f"  {i:>3}  {pad(show_token(step.token), 16)} {p * 100:5.1f}%   {others_text}{mark}")

    print(f"\n{len(res.logprobs or [])}トークンのうち、迷った所（確率{HESITATED * 100:.0f}%未満）: {hesitated}か所")


if __name__ == "__main__":
    run(main)
