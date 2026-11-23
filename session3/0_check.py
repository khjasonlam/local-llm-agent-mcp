"""0 事前準備の確認：発注サーバーを起動して、ツールの一覧を聞く

第3回の教材が動く状態かを確かめます。LLM は使わないので、Ollama が起動していなくても動きます。
発注サーバー（架空）を起動し、「何ができますか？」と聞いて、ツールが3つ返ってくれば準備完了です。

実行:
    uv run session3/0_check.py
"""
from _common import Server, run

EXPECTED = 3   # 発注サーバーが持っているツールの数


def main():
    server = Server("_order_server.py", "発注サーバー")
    try:
        server.hello()
        tools = server.list_tools()
    finally:
        server.close()

    print(f"{server.name}から、ツールの一覧が返ってきました。")
    for tool in tools:
        print(f"  ・{tool['name']}：{tool.get('description', '')}")
    print()
    if len(tools) == EXPECTED:
        print(f"OK：ツールが{EXPECTED}つ返ってきました。第3回の準備は完了です。")
    else:
        print(f"ツールが{len(tools)}つしか返ってきませんでした。教材のフォルダを入れ直して、uv sync を実行してください。")


if __name__ == "__main__":
    run(main)
