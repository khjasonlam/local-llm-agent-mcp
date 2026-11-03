"""運営用：配布用の zip を作る。

教材フォルダ（pyproject.toml がある場所）で実行する:
    uv run internal/tools/make_zip.py

dist/ に次の2つができる。
- local-llm-handson.zip        … 参加者に配るもの（GitHub のリリースに添付する）
- local-llm-handson-check.zip  … 上の中身＋検証スクリプト（運営の動作確認用。配らない）
"""
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOP = "local-llm-handson"  # 展開したときのフォルダ名
PUBLIC = ["README.md", "pyproject.toml", "uv.lock", "session1"]
CHECK_EXTRA = ["internal/tools/verify.py"]
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
    build(dist / "local-llm-handson.zip", PUBLIC)
    build(dist / "local-llm-handson-check.zip", PUBLIC + CHECK_EXTRA)
