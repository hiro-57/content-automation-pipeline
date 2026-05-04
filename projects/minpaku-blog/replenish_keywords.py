"""Ahrefs CSV エクスポートを inbox/ から取り込み、未処理キーワードとしてスプレッドシートに追加する。

詳細な使い方は inbox/README.md を参照。
"""
import csv
import os
import shutil
import sys
from pathlib import Path

import gspread
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

PROJECT_DIR = Path(__file__).resolve().parent
INBOX_DIR = PROJECT_DIR / "inbox"
PROCESSED_DIR = INBOX_DIR / "processed"
CREDENTIALS_PATH = PROJECT_DIR / "google-credentials.json"
KEYWORD_COLUMN_IN_CSV = "Keyword"
KEYWORD_COLUMN_IN_SHEET = "keyword"


def main() -> None:
    sheet_id = os.environ["KEYWORDS_SHEET_ID"]
    INBOX_DIR.mkdir(exist_ok=True)
    PROCESSED_DIR.mkdir(exist_ok=True)

    csv_files = sorted(p for p in INBOX_DIR.glob("*.csv"))
    if not csv_files:
        print(f"取り込み対象の CSV がありません ({INBOX_DIR})")
        return

    gc = gspread.service_account(filename=str(CREDENTIALS_PATH))
    ws = gc.open_by_key(sheet_id).sheet1

    headers = ws.row_values(1)
    if KEYWORD_COLUMN_IN_SHEET not in headers:
        raise SystemExit(
            f"スプレッドシートに '{KEYWORD_COLUMN_IN_SHEET}' 列がありません。実際のヘッダー: {headers}"
        )
    kw_col_index = headers.index(KEYWORD_COLUMN_IN_SHEET) + 1
    existing_keywords = {
        cell.strip()
        for cell in ws.col_values(kw_col_index)[1:]
        if cell.strip()
    }
    print(f"既存キーワード数: {len(existing_keywords)}")

    grand_new = 0
    grand_dup = 0
    grand_empty = 0

    for csv_path in csv_files:
        print(f"\n読み込み: {csv_path.name}")
        new_kws: list[str] = []
        skipped_dup = 0
        skipped_empty = 0

        with csv_path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if KEYWORD_COLUMN_IN_CSV not in (reader.fieldnames or []):
                print(
                    f"  ⚠ '{KEYWORD_COLUMN_IN_CSV}' 列がありません。スキップします。"
                    f"  実際のヘッダー: {reader.fieldnames}"
                )
                continue
            for row in reader:
                keyword = (row.get(KEYWORD_COLUMN_IN_CSV) or "").strip()
                if not keyword:
                    skipped_empty += 1
                    continue
                if keyword in existing_keywords:
                    skipped_dup += 1
                    continue
                new_kws.append(keyword)
                existing_keywords.add(keyword)

        print(
            f"  → 新規 {len(new_kws)} 件 / 重複スキップ {skipped_dup} 件"
            f" / 空行スキップ {skipped_empty} 件"
        )

        if new_kws:
            rows_to_add = [[kw] + [""] * (len(headers) - 1) for kw in new_kws]
            ws.append_rows(rows_to_add, value_input_option="USER_ENTERED")

        dest = PROCESSED_DIR / csv_path.name
        shutil.move(str(csv_path), str(dest))
        print(f"  → 移動: inbox/processed/{csv_path.name}")

        grand_new += len(new_kws)
        grand_dup += skipped_dup
        grand_empty += skipped_empty

    print(
        f"\n完了: 追加 {grand_new} 件 / 重複 {grand_dup} 件 / 空 {grand_empty} 件"
    )


if __name__ == "__main__":
    main()
