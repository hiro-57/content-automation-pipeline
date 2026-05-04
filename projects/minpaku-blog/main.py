import os
import sys

from dotenv import load_dotenv

from steps.dify import generate_article
from steps.sheets import get_unprocessed_keyword, mark_processed
from steps.wordpress import create_draft_post, split_title_from_markdown

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
    print(f"✓ 記事生成完了（{elapsed:.1f}秒 / {tokens:,}トークン）")

    title, body = split_title_from_markdown(result["text"])
    if not title:
        title = keyword
    print(f"タイトル: {title}")

    print("WordPress に下書き投稿中...")
    post = create_draft_post(title=title, body_markdown=body)
    print(f"✓ 下書き作成（ID={post['post_id']}）")
    print(f"  プレビュー: {post['link']}")
    print(f"  編集画面:   {post['edit_link']}")

    print(f"行 {row} を「処理済」に更新...")
    mark_processed(sheet_id, row, article_url=post["link"])
    print("✓ スプレッドシート更新完了")


if __name__ == "__main__":
    main()
