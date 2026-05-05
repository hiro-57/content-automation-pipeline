"""サムネイル生成: 記事 → Claude が画像プロンプト → Flux で背景 → HTML+CSS で文字入れ → PNG。"""
import os
import re
import shutil
import subprocess
from pathlib import Path

import anthropic
import replicate
import requests

PROJECT_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = PROJECT_DIR / "prompts"
TEMPLATES_DIR = PROJECT_DIR / "templates"
OUTPUTS_DIR = PROJECT_DIR / "outputs"

DEFAULT_FLUX_MODEL = "black-forest-labs/flux-1.1-pro"
DEFAULT_BRAND = "MINPAKU JOURNAL"


class ThumbnailError(RuntimeError):
    pass


def _load_prompt(name: str) -> tuple[str, str]:
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise ThumbnailError(f"プロンプトファイルが見つかりません: {path}")
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
        raise ThumbnailError(f"{path} に SYSTEM/USER PROMPT セクションが必要")
    return sys_match.group(1).strip(), user_match.group(1).strip()


def _find_edge() -> Path:
    """ヘッドレスブラウザの実行可能ファイルを探す。

    優先順位:
      1. 環境変数 `BROWSER_PATH` で明示指定（CI 環境で使用）
      2. Windows: Microsoft Edge の標準パス
      3. Linux: Chromium / Chrome の標準パス（GitHub Actions 等の Ubuntu 環境）
      4. PATH からの which() 検索

    Edge と Chromium は `--headless=new --screenshot --window-size` の
    フラグを共通でサポートするため、どちらでも render_thumbnail は動作する。
    """
    override = os.environ.get("BROWSER_PATH")
    if override:
        p = Path(override)
        if p.exists():
            return p
        raise ThumbnailError(f"BROWSER_PATH が指定されていますが見つかりません: {override}")

    candidates = [
        # Windows: Microsoft Edge
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        # Linux: Chromium / Chrome（GitHub Actions Ubuntu ランナー想定）
        Path("/usr/bin/chromium-browser"),
        Path("/usr/bin/chromium"),
        Path("/usr/bin/google-chrome"),
        Path("/usr/bin/google-chrome-stable"),
        # macOS: Chrome / Edge
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
    ]
    for p in candidates:
        if p.exists():
            return p

    # PATH からの検索
    for cmd in ("msedge", "chromium-browser", "chromium", "google-chrome", "google-chrome-stable"):
        found = shutil.which(cmd)
        if found:
            return Path(found)

    raise ThumbnailError(
        "ヘッドレスブラウザ（Edge/Chromium/Chrome）が見つかりません。"
        " CI では `BROWSER_PATH` 環境変数で明示指定してください。"
    )


def _title_size_class(title: str) -> str:
    """タイトルの文字数で CSS クラスを決定（自動的にフォントサイズ調整）。

    切れないギリギリの 1200x630 内 2 行収まり目安:
      - 〜24 文字  → デフォルト 54px
      - 25〜32 文字 → long 42px
      - 33 文字〜  → very-long 36px
    """
    if len(title) > 32:
        return "very-long"
    if len(title) > 24:
        return "long"
    return ""


# サイズクラスごとの 1 行最大文字数（折り返し位置判定用）
_MAX_CHARS_BY_CLASS = {
    "": 20,            # default 54px → 1100px / 54 ≈ 20
    "long": 26,        # 42px → 1100 / 42 ≈ 26
    "very-long": 30,   # 36px → 1100 / 36 ≈ 30
}

# 改行直後に来てはいけない日本語助詞・接尾辞（「を徹底解説」のように行頭に来ると不自然）
_PARTICLES_FORBIDDEN_AT_LINE_START = set("をがにでとのはもまでからよりへやかねよわけど")

# この文字の直後で改行すると自然（「青色申告の|メリット」のような切れ目）
_PREFERRED_BREAK_AFTER = set("｜・、,。 のはでをがにと")


def _smart_title_break(title: str, size_class: str) -> str:
    """日本語タイトルの「美しい改行位置」を計算して <br> を挿入する。

    例:
      入力: "民泊の確定申告完全ガイド｜申告方法・経費・青色申告のメリットを徹底解説"
      出力: "民泊の確定申告完全ガイド｜申告方法・経費・青色申告の<br>メリットを徹底解説"

    （ブラウザの自動折り返しに任せると「メリット|を徹底解説」のように
     行頭に「を」が来る不自然な分割になる場合があるため、明示的に制御する）
    """
    max_chars = _MAX_CHARS_BY_CLASS.get(size_class, 20)
    if len(title) <= max_chars:
        return title  # 1 行に収まるので何もしない

    half = len(title) // 2

    # フェーズ1: max_chars から逆順にスキャン → 「自然な切れ目」を探す
    for i in range(max_chars, half - 1, -1):
        if i <= 0 or i >= len(title):
            continue
        prev_char = title[i - 1]
        curr_char = title[i]
        if prev_char in _PREFERRED_BREAK_AFTER and curr_char not in _PARTICLES_FORBIDDEN_AT_LINE_START:
            return title[:i] + "<br>" + title[i:]

    # フェーズ2: 助詞行頭を避けるだけの緩い条件
    for i in range(max_chars, half - 1, -1):
        if i <= 0 or i >= len(title):
            continue
        if title[i] not in _PARTICLES_FORBIDDEN_AT_LINE_START:
            return title[:i] + "<br>" + title[i:]

    # フェーズ3: 諦めて max_chars 位置で機械的に分割
    return title[:max_chars] + "<br>" + title[max_chars:]


def generate_image_prompt(keyword: str, title: str, article_md: str) -> str:
    """Claude で記事 → Flux 用画像プロンプト（英語）に変換。"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ThumbnailError("ANTHROPIC_API_KEY が .env にありません")

    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5")
    sys_prompt, user_template = _load_prompt("generate_thumbnail_prompt")
    excerpt = article_md[:800]
    user_msg = user_template.format(
        keyword=keyword, title=title, article_excerpt=excerpt
    )

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=500,
        system=sys_prompt,
        messages=[{"role": "user", "content": user_msg}],
    )
    text = "".join(b.text for b in response.content if hasattr(b, "text")).strip()
    # クォーテーションが先頭末尾にあれば除去
    text = text.strip('"').strip("'").strip()
    return text


def generate_background_image(prompt: str, output_path: Path) -> None:
    """Flux 1.1 Pro で背景画像を生成して保存。"""
    api_token = os.environ.get("REPLICATE_API_TOKEN")
    if not api_token:
        raise ThumbnailError("REPLICATE_API_TOKEN が .env にありません")
    os.environ["REPLICATE_API_TOKEN"] = api_token

    output = replicate.run(
        DEFAULT_FLUX_MODEL,
        input={
            "prompt": prompt,
            "aspect_ratio": "16:9",
            "output_format": "jpg",
            "output_quality": 90,
            "safety_tolerance": 2,
        },
    )

    if hasattr(output, "read"):
        output_path.write_bytes(output.read())
    else:
        url = str(output)
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        output_path.write_bytes(response.content)


def render_thumbnail(
    background_path: Path,
    title: str,
    output_path: Path,
    *,
    category: str = "民泊運営",
    brand: str = DEFAULT_BRAND,
) -> None:
    """HTML テンプレ + Edge headless で 1200x630 PNG をレンダリング。

    Edge headless の `--window-size` は内部 chrome 領域分が差し引かれて
    実ビューポートが小さくなる。少し大きめ (1200x720) でレンダリングして、
    PIL で 1200x630 にクロップして対応する。
    """
    template_path = TEMPLATES_DIR / "thumbnail.html.tpl"
    if not template_path.exists():
        raise ThumbnailError(f"テンプレートが見つかりません: {template_path}")
    template = template_path.read_text(encoding="utf-8")

    image_uri = background_path.resolve().as_uri()
    size_class = _title_size_class(title)
    title_html = _smart_title_break(title, size_class)
    html = template.format(
        image_path=image_uri,
        title=title_html,
        category=category,
        brand=brand,
        title_size_class=size_class,
    )
    html_path = output_path.with_suffix(".html")
    html_path.write_text(html, encoding="utf-8")

    # 一旦大きめのサイズでスクショ → 1200x630 へクロップ
    raw_path = output_path.with_name(output_path.stem + ".raw.png")
    edge = _find_edge()
    cmd = [
        str(edge),
        "--headless=new",
        "--disable-gpu",
        "--force-device-scale-factor=1",
        f"--screenshot={raw_path}",
        "--window-size=1200,720",
        "--hide-scrollbars",
        html_path.resolve().as_uri(),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise ThumbnailError(
            f"Edge スクリーンショット失敗（exit {result.returncode}）: "
            f"{result.stderr[:300]}"
        )
    if not raw_path.exists():
        raise ThumbnailError("PNG ファイルが生成されませんでした")

    # PIL で 1200x630 にクロップ
    try:
        from PIL import Image  # noqa: PLC0415
    except ImportError as exc:
        raise ThumbnailError(
            "Pillow が必要です: pip install pillow"
        ) from exc

    with Image.open(raw_path) as img:
        cropped = img.crop((0, 0, 1200, 630))
        cropped.save(output_path)

    # 中間ファイルを掃除
    if html_path.exists():
        html_path.unlink()
    if raw_path.exists():
        raw_path.unlink()


def make_thumbnail(
    keyword: str,
    title: str,
    article_md: str,
    *,
    base_name: str,
    category: str = "民泊運営",
    brand: str = DEFAULT_BRAND,
) -> dict:
    """サムネイル生成のフルフロー。

    返り値: {"png_path": Path, "background_path": Path, "image_prompt": str}
    """
    OUTPUTS_DIR.mkdir(exist_ok=True)

    image_prompt = generate_image_prompt(keyword, title, article_md)

    bg_path = OUTPUTS_DIR / f"{base_name}.thumbnail-bg.jpg"
    generate_background_image(image_prompt, bg_path)

    png_path = OUTPUTS_DIR / f"{base_name}.thumbnail.png"
    render_thumbnail(bg_path, title, png_path, category=category, brand=brand)

    return {
        "png_path": png_path,
        "background_path": bg_path,
        "image_prompt": image_prompt,
    }
