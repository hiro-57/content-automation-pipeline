"""記事に加筆マーカー（HTML blockquote）を埋め込む。

evaluate.py で得た human_action_hints を Claude に渡し、適切な位置に
「加筆ヒント」マーカー（黄色いボックス）を挿入する。

WP 投稿後、担当者は編集画面で黄色いボックスを順次見つけて加筆 → ブロック削除。
これによりレポートと WP を行き来する作業が不要になる。
"""
import os
import re
from pathlib import Path

import anthropic

PROJECT_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = PROJECT_DIR / "prompts"

DEFAULT_MODEL = "claude-sonnet-4-5"


class AnnotateError(RuntimeError):
    pass


def _load_prompt(name: str) -> tuple[str, str]:
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise AnnotateError(f"プロンプトファイルが見つかりません: {path}")
    text = path.read_text(encoding="utf-8")
    sys_match = re.search(
        r"##\s*SYSTEM PROMPT[^\n]*\n(.*?)\n##\s*USER PROMPT",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    user_match = re.search(
        r"##\s*USER PROMPT[^\n]*\n(.*)$", text, re.DOTALL | re.IGNORECASE
    )
    if not sys_match or not user_match:
        raise AnnotateError(
            f"{path} には '## SYSTEM PROMPT' と '## USER PROMPT' セクションが必要です"
        )
    return sys_match.group(1).strip(), user_match.group(1).strip()


def annotate_article(
    article_md: str,
    hints: list[str],
    *,
    model: str | None = None,
    max_tokens: int = 16000,
) -> dict:
    """記事に加筆マーカーを挿入する。

    Args:
        article_md: 元の記事 Markdown
        hints: human_action_hints のリスト
        model: 使用モデル（デフォルト: claude-sonnet-4-5）

    Returns:
        {
            "annotated_text": str,    # マーカー入り記事
            "marker_count": int,      # 挿入されたマーカー数（推定）
            "input_tokens": int,
            "output_tokens": int,
            "model": str,
        }
    """
    if not hints:
        return {
            "annotated_text": article_md,
            "marker_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "model": "skipped (no hints)",
        }

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise AnnotateError("ANTHROPIC_API_KEY が .env にありません")

    model = model or os.environ.get("CLAUDE_MODEL", DEFAULT_MODEL)
    system_prompt, user_template = _load_prompt("annotate_article")

    hints_text = "\n".join(f"{i + 1}. {h}" for i, h in enumerate(hints))
    user_message = user_template.format(article_md=article_md, hints_text=hints_text)

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    annotated = "".join(b.text for b in response.content if hasattr(b, "text"))
    # マーカー数を「加筆ヒント」の出現回数で推定
    marker_count = annotated.count("加筆ヒント")

    return {
        "annotated_text": annotated,
        "marker_count": marker_count,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "model": model,
    }
