"""運営用：第3回の教材を実機でまとめて検証する（回ごとに verify_session<回>.py を作る）。

教材フォルダ（pyproject.toml がある場所）で実行する:
    uv run internal/tools/verify_session3.py            # 全部（Agent の課題を3回ずつ）
    uv run internal/tools/verify_session3.py --quick    # 課題を1回ずつにして短く

結果は internal/verify_results/session3/<日時>/ に保存される。途中で止めても、そこまでの結果は残る。

第3回は、教材のスクリプト（4.1・4.2）をそのまま実行して、画面の表示から成功かどうかを判定する。
教材は temperature 0（くじ引きなし）で動くので、同じ PC・同じモデルなら、くり返しても同じ流れになるはず（そうなるかも確かめる）。
サーバーを別のプログラムとして起動するところ（Windows で特に確かめたい部分）も、参加者と同じ形で通るようにするため。
"""
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from verify_common import ROOT, environment, log, results_dir, run_script, save

BIG_CANDIDATES = ["qwen3.5:4b", "qwen3.5:2b"]
ORDERED = "を発注しました"            # 発注サーバーの place_order が成功したときの結果に入る言葉
SENT = "にメッセージを送りました"     # チャット通知サーバーの send_message が成功したときの結果に入る言葉
CANCELED = "取りやめました"           # 確認で「いいえ」のときに Agent が画面に出す言葉
EXTERNAL = "外部なので頼む"           # Agent が MCP でサーバーに頼んだときの表示


def says_days(answer: str, days: int) -> bool:
    """答えに「○日」（日付の「12月10日」ではなく日数）として days が書いてあるか。全角数字もそろえて見る。"""
    answer = answer.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    return re.search(rf"(?<![0-9月]){days}\s*日", answer) is not None


# Agent の課題。（名前, スクリプト, 質問（None なら既定の質問）, y/n への答え, 成功の条件の説明, 判定）
# 判定は画面の表示（text）と最後の答え（answer）から機械的に行う。最後は人が流れと答えを読んで確かめる。
CANDIDATES = [
    ("order", "4.1_mcp_agent.py", None, "y",
     "既定の質問。発注サーバーの place_order が成功し、答えまでたどり着く",
     lambda text, answer: ORDERED in text and bool(answer)),
    ("order_no", "4.1_mcp_agent.py", None, "n",
     "既定の質問で、確認に n と答える。place_order まで進み、発注されずに Agent が取りやめを伝えて終わる",
     lambda text, answer: ORDERED not in text and CANCELED in text and "── まとめ" in text),
    ("days", "4.1_mcp_agent.py", "「はじめてのGo」は、発注したら何日で届きますか？発注はしないでください", "n",
     "発注サーバーの check_stock を使い、発注せずに「3日」と答える",
     lambda text, answer: "check_stock" in text and ORDERED not in text and says_days(answer, 3)),
    ("library", "4.1_mcp_agent.py", "「AIエージェント入門」は、いま図書館で借りられますか？", "n",
     "内蔵の図書館の道具だけで答える（外部のサーバーには頼まない）",
     lambda text, answer: EXTERNAL not in text and "内蔵なので自分で実行" in text and bool(answer)),
    ("notify", "4.2_add_server.py", None, "y",
     "既定の質問。place_order と send_message の両方が成功し、答えまでたどり着く",
     lambda text, answer: ORDERED in text and SENT in text and bool(answer)),
]


def main():
    quick = "--quick" in sys.argv
    trials = 1 if quick else 3
    out = results_dir(3)

    env = environment()
    save(out / "00_environment.json", env)
    big = next((m for m in BIG_CANDIDATES if m in env["models"]), None)
    if not big:
        log(f"モデルが足りません。必要: {' / '.join(BIG_CANDIDATES)} のどちらか。今あるもの: {env['models']}")
        sys.exit(1)

    # 1) 教材のスクリプトを、参加者と同じ形で実行する（入力なし。Enter は待たずに進み、y/n は「いいえ」になる）
    scripts = [
        ("0_check", ["0_check.py"]),
        ("3.1_talk_to_server", ["3.1_talk_to_server.py"]),
        ("3.1_talk_to_server_go", ["3.1_talk_to_server.py", "Go"]),
        ("4.1_mcp_agent", ["4.1_mcp_agent.py"]),
        ("4.2_add_server", ["4.2_add_server.py"]),
    ]
    for name, args in scripts:
        run_script(out, "session3", name, args)

    # 2) Agent の課題（y/n に答えながら、教材のスクリプトをそのまま trials 回ずつ実行する）
    path = out / "30_agent_candidates.json"
    rows = []
    for key, script, question, yn, expect, check in CANDIDATES:
        for t in range(trials):
            log(f"課題 {key} / {big}（{t + 1}/{trials}回目）")
            r = agent(script, question, yn)
            rows.append({"key": key, "script": script, "question": question or "（既定）", "yn": yn, "expect": expect,
                         "model": big, "trial": t + 1, "ok": bool(check(r["text"], r["answer"])), **r})
            save(path, rows)  # 1回ごとに保存（途中で止めても残る）

    summary(out, rows)
    log(f"完了しました。結果: {out}")


def agent(script: str, question: str | None, yn: str) -> dict:
    """教材のスクリプトを実行し、確認にはすべて yn で答えて、画面の表示から流れを読み取る。"""
    args = [sys.executable, str(ROOT / "session3" / script)] + ([question] if question else [])
    start = time.perf_counter()
    p = subprocess.run(args, cwd=ROOT, env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                       input=f"{yn}\n" * 10, capture_output=True, text=True, encoding="utf-8", errors="replace")
    seconds = round(time.perf_counter() - start, 1)
    text = p.stdout
    answer = ""
    if "── 答え" in text:
        answer = text.split("── 答え", 1)[1].split("\n", 1)[1].split("── まとめ", 1)[0].strip()
    calls = re.findall(r"Agent ← LLM\s+(\w+) を (\{.*?\}) で使いたい", text)
    return {"returncode": p.returncode, "seconds": seconds, "steps": len(re.findall(r"回目の往復", text)),
            "calls": [{"name": n, "args": a} for n, a in calls], "answer": answer, "text": text, "stderr": p.stderr}


def summary(out: Path, rows: list[dict]) -> None:
    lines = ["# 第3回の Agent の課題（成功の数と時間）", "",
             "| 課題 | モデル | y/n | 成功 | 平均秒 | 平均ツール回数 | 平均往復 |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(r["key"], []).append(r)
    for key, rs in groups.items():
        ok = sum(r["ok"] for r in rs)
        secs = sum(r["seconds"] for r in rs) / len(rs)
        n_calls = sum(len(r["calls"]) for r in rs) / len(rs)
        steps = sum(r["steps"] for r in rs) / len(rs)
        lines.append(f"| {key} | {rs[0]['model']} | {rs[0]['yn']} | {ok}/{len(rs)} | {secs:.1f} | {n_calls:.1f} | {steps:.1f} |")
    lines += ["", "秒数には、モデルの読み込みと、サーバーの起動も含む。", "", "## 成功の判定", ""]
    lines += [f"- {key}（{script}、質問：{question or '既定'}）：{expect}" for key, script, question, _, expect, _ in CANDIDATES]
    lines += ["", "## 各回の流れ", ""]
    for r in rows:
        flow = " → ".join(f"{c['name']}({c['args']})" for c in r["calls"]) or "なし"
        ans = r["answer"].replace("\n", " ")[:80] or "（答えなし）"
        lines.append(f"- {r['key']} / {r['trial']}回目：{'成功' if r['ok'] else '失敗'}、{r['seconds']}秒、"
                     f"終了コード {r['returncode']}、{flow}、答え「{ans}」")
    (out / "31_agent_summary.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
