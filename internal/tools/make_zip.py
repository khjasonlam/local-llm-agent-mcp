"""運営用：配布用の zip を作る。

教材フォルダ（pyproject.toml がある場所）で実行する:
    uv run internal/tools/make_zip.py

dist/llm-agent-mcp-handson.zip ができる（参加者に配るもの）。
main に push すると GitHub Actions がこのスクリプトで zip を作り、リリースに添付し直すので、
手元で実行するのは中身を確かめたいときだけでよい。
運営の動作確認は、リポジトリを git clone して internal/tools/verify.py を実行する（internal/windows_check.md）。
"""
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOP = "llm-agent-mcp-handson"  # 展開したときのフォルダ名
PUBLIC = ["README.md", "pyproject.toml", "uv.lock", "session1"]
SKIP = {"__pycache__", ".DS_Store"}


def files(names: list[str]) -> list[Path]:
    out = []
    for name in names:
        p = ROOT / name
        if p.is_dir():
            out += sorted(f for f in p.rglob("*") if f.is_file() and not SKIP & set(f.parts))
        else:
            out.append(p)
    return out


def build(path: Path, names: list[str]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files(names):
            z.write(f, f"{TOP}/{f.relative_to(ROOT).as_posix()}")
    print(f"作成: {path.relative_to(ROOT)}（{path.stat().st_size // 1024} KB）")


if __name__ == "__main__":
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    build(dist / "llm-agent-mcp-handson.zip", PUBLIC)
