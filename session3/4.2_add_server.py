"""4.2 外部のサーバーをもう1つつなぐ

4.1 に、チャット通知サーバー（架空）を足します。
Agent の本体（_agent.py）は 4.1 と同じものです。ちがうのは、下の SERVERS に1行足したことだけです。
発注（place_order）とチャットの送信（send_message）の前に、y/n で確認を求めます。
どちらのサーバーも架空なので、y と答えても実際には発注も送信もされません。

質問は差し替えられます。

実行:
    uv run session3/4.2_add_server.py
"""
import sys

from _agent import run_agent
from _common import run

# つなぐ MCP サーバー（ファイル名と、画面に出す名前）
SERVERS = [
    ("_order_server.py", "発注サーバー"),
    ("_chat_server.py", "チャット通知"),   # ← 4.1 から足したのは、この1行だけ
]


def main():
    question = (sys.argv[1] if len(sys.argv) > 1
                else "「はじめてのRust」を発注してください。発注できたら、図書館の担当者にチャットで知らせてください")
    run_agent(question, SERVERS)


if __name__ == "__main__":
    run(main)
