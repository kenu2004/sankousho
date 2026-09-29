# ITパスポート参考書診断

YES/NO 10問で、勉強スタイルに合う ITパスポートの参考書（メイン＋仕上げの2冊）を提案する静的サイト。
表紙・価格・レビュー・アフィリエイトリンクは楽天ブックス書籍検索APIから取得する。

公開URL: https://kenu2004.github.io/sankousho/

## しくみ

```
config/quiz.yaml    質問・重み・結果タイプ（9タイプ）
config/books.yaml   紹介する本（ISBN・紹介ポイント）
config/site.yaml    タイトル・公開URL・GA4
scripts/fetch_books.py  楽天ブックスAPI → data/books.json
scripts/build.py        YAML + books.json → dist/（トップ + タイプ別の結果ページ）
site/assets/        CSS・JS
.github/workflows/deploy.yml  push時と毎週月曜6時に取り直して GitHub Pages に公開
```

- 判定：各質問の YES/NO ごとにタイプへ点数を足し、合計が最大のタイプを表示する（同点は quiz.yaml の並び順）
- 結果ページはタイプごとの静的ページ。X でシェアされるとそのURLが出る
- 楽天APIは「許可されたWebサイト」を Referer で判定するので、`https://kenu2004.github.io/` を送っている

## ローカルで動かす

```bash
cp .env.example .env   # 楽天のキーを入れる
pip install -r requirements.txt
python scripts/fetch_books.py
python scripts/build.py
python -m http.server 8765 --directory dist
```

## よくある変更

- **本を差し替える**：`config/books.yaml` の ISBN と points を変えて `fetch_books.py` → `build.py`
  - points には出版社の商品説明に書いてあることだけを書く（使っていない本を使ったと書かない）
- **質問や重みを変える**：`config/quiz.yaml` を編集して `python scripts/build.py --check`
  - 1024通りの回答で各タイプが何回出るかを表示する。0回のタイプがあるとエラー
- **別の資格に広げる**：`config/` を資格ごとのフォルダに分けて、build.py を資格ごとに回す形にする

## 公開前チェック

- 結果ページとフッターに PR 表記（ステマ規制・楽天のガイドライン）
- フッターに「Supported by Rakuten Developers」のクレジット（楽天ウェブサービスの規約）
- 価格は取得日時点の表示であることを明記
