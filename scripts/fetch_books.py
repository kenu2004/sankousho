"""config/books.yaml の ISBN から、楽天ブックスの表紙・価格・レビュー・アフィリエイトURLを取ってくる。

楽天ブックス書籍検索APIを isbn 指定で呼ぶ。結果は data/books.json に保存し、取得に失敗した本は前回の値を残す。

必要な環境変数（.env でも可）:
  RAKUTEN_APPLICATION_ID, RAKUTEN_ACCESS_KEY, RAKUTEN_AFFILIATE_ID, RAKUTEN_REFERER
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "books.json"
ENDPOINT = "https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404"
INTERVAL_SEC = 1.5  # 短時間に連続で呼ぶと429になるため
IMAGE_SIZE = "300x300"


def load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def search(isbn: str) -> dict | None:
    params = {
        "applicationId": os.environ["RAKUTEN_APPLICATION_ID"],
        "accessKey": os.environ["RAKUTEN_ACCESS_KEY"],
        "affiliateId": os.environ.get("RAKUTEN_AFFILIATE_ID", ""),
        "format": "json",
        "formatVersion": 2,
        "isbn": isbn,
    }
    referer = os.environ.get("RAKUTEN_REFERER", "https://kenu2004.github.io/")
    parsed = urllib.parse.urlparse(referer)
    req = urllib.request.Request(
        f"{ENDPOINT}?{urllib.parse.urlencode(params)}",
        # アプリ設定の「許可されたWebサイト」と合わせる必要がある
        headers={"Referer": referer, "Origin": f"{parsed.scheme}://{parsed.netloc}"},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                items = json.load(resp).get("Items", [])
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < 2:
                time.sleep(5 * (attempt + 1))
                continue
            raise
    return items[0] if items else None


def to_record(isbn: str, item: dict) -> dict:
    image = item.get("largeImageUrl") or ""
    if image:
        image = image.split("?")[0] + f"?_ex={IMAGE_SIZE}"
    return {
        "isbn": isbn,
        "item_name": item["title"],
        "sales_date": item.get("salesDate", ""),
        # 1: 在庫あり 2: 通常3〜7日 3: 通常3〜9日 4: メーカー取り寄せ 5: 予約受付中 6: メーカーに在庫確認
        "availability": str(item.get("availability", "")),
        "price": int(item.get("itemPrice") or 0),
        "image": image,
        "url": item.get("affiliateUrl") or item["itemUrl"],
        "review_count": int(item.get("reviewCount") or 0),
        "review_average": float(item.get("reviewAverage") or 0),
    }


def main() -> int:
    load_env()
    if not (os.environ.get("RAKUTEN_APPLICATION_ID") and os.environ.get("RAKUTEN_ACCESS_KEY")):
        print("RAKUTEN_APPLICATION_ID と RAKUTEN_ACCESS_KEY を設定してください", file=sys.stderr)
        return 1

    books = yaml.safe_load((ROOT / "config" / "books.yaml").read_text(encoding="utf-8"))
    previous = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    result, failed = {}, []

    for book_id, book in books.items():
        isbn = book["isbn"]
        try:
            item = search(isbn)
        except Exception as e:  # 1冊の失敗でサイト全体を止めない
            item = None
            print(f"[{book_id}] 取得エラー: {e}", file=sys.stderr)
        if item:
            result[book_id] = to_record(isbn, item)
            print(f"[{book_id}] {result[book_id]['price']}円 レビュー{result[book_id]['review_count']}件")
        elif book_id in previous:
            result[book_id] = previous[book_id]
            failed.append(book_id)
            print(f"[{book_id}] 見つからないので前回の値を使います", file=sys.stderr)
        else:
            failed.append(book_id)
            print(f"[{book_id}] 見つかりません（ISBN {isbn}）", file=sys.stderr)
        time.sleep(INTERVAL_SEC)

    result["_fetched_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)} に保存しました（失敗 {len(failed)} 件）")
    # 1冊もデータがない本があるとページが作れないので失敗扱いにする
    missing = [b for b in books if b not in result]
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
