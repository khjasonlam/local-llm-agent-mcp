# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright"]
# ///
"""運営用：当日資料・事前準備ページ（Artifact）の HTML から、PDF の控えを作る。

Artifact が開けないときのための控え（internal/backup/）。折りたたみはすべて開き、
事前準備ページは Windows / Mac、メモリ 16GB / 8GB の両方を並べて載せる。

playwright は受講者に入れたくないので、プロジェクトの依存関係には入れていない。
先頭の「script」の欄に書いてあるので、uv run で実行すると uv が自動で用意する。

使い方（ページの HTML を保存してから）:
    uv run internal/tools/make_backup_pdf.py s1.html internal/backup/第1回_当日資料.pdf s1
    uv run internal/tools/make_backup_pdf.py prep.html internal/backup/事前準備.pdf prep
初めて使うときは、先に Chromium を入れる:
    uv run --with playwright playwright install chromium
日付（DATE）はバックアップの時点に合わせて書き換える。
"""
import sys
from pathlib import Path

# playwright はプロジェクトの .venv に入れていないので、エディタの「見つからない」警告だけ止める
from playwright.sync_api import sync_playwright  # pyright: ignore[reportMissingImports]

DATE = "2026-11-09"

COMMON_CSS = """
@page { size: A4; margin: 14mm 12mm; }
html, body { background: #fff !important; }
body::before { display: none !important; }
.index, .status, .chooser, .copy, .check { display: none !important; }
details > summary::after { display: none !important; }
.term, .predict, .observe, .vs figure, .table-wrap, .qset, .note, .learn, .faq details, ul.sum,
.where figure, .roles div, .task h4 { break-inside: avoid; }
h2, h3, h4, .head { break-after: avoid; }
.backup-note { margin-top: 16px; padding: 10px 14px; border: 1px solid var(--line); border-radius: 8px;
  font-size: 12.5px; color: var(--muted); }
.faq-band { break-before: page; }
.os-chip { display: inline-block; font-size: 10.5px; font-weight: 600; line-height: 1.3; padding: 0 5px;
  border: 1px solid var(--muted); border-radius: 4px; margin-right: 6px; vertical-align: 1px; white-space: nowrap; }
.os-head { font-size: 12.5px; font-weight: 700; color: var(--muted); margin: 2px 0 -6px; }
.cmt { color: var(--term-dim); }
/* 印刷では grid をやめる（grid の中で改ページを避けると、Chromium で文字が重なるため） */
.content, details.more > div, details.explain > div, .task, .observe, .faq details > div, .qset { display: block !important; }
.content > * + *, details.more > div > * + *, details.explain > div > * + *, .task > * + *, .observe > * + *,
.faq details > div > * + *, .qset > * + * { margin-top: 12px; }
.faq-band { padding-block: 8px 12px !important; }
.faq summary { padding: 8px 40px 8px 14px !important; }
.faq details > div { padding: 8px 14px 10px !important; }
.faq details > div > * + * { margin-top: 6px; }
.step { display: block !important; position: relative; padding-left: 54px; }
.rail { position: absolute; left: 0; top: 0; bottom: 0; }
"""

S1_CSS = """
#s5 { break-before: page; }
/* 困ったときは項目が多く1ページに収まらないので、まとめの続きから始める */
.faq-band { break-before: auto; margin-top: 24px; }
"""

PREP_CSS = """
.step, #after { break-inside: avoid; }
#finish { break-inside: avoid; }
"""

# 事前準備ページ: Windows / Mac、メモリ 16GB / 8GB の両方を並べて見せる
PREP_JS = r"""
() => {
  const root = document.documentElement;
  delete root.dataset.os; delete root.dataset.mem;
  const LABEL = {win: 'Windows', mac: 'Mac', m16: 'メモリ16GB以上', m8: 'メモリ8GB'};
  const kind = el => ['win', 'mac', 'm16', 'm8'].find(k => el.classList.contains(k));
  const chip = k => { const s = document.createElement('span'); s.className = 'os-chip'; s.textContent = LABEL[k]; return s; };

  // コマンド: 1行ずつに分け、どの PC 向けかをコメントで添える
  document.querySelectorAll('.term pre').forEach(pre => {
    const inOut = pre.closest('.out');
    pre.querySelectorAll('span.in, span.hl').forEach(s => {
      const k = kind(s);
      if (!k) return;
      if (inOut && k === 'm8') { s.remove(); return; }   // 出力例は 16GB の方だけ
      if (inOut) return;
      const c = document.createElement('span'); c.className = 'cmt'; c.textContent = '   # ' + LABEL[k];
      s.appendChild(c);
      const next = s.nextSibling;
      if (next && next.nodeType === 1 && next.classList.contains('in')) s.after(document.createTextNode('\n'));
    });
  });

  // ターミナルの見出し: 「PowerShell／ターミナル」
  document.querySelectorAll('.term-bar span.win').forEach(w => {
    const m = w.nextElementSibling;
    if (m && m.classList.contains('mac')) w.after(document.createTextNode('／'));
  });

  // 文中の Windows / Mac の言い分け
  document.querySelectorAll('main span.win, main span.mac, .faq span.win, .faq span.mac').forEach(s => {
    if (s.closest('.term-bar') || s.closest('pre')) return;
    const k = kind(s);
    const short = s.textContent.length <= 12;
    if (short) {
      if (k === 'win') { const m = s.nextElementSibling; if (m && m.classList.contains('mac')) s.after(document.createTextNode('／')); }
      return;
    }
    s.prepend(chip(k));
    if (k === 'win') { const m = s.nextElementSibling; if (m && m.classList.contains('mac')) s.after(document.createTextNode(' ／ ')); }
  });

  // 文中のコマンドでメモリ別に言い分けているもの: 「A（メモリ16GB以上）／B（メモリ8GB）」に並べる
  document.querySelectorAll('main code').forEach(c => {
    const a = c.querySelector(':scope > span.m16'), b = c.querySelector(':scope > span.m8');
    if (!a || !b) return;
    const c2 = c.cloneNode(false); c2.append(b);
    c.after(document.createTextNode('（メモリ16GB以上）／'), c2, document.createTextNode('（メモリ8GB）'));
  });

  // 手順の箇条書き（Windows / Mac で別の ol）に見出しを付ける
  document.querySelectorAll('main ol.win, main ol.mac').forEach(ol => {
    const h = document.createElement('p'); h.className = 'os-head';
    h.textContent = (ol.classList.contains('win') ? 'Windows' : 'Mac') + ' の場合';
    ol.before(h);
  });
  // 1項目だけの言い分け（li / p）にはラベルを付ける
  document.querySelectorAll('main li.win, main li.mac, main p.win, main p.mac, .faq p.win, .faq p.mac').forEach(el => {
    el.prepend(chip(kind(el)));
  });

  // 「あなたのPCは青い線の行です」は、PDF では強調しないので外す
  document.querySelectorAll('#step2 .content > p').forEach(p => { p.textContent = p.textContent.replace('あなたのPCは青い線の行です。', ''); });
  // 表の「あなたのPC」の強調は外す
  document.querySelectorAll('tr.is-you').forEach(tr => tr.classList.remove('is-you'));

  // 完了欄: チェックの状態によらない文にする
  const ft = document.getElementById('finish-title');
  if (ft) ft.textContent = '準備が終わったら';
  const fin = document.getElementById('finish'); if (fin) fin.classList.remove('is-complete');
  const fx = document.getElementById('finish-text');
  if (fx) fx.textContent = '第1回の前日までに準備を終えて、アップデート担当へ「準備完了」と連絡してください。うまくいかないときも、どの手順で止まったかと、表示された画面のスクリーンショットを添えて連絡してください。';

  // フッターのチェック保存の説明は PDF では不要
  const foot = document.querySelector('footer p');
  if (foot) foot.firstChild.textContent = foot.firstChild.textContent.replace('チェックの状態はこのブラウザにだけ保存されます。', '');

  return 'Webページのバックアップ（DATE時点）。Windows と Mac、メモリ16GB以上と8GBで違うところは、両方を並べて載せています。';
}
"""

S1_JS = r"""
() => 'Webページのバックアップ（DATE時点）。折りたたみ部分（実行結果の例・解説・もっと試す・困ったとき）は、すべて開いて載せています。'
"""


def main():
    src, out, kind = sys.argv[1], sys.argv[2], sys.argv[3]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 820, "height": 1200}, color_scheme="light")
        page.goto(Path(src).resolve().as_uri(), wait_until="load")
        page.add_style_tag(content=COMMON_CSS + (S1_CSS if kind == "s1" else PREP_CSS))
        note = page.evaluate((PREP_JS if kind == "prep" else S1_JS).replace("DATE", DATE))
        page.evaluate("""(note) => {
          document.querySelectorAll('details').forEach(d => d.open = true);
          const p = document.createElement('p'); p.className = 'backup-note'; p.textContent = note;
          const facts = document.querySelector('header.top dl.facts');
          (facts || document.querySelector('header.top .wrap')).after(p);
        }""", note)
        page.pdf(path=out, format="A4", print_background=True, scale=0.9 if kind == "prep" else 0.95,
                 margin={"top": "14mm", "bottom": "14mm", "left": "12mm", "right": "12mm"})
        browser.close()
    print("作成:", out)


if __name__ == "__main__":
    main()
