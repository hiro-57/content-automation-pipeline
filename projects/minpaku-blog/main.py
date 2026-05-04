import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from steps.claude import generate_article
from steps.sheets import get_unprocessed_keyword, mark_processed
from steps.wordpress import create_draft_post, split_title_from_markdown

sys.stdout.reconfigure(encoding="utf-8")
# override=True: .env の値で OS の環境変数を上書きする
# （空の ANTHROPIC_API_KEY などが OS 側にあっても .env 優先）
load_dotenv(override=True)

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = PROJECT_DIR / "outputs"


def _slug(text: str) -> str:
    """ファイル名に使える形に整える（スペース→ハイフン、Windowsで使えない文字を除去）。"""
    cleaned = re.sub(r'[\\/:*?"<>|]', "", text).strip()
    return cleaned.replace(" ", "-")[:60]


def _backup_article(keyword: str, article_md: str) -> Path:
    """生成記事を outputs/ に保存。"""
    OUTPUTS_DIR.mkdir(exist_ok=True)
    now_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = OUTPUTS_DIR / f"{now_str}_{_slug(keyword)}.md"
    path.write_text(article_md, encoding="utf-8")
    return path


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

    print("Claude API に記事生成をリクエスト中...")
    t0 = time.time()
    result = generate_article(keyword)
    elapsed = time.time() - t0

    in_tok = result["input_tokens"]
    out_tok = result["output_tokens"]
    cache_create = result["cache_creation_tokens"]
    cache_read = result["cache_read_tokens"]
    print(
        f"✓ 記事生成完了（{elapsed:.1f}秒 / "
        f"in={in_tok:,} out={out_tok:,} cache作成={cache_create:,} cache読込={cache_read:,}）"
    )

    backup_path = _backup_article(keyword, result["text"])
    print(f"✓ バックアップ保存: outputs/{backup_path.name}")

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
