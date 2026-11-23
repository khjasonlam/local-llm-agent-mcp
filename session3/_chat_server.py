"""4.2 で Agent にもう1つつなぐ「外部のツール」：架空の社内チャットの通知サーバー（MCP サーバー）。

社内チャットのサービスが提供している MCP サーバー、という想定で作った架空のものです。
実際にはどこにも通信せず、だれにもメッセージは届きません。

自分で直接実行するものではありません（4.2 のスクリプトが起動します）。
"""
import json
import sys
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from pydantic import Field

server = MCPServer("チャット通知サーバー")

sent: list[dict] = []   # 送ったことにしたメッセージ（プログラムを動かしている間だけ覚えている）


@server.tool(structured_output=False)
def send_message(
    to: Annotated[str, Field(description="送る相手（例：図書館の担当者）")],
    message: Annotated[str, Field(description="送る文章")],
) -> str:
    """社内チャットで、相手を指定してメッセージを送る"""
    # 本物の MCP サーバーなら、ここでチャットのサービスの API を呼び出す（実際には通信しない）
    print("    （サーバーの中：社内チャットの API を呼び出し　POST /messages）", file=sys.stderr, flush=True)
    sent.append({"to": to, "message": message})
    return json.dumps({"結果": f"{to} にメッセージを送りました", "送った文章": message}, ensure_ascii=False)


if __name__ == "__main__":
    server.run()   # 標準入出力で、クライアント（Agent）からのメッセージを待つ
