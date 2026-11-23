"""4.1 Agent に MCP サーバーをつなぐ（Agent・LLM・サーバーのやりとりを見る）

第2回 3.2 の Agent に、発注サーバー（架空）を MCP でつなぎます。
図書館の道具はこれまでどおり Agent の中にあり（内蔵）、発注の道具だけをサーバーから借ります（外部）。
行の先頭を見ると、Agent が LLM と話しているのか、サーバーと話しているのかがわかります。
発注（place_order）の前だけ、y/n で確認を求めます。n と答えると、発注せずにそこで終わります。
発注サーバーは架空なので、y と答えても実際には発注されません。

質問は差し替えられます。

実行:
    uv run session3/4.1_mcp_agent.py
    uv run session3/4.1_mcp_agent.py "「はじめてのGo」は発注したら何日で届きますか？"
"""
import sys

from _agent import run_agent
from _common import run

# つなぐ MCP サーバー（ファイル名と、画面に出す名前）
SERVERS = [
    ("_order_server.py", "発注サーバー"),
]


def main():
    question = sys.argv[1] if len(sys.argv) > 1 else "「はじめてのRust」を読みたいです。図書館になければ発注してください"
    run_agent(question, SERVERS)


if __name__ == "__main__":
    run(main)
