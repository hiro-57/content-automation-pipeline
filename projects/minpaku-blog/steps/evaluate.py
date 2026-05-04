"""Claude API + web_search ツールで記事を評価する。

prompts/evaluate_article.md を読み込み、Anthropic API を web_search 付きで呼ぶ。
Claude が Google 検索の上位5件を自動取得し、対象記事と比較して JSON で評価結果を返す。
"""
import json
import os
import re
from pathlib import Path

import anthropic
import json_repair

PROJECT_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = PROJECT_DIR / "prompts"

DEFAULT_MODEL = "claude-sonnet-4-5"
WEB_SEARCH_MAX_USES = 5


class EvaluationError(RuntimeError):
    pass


def _load_prompt(name: str) -> tuple[str, str]:
    """prompts/<name>.md から SYSTEM と USER を抽出。"""
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise EvaluationError(f"プロンプトファイルが見つかりません: {path}")
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
        raise EvaluationError(
            f"{path} には '## SYSTEM PROMPT' と '## USER PROMPT' セクションが必要です"
        )
    return sys_match.group(1).strip(), user_match.group(1).strip()


def _extract_json(text: str) -> dict:
    """応答テキストから JSON ブロックを抜き出す。

    LLM 出力の JSON は時々壊れている（未エスケープの引用符、末尾カンマ、コメントなど）ため、
    厳格な json.loads → json_repair の順でフォールバックする。
    """
    match = re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
    if not match:
        # フォールバック: { から始まり } で終わる最大マッチ
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if not match:
            raise EvaluationError("評価レスポンスに JSON が見つかりません")
    raw = match.group(1)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # json-repair で修復を試みる
        try:
            repaired = json_repair.loads(raw)
            if isinstance(repaired, dict):
                return repaired
            raise EvaluationError(f"JSON 修復後も dict にならない: {type(repaired)}")
        except Exception as exc:
            raise EvaluationError(
                f"JSON パース失敗（修復不能）: {exc}\n生データ先頭500文字:\n{raw[:500]}"
            )


def evaluate_article(
    keyword: str,
    article_md: str,
    *,
    model: str | None = None,
    max_tokens: int = 8000,
) -> dict:
    """記事を web_search 付きで評価する。

    返り値（評価 JSON + メタ）:
      {
        "overall_score": float,
        "scores": {...},
        "strengths": [...],
        "missing_topics": [...],
        "improvements": [...],
        "competitors_analyzed": [...],
        "human_action_hints": [...],
        "_raw_text": str,
        "_input_tokens": int,
        "_output_tokens": int,
        "_search_count": int,
        "_model": str,
      }
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EvaluationError("ANTHROPIC_API_KEY が .env にありません")

    model = model or os.environ.get("CLAUDE_MODEL", DEFAULT_MODEL)
    system_prompt, user_template = _load_prompt("evaluate_article")
    user_message = user_template.format(keyword=keyword, article_md=article_md)

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        tools=[
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": WEB_SEARCH_MAX_USES,
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )

    text_blocks = [
        b.text for b in response.content if hasattr(b, "text") and b.text
    ]
    full_text = "\n".join(text_blocks)

    # web_search の使用回数を数える
    search_count = sum(
        1
        for b in response.content
        if getattr(b, "type", None) == "server_tool_use"
        and getattr(b, "name", None) == "web_search"
    )

    eval_data = _extract_json(full_text)

    return {
        **eval_data,
        "_raw_text": full_text,
        "_input_tokens": response.usage.input_tokens,
        "_output_tokens": response.usage.output_tokens,
        "_search_count": search_count,
        "_model": model,
        "_stop_reason": response.stop_reason,
    }


def format_evaluation_markdown(evaluation: dict, keyword: str) -> str:
    """評価結果を人間が読みやすい Markdown に整形する。"""
    lines: list[str] = []
    lines.append(f"# 評価レポート: {keyword}")
    lines.append("")
    score = evaluation.get("overall_score", "?")
    lines.append(f"**総合スコア**: {score} / 10")
    lines.append("")

    scores = evaluation.get("scores", {})
    if scores:
        lines.append("## スコア内訳")
        lines.append("")
        lines.append("| 評価軸 | スコア |")
        lines.append("|---|---|")
        labels = {
            "comprehensiveness": "網羅性",
            "depth": "深さ・具体性",
            "originality": "独自性",
            "actionability": "実用性",
            "readability": "読みやすさ",
            "search_intent_fit": "検索意図適合",
        }
        for key, label in labels.items():
            if key in scores:
                lines.append(f"| {label} | {scores[key]} / 10 |")
        lines.append("")

    if evaluation.get("strengths"):
        lines.append("## 強み")
        lines.append("")
        for s in evaluation["strengths"]:
            lines.append(f"- {s}")
        lines.append("")

    if evaluation.get("missing_topics"):
        lines.append("## 不足トピック（上位記事が扱っているのに無い）")
        lines.append("")
        for t in evaluation["missing_topics"]:
            lines.append(f"- {t}")
        lines.append("")

    if evaluation.get("improvements"):
        lines.append("## 具体的な改善提案")
        lines.append("")
        for imp in evaluation["improvements"]:
            lines.append(f"### {imp.get('what', '?')}")
            if imp.get("where"):
                lines.append(f"- **追加位置**: {imp['where']}")
            if imp.get("why"):
                lines.append(f"- **理由**: {imp['why']}")
            lines.append("")

    if evaluation.get("human_action_hints"):
        lines.append("## 人間（運営者）が編集時に追加すべきこと")
        lines.append("")
        for h in evaluation["human_action_hints"]:
            lines.append(f"- {h}")
        lines.append("")

    if evaluation.get("competitors_analyzed"):
        lines.append("## 比較した上位記事")
        lines.append("")
        for c in evaluation["competitors_analyzed"]:
            lines.append(f"### [{c.get('title', '?')}]({c.get('url', '#')})")
            if c.get("summary"):
                lines.append(c["summary"])
            lines.append("")

    lines.append("---")
    lines.append(
        f"_モデル: {evaluation.get('_model', '?')}"
        f" / 入力 {evaluation.get('_input_tokens', '?')} tok"
        f" / 出力 {evaluation.get('_output_tokens', '?')} tok"
        f" / web_search {evaluation.get('_search_count', '?')} 回_"
    )

    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    from dotenv import load_dotenv

    sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv(PROJECT_DIR / ".env", override=True)

    if len(sys.argv) < 3:
        print("使い方: python steps/evaluate.py <keyword> <article.md>")
        sys.exit(1)

    test_keyword = sys.argv[1]
    article_path = Path(sys.argv[2])
    article_text = article_path.read_text(encoding="utf-8")

    print(f"キーワード: {test_keyword}")
    print(f"対象記事: {article_path}")
    print("Claude API + web_search で評価中...（30〜60秒）")

    evaluation = evaluate_article(test_keyword, article_text)

    print("=" * 60)
    print(format_evaluation_markdown(evaluation, test_keyword))
