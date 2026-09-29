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
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext y='.9em' font-size='90'%3E%F0%9F%93%9A%3C/text%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=M+PLUS+Rounded+1c:wght@500;800&family=Noto+Sans+JP:wght@400;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{root}assets/style.css">
{extra_head}{ga}
</head>
<body>
<header class="site-header"><a href="{root}" class="logo">📚 {escape(site['title'])}</a></header>
<main>
{body}
</main>
<footer class="site-footer">
<p>当サイトは楽天アフィリエイトを利用しています（PR）。リンク先で購入されると、運営者に紹介料が入ることがあります。</p>
<p>参考書の紹介文は出版社の商品説明をもとにまとめたものです。価格・在庫は{{updated}}時点の楽天ブックスの情報で、現在の価格はリンク先でご確認ください。</p>
<p class="credit"><!-- Rakuten Web Service Center --><a href="https://developers.rakuten.com/" target="_blank" rel="noopener">Supported by Rakuten Developers</a></p>
</footer>
</body>
</html>
"""


def book_card(book: dict, info: dict, *, role: str, type_id: str) -> str:
    points = "".join(f"<li>{escape(p)}</li>" for p in book["points"])
    review = ""
    if info.get("review_count"):
        review = (f'<span class="review">★ {info["review_average"]:.1f}'
                  f'<small>（楽天ブックスのレビュー{info["review_count"]}件）</small></span>')
    image = (f'<img src="{escape(info["image"])}" alt="{escape(book["title"])}の表紙" loading="{'eager' if role == 'main' else 'lazy'}" width="150">'
             if info.get("image") else "")
    return f"""<article class="book book--{role}">
  <div class="book__cover">{image}</div>
  <div class="book__body">
    <h3 class="book__title">{escape(book['title'])}</h3>
    <p class="book__meta">{escape(book['publisher'])}　<span class="price">{info['price']:,}円</span>{review}</p>
    <ul class="book__points">{points}</ul>
    <a class="btn btn--buy" href="{escape(info['url'])}" target="_blank" rel="nofollow sponsored noopener"
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
    type_links = lambda depth, current=None: "".join(
        f'<li><a href="{"../" * depth}result/{tid}/"{" aria-current=page" if tid == current else ""}>'
        f'{escape(t["name"])}<small>{escape(t["catch"])}</small></a></li>'
        for tid, t in types.items())
    pages = [""]

    # トップ（診断）
    quiz_json = json.dumps({
        "questions": [{"text": q["text"], "yes": q.get("yes") or {}, "no": q.get("no") or {}} for q in quiz["questions"]],
        "order": list(types),
    }, ensure_ascii=False)
    body = f"""<section class="hero" id="intro">
  <p class="hero__eyebrow">2026年度版 ITパスポート</p>
  <h1>{escape(site['subtitle']).replace("。", "。<br>")}</h1>
  <p>参考書が多すぎて選べない人へ。勉強のクセに合わせて、{len(types)}タイプから<strong>メインの1冊</strong>と<strong>仕上げの1冊</strong>を提案します。</p>
  <button class="btn btn--start" id="start" type="button">診断をはじめる</button>
  <p class="hero__note">所要時間 約1分・登録不要</p>
</section>
<section class="quiz" id="quiz" hidden>
  <div class="progress"><div class="progress__bar" id="bar"></div></div>
  <p class="quiz__count" id="count"></p>
  <h2 class="quiz__q" id="question"></h2>
  <div class="quiz__answers">
    <button class="btn btn--yes" type="button" data-answer="yes">YES</button>
    <button class="btn btn--no" type="button" data-answer="no">NO</button>
  </div>
  <button class="quiz__back" id="back" type="button">← ひとつ前に戻る</button>
</section>
<section class="types">
  <h2>診断でわかる{len(types)}つのタイプ</h2>
  <ul class="type-list">{type_links(0)}</ul>
</section>
<script id="quiz-data" type="application/json">{quiz_json}</script>
<script src="assets/app.js" defer></script>"""
    (DIST / "index.html").write_text(
        page(site, title=f"{site['title']}｜{site['subtitle']}", description=site["description"],
             path="", body=body, depth=0).replace("{updated}", updated), encoding="utf-8")

    # 結果ページ（タイプごとに1ページ。シェアされたときにこのURLが出る）
    for tid, t in types.items():
        main, sub = books[t["main"]], books[t["sub"]]
        url = site["base_url"] + f"result/{tid}/"
        share_text = f"私は「{t['name']}」でした！\nおすすめは『{main['title']}』\n#{' #'.join(site['hashtags'])}\n"
        body = f"""<section class="result">
  <p class="pr">PR</p>
  <p class="result__label">あなたは…</p>
  <h1 class="result__name">{escape(t['name'])}</h1>
  <p class="result__catch">{escape(t['catch'])}</p>
  <p class="result__desc">{escape(t['description'])}</p>
  <h2 class="section-title">メインの1冊</h2>
  {book_card(main, data[t['main']], role="main", type_id=tid)}
  <h2 class="section-title">あわせて使うなら</h2>
  <p class="sub-reason">{escape(t['sub_reason'])}</p>
  {book_card(sub, data[t['sub']], role="sub", type_id=tid)}
  <div class="result__actions">
    <a class="btn btn--share" target="_blank" rel="noopener"
       href="https://x.com/intent/post?text={_q(share_text)}&url={_q(url)}">結果をXでシェア</a>
    <a class="btn btn--retry" href="../../">もう一度診断する</a>
  </div>
</section>
<section class="types">
  <h2>ほかのタイプも見る</h2>
  <ul class="type-list">{type_links(2, tid)}</ul>
</section>
<script src="../../assets/app.js" defer></script>"""
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
    from urllib.parse import quote
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
