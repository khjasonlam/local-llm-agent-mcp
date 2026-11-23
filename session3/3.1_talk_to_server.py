"""3.1 LLM なしで、サーバーに1つずつ話しかける

発注サーバー（架空）を起動し、用意したメッセージを Enter を押すたびに1つずつ送ります。
送るものも返ってくるものも、JSON（データを書く決まった形）の1行です。MCP は、この1行に何を書くかの決まりです。
LLM は使わないので、Ollama が起動していなくても動きます。

探す言葉は差し替えられます。

実行:
    uv run session3/3.1_talk_to_server.py
    uv run session3/3.1_talk_to_server.py "Go"
"""
import json
import sys

from _common import Server, heading, initialize_params, run


def main():
    keyword = sys.argv[1] if len(sys.argv) > 1 else "Rust"

    server = Server("_order_server.py", "発注サーバー")
    print("発注サーバーを起動しました。Enter を押すと、次のメッセージを送ります。\n")
    try:
        # ① はじめまして：おたがいの名前と、使える機能を伝え合う
        talk(server, "① はじめまして（initialize）", "initialize", initialize_params())
        server.notify("notifications/initialized")   # 「準備できました」の合図（返事は来ない）

        # ② 何ができますか？：ツールの名前・説明・引数の形の一覧が返ってくる
        talk(server, "② 何ができますか？（tools/list）", "tools/list")

        # ③ これを実行して：ツールの名前と引数を、決まった形で書いて頼む
        talk(server, "③ search_catalog を実行して（tools/call）", "tools/call",
             {"name": "search_catalog", "arguments": {"keyword": keyword}})
    finally:
        server.close()
    print("サーバーを終了しました。")


def talk(server: Server, title: str, method: str, params: dict | None = None) -> None:
    """メッセージを1つ見せて、Enter を待ってから送り、返ってきた1行をそのまま見せる。"""
    msg = server.message(method, params)
    print(heading(title))
    print("送る：")
    print(json.dumps(msg, ensure_ascii=False))
    wait_enter()
    reply = server.send(msg)
    print("返ってきた：")
    print(reply)
    print()


def wait_enter() -> None:
    try:
        input("[Enter で送る] ")
    except EOFError:   # 入力を受け付けられない実行のしかたのとき
        print()


if __name__ == "__main__":
    run(main)
