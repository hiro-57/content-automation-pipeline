"""knowledge/past_articles/ から voice_guide / industry_facts の提案を生成する。

K2（過去記事）が `knowledge/past_articles/*.md` に揃っている前提で実行する。
出力は `knowledge/_proposed_voice_guide.md` と `knowledge/_proposed_industry_facts.md`。
担当者レビュー後にリネームして本番反映する想定。

使い方:
    python extract_kb.py
"""
import os
import re
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent
KNOWLEDGE_DIR = PROJECT_DIR / "knowledge"
PROMPTS_DIR = PROJECT_DIR / "prompts"
PAST_ARTICLES_DIR = KNOWLEDGE_DIR / "past_articles"

DEFAULT_MODEL = "claude-sonnet-4-5"


class ExtractError(RuntimeError):
    pass


def _load_prompt(name: str) -> tuple[str, str]:
    """prompts/<name>.md から SYSTEM と USER を抽出。"""
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise ExtractError(f"プロンプトファイルが見つかりません: {path}")
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
        raise ExtractError(
            f"{path} には '## SYSTEM PROMPT' と '## USER PROMPT' セクションが必要です"
        )
    return sys_match.group(1).strip(), user_match.group(1).strip()


def _load_past_articles() -> list[tuple[str, str]]:
    """knowledge/past_articles/*.md（README.md 除外）を読み込む。"""
    if not PAST_ARTICLES_DIR.exists():
        return []
    articles: list[tuple[str, str]] = []
    for path in sorted(PAST_ARTICLES_DIR.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        body = path.read_text(encoding="utf-8").strip()
        if body:
            articles.append((path.name, body))
    return articles


def _format_articles_block(articles: list[tuple[str, str]]) -> str:
    parts: list[str] = []
    for name, body in articles:
        parts.append(f"=== {name} ===\n{body}\n")
    return "\n".join(parts)


def _extract_text(response) -> str:
    return "".join(b.text for b in response.content if hasattr(b, "text") and b.text)


def extract_voice_guide(
    client: anthropic.Anthropic,
    model: str,
    articles: list[tuple[str, str]],
) -> str:
    system_prompt, user_template = _load_prompt("extract_voice_guide")
    user_message = user_template.format(
        article_count=len(articles),
        articles_content=_format_articles_block(articles),
    )
    response = client.messages.create(
        model=model,
        max_tokens=8000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return _extract_text(response)


def extract_industry_facts(
    client: anthropic.Anthropic,
    model: str,
    articles: list[tuple[str, str]],
) -> str:
    system_prompt, user_template = _load_prompt("extract_industry_facts")
    user_message = user_template.format(
        article_count=len(articles),
        articles_content=_format_articles_block(articles),
    )
    response = client.messages.create(
        model=model,
        max_tokens=8000,
        system=system_prompt,
        tools=[
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 8,
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )
    return _extract_text(response)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv(PROJECT_DIR / ".env", override=True)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY が .env にありません")

    articles = _load_past_articles()
    if not articles:
        print(f"⚠ 過去記事が見つかりません: {PAST_ARTICLES_DIR}")
        print("  knowledge/past_articles/ に .md ファイルを 3〜5 本配置してから")
        print("  もう一度このスクリプトを実行してください。")
        return

    print(f"読み込み: {len(articles)} 記事")
    for name, _ in articles:
        print(f"  - {name}")

    model = os.environ.get("CLAUDE_MODEL", DEFAULT_MODEL)
    client = anthropic.Anthropic(api_key=api_key)

    print(f"\n[1/2] voice_guide を抽出中...（モデル: {model}）")
    voice_md = extract_voice_guide(client, model, articles)
    voice_path = KNOWLEDGE_DIR / "_proposed_voice_guide.md"
    voice_path.write_text(voice_md, encoding="utf-8")
    print(f"  → 保存: {voice_path.relative_to(PROJECT_DIR)}")

    print("\n[2/2] industry_facts を抽出中...（web_search で最新情報照合）")
    facts_md = extract_industry_facts(client, model, articles)
    facts_path = KNOWLEDGE_DIR / "_proposed_industry_facts.md"
    facts_path.write_text(facts_md, encoding="utf-8")
    print(f"  → 保存: {facts_path.relative_to(PROJECT_DIR)}")

    print("\n=" * 30)
    print("✅ 抽出完了。次の手順:")
    print(f"  1. {voice_path.name} を開いてレビュー → 修正 → voice_guide.md にリネーム上書き")
    print(f"  2. {facts_path.name} を開いてレビュー → 修正 → industry_facts.md にリネーム上書き")
    print("  3. Git で diff を確認してコミット")


if __name__ == "__main__":
    main()
