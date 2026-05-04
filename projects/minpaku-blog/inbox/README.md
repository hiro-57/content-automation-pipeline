# CSV Inbox

Ahrefs からエクスポートした CSV をここに置くと、`replenish_keywords.py` がスプレッドシートに取り込みます。

## 使い方

1. **Ahrefs Keywords Explorer** で対象キーワードを検索
2. 左メニュー「**Matching terms**」または「**Related terms**」を開く
3. 検索ボリューム・KD などでフィルタリング
4. 右上の「**Export**」 → **CSV (UTF-8, best for OpenOffice...)** を選択 → ダウンロード
5. ダウンロードした CSV を**このフォルダ**（`inbox/`）にコピー
6. ターミナルで実行:
   ```
   .venv/Scripts/python.exe replenish_keywords.py
   ```
7. 取り込み済みの CSV は `inbox/processed/` に自動移動されます

## 重複防止

スプレッドシートの `keyword` 列に既に存在するキーワードは**自動でスキップ**されます（status が「処理済」かどうかに関わらず）。

## 必須の CSV カラム

CSV のヘッダー行に **`Keyword`** という列が必須。Ahrefs のデフォルトエクスポートは満たしています。
