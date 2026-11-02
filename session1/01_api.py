"""01 プログラムからLLMを呼ぶ

チャット画面の裏では、プログラムが「会話の履歴」を JSON で送り、
返事を少しずつ受け取っているだけ。それをそのまま表示する。

実行:  uv run session1/01_api.py
       uv run session1/01_api.py "好きな質問"
"""
import json
import sys

import ollama

from _common import big_model, run


def main():
    question = sys.argv[1] if len(sys.argv) > 1 else "「おはようございます」を英語にして。訳だけ答えて"

    # Ollama に送るデータ。messages が「会話の履歴」。
    request = {
        "model": big_model(),
        "messages": [
            {"role": "user", "content": question},
        ],
        "stream": True,   # 返事を少しずつ受け取る
        "think": False,   # 思考はオフ（思考は 04 で見る）
    }

    print("── 送ったデータ " + "─" * 40)
    print(json.dumps(request, ensure_ascii=False, indent=2))

    print("\n── 返ってきたデータ（届いた順）" + "─" * 26)
    answer = ""
    last = None
    for chunk in ollama.chat(**request):
        # 1行 = 1回分の書き足し。読みやすさのため model と created_at は省いている
        print(chunk.model_dump_json(exclude_none=True, exclude={"model", "created_at"}))
        answer += chunk.message.content or ""
        last = chunk

    print("\n── まとめると " + "─" * 42)
    print(answer)
    if last and last.eval_count and last.eval_duration:
        seconds = last.eval_duration / 1e9  # ナノ秒 → 秒
        print(f"\n書いたトークン数: {last.eval_count}　かかった時間: {seconds:.2f}秒"
              f"（1秒に約{last.eval_count / seconds:.0f}トークン）")


if __name__ == "__main__":
    run(main)
