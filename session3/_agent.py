"""第3回の Agent の本体：第2回 3.2 の「往復のくり返し」に、MCP サーバーの道具を足したもの。

4.1 と 4.2 は、どちらもこのファイルの run_agent() を呼び出します。ちがうのは「つなぐサーバーの一覧」だけです。

第2回との大きなちがいは2つです。
  ・始める前に、外部のサーバーに「何ができますか？」と聞いて、ツールの説明を受け取る
  ・LLM が使いたいと書いてきたツールが、内蔵なら自分で実行し、外部ならサーバーに頼む
このほか、取り消しにくい操作（発注・送信）の前に人の確認を挟み、「いいえ」ならそこで終わります。
LLM に渡すツールの説明は、内蔵と外部を区別せずに1つの一覧にまとめます。
"""
import json
import sys

import ollama

from _common import Server, big_model, heading, pad
from _library import FUNCTIONS, TOOLS, call_tool

MAX_STEPS = 8    # 往復の上限。LLM が同じツールを使い続けても、ここで止める
WHO_WIDTH = 24   # 行の先頭の「誰と誰のやりとりか」の幅

# LLM のくじ引きの度合い（第1回 3.2 の --temperature と同じ設定）。
# 0 にすると、いちばん確率の高い候補だけを選ぶので、同じ質問なら毎回ほぼ同じ流れになる。
# 第3回は Agent とサーバーのやりとりを見たいので、くじ引きを止めている
TEMPERATURE = 0

# 実行する前に人の確認が要るツール（取り消しにくい操作）。
# 1つ目は確認のときに出す説明、2つ目は「いいえ」のときに画面に出す言葉
NEED_CONFIRM = {
    "place_order": ("外部のサービスに発注します", "発注を取りやめました"),
    "send_message": ("外部のチャットに送ります", "メッセージの送信を取りやめました"),
}


def run_agent(question: str, server_list: list[tuple[str, str]]) -> None:
    """question に答える。server_list は、つなぐ MCP サーバーの（ファイル名, 画面に出す名前）の一覧。"""
    model = big_model()
    print(f"モデル: {model}")
    print(f"質問: {question}\n")

    servers: list[Server] = []
    try:
        # ── 準備：外部のサーバーにつないで、ツールの説明を受け取る ──
        print(heading("準備：外部のサーバーにつなぐ"))
        tools = list(TOOLS)               # LLM に渡すツールの説明（まず内蔵の図書館の3つ）
        owner: dict[str, Server] = {}     # 外部のツールの名前 → 持っているサーバー
        for script, label in server_list:
            server = Server(script, label)
            servers.append(server)
            say(f"Agent → {label}", "はじめまして（initialize）")
            server.hello()
            say(f"Agent ← {label}", f"{server.name}です")
            say(f"Agent → {label}", "何ができますか？（tools/list）")
            for i, tool in enumerate(server.list_tools()):
                say(f"Agent ← {label}" if i == 0 else "", f"{tool['name']}：{tool.get('description', '')}")
                tools.append(to_ollama(tool))
                owner[tool["name"]] = server
        print(f"使える道具：内蔵 {len(TOOLS)}つ（図書館）＋ 外部 {len(owner)}つ（サーバー{len(servers)}つ）\n")

        # ── ここからは第2回 3.2 と同じ、往復のくり返し ──
        messages: list = [{"role": "user", "content": question}]
        llm_count = 0
        for step in range(1, MAX_STEPS + 1):
            print(heading(f"{step}回目の往復"))
            if step == 1:
                say("Agent → LLM", f"質問 ＋ ツールの説明{len(tools)}つ（内蔵と外部を区別せずに）")
            else:
                say("Agent → LLM", f"ここまでの履歴をまるごと（{len(messages)}件）")
            res = ollama.chat(model=model, messages=messages, tools=tools, think=False,
                              options={"num_predict": 1024, "temperature": TEMPERATURE})
            llm_count += 1
            messages.append(res.message)

            # ツールを使いたいと書いてこなければ、それが最終的な答え
            if not res.message.tool_calls:
                say("Agent ← LLM", "（ツールを使わずに、答えを書いた）")
                print()
                print(heading("答え"))
                print((res.message.content or "").strip())
                print()
                summary(llm_count, servers)
                return

            for call in res.message.tool_calls:
                name, args = call.function.name, dict(call.function.arguments or {})
                say("Agent ← LLM", f"{name} を {json.dumps(args, ensure_ascii=False)} で使いたい")
                result = use_tool(name, args, owner)
                if result is None:   # 確認で「いいえ」。LLM には戻さず、Agent がここで終える
                    print()
                    summary(llm_count, servers)
                    return
                messages.append({"role": "tool", "tool_name": name, "content": result})
            print()

        print(f"{MAX_STEPS}回往復しても答えが出なかったので、止めました。\n")
        summary(llm_count, servers)
    finally:
        for server in servers:
            server.close()


def use_tool(name: str, args: dict, owner: dict[str, Server]) -> str | None:
    """ツールを1つ使って、結果を文字で返す。内蔵なら自分で実行し、外部ならサーバーに頼む。

    確認で「いいえ」と答えたときは、実行せずに None を返す（呼び出した側は、そこで Agent を終える）。
    取りやめたことを LLM に説明させると、発注していないのに「発注しました」と答えることがあったので、
    人が止めたときは LLM に戻さず、Agent が自分で伝えて終わる形にしている。
    """
    if name in NEED_CONFIRM and not confirm(f"確認：{NEED_CONFIRM[name][0]}。実行してよいですか？ [y/n] "):
        say("Agent", f"{NEED_CONFIRM[name][1]}（{name} は実行していません）。LLM には戻さず、ここで終わります")
        return None

    server = owner.get(name)
    if server is not None:
        # 外部のツール：MCP でサーバーに頼む
        say(f"Agent → {server.label}", f"外部なので頼む：{name}（tools/call）")
        result = server.call_tool(name, args)
        say(f"Agent ← {server.label}", result)
    elif name in FUNCTIONS:
        # 内蔵のツール：第2回と同じように、自分で関数を実行する
        result = call_tool(name, args)
        say("Agent", f"内蔵なので自分で実行 → {result}")
    else:
        names = ", ".join([*FUNCTIONS, *owner])
        result = json.dumps({"エラー": f"{name} というツールはありません。使えるのは {names} です"}, ensure_ascii=False)
        say("Agent", f"そのツールはないと LLM に伝える → {result}")
    return result


def to_ollama(tool: dict) -> dict:
    """MCP のツールの説明を、第2回の TOOLS と同じ形に入れ替える（中身は同じで、入れ物の名前がちがうだけ）。"""
    return {"type": "function",
            "function": {"name": tool["name"], "description": tool.get("description", ""),
                         "parameters": tool.get("inputSchema", {"type": "object", "properties": {}})}}


def say(who: str, text: str) -> None:
    """「誰と誰のやりとりか」を行の先頭にそろえて表示する。"""
    print(pad(who, WHO_WIDTH) + text)


def confirm(prompt: str) -> bool:
    """人に y/n で確かめる。y 以外（何も入力できないときも含む）は「いいえ」とみなす。"""
    try:
        answer = input(prompt)
    except EOFError:   # 入力を受け付けられない実行のしかたのとき
        print("（入力がないので、いいえ とみなします）")
        return False
    if not sys.stdin.isatty():   # 入力をキーボード以外から受け取ったときは、画面に出ないので書き足す
        print(answer)
    return answer.strip().lower() in ("y", "yes", "ｙ")


def summary(llm_count: int, servers: list[Server]) -> None:
    print(heading("まとめ"))
    print(f"LLM に送った回数：{llm_count}回　　サーバーに送った回数：{sum(s.sent for s in servers)}回")
    print("LLM に渡したツールの説明は、内蔵と外部を区別していません")
    print("MCP が使われたのは、Agent とサーバーの間（準備と、外部の道具を使うとき）だけです")
