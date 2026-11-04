"""運営用：配布する zip を、参加者と同じ手順で動かして確かめる（Ollama は不要）。

    uv run internal/tools/check_zip.py

zip を展開して uv sync し、各スクリプトが起動できるかを見る。
Ollama には接続させないので、確認できるのは「接続の手前まで」。モデルを使う確認は verify_session<回>.py で行う。
main に push すると GitHub Actions が実行し、失敗すると zip は差し替えられない。
"""
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from make_zip import PUBLIC, ROOT, TOP, build, files

ZIP_PATH = ROOT / "dist" / "llm-agent-mcp-handson.zip"
TOP_FILES = ["README.md", "pyproject.toml", "uv.lock"]
EXPECTED_MESSAGES = ["Ollama に接続できません", "使い方:"]  # 正常に起動できたときに出る案内
ENV = {
    **{k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"},  # 展開先の環境を使わせる
    "OLLAMA_HOST": "127.0.0.1:1",  # 手元で Ollama が動いていても接続させない
    "PYTHONUTF8": "1",  # Windows のランナーで日本語の表示に失敗する誤検知を防ぐ
}


def check_contents(names: set[str]) -> list[str]:
    """入っていないものと、入ってはいけないものを探す。"""
    sessions = [p.name for p in ROOT.glob("session*") if p.is_dir()]
    expected = {f"{TOP}/{f.relative_to(ROOT).as_posix()}" for f in files(TOP_FILES + sessions)}
    errors = [f"zip に入っていない: {name}" for name in sorted(expected - names)]
    errors += [f"zip に入ってはいけない: {n}" for n in sorted(names) if n.startswith(f"{TOP}/internal/")]
    return errors


def check_script(project: Path, script: Path) -> list[str]:
    """スクリプトを起動して、エラーで落ちず案内が出るかを見る。"""
    name = script.relative_to(project).as_posix()
    print(f"実行: {name}")
    result = subprocess.run(
        ["uv", "run", "--locked", name],
        cwd=project, env=ENV, capture_output=True, timeout=300,
    )
    output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
    if "Traceback" in output or not any(m in output for m in EXPECTED_MESSAGES):
        return [f"{name} の起動に失敗:\n{output}"]
    return []


def main() -> None:
    ZIP_PATH.parent.mkdir(exist_ok=True)
    build(ZIP_PATH, PUBLIC)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp, zipfile.ZipFile(ZIP_PATH) as z:
        errors = check_contents(set(z.namelist()))
        z.extractall(tmp)
        project = Path(tmp) / TOP

        sync = subprocess.run(["uv", "sync", "--locked"], cwd=project, env=ENV, capture_output=True, timeout=600)
        if sync.returncode != 0:
            errors.append(f"uv sync に失敗:\n{sync.stderr.decode('utf-8', errors='replace')}")
        else:
            scripts = sorted(project.glob("session*/[0-9]*.py"))
            if not scripts:
                errors.append("zip にスクリプトが見つからない")
            for script in scripts:
                errors += check_script(project, script)

    if errors:
        sys.exit("\n".join(["── 確認に失敗 ───", *errors]))
    print("── 確認に成功 ───")


if __name__ == "__main__":
    main()
