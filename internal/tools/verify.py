"""運営用：第1回の教材を実機でまとめて検証する。

教材フォルダ（pyproject.toml がある場所）で実行する:
    uv run internal/tools/verify.py            # 全部（20分前後）
    uv run internal/tools/verify.py --quick    # 比較の質問を1回ずつにして短く（10分前後）

結果は internal/verify_results/<日時>/ に保存される。途中で止めても、そこまでの結果は残る。
"""
import json
import math
import os
import platform
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
import ollama

ROOT = Path(__file__).resolve().parents[2]
S1 = ROOT / "session1"
SMALL = "qwen3.5:0.8b"
BIG_CANDIDATES = ["qwen3.5:4b", "qwen3.5:2b"]

# 4.1 の比較に使う質問の候補。expect は正解の目安（判定は人が答えを読んで行う）
COMPARE_CANDIDATES = [
    ("strawberry", "英単語 strawberry の中に、r は何個ありますか？", "3個"),
    ("lily", "池の睡蓮は毎日2倍に増え、48日目に池全体を覆いました。池の半分を覆ったのは何日目ですか？", "47日目"),
    ("cover", "本とブックカバーを合わせて1100円です。本はブックカバーより1000円高いです。ブックカバーは何円ですか？", "50円"),
]
LIMITS = {"small": 2048, "big": 4096}

# 3.2 の既定の質問の候補
ANSWER_TOKEN_CANDIDATES = [
    "新しいカフェの名前を1つ考えて。名前だけ答えて",
    "日本の首都を一言で答えて",
    "「おはようございます」を英語にして。訳だけ答えて",
]

# 3.1 の既定の書きかけの文の候補
NEXT_TOKEN_CANDIDATES = ["日本の首都は", "むかしむかし、あるところに"]


def main():
    quick = "--quick" in sys.argv
    trials = 1 if quick else 3
    out = ROOT / "internal" / "verify_results" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    log(f"結果の保存先: {out}")

    env = environment()
    save(out / "00_environment.json", env)
    big = next((m for m in BIG_CANDIDATES if m in env["models"]), None)
    if SMALL not in env["models"] or not big:
        log(f"モデルが足りません。必要: {SMALL} と {' / '.join(BIG_CANDIDATES)} のどちらか。今あるもの: {env['models']}")
        sys.exit(1)

    # 1) 教材のスクリプトを、参加者と同じ形で実行する
    scripts = [
        ("2.1_api", ["2.1_api.py"]),
        ("3.1_next_token", ["3.1_next_token.py"]),
        ("3.2_answer_tokens", ["3.2_answer_tokens.py"]),
        ("3.2_answer_tokens_rare", ["3.2_answer_tokens.py", "「バラ」を漢字で書いて。漢字だけ答えて"]),
        ("3.2_answer_tokens_temp0_a", ["3.2_answer_tokens.py", "--temperature", "0"]),
        ("3.2_answer_tokens_temp0_b", ["3.2_answer_tokens.py", "--temperature", "0"]),
        ("4.1_compare_list", ["4.1_compare.py"]),
        ("4.1_compare_q1", ["4.1_compare.py", "1"]),
        ("4.1_compare_q1_nothink", ["4.1_compare.py", "1", "--no-think"]),
        ("4.1_compare_q2", ["4.1_compare.py", "2"]),
        ("4.1_compare_q3", ["4.1_compare.py", "3"]),
        ("2.2_openai_compat", ["2.2_openai_compat.py"]),
        ("2.3_history", ["2.3_history.py"]),
        ("3.3_image", ["3.3_image.py"]),
        ("3.4_pdf", ["3.4_pdf.py"]),
    ]
    for name, args in scripts:
        run_script(out, name, args)

    # 2) 3.1 の書きかけの文の候補
    rows = []
    for text in NEXT_TOKEN_CANDIDATES:
        log(f"3.1 候補: {text}")
        res = ollama.generate(model=big, prompt=text, raw=True, options={"num_predict": 1},
                              logprobs=True, top_logprobs=10)
        if not res.logprobs:
            log("  → 確率が返ってきませんでした（Ollama が古い可能性）")
            continue
        step = res.logprobs[0]
        rows.append({"prompt": text, "chosen": step.token,
                     "top": [(c.token, round(math.exp(c.logprob), 4)) for c in step.top_logprobs or []]})
    save(out / "20_next_token_candidates.json", rows)

    # 3) 3.2 の質問の候補（ばらつきを見るため2回ずつ）
    rows = []
    for q in ANSWER_TOKEN_CANDIDATES:
        for t in range(2):
            log(f"3.2 候補（{t + 1}回目）: {q}")
            res = ollama.chat(model=big, messages=[{"role": "user", "content": q}], think=False,
                              logprobs=True, top_logprobs=4)
            steps = [{"token": s.token, "p": round(math.exp(s.logprob), 4),
                      "others": [(c.token, round(math.exp(c.logprob), 4)) for c in s.top_logprobs or []]}
                     for s in res.logprobs or []]
            rows.append({"question": q, "trial": t + 1, "answer": res.message.content,
                         "hesitated": sum(s["p"] < 0.5 for s in steps), "steps": steps})
    save(out / "30_answer_token_candidates.json", rows)

    # 4) 4.1 の比較に使う質問の候補（各モデル trials 回ずつ）
    path = out / "40_compare_candidates.json"
    rows = []
    for key, q, expect in COMPARE_CANDIDATES:
        for model in [SMALL, big]:
            for t in range(trials):
                log(f"4.1 候補 {key} / {model}（{t + 1}/{trials}回目）")
                limit = LIMITS["small"] if model == SMALL else LIMITS["big"]
                rows.append({"key": key, "question": q, "expect": expect, "model": model, "trial": t + 1,
                             **ask(model, q, limit)})
                save(path, rows)  # 1回ごとに保存（途中で止めても残る）

    summary(out, rows, trials)
    log(f"完了しました。結果: {out}")


def environment() -> dict:
    try:
        server = httpx.get("http://localhost:11434/api/version", timeout=5).json().get("version")
    except Exception as e:  # noqa: BLE001
        log(f"Ollama に接続できません: {e}")
        sys.exit(1)
    models = sorted(m.model for m in ollama.list().models if m.model)
    lib = subprocess.run([sys.executable, "-c", "import importlib.metadata as m; print(m.version('ollama'))"],
                         capture_output=True, text=True).stdout.strip()
    env = {"ollama_server": server, "ollama_python": lib, "python": sys.version.split()[0],
           "os": f"{platform.system()} {platform.release()} {platform.machine()}", "models": models}
    log(json.dumps(env, ensure_ascii=False))
    return env


def run_script(out: Path, name: str, args: list[str]) -> None:
    log(f"実行: session1/{' '.join(args)}")
    start = time.perf_counter()
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    p = subprocess.run([sys.executable, str(S1 / args[0]), *args[1:]], cwd=ROOT, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    secs = time.perf_counter() - start
    (out / f"1x_{name}.txt").write_text(
        f"$ uv run session1/{' '.join(args)}\n# 終了コード {p.returncode} / {secs:.1f}秒\n\n"
        f"{p.stdout}\n--- stderr ---\n{p.stderr}", encoding="utf-8")
    log(f"  → 終了コード {p.returncode}（{secs:.1f}秒）")


def ask(model: str, question: str, limit: int) -> dict:
    start = time.perf_counter()
    res = ollama.chat(model=model, messages=[{"role": "user", "content": question}], think=True,
                      options={"num_predict": limit})
    return {"answer": res.message.content or "", "thinking": res.message.thinking or "",
            "thinking_chars": len(res.message.thinking or ""), "tokens": res.eval_count,
            "seconds": round(time.perf_counter() - start, 1), "cut": res.done_reason == "length"}


def summary(out: Path, rows: list[dict], trials: int) -> None:
    lines = ["# 4.1 比較の候補（答えの先頭と思考の長さ）", ""]
    for key, q, expect in COMPARE_CANDIDATES:
        lines += [f"## {key}：{q}（目安: {expect}）", "", "| モデル | 回 | 思考文字数 | 秒 | 答え（先頭80字） |",
                  "| --- | --- | --- | --- | --- |"]
        for r in rows:
            if r["key"] == key:
                ans = r["answer"].replace("\n", " ")[:80] + ("（打ち切り）" if r["cut"] else "")
                lines.append(f"| {r['model']} | {r['trial']} | {r['thinking_chars']} | {r['seconds']} | {ans} |")
        lines.append("")
    (out / "41_compare_summary.md").write_text("\n".join(lines), encoding="utf-8")


def save(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


if __name__ == "__main__":
    main()
