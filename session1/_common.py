"""第1回のスクリプトで共通に使う、ちょっとした関数（読み飛ばして大丈夫です）。"""
import sys
import unicodedata

import ollama

SMALL_MODEL = "qwen3.5:0.8b"
BIG_MODEL_CANDIDATES = ["qwen3.5:4b", "qwen3.5:2b"]  # メモリ16GB以上なら4b、8GBなら2b


def installed_models() -> set[str]:
    return {m.model for m in ollama.list().models if m.model}


def big_model() -> str:
    """大きい方のモデル名を返す（4b があれば 4b、なければ 2b）。"""
    names = installed_models()
    for name in BIG_MODEL_CANDIDATES:
        if name in names:
            return name
    sys.exit("qwen3.5:4b も qwen3.5:2b も見つかりません。事前準備の手順2（ollama pull）を確認してください。")


def small_model() -> str:
    if SMALL_MODEL not in installed_models():
        sys.exit(f"{SMALL_MODEL} が見つかりません。事前準備の手順2（ollama pull {SMALL_MODEL}）を確認してください。")
    return SMALL_MODEL


def show_token(token: str) -> str:
    """トークンを画面で見やすい形にする。

    日本語の1文字が2つのトークンに分かれると、Ollama は途中の部分を「�」で返す。
    それを「（文字の一部）」と表示する。
    <|im_end|> のような特別なトークンは「ここで書き終える」という合図なので、「（書き終わり）」と表示する。
    """
    if "�" in token:
        return "（文字の一部）"
    if token.startswith("<|") and token.endswith("|>"):
        return "（書き終わり）"
    if token == "":
        return "（空）"
    return token.replace("\n", "[改行]").replace(" ", "[空白]")


def text_width(s: str) -> int:
    """画面上の幅（全角は2、半角は1）。"""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s: str, width: int) -> str:
    return s + " " * max(0, width - text_width(s))


def bar(p: float, width: int = 30) -> str:
    """確率 p（0〜1）を棒で表す。"""
    full = int(p * width)
    half = "▌" if p * width - full >= 0.5 else ""
    return "█" * full + half


def run(main) -> None:
    """main() を実行し、よくあるエラーをわかりやすく表示する。"""
    try:
        main()
    except ConnectionError:
        sys.exit("Ollama に接続できません。Ollama のアプリが起動しているか確認してください。")
    except ollama.ResponseError as e:
        sys.exit(f"Ollama からエラーが返りました：{e.error}")
    except Exception as e:
        if type(e).__name__ == "APIConnectionError":  # openai ライブラリ（2.2）の接続エラー
            sys.exit("Ollama に接続できません。Ollama のアプリが起動しているか確認してください。")
        raise
    except KeyboardInterrupt:
        print("\n中断しました。")
