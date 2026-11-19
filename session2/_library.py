"""第2回で LLM に使わせる「ツール」：架空の社内図書館（ダミーのデータだけを使う）。

このファイルは読んでみてください。ツールの正体は、ふつうの Python の関数です。
LLM にはこの関数そのものではなく、TOOLS に書いた「ツールの説明」（名前・何をするか・引数）だけを渡します。
LLM が「このツールを、この引数で使いたい」と書いてきたら、call_tool() で実際に関数を実行します。

本のデータは架空のもので、プログラムを動かしている間だけメモリ上にあります（実行し直すと元に戻ります）。
"""
import inspect
import json
from datetime import date, timedelta

# ── 本の一覧（架空） ─────────────────────────────────────
BOOKS = [
    {"id": "B001", "title": "はじめてのPython", "author": "青山 一郎", "genre": "プログラミング"},
    {"id": "B002", "title": "Pythonでつくる業務自動化", "author": "川口 さくら", "genre": "プログラミング"},
    {"id": "B003", "title": "やさしい機械学習", "author": "森田 健", "genre": "AI"},
    {"id": "B004", "title": "生成AIのしくみ", "author": "星野 葵", "genre": "AI"},
    {"id": "B005", "title": "AIエージェント入門", "author": "星野 葵", "genre": "AI"},
    {"id": "B006", "title": "伝わる文章の書き方", "author": "高木 みどり", "genre": "ビジネス"},
    {"id": "B007", "title": "会議がうまくいく段取り", "author": "西村 拓也", "genre": "ビジネス"},
    {"id": "B008", "title": "はじめての統計", "author": "森田 健", "genre": "数学"},
    {"id": "B009", "title": "おいしいお茶の入れ方", "author": "竹内 ゆり", "genre": "くらし"},
    {"id": "B010", "title": "週末キャンプの本", "author": "大野 隼人", "genre": "くらし"},
]

# 最初から貸出中にしておく本と、返却予定日が今日から何日後か
FIRST_LOANS = {"B002": 10, "B004": 17, "B010": 24}

LOAN_DAYS = 14  # 貸出期間は2週間（第1回の sample.pdf の利用案内と同じ）


def first_loans() -> dict:
    """最初の貸出の記録（本の番号 → 返却予定日）を、今日の日付から作る。"""
    return {book_id: (date.today() + timedelta(days=days)).isoformat()
            for book_id, days in FIRST_LOANS.items()}


loans = first_loans()   # 貸出中の本と返却予定日（借りると増える）


def reset() -> None:
    """貸出の状態を最初に戻す（同じ課題を別のモデルでもう一度試すときに使う）。"""
    loans.clear()
    loans.update(first_loans())


# ── ツールの中身（ふつうの Python の関数） ─────────────────────────
def search_books(keyword: str) -> dict:
    """書名・著者名・分野に keyword を含む本を探す。

    LLM は「Pythonの本」「Python 本」のような言葉で探してくることがあるので、
    「の本」と「本」は除き、スペースで区切った言葉がすべて含まれる本を返す。
    """
    keyword = str(keyword).strip()
    words = [w.lower() for w in keyword.replace("の本", " ").split() if w != "本"]
    hits = [b for b in BOOKS
            if words and all(any(w in b[field].lower() for field in ("title", "author", "genre"))
                             for w in words)]
    if not hits:
        return {"結果": f"「{keyword}」を含む本は見つかりませんでした"}
    return {"見つかった本": [{"番号": b["id"], "書名": b["title"], "著者": b["author"]} for b in hits]}


def check_availability(book_id: str) -> dict:
    """本の番号から、いま借りられるかを調べる。"""
    book = find_book(book_id)
    if book is None:
        return {"エラー": f"番号 {book_id} の本はありません。番号は B001 のような形です"}
    if book["id"] in loans:
        return {"番号": book["id"], "書名": book["title"], "状態": f"貸出中（返却予定 {loans[book['id']]}）"}
    return {"番号": book["id"], "書名": book["title"], "状態": "借りられます"}


def borrow_book(book_id: str) -> dict:
    """本を借りる（貸出の記録を変える）。"""
    book = find_book(book_id)
    if book is None:
        return {"エラー": f"番号 {book_id} の本はありません。番号は B001 のような形です"}
    if book["id"] in loans:
        return {"エラー": f"「{book['title']}」は貸出中のため借りられません（返却予定 {loans[book['id']]}）"}
    due = (date.today() + timedelta(days=LOAN_DAYS)).isoformat()
    loans[book["id"]] = due
    return {"結果": f"「{book['title']}」を貸し出しました", "返却期限": due}


def find_book(book_id: str):
    return next((b for b in BOOKS if b["id"] == str(book_id).strip().upper()), None)


# ── LLM に渡す「ツールの説明」 ─────────────────────────────────
# LLM が見るのはここだけ。関数の中身は見えない。
# description（何をするか）の書き方しだいで、LLM がツールを選べるかどうかが変わる。
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_books",
            "description": "社内図書館の本を、書名・著者名・分野のキーワードで探す。本の番号がわかる",
            "parameters": {
                "type": "object",
                "properties": {"keyword": {"type": "string", "description": "探したい言葉（例：Python）"}},
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "本の番号を指定して、その本がいま借りられるか（貸出中か）を調べる",
            "parameters": {
                "type": "object",
                "properties": {"book_id": {"type": "string", "description": "本の番号（例：B001）"}},
                "required": ["book_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "borrow_book",
            "description": "本の番号を指定して、その本を借りる。貸出の記録が変わる",
            "parameters": {
                "type": "object",
                "properties": {"book_id": {"type": "string", "description": "本の番号（例：B001）"}},
                "required": ["book_id"],
            },
        },
    },
]

# ツールの名前 → 実際に実行する関数
FUNCTIONS = {
    "search_books": search_books,
    "check_availability": check_availability,
    "borrow_book": borrow_book,
}


def call_tool(name: str, arguments, functions: dict = FUNCTIONS) -> str:
    """LLM が使いたいと書いてきたツールを、プログラムが実際に実行し、結果を文字にして返す。

    LLM は存在しないツール名や、まちがった引数を書いてくることがある。
    そのときも止まらずに、エラーの内容を文字で返す（LLM はそれを読んで、やり直せることがある）。
    """
    func = functions.get(name)
    if func is None:
        result = {"エラー": f"{name} というツールはありません。使えるのは {', '.join(functions)} です"}
        return json.dumps(result, ensure_ascii=False)

    # 実行する前に、引数の名前と数が関数に合っているかを確かめる
    signature = inspect.signature(func)
    try:
        bound = signature.bind(**dict(arguments or {}))
    except TypeError:
        names = ", ".join(signature.parameters) or "なし"
        result = {"エラー": f"引数がまちがっています。{name} の引数は {names} です"}
        return json.dumps(result, ensure_ascii=False)

    result = func(*bound.args, **bound.kwargs)
    return json.dumps(result, ensure_ascii=False)
