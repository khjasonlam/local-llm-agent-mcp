"""運営用：各回の verify_sessionN.py で共通に使う処理。

結果のフォルダを作る、環境を記録する、教材のスクリプトを参加者と同じ形で実行する、保存する、など。
このファイルを直接実行することはない。
"""
import json
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


def results_dir(session: int) -> Path:
    """結果の保存先 internal/verify_results/session<回>/<日時>/ を作って返す。"""
    out = ROOT / "internal" / "verify_results" / f"session{session}" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    log(f"結果の保存先: {out}")
    return out


def environment() -> dict:
    """Ollama・Python・OS の版と、入っているモデルを調べる。Ollama に接続できなければ終了する。"""
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


def run_script(out: Path, folder: str, name: str, args: list[str]) -> None:
    """教材のスクリプト（folder/args[0]）を参加者と同じ形で実行し、画面の出力を 1x_<name>.txt に保存する。"""
    log(f"実行: {folder}/{' '.join(args)}")
    start = time.perf_counter()
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    # stdin は空にする（y/n を聞くスクリプトでも止まらず、「入力なし」として進む）
    p = subprocess.run([sys.executable, str(ROOT / folder / args[0]), *args[1:]], cwd=ROOT, env=env,
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace")
    secs = time.perf_counter() - start
    (out / f"1x_{name}.txt").write_text(
        f"$ uv run {folder}/{' '.join(args)}\n# 終了コード {p.returncode} / {secs:.1f}秒\n\n"
        f"{p.stdout}\n--- stderr ---\n{p.stderr}", encoding="utf-8")
    log(f"  → 終了コード {p.returncode}（{secs:.1f}秒）")


def save(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)
