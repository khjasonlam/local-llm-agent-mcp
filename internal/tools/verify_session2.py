"""運営用：第2回の教材を実機でまとめて検証する（回ごとに verify_session<回>.py を作る）。

教材フォルダ（pyproject.toml がある場所）で実行する:
    uv run internal/tools/verify_session2.py            # 全部（ツール呼び出しの候補を3回ずつ）
    uv run internal/tools/verify_session2.py --quick    # 候補を1回ずつにして短く

結果は internal/verify_results/session2/<日時>/ に保存される。途中で止めても、そこまでの結果は残る。
"""
import importlib.util
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

import ollama

from verify_common import ROOT, environment, log, results_dir, run_script, save

SMALL = "qwen3.5:0.8b"
BIG_CANDIDATES = ["qwen3.5:4b", "qwen3.5:2b"]
MAX_STEPS = 6
MAX_TOKENS = 1024        # 教材の 3.2・4.1 と同じ上限
MAX_TOKENS_THINK = 2048  # 教材の 4.1 --think と同じ上限


def load_session2(name: str):
    """session2/ のモジュールを読み込む（教材と同じツール・同じ処理で測るため）。

    sys.modules に登録するので、あとで読み込む 3.3 の `from _library import …` も同じモジュールを使う
    （貸出の記録が1つにまとまり、reset() が効く）。
    """
    spec = importlib.util.spec_from_file_location(name, ROOT / "session2" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


lib = load_session2("_library")         # 架空の図書館のツール
common = load_session2("_common")       # free_memory() を使う
my_tool = load_session2("3.3_my_tool")  # 3.3 のツール一覧（get_today を足し、borrow_book を外したもの）


def first_is(name: str, **want):
    """最初に使ったツールが name で、引数に want の値（大文字小文字は無視して含む）が入っているか。"""
    def check(calls, answer):
        if not calls:
            return False
        c = calls[0]
        return c["name"] == name and all(v.lower() in str(c["args"].get(k, "")).lower() for k, v in want.items())
    return check


UNAVAILABLE_WORDS = ("貸出中", "貸し出し中", "貸出し中", "借りられません", "借りられない", "借りることができません",
                     "借りることができない", "貸し出されて", "可能ではない", "可能ではありません")


# 「貸出中ではありません」「貸し出されていません」のような打ち消し（＝借りられる）は、先に除いてから見る
NEGATED = re.compile(r"(貸出中|貸し出し中|貸出し中)(では|じゃ)(ない|なく|ありません)|貸し?出されて(いない|いません|おらず)")


def plain(text: str) -> str:
    """全角の英数字を半角にそろえ、空白を除く（「Python でつくる」と「Pythonでつくる」を同じに見る）。"""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


def says_unavailable(answer: str) -> bool:
    """答えに「借りられない」という意味の言葉があるか（打ち消しの「貸出中ではない」は数えない）。"""
    answer = NEGATED.sub("", plain(answer))
    return any(w in answer for w in UNAVAILABLE_WORDS)


def mentions(answer: str, *titles: str) -> bool:
    """答えに titles の書名がすべて書いてあるか（空白の入れ方の違いは無視する）。"""
    answer = plain(answer)
    return all(plain(t) in answer for t in titles)


def used_on(calls, book_id: str, *names: str) -> bool:
    """names のどれかのツールを book_id で使ったか（ツールに断られた場合も含む）。"""
    return any(c["name"] in names and str(c["args"].get("book_id", "")).strip().upper() == book_id for c in calls)


KANJI_DIGITS = "〇一二三四五六七八九"


def kanji_number(text: str) -> str:
    """漢数字（「十」「十七」「二十四」など、99まで）を算用数字にする。"""
    tens, sep, ones = text.partition("十")
    if not sep:
        return str(KANJI_DIGITS.index(text))
    return str((KANJI_DIGITS.index(tens) if tens else 1) * 10 + (KANJI_DIGITS.index(ones) if ones else 0))


def says_days(answer: str, days: int) -> bool:
    """答えに「○日」（日付の「12月10日」ではなく日数）として days が書いてあるか。
    全角数字・漢数字（「十日」）・空白（「10 日」）の違いはそろえて見る。"""
    answer = re.sub(r"[一二三四五六七八九]?十[一二三四五六七八九]?|[〇一二三四五六七八九]",
                    lambda m: kanji_number(m.group()), plain(answer))
    return re.search(rf"(?<![0-9月]){days}日", answer) is not None


B002_DAYS = lib.FIRST_LOANS["B002"]   # B002 が返ってくるのは、実行した日の何日後か

# Agent の課題の候補。check で「うまくいったか」を機械的に判定する（最後は人が答えを読んで確かめる）。
# 5つ目は使うツールの一覧（None なら _library.py の3つ）
CANDIDATES = [
    ("single", "B001 の本は、いま借りられますか？",
     "最初に check_availability(B001) を使い、借りられないとは答えない",
     lambda calls, answer: first_is("check_availability", book_id="B001")(calls, answer)
     and bool(answer) and not says_unavailable(answer), None),
    ("search", "Pythonの本を探して", "最初に search_books(Python を含む) を使い、答えに Python の本2冊の書名がある",
     lambda calls, answer: first_is("search_books", keyword="python")(calls, answer)
     and mentions(answer, "はじめてのPython", "Pythonでつくる業務自動化"), None),
    ("chain", "「AIエージェント入門」を借りたいです。借りられるなら借りてください",
     "B005 が貸出され、答えで借りられないとは言っていない",
     lambda calls, answer: "B005" in lib.loans and bool(answer) and not says_unavailable(answer), None),
    ("multi", "AIの本で、いま借りられるものをすべて教えて",
     "答えに B003 と B005 の書名がある。B004（貸出中）の書名を出すなら、借りられないことも書いている",
     lambda calls, answer: mentions(answer, "やさしい機械学習", "AIエージェント入門")
     and (not mentions(answer, "生成AIのしくみ") or says_unavailable(answer)), None),
    ("unavailable", "「生成AIのしくみ」を借りてください",
     "B004 をツールで確かめて（borrow_book に断られた場合も含む）、借りられないと答える",
     lambda calls, answer: used_on(calls, "B004", "check_availability", "borrow_book") and says_unavailable(answer),
     None),
    ("today", "B002 の本は、あと何日で返ってきますか？",
     f"3.3 のツールで、get_today を使い、答えに「{B002_DAYS}日」がある",
     lambda calls, answer: any(c["name"] == "get_today" for c in calls) and says_days(answer, B002_DAYS),
     (my_tool.MY_TOOLS, my_tool.MY_FUNCTIONS)),
]


def main():
    quick = "--quick" in sys.argv
    trials = 1 if quick else 3
    out = results_dir(2)

    env = environment()
    save(out / "00_environment.json", env)
    big = next((m for m in BIG_CANDIDATES if m in env["models"]), None)
    if SMALL not in env["models"] or not big:
        log(f"モデルが足りません。必要: {SMALL} と {' / '.join(BIG_CANDIDATES)} のどちらか。今あるもの: {env['models']}")
        sys.exit(1)

    # 0) モデルの設定を記録する。いまの Ollama の qwen3.5 は TEMPLATE が {{ .Prompt }} だけで、
    #    組み立ては Ollama に内蔵の RENDERER が行うので、2.2 の手書きの形との見比べには使えない。
    #    手書きの形が合っているかは、2.2 の書き足し（1x_2.2_tool_prompt.txt）が <tool_call> の形かで見る
    info = ollama.show(big)
    save(out / "02_template.json", {"model": big, "modelfile": info.modelfile, "template": info.template})

    # 1) 教材のスクリプトを、参加者と同じ形で実行する
    scripts = [
        ("2.1_tool_call", ["2.1_tool_call.py"]),
        ("2.1_tool_call_hello", ["2.1_tool_call.py", "こんにちは"]),
        ("2.2_tool_prompt", ["2.2_tool_prompt.py"]),
        ("3.1_one_round", ["3.1_one_round.py"]),
        ("3.2_agent_loop", ["3.2_agent_loop.py"]),
        ("3.2_agent_loop_unavailable", ["3.2_agent_loop.py", "「生成AIのしくみ」を借りてください"]),
        ("3.3_my_tool", ["3.3_my_tool.py"]),
        ("3.3_my_tool_think", ["3.3_my_tool.py", "--think"]),
        ("3.3_my_tool_without", ["3.3_my_tool.py", "--without"]),
        ("3.4_confirm", ["3.4_confirm.py"]),   # 入力なし → 「いいえ」として進む
        ("4.1_compare_list", ["4.1_compare.py"]),
        ("4.1_compare_q1", ["4.1_compare.py", "1"]),
        ("4.1_compare_q2", ["4.1_compare.py", "2"]),
        ("4.1_compare_q3", ["4.1_compare.py", "3"]),
        ("4.1_compare_q1_think", ["4.1_compare.py", "1", "--think"]),
    ]
    for name, args in scripts:
        run_script(out, "session2", name, args)

    # 2) ツール呼び出しの候補（モデル × 思考あり／なし × trials 回）
    path = out / "20_tool_call_candidates.json"
    rows = []
    for key, task, expect, check, toolset in CANDIDATES:
        tools, functions = toolset or (lib.TOOLS, lib.FUNCTIONS)
        for model in [SMALL, big]:
            for think in [False, True]:
                for t in range(trials):
                    log(f"候補 {key} / {model} / 思考{'あり' if think else 'なし'}（{t + 1}/{trials}回目）")
                    r = agent(model, task, think, tools, functions)
                    rows.append({"key": key, "task": task, "expect": expect, "model": model, "think": think,
                                 "trial": t + 1, "ok": bool(check(r["calls"], r["answer"])), **r})
                    save(path, rows)  # 1回ごとに保存（途中で止めても残る）

    summary(out, rows)
    log(f"完了しました。結果: {out}")


def agent(model: str, task: str, think: bool, tools: list, functions: dict) -> dict:
    """教材の 4.1 の solve() と同じ Agent のくり返しを、表示なしで実行して記録する。"""
    lib.reset()
    common.free_memory(keep=model)   # もう1つのモデルをメモリから外す（8GB の PC で両方が載らないように）
    ollama.generate(model=model)      # モデルを先に読み込んでおく（読み込みの時間を秒数に入れない）
    start = time.perf_counter()
    messages: list = [{"role": "user", "content": task}]
    calls, thinking_chars = [], 0
    rounds = []   # 往復ごとのトークン数と時間（Ollama の返事に入っている値）
    for step in range(1, MAX_STEPS + 1):
        res = ollama.chat(model=model, messages=messages, tools=tools, think=think,
                          options={"num_predict": MAX_TOKENS_THINK if think else MAX_TOKENS})
        rounds.append({"step": step,
                       "prompt_tokens": res.prompt_eval_count or 0,   # 送った文字（履歴＋ツールの説明）のトークン数
                       "output_tokens": res.eval_count or 0,          # 書いた文字（思考を含む）のトークン数
                       "prompt_secs": round((res.prompt_eval_duration or 0) / 1e9, 2),
                       "output_secs": round((res.eval_duration or 0) / 1e9, 2),
                       "load_secs": round((res.load_duration or 0) / 1e9, 2),
                       "total_secs": round((res.total_duration or 0) / 1e9, 2)})
        messages.append(res.message)
        thinking_chars += len(res.message.thinking or "")
        if not res.message.tool_calls:
            return {"answer": res.message.content or "", "steps": step, "calls": calls, "answered": True,
                    "thinking_chars": thinking_chars, "seconds": round(time.perf_counter() - start, 1),
                    "cut": res.done_reason == "length", "rounds": rounds}
        for c in res.message.tool_calls:
            args = dict(c.function.arguments or {})
            result = lib.call_tool(c.function.name, args, functions)
            calls.append({"name": c.function.name, "args": args, "result": json.loads(result)})
            messages.append({"role": "tool", "tool_name": c.function.name, "content": result})
    return {"answer": "", "steps": MAX_STEPS, "calls": calls, "answered": False,
            "thinking_chars": thinking_chars, "seconds": round(time.perf_counter() - start, 1), "cut": False,
            "rounds": rounds}


def summary(out: Path, rows: list[dict]) -> None:
    lines = ["# ツール呼び出しの候補（成功の数と時間）", "",
             "| 課題 | モデル | 思考 | 成功 | 平均秒 | 平均ツール回数 | 平均往復 | 入力トークン（最後の往復） "
             "| 出力トークン（合計） | 出力の速さ（トークン/秒） |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        groups.setdefault((r["key"], r["model"], r["think"]), []).append(r)
    for (key, model, think), rs in groups.items():
        ok = sum(r["ok"] for r in rs)
        secs = sum(r["seconds"] for r in rs) / len(rs)
        n_calls = sum(len(r["calls"]) for r in rs) / len(rs)
        steps = sum(r["steps"] for r in rs) / len(rs)
        last_in = sum(r["rounds"][-1]["prompt_tokens"] for r in rs) / len(rs)
        out_tok = sum(sum(x["output_tokens"] for x in r["rounds"]) for r in rs) / len(rs)
        out_secs = sum(sum(x["output_secs"] for x in r["rounds"]) for r in rs)
        speed = sum(sum(x["output_tokens"] for x in r["rounds"]) for r in rs) / out_secs if out_secs else 0
        lines.append(f"| {key} | {model} | {'あり' if think else 'なし'} | {ok}/{len(rs)} | {secs:.1f} | {n_calls:.1f}"
                     f" | {steps:.1f} | {last_in:.0f} | {out_tok:.0f} | {speed:.1f} |")
    lines += ["", "## 成功の判定", ""]
    lines += [f"- {key}：{expect}" for key, _, expect, _, _ in CANDIDATES]
    lines += ["", "## 各回の流れ", ""]
    for r in rows:
        flow = " → ".join(f"{c['name']}({json.dumps(c['args'], ensure_ascii=False)})" for c in r["calls"]) or "なし"
        ans = r["answer"].replace("\n", " ")[:80] or "（答えなし）"
        tokens = " / ".join(f"{x['step']}回目 入力{x['prompt_tokens']}・出力{x['output_tokens']}" for x in r["rounds"])
        lines.append(f"- {r['key']} / {r['model']} / 思考{'あり' if r['think'] else 'なし'} / {r['trial']}回目"
                     f"：{'成功' if r['ok'] else '失敗'}、{r['seconds']}秒、{flow}、答え「{ans}」"
                     f"（トークン：{tokens}）")
    (out / "41_compare_summary.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
