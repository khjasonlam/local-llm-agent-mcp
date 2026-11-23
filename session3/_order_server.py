"""第3回で Agent につなぐ「外部のツール」：架空の本の発注サーバー（MCP サーバー）。

他の会社（本の取次サービス）が提供している MCP サーバー、という想定で作った架空のものです。
実際にはどこにも通信せず、どこにも発注しません。データはこのファイルの中のダミーだけです。

このファイルは Agent とは別のプログラムとして起動され、MCP の決まりで「何ができますか？」「これを実行して」に答えます。
MCP の決まりどおりに受け答えする部分は、公式のライブラリ（mcp）に任せています。
ここに書いてあるのは、ツールの中身（ふつうの Python の関数）と、その説明だけです。

自分で直接実行するものではありません（3.1・4.1・4.2 のスクリプトが起動します）。
"""
import json
import sys
from datetime import date, timedelta
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from pydantic import Field

server = MCPServer("本の発注サーバー")

# ── 取次サービスが取り扱っている本（架空） ──────────────────────────
CATALOG = [
    {"id": "C101", "title": "Linuxコマンド入門", "price": 3520, "stock": 0, "days": 14},
    {"id": "C102", "title": "はじめてのRust", "price": 2860, "stock": 12, "days": 3},
    {"id": "C103", "title": "はじめてのGo", "price": 2640, "stock": 5, "days": 3},
    {"id": "C104", "title": "TypeScript入門", "price": 2970, "stock": 8, "days": 3},
    {"id": "C105", "title": "データベース設計のきほん", "price": 3080, "stock": 3, "days": 5},
    {"id": "C106", "title": "図解 ネットワークのしくみ", "price": 2420, "stock": 0, "days": 21},
]

orders: list[dict] = []   # 受け付けた発注（プログラムを動かしている間だけ覚えている）


def call_api(request: str) -> None:
    """取次サービスの API を呼び出したことにして、画面に1行出す（実際には通信しない）。

    本物の MCP サーバーなら、ここで取次サービスの API を呼び出す。MCP は API の代わりではなく、
    API を AI が使いやすい形に包んだもの、ということを見せるための表示。
    標準出力は MCP のやりとりに使っているので、標準エラー出力に出す。
    """
    print(f"    （サーバーの中：取次サービスの API を呼び出し　{request}）", file=sys.stderr, flush=True)


def text(result: dict) -> str:
    return json.dumps(result, ensure_ascii=False)


def find_item(item_id: str):
    return next((b for b in CATALOG if b["id"] == str(item_id).strip().upper()), None)


# ── ツール（関数の上の @server.tool(...) で、MCP のツールとして登録される） ─────────
# 関数の説明（""" """ の中）と引数の説明が、そのまま「何ができますか？」の返事になる。
@server.tool(structured_output=False)
def search_catalog(
    keyword: Annotated[str, Field(description="探したい言葉（例：Rust）")],
) -> str:
    """取次サービスで取り扱っている本を、書名のキーワードで探す。商品番号と価格がわかる"""
    call_api(f"GET /catalog?q={keyword}")
    words = [w.lower() for w in str(keyword).replace("の本", " ").split() if w != "本"]
    hits = [b for b in CATALOG if words and all(w in b["title"].lower() for w in words)]
    if not hits:
        return text({"結果": f"「{keyword}」を含む本は取り扱っていません"})
    return text({"見つかった本": [{"商品番号": b["id"], "書名": b["title"], "価格": b["price"]} for b in hits]})


@server.tool(structured_output=False)
def check_stock(
    item_id: Annotated[str, Field(description="商品番号（例：C101）")],
) -> str:
    """商品番号を指定して、その本の在庫があるかと、発注してから届くまでの日数を調べる"""
    call_api(f"GET /stock/{item_id}")
    item = find_item(item_id)
    if item is None:
        return text({"エラー": f"商品番号 {item_id} の本はありません。商品番号は C101 のような形です"})
    state = "在庫あり" if item["stock"] > 0 else "在庫なし（取り寄せ）"
    return text({"商品番号": item["id"], "書名": item["title"], "在庫": state, "届くまで": f"{item['days']}日"})


@server.tool(structured_output=False)
def place_order(
    item_id: Annotated[str, Field(description="商品番号（例：C101）")],
) -> str:
    """商品番号を指定して、その本を1冊発注する"""
    call_api(f"POST /orders　{{\"item\": \"{item_id}\"}}")
    item = find_item(item_id)
    if item is None:
        return text({"エラー": f"商品番号 {item_id} の本はありません。商品番号は C101 のような形です"})
    order = {"発注番号": f"PO-{len(orders) + 1:04d}", "書名": item["title"],
             "届く予定日": (date.today() + timedelta(days=item["days"])).isoformat()}
    orders.append(order)
    return text({"結果": f"「{item['title']}」を発注しました", **order})


if __name__ == "__main__":
    server.run()   # 標準入出力で、クライアント（3.1 のスクリプトや Agent）からのメッセージを待つ
