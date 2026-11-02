"""05（持ち帰り）画像を読ませる

qwen3.5 は画像も読める。画像もいったんトークンに変換され、
文章と同じように「次のトークンの予測」で説明文が書かれる。

実行:  uv run session1/05_image.py                     付属の sample.png を読ませる
       uv run session1/05_image.py 画像ファイルのパス
"""
import sys
from pathlib import Path

import ollama

from _common import big_model, run


def main():
    image = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "sample.png"
    if not image.exists():
        sys.exit(f"画像が見つかりません: {image}")
    model = big_model()
    print(f"モデル: {model}\n画像　: {image.name}\n")

    stream = ollama.chat(
        model=model,
        messages=[{
            "role": "user",
            "content": "この画像に何が写っているか、日本語で3行で説明して",
            "images": [str(image)],  # ファイルのパスを渡すと、ライブラリが中身を送ってくれる
        }],
        think=False,
        stream=True,
    )
    for chunk in stream:
        print(chunk.message.content or "", end="", flush=True)
    print()


if __name__ == "__main__":
    run(main)
