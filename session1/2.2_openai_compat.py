"""2.2（もっと試す）OpenAI 互換の書き方で、同じことをする

Ollama は、ChatGPT の API（OpenAI API）と同じ形でも呼べる。
base_url とモデル名（と API キー）を変えれば、同じコードのまま接続先を ChatGPT などに切り替えられる。
2.1 と見比べて、送るデータと返ってくるデータの形の違いを確かめる。

実行:  uv run session1/2.2_openai_compat.py
"""
import json
import sys

from openai import OpenAI

from _common import big_model, run

# 接続先を Ollama にする。キーは必須だが、Ollama では中身は使われない
client = OpenAI(base_url="http://localhost:11434/v1/", api_key="ollama")


def main():
    question = sys.argv[1] if len(sys.argv) > 1 else "「おはようございます」を英語にして。訳だけ答えて"
    request = {
        "model": big_model(),
        "messages": [{"role": "user", "content": question}],
        "reasoning_effort": "high",  # 思考あり（"none" にすると思考なし）
    }
    print("── 送ったデータ " + "─" * 40)
    print(json.dumps(request, ensure_ascii=False, indent=2))

    print("\n（思考ありなので、答えが返るまで数十秒〜1分ほどかかります）")
    res = client.chat.completions.create(**request)

    print("\n── 返ってきたデータ " + "─" * 36)
    print(json.dumps(res.model_dump(exclude_none=True), ensure_ascii=False, indent=2))

    message = res.choices[0].message
    # 思考は reasoning に入る（OpenAI の公式の項目ではないので、model_extra から取り出す）
    reasoning = (message.model_extra or {}).get("reasoning", "")
    print("\n── まとめると " + "─" * 42)
    print(f"［考えていること］\n{reasoning.strip() or '（なし）'}\n")
    print(f"［答え］\n{message.content}")


if __name__ == "__main__":
    run(main)
