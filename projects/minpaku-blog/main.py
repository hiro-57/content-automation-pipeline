import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from steps.claude import generate_article
from steps.evaluate import evaluate_article, format_evaluation_markdown
from steps.sheets import get_unprocessed_keyword, mark_processed
from steps.wordpress import create_draft_post, split_title_from_markdown

sys.stdout.reconfigure(encoding="utf-8")
# override=True: .env を OS の環境変数より優先（空の API key などのシャドー回避）
load_dotenv(override=True)

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = PROJECT_DIR / "outputs"


def _slug(text: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]', "", text).strip()
    return cleaned.replace(" ", "-")[:60]


def _save(path: Path, content: str) -> None:
    OUTPUTS_DIR.mkdir(exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _print_eval_summary(evaluation: dict) -> None:
    score = evaluation.get("overall_score", "?")
    scores = evaluation.get("scores", {})
    print(f"  総合スコア: {score} / 10")
    if scores:
        labels = {
            "comprehensiveness": "網羅性",
            "originality": "独自性",
            "seo": "SEO",
            "readability": "読みやすさ",
            "eeat": "E-E-A-T",
        }
        parts = [f"{labels.get(k, k)}={scores.get(k, '?')}" for k in labels]
        print(f"  内訳: {' / '.join(parts)}")
    missing = evaluation.get("missing_topics", [])
    if missing:
        print(f"  不足トピック {len(missing)} 件（詳細は .evaluation.md 参照）")
    hints = evaluation.get("human_action_hints", [])
    if hints:
        print(f"  実体験追記ヒント {len(hints)} 箇所（人間編集時に確認）")


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

    # ① 記事生成
    print("\n[1/4] Claude API で記事生成中...")
    t0 = time.time()
    gen = generate_article(keyword)
    elapsed = time.time() - t0
    print(
        f"  完了（{elapsed:.1f}秒 / "
        f"in={gen['input_tokens']:,} out={gen['output_tokens']:,} "
        f"cache作成={gen['cache_creation_tokens']:,} cache読込={gen['cache_read_tokens']:,}）"
    )

    now_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    base_name = f"{now_str}_{_slug(keyword)}"
    article_path = OUTPUTS_DIR / f"{base_name}.md"
    _save(article_path, gen["text"])
    print(f"  バックアップ: outputs/{article_path.name}")

    # ② 評価（web_search で競合分析）
    # 評価が失敗しても WP 投稿は続行する（評価は補助情報・ブロッカーではない）
    print("\n[2/4] Claude + web_search で評価中...（30〜90秒）")
    eval_path: Path | None = None
    try:
        t1 = time.time()
        evaluation = evaluate_article(keyword, gen["text"])
        elapsed = time.time() - t1
        print(
            f"  完了（{elapsed:.1f}秒 / "
            f"in={evaluation['_input_tokens']:,} out={evaluation['_output_tokens']:,} "
            f"web検索={evaluation['_search_count']} 回）"
        )
        _print_eval_summary(evaluation)
        eval_md = format_evaluation_markdown(evaluation, keyword)
        eval_path = OUTPUTS_DIR / f"{base_name}.evaluation.md"
        _save(eval_path, eval_md)
        print(f"  評価レポート: outputs/{eval_path.name}")
    except Exception as exc:
        print(f"  ⚠ 評価に失敗しました（パイプラインは続行）: {exc}")
        # 評価失敗時もデバッグ用に応答を保存
        eval_path = OUTPUTS_DIR / f"{base_name}.evaluation_error.txt"
        _save(eval_path, f"評価失敗: {exc}\n")

    # ③ WordPress に下書き投稿
    print("\n[3/4] WordPress に下書き投稿中...")
    title, body = split_title_from_markdown(gen["text"])
    if not title:
        title = keyword
    print(f"  タイトル: {title}")
    post = create_draft_post(title=title, body_markdown=body)
    print(f"  下書きID={post['post_id']}")
    print(f"  編集URL: {post['edit_link']}")

    # ④ スプレッドシート更新
    print("\n[4/4] スプレッドシート更新...")
    mark_processed(sheet_id, row, article_url=post["link"])
    print(f"  行 {row} → 処理済 / URL記録")

    # 最終ガイド
    print("\n" + "=" * 60)
    print("✅ パイプライン完了")
    if eval_path is not None:
        print(f"次のアクション: outputs/{eval_path.name} を見ながら、")
    print(f"  {post['edit_link']}")
    print("で実体験を追記して公開してください。")


if __name__ == "__main__":
    main()
