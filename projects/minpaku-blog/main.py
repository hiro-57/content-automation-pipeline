import os
import sys

from dotenv import load_dotenv

from steps.dify import generate_article
from steps.sheets import get_unprocessed_keyword, mark_processed

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()


def main() -> None:
    sheet_id = os.environ["KEYWORDS_SHEET_ID"]

    print("スプレッドシートから未処理キーワードを取得...")
    target = get_unprocessed_keyword(sheet_id)
    if target is None:
        print("未処理のキーワードがありません。終了します。")
        return

    keyword = target["keyword"]
    row = target["row_number"]
    print(f"対象: 行 {row} / キーワード '{keyword}'")
    print("Dify に記事生成をリクエスト中...")

    result = generate_article(keyword)

    elapsed = result["elapsed_seconds"]
    tokens = result["tokens"]
    steps = result["steps"]
    print(f"✓ 完了（{elapsed:.1f}秒 / {tokens:,}トークン / {steps}ステップ）")
    print()
    print("────── 記事本文 ──────")
    print(result["text"])
    print("────── ここまで ──────")
    print()

    print(f"行 {row} を「処理済」に更新...")
    mark_processed(sheet_id, row)
    print("✓ スプレッドシート更新完了")


if __name__ == "__main__":
    main()
