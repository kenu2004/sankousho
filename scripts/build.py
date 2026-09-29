"""config/*.yaml と data/books.json から、静的サイトを dist/ に書き出す。

  python scripts/build.py          # dist/ を作る
  python scripts/build.py --check  # 全回答パターンで各タイプに到達できるか確認するだけ
"""
from __future__ import annotations

import argparse
import itertools
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from urllib.parse import quote

import yaml

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
JST = timezone(timedelta(hours=9))


def load() -> tuple[dict, dict, dict, dict]:
    read = lambda name: yaml.safe_load((ROOT / "config" / name).read_text(encoding="utf-8"))
    site, quiz, books = read("site.yaml"), read("quiz.yaml"), read("books.yaml")
    data = json.loads((ROOT / "data" / "books.json").read_text(encoding="utf-8"))
    # YAML 1.1 では yes/no が True/False として読まれるので、キーを文字列に戻す
    for q in quiz["questions"]:
        q["yes"] = q.pop(True, None) or q.get("yes") or {}
        q["no"] = q.pop(False, None) or q.get("no") or {}
    return site, quiz, books, data


def validate(quiz: dict, books: dict, data: dict) -> list[str]:
    errors = []
    types = quiz["types"]
    for i, q in enumerate(quiz["questions"], 1):
        for side in ("yes", "no"):
            for t in (q.get(side) or {}):
                if t not in types:
                    errors.append(f"質問{i}の{side}に存在しないタイプ {t}")
    for tid, t in types.items():
        for key in ("main", "sub"):
            if t[key] not in books:
                errors.append(f"タイプ {tid} の {key} に存在しない本 {t[key]}")
            elif t[key] not in data:
                errors.append(f"タイプ {tid} の {key}（{t[key]}）の楽天データがない。fetch_books.py を実行してください")
    return errors


def diagnose(quiz: dict, answers: tuple[bool, ...]) -> str:
    """app.js の判定と同じ。同点なら types の並び順が先のほう。"""
    order = list(quiz["types"])
    score = Counter()
    for q, yes in zip(quiz["questions"], answers):
        score.update(q.get("yes" if yes else "no") or {})
    return max(order, key=lambda t: (score[t], -order.index(t)))


def check(quiz: dict) -> bool:
    n = len(quiz["questions"])
    dist = Counter(diagnose(quiz, a) for a in itertools.product([True, False], repeat=n))
    total = 2 ** n
    print(f"全 {total} 通りの回答で出る結果の割合:")
    for tid, t in quiz["types"].items():
        print(f"  {t['name']:<14} {dist[tid]:>5} 通り ({dist[tid] / total:5.1%})")
    unreachable = [t for t in quiz["types"] if dist[t] == 0]
    if unreachable:
        print(f"どの回答でも出ないタイプがあります: {unreachable}", file=sys.stderr)
    return not unreachable


# ---------- HTML ----------

def page(site: dict, *, title: str, description: str, path: str, body: str, depth: int,
         og_image: str = "", extra_head: str = "") -> str:
    root = "../" * depth
    url = site["base_url"] + path
    ga = ""
    if site.get("ga4_id"):
        gid = escape(site["ga4_id"])
        ga = (f'<script async src="https://www.googletagmanager.com/gtag/js?id={gid}"></script>'
              f"<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}"
              f"gtag('js',new Date());gtag('config','{gid}');</script>")
    og_img = f'<meta property="og:image" content="{escape(og_image)}">' if og_image else ""
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="{escape(description)}">
<link rel="canonical" href="{escape(url)}">
<meta property="og:type" content="website">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(description)}">
<meta property="og:url" content="{escape(url)}">
<meta property="og:site_name" content="{escape(site['title'])}">
{og_img}
<meta name="twitter:card" content="summary">
<link rel="icon" href="{FAVICON}">
<script>document.documentElement.classList.add("js")</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Shippori+Mincho:wght@400;500;700;800&family=Zen+Old+Mincho:wght@400&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{root}assets/style.css">
{extra_head}{ga}
</head>
<body>
<header>
  <div class="wrap header-inner">
    <a class="logo" href="{root}">参考書診断<span class="logo-sub">ITパスポート</span></a>
    <nav><a class="nav-link" href="{root}#types">タイプ一覧</a><a class="nav-cta" href="{root}">診断する</a></nav>
  </div>
  <div class="wrap"><div class="hikisen"></div><div class="hikisen"></div></div>
</header>
<main class="wrap">
{body}
</main>
<footer>
  <div class="wrap">
    <div class="hikisen thin"></div>
    <div class="footer-inner">
      <p>当サイトは楽天アフィリエイトを利用しています（PR）。リンク先で購入されると、運営者に紹介料が入ることがあります。</p>
      <p>参考書の紹介文は、出版社の商品説明をもとにまとめたものです。価格・在庫は{{updated}}時点の楽天ブックスの情報です。最新の価格はリンク先でご確認ください。</p>
      <p class="credit"><!-- Rakuten Web Service Center --><a href="https://developers.rakuten.com/" target="_blank" rel="noopener">Supported by Rakuten Developers</a></p>
    </div>
  </div>
</footer>
<script src="{root}assets/app.js" defer></script>
</body>
</html>
"""


KANJI = "一二三四五六七八九十"
FAVICON = "data:image/svg+xml," + quote(
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
    "<path d='M6,8 L94,5 L96,93 L8,96 Z' fill='#C73E3A'/>"
    "<text x='50' y='72' font-family='serif' font-size='62' font-weight='700' fill='#F5F1E8' text-anchor='middle'>診</text></svg>")

# 手で引いたような波線（見出しの下線）
WAVE = ('<svg viewBox="0 0 320 16" preserveAspectRatio="none" aria-hidden="true"><path d="M2,7 C 20,2 34,12 54,7 '
        'C 74,2 88,12 108,7 C 128,2 142,12 162,7 C 182,2 196,12 216,7 C 236,2 250,12 270,7 C 288,3 300,11 316,6"/></svg>')


def seal(chars: str) -> str:
    """朱肉で押したハンコ。2文字を縦に並べる。"""
    return f"""<svg class="seal" viewBox="0 0 120 120" aria-hidden="true">
  <path d="M9,11 L111,7 L115,111 L11,115 Z" fill="#C73E3A"/>
  <rect x="17" y="17" width="86" height="86" fill="none" stroke="#F5F1E8" stroke-width="2" opacity=".8"/>
  <text x="60" y="50" font-family="Shippori Mincho, serif" font-size="32" font-weight="700" fill="#F5F1E8" text-anchor="middle">{chars[0]}</text>
  <text x="60" y="90" font-family="Shippori Mincho, serif" font-size="32" font-weight="700" fill="#F5F1E8" text-anchor="middle">{chars[1]}</text>
</svg>"""


def book_card(book: dict, info: dict, *, role: str, type_id: str) -> str:
    points = "".join(f'<li><span class="kanji-num">{KANJI[i]}</span><p>{escape(p)}</p></li>'
                     for i, p in enumerate(book["points"]))
    review = ""
    if info.get("review_count"):
        review = (f'<p class="book-review">楽天ブックスのレビュー　<span class="stars">★</span> '
                  f'{info["review_average"]:.1f}（{info["review_count"]}件）</p>')
    loading = "eager" if role == "main" else "lazy"  # 画面上部のメインの表紙はすぐ読み込む
    image = (f'<img src="{escape(info["image"])}" alt="{escape(book["title"])}の表紙" loading="{loading}" width="150">'
             if info.get("image") else "")
    return f"""<article class="book book--{role}">
  <div class="book-cover">{image}</div>
  <div class="book-body">
    <p class="book-publisher">{escape(book['publisher'])}</p>
    <h3 class="book-title">{escape(book['title'])}</h3>
    <p class="book-price">{info['price']:,}<span>円（税込）</span></p>
    {review}
    <ul class="book-points">{points}</ul>
    <a class="btn-buy" href="{escape(info['url'])}" target="_blank" rel="nofollow sponsored noopener"
       data-book="{escape(type_id)}:{escape(role)}">楽天ブックスで見る</a>
  </div>
</article>"""


def build(site: dict, quiz: dict, books: dict, data: dict) -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "assets").mkdir(parents=True)
    for f in (ROOT / "site" / "assets").iterdir():
        shutil.copy(f, DIST / "assets" / f.name)
    (DIST / ".nojekyll").write_text("")

    fetched = data.get("_fetched_at")
    d = datetime.fromisoformat(fetched).astimezone(JST) if fetched else datetime.now(JST)
    updated = f"{d.year}年{d.month}月{d.day}日"
    types = quiz["types"]
    n_types, n_questions = len(types), len(quiz["questions"])

    def type_rows(depth: int, current: str | None = None) -> str:
        rows = []
        for i, (tid, t) in enumerate(types.items()):
            here = '<span class="type-here">いまのタイプ</span>' if tid == current else ""
            rows.append(f"""<a class="type-row reveal" href="{"../" * depth}result/{tid}/">
  <span class="type-num">{KANJI[i]}</span>
  <span class="type-body"><span class="type-name">{escape(t["name"])}{here}</span><span class="type-catch">{escape(t["catch"])}</span></span>
  <span class="type-arrow" aria-hidden="true">→</span>
</a>
<div class="hikisen thin"></div>""")
        return "\n".join(rows)

    pages = [""]

    # トップ（診断）
    quiz_json = json.dumps({
        "questions": [{"text": q["text"], "yes": q.get("yes") or {}, "no": q.get("no") or {}} for q in quiz["questions"]],
        "order": list(types),
    }, ensure_ascii=False)
    dots = "".join("<li></li>" for _ in quiz["questions"])
    body = f"""<section class="hero" id="intro">
  <div class="hero-inner reveal">
    {seal("診断")}
    <p class="kicker">IT Passport — 2026</p>
    <p class="hero-lead">参考書が多すぎて、選べない人へ</p>
    <h1><span class="line">あなたに合う参考書を、</span><span class="line waved">{n_questions}の問いで。{WAVE}</span></h1>
    <p class="subcopy">「はい」「いいえ」で答えるだけ。勉強のクセに合わせて、{n_types}つのタイプから<span class="ten">主役の一冊</span>と<span class="ten">仕上げの一冊</span>をおすすめします。所要時間はおよそ一分、登録は要りません。</p>
    <div class="hero-ctas">
      <button class="btn-stamp" id="start" type="button">診断をはじめる</button>
      <a class="btn-text" href="#types">{n_types}つのタイプを見る</a>
    </div>
  </div>
</section>
<section class="quiz" id="quiz" hidden>
  <div class="quiz-frame">
    <div class="quiz-head">
      <p class="kicker">Question</p>
      <p class="quiz-count"><span id="num"></span><span class="quiz-total">／全{n_questions}問</span></p>
    </div>
    <ol class="dots" id="dots" aria-hidden="true">{dots}</ol>
    <div class="hikisen thin"></div>
    <h2 class="quiz-q" id="question" aria-live="polite"></h2>
    <div class="quiz-answers">
      <button class="btn-stamp btn-answer" type="button" data-answer="yes">はい<small>Yes</small></button>
      <button class="btn-stamp btn-answer" type="button" data-answer="no">いいえ<small>No</small></button>
    </div>
    <button class="btn-text quiz-back" id="back" type="button">ひとつ前の問いに戻る</button>
  </div>
</section>
<section class="block" id="types">
  <div class="section-head reveal"><p class="kicker">Types</p><h2>診断でわかる、{n_types}つのタイプ</h2></div>
  <div class="hikisen thin"></div>
  {type_rows(0)}
</section>
<script id="quiz-data" type="application/json">{quiz_json}</script>"""
    (DIST / "index.html").write_text(
        page(site, title=f"{site['title']}｜{site['subtitle']}", description=site["description"],
             path="", body=body, depth=0).replace("{updated}", updated), encoding="utf-8")

    # 結果ページ（タイプごとに1ページ。シェアされたときにこのURLが出る）
    for tid, t in types.items():
        main, sub = books[t["main"]], books[t["sub"]]
        url = site["base_url"] + f"result/{tid}/"
        share_text = f"私は「{t['name']}」でした！\nおすすめは『{main['title']}』\n#{' #'.join(site['hashtags'])}\n"
        body = f"""<section class="result">
  <div class="result-head reveal">
    {seal("推薦")}
    <p class="kicker">Result <span class="pr">PR</span></p>
    <p class="result-label">あなたは</p>
    <h1 class="result-name"><span class="waved">{escape(t['name'])}{WAVE}</span></h1>
    <p class="result-catch">{escape(t['catch'])}</p>
    <p class="result-desc">{escape(t['description'])}</p>
  </div>
  <div class="section-head reveal"><p class="kicker">Main</p><h2>主役の一冊</h2></div>
  <div class="obi reveal">{book_card(main, data[t['main']], role="main", type_id=tid)}</div>
  <div class="section-head reveal"><p class="kicker">Finish</p><h2>仕上げに、もう一冊</h2>
    <p class="sub-reason">{escape(t['sub_reason'])}</p></div>
  <div class="sub-frame reveal">{book_card(sub, data[t['sub']], role="sub", type_id=tid)}</div>
  <div class="cta-frame reveal">
    <p class="cta-lead">結果を、だれかに。</p>
    <div class="hero-ctas">
      <a class="btn-stamp" target="_blank" rel="noopener"
         href="https://x.com/intent/post?text={_q(share_text)}&url={_q(url)}">Xでシェアする</a>
      <a class="btn-text" href="../../">もう一度診断する</a>
    </div>
  </div>
</section>
<section class="block" id="types">
  <div class="section-head reveal"><p class="kicker">Types</p><h2>ほかのタイプも見る</h2></div>
  <div class="hikisen thin"></div>
  {type_rows(2, tid)}
</section>"""
        out = DIST / "result" / tid
        out.mkdir(parents=True)
        (out / "index.html").write_text(
            page(site, title=f"{t['name']}のあなたに合うITパスポート参考書｜{site['title']}",
                 description=f"{t['catch']}。{t['description']}", path=f"result/{tid}/", body=body, depth=2,
                 og_image=data[t["main"]].get("image", "")).replace("{updated}", updated),
            encoding="utf-8")
        pages.append(f"result/{tid}/")

    today = datetime.now(JST).date().isoformat()
    (DIST / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{site['base_url']}{p}</loc><lastmod>{today}</lastmod></url>\n" for p in pages)
        + "</urlset>\n", encoding="utf-8")
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {site['base_url']}sitemap.xml\n")
    print(f"dist/ に {len(pages)} ページを書き出しました（価格情報: {updated}）")


def _q(s: str) -> str:
    return quote(s, safe="")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="到達チェックだけ行う")
    args = parser.parse_args()
    site, quiz, books, data = load()
    errors = validate(quiz, books, data)
    for e in errors:
        print(e, file=sys.stderr)
    if errors or not check(quiz):
        return 1
    if not args.check:
        build(site, quiz, books, data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
