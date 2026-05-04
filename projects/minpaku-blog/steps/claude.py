"""Claude API で記事を生成する。

prompts/generate_article.md と knowledge/*.md を読み込み、Anthropic API を呼ぶ。
プロンプトキャッシュ（5分TTL）で2回目以降のコストを大幅に削減。
"""
import os
import re
from pathlib import Path

import anthropic

PROJECT_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = PROJECT_DIR / "prompts"
KNOWLEDGE_DIR = PROJECT_DIR / "knowledge"

DEFAULT_MODEL = "claude-sonnet-4-5"
KEYWORD_ANCHOR = "【今回のターゲットキーワード】"


class ClaudeGenerationError(RuntimeError):
    pass


def _load_prompt_template(name: str) -> tuple[str, str]:
    """prompts/<name>.md から SYSTEM と USER テンプレートを抽出する。"""
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise ClaudeGenerationError(f"プロンプトファイルが見つかりません: {path}")
    text = path.read_text(encoding="utf-8")

    sys_match = re.search(
        r"##\s*SYSTEM PROMPT[^\n]*\n(.*?)\n##\s*USER PROMPT",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    user_match = re.search(
        r"##\s*USER PROMPT[^\n]*\n(.*)$",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if not sys_match or not user_match:
        raise ClaudeGenerationError(
            f"{path} には '## SYSTEM PROMPT' と '## USER PROMPT' セクションが必要です"
        )
    return sys_match.group(1).strip(), user_match.group(1).strip()


def _load_knowledge_file(filename: str) -> str:
    """knowledge/<filename> を読む。無い/空なら '（未設定）'。"""
    path = KNOWLEDGE_DIR / filename
    if not path.exists():
        return "（未設定）"
    content = path.read_text(encoding="utf-8").strip()
    return content or "（未設定）"


def _load_past_articles() -> str:
    """knowledge/past_articles/*.md（README.md 除く）を結合して返す。"""
    past_dir = KNOWLEDGE_DIR / "past_articles"
    if not past_dir.exists():
        return "（未設定）"
    parts: list[str] = []
    for p in sorted(past_dir.glob("*.md")):
        if p.name.lower() == "readme.md":
            continue
        body = p.read_text(encoding="utf-8").strip()
        if body:
            parts.append(f"--- {p.name} ---\n{body}")
    return "\n\n".join(parts) if parts else "（未設定）"


def generate_article(
    keyword: str,
    *,
    model: str | None = None,
    max_tokens: int = 16000,
) -> dict:
    """記事を生成する。

    返り値:
      {
        "text": 生成された Markdown 記事,
        "model": 使用したモデルID,
        "input_tokens": int,
        "output_tokens": int,
        "cache_creation_tokens": int,
        "cache_read_tokens": int,
        "stop_reason": str,
      }
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ClaudeGenerationError("ANTHROPIC_API_KEY が .env にありません")

    model = model or os.environ.get("CLAUDE_MODEL", DEFAULT_MODEL)

    system_prompt, user_template = _load_prompt_template("generate_article")
    user_message_full = user_template.format(
        keyword=keyword,
        target_audience=_load_knowledge_file("target_audience.md"),
        voice_guide=_load_knowledge_file("voice_guide.md"),
        industry_facts=_load_knowledge_file("industry_facts.md"),
        personal_experiences=_load_knowledge_file("personal_experiences.md"),
        unique_perspectives=_load_knowledge_file("unique_perspectives.md"),
        past_articles=_load_past_articles(),
    )

    # キーワード手前で分割 → 前半をキャッシュ対象に
    if KEYWORD_ANCHOR in user_message_full:
        cacheable_part, variable_part = user_message_full.split(KEYWORD_ANCHOR, 1)
        variable_part = KEYWORD_ANCHOR + variable_part
    else:
        cacheable_part = user_message_full
        variable_part = ""

    user_content = [
        {
            "type": "text",
            "text": cacheable_part.strip(),
            "cache_control": {"type": "ephemeral"},
        }
    ]
    if variable_part:
        user_content.append({"type": "text", "text": variable_part.strip()})

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_content}],
    )

    text = "".join(b.text for b in response.content if hasattr(b, "text"))
    usage = response.usage

    return {
        "text": text,
        "model": model,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cache_creation_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
        "cache_read_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
        "stop_reason": response.stop_reason,
    }


if __name__ == "__main__":
    import sys

    from dotenv import load_dotenv

    sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv(PROJECT_DIR / ".env", override=True)

    test_keyword = sys.argv[1] if len(sys.argv) > 1 else "民泊 始め方"
    print(f"テストキーワード: {test_keyword}")
    print("Claude API に記事生成をリクエスト中...\n")

    result = generate_article(test_keyword)

    print("=" * 60)
    print(f"モデル: {result['model']}")
    print(
        f"トークン: input={result['input_tokens']:,}"
        f" / output={result['output_tokens']:,}"
        f" / cache作成={result['cache_creation_tokens']:,}"
        f" / cache読込={result['cache_read_tokens']:,}"
    )
    print(f"停止理由: {result['stop_reason']}")
    print("=" * 60)
    print()
    print(result["text"])
