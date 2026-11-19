"""2.2（もっと試す）ツールの説明も「ただの文字」として渡っていることを確かめる

2.1 では tools という欄でツールの説明を送ったが、LLM が読めるのは結局ひと続きの文字だけ。
Ollama は送られた messages と tools を、モデルが学習した決まった形の文章に組み立ててから渡している。
ここでは、その組み立てを自分で行い（形は qwen3.5 の決まりにならう）、
第1回 3.1 と同じ raw（加工なし）で渡す。LLM が「ツールを使いたい」という文字を書き足す様子を見る。

実行:  uv run session2/2.2_tool_prompt.py
       uv run session2/2.2_tool_prompt.py "好きな質問"
"""
import json
import sys

import ollama

from _common import big_model, heading, run
from _library import TOOLS


def main():
    model = big_model()
    question = sys.argv[1] if len(sys.argv) > 1 else "Pythonの本を探して"

    # ツールの説明を、ひと続きの文章に組み立てる（qwen3.5 が学習した決まりの形）。
    # <|im_start|> や <|im_end|> は「ここから誰の発言か」を表す、モデル用の特別な目印。
    # ツールの説明は JSON のまま並べ、「使いたいときは <tool_call> の形で書く」という決まりを英語で添える
    tool_lines = "\n".join(json.dumps(t, ensure_ascii=False) for t in TOOLS)
    prompt = (
        "<|im_start|>system\n"
        "# Tools\n\n"
        "You have access to the following functions:\n\n"
        f"<tools>\n{tool_lines}\n</tools>\n\n"
        "If you choose to call a function ONLY reply in the following format with NO suffix:\n\n"
        "<tool_call>\n"
        "<function=example_function_name>\n"
        "<parameter=example_parameter_1>\n"
        "value_1\n"
        "</parameter>\n"
        "</function>\n"
        "</tool_call>\n\n"
        "<IMPORTANT>\n"
        "Reminder:\n"
        "- Function calls MUST follow the specified format: an inner <function=...></function> "
        "block must be nested within <tool_call></tool_call> XML tags\n"
        "- Required parameters MUST be specified\n"
        "- You may provide optional reasoning for your function call in natural language "
        "BEFORE the function call, but NOT after\n"
        "- If there is no function call available, answer the question like normal with your "
        "current knowledge and do not tell the user about function calls\n"
        "</IMPORTANT><|im_end|>\n"
        f"<|im_start|>user\n{question}<|im_end|>\n"
        "<|im_start|>assistant\n"
        "<think>\n\n</think>\n\n"   # 思考は空にしておく（思考なしで答えさせる）
    )

    print(heading("LLM に渡した文字（これで全部）"))
    print(prompt)

    print(heading("LLM が続きに書き足した文字"))
    res = ollama.generate(model=model, prompt=prompt, raw=True, options={"num_predict": 200})
    print(res.response)

    print("\n" + heading("つまり"))
    print("ツールの説明も、ツールを使いたいという返事も、どちらも「ただの文字」です。")
    print("<tool_call> の中の <function=…>（ツールの名前）と <parameter=…>（引数）を読み取り、")
    print("2.1 の tool_calls の形（JSON）にしているのは Ollama です。")


if __name__ == "__main__":
    run(main)
