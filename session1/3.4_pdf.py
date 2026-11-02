"""3.4（もっと試す）PDFを読ませる

Ollama には、PDF などのファイルをそのまま渡す機能はない。
ChatGPT などの「ファイル添付」も、アプリが裏で PDF から文字（または画像）を取り出し、
それをトークンにしてから LLM に渡している。ここではその「取り出す」部分を自分でやる。

実行:  uv run session1/3.4_pdf.py                     付属の assets/sample.pdf（架空の社内図書館の利用案内）を読ませる
       uv run session1/3.4_pdf.py PDFファイルのパス
"""
import sys
from pathlib import Path

import ollama
from pypdf import PdfReader

from _common import big_model, run


def main():
    pdf = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "assets" / "sample.pdf"
    if not pdf.exists():
        sys.exit(f"PDF が見つかりません: {pdf}")

    # PDF から文字だけを取り出す（LLM に渡るのは、この文字だけ）
    text = "\n".join(page.extract_text() or "" for page in PdfReader(pdf).pages).strip()
    if not text:
        sys.exit("文字を取り出せませんでした。スキャンした画像だけの PDF かもしれません。")

    model = big_model()
    print(f"モデル: {model}\nPDF　 : {pdf.name}\n")
    print("── LLM に渡した文字（PDF から取り出したもの）" + "─" * 16)
    print(text)
    print("\n── 返事 " + "─" * 46)

    stream = ollama.chat(
        model=model,
        messages=[{
            "role": "user",
            "content": f"次の文書を読んで、大事な点を日本語で3行にまとめて。\n\n{text}",
        }],
        think=False,
        stream=True,
    )
    for chunk in stream:
        print(chunk.message.content or "", end="", flush=True)
    print()


if __name__ == "__main__":
    run(main)
