"""第3回のスクリプトで共通に使う、ちょっとした関数（読み飛ばして大丈夫です）。

前半は第2回の _common.py と同じです。後半の Server が、MCP サーバーとのやりとりを受け持ちます。
"""
import json
import os
import subprocess
import sys
import unicodedata
from pathlib import Path

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
    except ServerError as e:
        sys.exit(str(e))
    except KeyboardInterrupt:
        print("\n中断しました。")


# ── ここから第3回で足したもの：MCP サーバーとのやりとり ─────────────────
HERE = Path(__file__).resolve().parent
PROTOCOL_VERSION = "2025-06-18"   # MCP の決まりの版（日付で表す）


class ServerError(Exception):
    """サーバーを起動できない、返事が来ない、などのとき。"""


class Server:
    """MCP サーバーを起動して、JSON を1行ずつやりとりする（3.1 で画面に出るやりとりと同じもの）。

    サーバーは別のプログラムとして同じ PC の中で動く。こちらが1行書くと、サーバーが1行返す。
    MCP の決まりは「その1行に何を書くか」で、ネットワークは使っていない（標準入出力というつなぎ方）。
    """

    def __init__(self, script: str, label: str):
        self.label = label          # 画面に出す名前（例：発注サーバー）
        self.name = ""              # サーバーが名乗った名前（initialize の返事に入っている）
        self.sent = 0               # サーバーに送った回数（返事が要るものだけ数える）
        self._next_id = 1
        path = HERE / script
        if not path.exists():
            raise ServerError(f"サーバーを起動できません。{script} が見つかりません。教材のフォルダで実行しているか確認してください。")
        sys.stdout.flush()
        self._proc = subprocess.Popen(
            [sys.executable, str(path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"})   # Windows でも日本語が崩れないようにする

    # ── 1行送って、1行受け取る ──
    def message(self, method: str, params: dict | None = None) -> dict:
        """送るメッセージ（返事が要るもの）を作る。id は返事と組み合わせるための番号。"""
        msg: dict = {"jsonrpc": "2.0", "id": self._next_id, "method": method}
        if params is not None:
            msg["params"] = params
        self._next_id += 1
        return msg

    def send(self, msg: dict) -> str:
        """メッセージを1行で送り、同じ id の返事を1行のまま返す。"""
        self._write(msg)
        self.sent += 1
        assert self._proc.stdout
        while True:
            line = self._proc.stdout.readline()
            if not line:
                raise ServerError(f"サーバーを起動できません（{self.label} から返事がありません）。"
                                  "uv sync を実行したか確認してください。")
            line = line.strip()
            try:
                if json.loads(line).get("id") == msg["id"]:
                    return line
            except ValueError:
                continue   # JSON でない行や、こちらの質問への返事でない行は読み飛ばす

    def notify(self, method: str) -> None:
        """返事が要らない合図を送る。"""
        self._write({"jsonrpc": "2.0", "method": method})

    def _write(self, msg: dict) -> None:
        sys.stdout.flush()   # 画面の表示の順番が、やりとりの順番とそろうようにする
        assert self._proc.stdin
        try:
            self._proc.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
            self._proc.stdin.flush()
        except OSError:
            raise ServerError(f"サーバーを起動できません（{self.label} が止まっています）。"
                              "uv sync を実行したか確認してください。") from None

    # ── よく使うやりとり ──
    def request(self, method: str, params: dict | None = None) -> dict:
        """送って、返事の中身（result）だけを取り出す。"""
        reply = json.loads(self.send(self.message(method, params)))
        if "error" in reply:
            raise ServerError(f"{self.label} からエラーが返りました：{reply['error'].get('message')}")
        return reply["result"]

    def hello(self) -> None:
        """はじめまして（initialize）と、準備できましたの合図。"""
        result = self.request("initialize", initialize_params())
        self.name = result.get("serverInfo", {}).get("name", "")
        self.notify("notifications/initialized")

    def list_tools(self) -> list[dict]:
        """何ができますか？（tools/list）。ツールの名前・説明・引数の形の一覧が返る。"""
        return self.request("tools/list")["tools"]

    def call_tool(self, name: str, arguments: dict) -> str:
        """これを実行して（tools/call）。結果を文字にして返す。"""
        reply = json.loads(self.send(self.message("tools/call", {"name": name, "arguments": arguments})))
        if "error" in reply:   # ツールの名前がまちがっているときなど。止まらずに、エラーの内容を文字で返す
            return json.dumps({"エラー": reply["error"].get("message", "実行できませんでした")}, ensure_ascii=False)
        content = reply["result"].get("content", [])
        return "".join(c.get("text", "") for c in content if c.get("type") == "text")

    def close(self) -> None:
        """サーバーを終わらせる（入力を閉じると、サーバーは自分で終了する）。"""
        try:
            if self._proc.stdin:
                self._proc.stdin.close()
            self._proc.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            self._proc.kill()


def initialize_params() -> dict:
    return {"protocolVersion": PROTOCOL_VERSION, "capabilities": {},
            "clientInfo": {"name": "handson", "version": "1.0"}}
