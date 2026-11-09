"""運営用：第2回の教材を実機でまとめて検証する（回ごとに verify_session<回>.py を作る）。

教材フォルダ（pyproject.toml がある場所）で実行する:
    uv run internal/tools/verify_session2.py            # 全部（ツール呼び出しの候補を3回ずつ）
    uv run internal/tools/verify_session2.py --quick    # 候補を1回ずつにして短く

結果は internal/verify_results/session2/<日時>/ に保存される。途中で止めても、そこまでの結果は残る。
"""
import importlib.util
import json
import sys
import time
from pathlib import Path

import ollama

from verify_common import ROOT, environment, log, results_dir, run_script, save

SMALL = "qwen3.5:0.8b"
BIG_CANDIDATES = ["qwen3.5:4b", "qwen3.5:2b"]
MAX_STEPS = 6
MAX_TOKENS = 2048

# 教材と同じ架空の図書館（session2/_library.py）を読み込む
_spec = importlib.util.spec_from_file_location("_library", ROOT / "session2" / "_library.py")
assert _spec and _spec.loader
lib = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lib)


def first_is(name: str, **want):
    """最初に使ったツールが name で、引数に want の値（大文字小文字は無視して含む）が入っているか。"""
    def check(calls, answer):
        if not calls:
            return False
        c = calls[0]
        return c["name"] == name and all(v.lower() in str(c["args"].get(k, "")).lower() for k, v in want.items())
    return check


# Agent の課題の候補。check で「うまくいったか」を機械的に判定する（最後は人が答えを読んで確かめる）
CANDIDATES = [
    ("single", "B001 の本は、いま借りられますか？", "最初に check_availability(B001)",
     first_is("check_availability", book_id="B001")),
    ("search", "Pythonの本を探して", "最初に search_books(Python を含む)",
     first_is("search_books", keyword="python")),
    ("chain", "「AIエージェント入門」を借りたいです。借りられるなら借りてください", "B005 が貸出された",
     lambda calls, answer: "B005" in lib.loans),
    ("multi", "AIの本で、いま借りられるものをすべて教えて", "答えに B003 と B005 の書名がある",
     lambda calls, answer: "やさしい機械学習" in answer and "AIエージェント入門" in answer),
    ("unavailable", "「生成AIのしくみ」を借りてください", "B004 を借りず、貸出中と答える",
     lambda calls, answer: lib.loans.get("B004") == lib.FIRST_LOANS["B004"] and "貸出中" in answer),
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

    # 1) 教材のスクリプトを、参加者と同じ形で実行する
    scripts = [
        ("2.1_tool_call", ["2.1_tool_call.py"]),
        ("2.1_tool_call_hello", ["2.1_tool_call.py", "こんにちは"]),
        ("2.2_tool_prompt", ["2.2_tool_prompt.py"]),
        ("3.1_one_round", ["3.1_one_round.py"]),
        ("3.2_agent_loop", ["3.2_agent_loop.py"]),
        ("3.3_my_tool", ["3.3_my_tool.py"]),
        ("3.3_my_tool_without", ["3.3_my_tool.py", "--without"]),
        ("4.1_compare_list", ["4.1_compare.py"]),
        ("4.1_compare_q1", ["4.1_compare.py", "1"]),
        ("4.1_compare_q2", ["4.1_compare.py", "2"]),
        ("4.1_compare_q3", ["4.1_compare.py", "3"]),
        ("4.1_compare_q1_think", ["4.1_compare.py", "1", "--think"]),
        ("4.2_confirm", ["4.2_confirm.py"]),   # 入力なし → 「いいえ」として進む
    ]
    for name, args in scripts:
        run_script(out, "session2", name, args)

    # 2) ツール呼び出しの候補（モデル × 思考あり／なし × trials 回）
    path = out / "20_tool_call_candidates.json"
    rows = []
    for key, task, expect, check in CANDIDATES:
        for model in [SMALL, big]:
            for think in [False, True]:
                for t in range(trials):
                    log(f"候補 {key} / {model} / 思考{'あり' if think else 'なし'}（{t + 1}/{trials}回目）")
                    r = agent(model, task, think)
                    rows.append({"key": key, "task": task, "expect": expect, "model": model, "think": think,
                                 "trial": t + 1, "ok": bool(check(r["calls"], r["answer"])), **r})
                    save(path, rows)  # 1回ごとに保存（途中で止めても残る）

    summary(out, rows)
    log(f"完了しました。結果: {out}")


def agent(model: str, task: str, think: bool) -> dict:
    """教材の 3.2 と同じ Agent のくり返しを、表示なしで実行して記録する。"""
    lib.reset()
    start = time.perf_counter()
    messages: list = [{"role": "user", "content": task}]
    calls, thinking_chars = [], 0
    for step in range(1, MAX_STEPS + 1):
        res = ollama.chat(model=model, messages=messages, tools=lib.TOOLS, think=think,
                          options={"num_predict": MAX_TOKENS})
        messages.append(res.message)
        thinking_chars += len(res.message.thinking or "")
        if not res.message.tool_calls:
            return {"answer": res.message.content or "", "steps": step, "calls": calls, "answered": True,
                    "thinking_chars": thinking_chars, "seconds": round(time.perf_counter() - start, 1),
                    "cut": res.done_reason == "length"}
        for c in res.message.tool_calls:
            args = dict(c.function.arguments or {})
            result = lib.call_tool(c.function.name, args)
            calls.append({"name": c.function.name, "args": args, "result": json.loads(result)})
            messages.append({"role": "tool", "tool_name": c.function.name, "content": result})
    return {"answer": "", "steps": MAX_STEPS, "calls": calls, "answered": False,
            "thinking_chars": thinking_chars, "seconds": round(time.perf_counter() - start, 1), "cut": False}


def summary(out: Path, rows: list[dict]) -> None:
    lines = ["# ツール呼び出しの候補（成功の数と時間）", "",
             "| 課題 | モデル | 思考 | 成功 | 平均秒 | 平均ツール回数 |", "| --- | --- | --- | --- | --- | --- |"]
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        groups.setdefault((r["key"], r["model"], r["think"]), []).append(r)
    for (key, model, think), rs in groups.items():
        ok = sum(r["ok"] for r in rs)
        secs = sum(r["seconds"] for r in rs) / len(rs)
        n_calls = sum(len(r["calls"]) for r in rs) / len(rs)
        lines.append(f"| {key} | {model} | {'あり' if think else 'なし'} | {ok}/{len(rs)} | {secs:.1f} | {n_calls:.1f} |")
    lines += ["", "## 各回の流れ", ""]
    for r in rows:
        flow = " → ".join(f"{c['name']}({json.dumps(c['args'], ensure_ascii=False)})" for c in r["calls"]) or "なし"
        ans = r["answer"].replace("\n", " ")[:80] or "（答えなし）"
        lines.append(f"- {r['key']} / {r['model']} / 思考{'あり' if r['think'] else 'なし'} / {r['trial']}回目"
                     f"：{'成功' if r['ok'] else '失敗'}、{flow}、答え「{ans}」")
    (out / "41_compare_summary.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
