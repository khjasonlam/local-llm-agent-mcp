"""第2回のスクリプトで共通に使う、ちょっとした関数（読み飛ばして大丈夫です）。"""
import sys
import unicodedata

import httpx
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


def free_memory(keep: str) -> None:
    """keep 以外の、メモリに読み込まれているモデルを外す。

    Ollama は使ったモデルをしばらくメモリに残すので、2つのモデルを続けて使うと両方が載ったままになる。
    メモリ8GBのPCや、Google Meet などを開いたままのPCで重くならないように、使う前に外しておく。
    """
    for m in ollama.ps().models:
        if m.model and m.model != keep:
            ollama.generate(model=m.model, keep_alive=0)  # keep_alive=0 で「すぐ外す」


def text_width(s: str) -> int:
    """画面上の幅（全角は2、半角は1）。"""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s: str, width: int) -> str:
    return s + " " * max(0, width - text_width(s))


def heading(title: str) -> str:
    """「── 見出し ─────」の形の区切り線を返す（全角を含んでも長さがそろう）。"""
    head = f"── {title} "
    return head + "─" * max(4, 56 - text_width(head))


def run(main) -> None:
    """main() を実行し、よくあるエラーをわかりやすく表示する。"""
    try:
        main()
    except ConnectionError:
        sys.exit("Ollama に接続できません。Ollama のアプリが起動しているか確認してください。")
    except ollama.ResponseError as e:
        if "does not support tools" in e.error:
            sys.exit(f"このモデルはツールを使えません：{e.error}")
        sys.exit(f"Ollama からエラーが返りました：{e.error}")
    except httpx.TransportError:  # 返事を受け取っている途中で切れたとき（メモリ不足で Ollama が止まった場合など）
        sys.exit("Ollama との接続が切れました。Ollama のアプリが起動しているか確認し、ほかのアプリを閉じてからもう一度試してください。")
    except KeyboardInterrupt:
        print("\n中断しました。")
