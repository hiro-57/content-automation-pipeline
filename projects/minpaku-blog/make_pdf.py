"""手順書.md を PDF に変換するワンショット スクリプト。

Markdown → HTML → PDF（Microsoft Edge headless）の流れで、
Japanese・絵文字・テーブルを正確にレンダリング。
"""
import shutil
import subprocess
import sys
from pathlib import Path

import markdown

sys.stdout.reconfigure(encoding="utf-8")

PROJECT_DIR = Path(__file__).resolve().parent
MD_PATH = PROJECT_DIR / "手順書.md"
HTML_PATH = PROJECT_DIR / "_手順書.html"
PDF_PATH = PROJECT_DIR / "手順書.pdf"


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>民泊ブログ自動化パイプライン 手順書</title>
<style>
@page {{
    size: A4;
    margin: 18mm 16mm 20mm 16mm;
}}
body {{
    font-family: "Yu Gothic", "Meiryo", "MS Gothic", "Noto Sans CJK JP", sans-serif;
    line-height: 1.7;
    color: #1a1a1a;
    font-size: 10.5pt;
    margin: 0;
}}
h1 {{
    color: #1a1a1a;
    border-bottom: 3px solid #0a4d8c;
    padding-bottom: 8px;
    margin-top: 28px;
    margin-bottom: 16px;
    font-size: 22pt;
    page-break-before: always;
    page-break-after: avoid;
}}
h1:first-of-type {{
    page-break-before: auto;
    margin-top: 0;
    font-size: 26pt;
    color: #0a4d8c;
}}
h2 {{
    color: #0a4d8c;
    border-bottom: 1px solid #aac6e1;
    padding-bottom: 5px;
    margin-top: 22px;
    font-size: 16pt;
    page-break-after: avoid;
}}
h3 {{
    color: #1f1f1f;
    margin-top: 18px;
    font-size: 13pt;
    page-break-after: avoid;
}}
h4 {{
    color: #333;
    margin-top: 14px;
    font-size: 11pt;
    page-break-after: avoid;
}}
p {{
    margin: 8px 0;
}}
ul, ol {{
    margin: 8px 0 8px 0;
    padding-left: 24px;
}}
li {{
    margin: 3px 0;
}}
code {{
    background: #f3f4f6;
    padding: 2px 6px;
    border-radius: 3px;
    font-family: Consolas, "Courier New", "MS Gothic", monospace;
    font-size: 9.5pt;
    color: #c7254e;
}}
pre {{
    background: #f6f8fa;
    padding: 12px 14px;
    border-radius: 5px;
    border: 1px solid #e1e4e8;
    overflow-x: auto;
    font-size: 9pt;
    line-height: 1.5;
    page-break-inside: avoid;
}}
pre code {{
    background: transparent;
    padding: 0;
    color: #24292e;
    font-size: 9pt;
}}
table {{
    border-collapse: collapse;
    width: 100%;
    margin: 14px 0;
    font-size: 9.5pt;
    page-break-inside: avoid;
}}
th, td {{
    border: 1px solid #c0c8d2;
    padding: 7px 10px;
    text-align: left;
    vertical-align: top;
}}
th {{
    background: #e8eef5;
    font-weight: bold;
    color: #0a4d8c;
}}
tr:nth-child(even) td {{
    background: #fafbfc;
}}
blockquote {{
    border-left: 4px solid #0a4d8c;
    margin: 14px 0;
    padding: 8px 16px;
    background: #f0f4f8;
    color: #2c3e50;
    font-style: normal;
}}
blockquote p {{
    margin: 4px 0;
}}
a {{
    color: #0066cc;
    text-decoration: none;
}}
a:hover {{
    text-decoration: underline;
}}
hr {{
    border: none;
    border-top: 1px solid #d0d7de;
    margin: 24px 0;
}}
strong {{
    color: #0a4d8c;
}}
.cover {{
    text-align: center;
    padding-top: 80mm;
}}
.cover h1 {{
    border: none;
    page-break-before: avoid;
    font-size: 32pt;
    color: #0a4d8c;
    margin-bottom: 20mm;
}}
.cover .subtitle {{
    font-size: 14pt;
    color: #555;
    margin-bottom: 40mm;
}}
.cover .meta {{
    font-size: 10pt;
    color: #666;
    line-height: 2.2;
}}
</style>
</head>
<body>

<div class="cover">
<h1>民泊ブログ自動化パイプライン<br>手順書</h1>
<div class="subtitle">運用マニュアル｜担当者向け</div>
<div class="meta">
プロジェクト: content-automation-pipeline / minpaku-blog<br>
発行: 2026年5月<br>
リポジトリ: github.com/hiro-57/content-automation-pipeline
</div>
</div>

{body}

</body>
</html>
"""


def find_edge() -> Path:
    candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ]
    for p in candidates:
        if p.exists():
            return p
    found = shutil.which("msedge")
    if found:
        return Path(found)
    raise SystemExit("Microsoft Edge が見つかりません。Edge をインストールしてください。")


def main() -> None:
    if not MD_PATH.exists():
        raise SystemExit(f"手順書.md が見つかりません: {MD_PATH}")

    md_text = MD_PATH.read_text(encoding="utf-8")
    body_html = markdown.markdown(
        md_text, extensions=["tables", "fenced_code", "toc", "sane_lists", "nl2br"]
    )
    full_html = HTML_TEMPLATE.format(body=body_html)
    HTML_PATH.write_text(full_html, encoding="utf-8")
    print(f"HTML 生成: {HTML_PATH.name}")

    edge = find_edge()
    file_url = HTML_PATH.resolve().as_uri()

    cmd = [
        str(edge),
        "--headless=new",
        "--disable-gpu",
        f"--print-to-pdf={PDF_PATH}",
        "--no-pdf-header-footer",
        "--print-to-pdf-no-header",
        file_url,
    ]
    print(f"Edge で印刷中: {edge.name}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print("Edge stderr:", result.stderr[:500])
        raise SystemExit(f"PDF 生成失敗（exit {result.returncode}）")

    if not PDF_PATH.exists():
        raise SystemExit("PDF ファイルが作成されませんでした")

    size_kb = PDF_PATH.stat().st_size / 1024
    print(f"✅ PDF 生成完了: {PDF_PATH.name} ({size_kb:.1f} KB)")

    # 中間 HTML を削除（残したい場合は次の3行をコメントアウト）
    if HTML_PATH.exists():
        HTML_PATH.unlink()
        print(f"  中間 HTML を削除: {HTML_PATH.name}")


if __name__ == "__main__":
    main()
