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
    raise ThumbnailError("Microsoft Edge が見つかりません")


def _title_size_class(title: str) -> str:
    """タイトルの文字数で CSS クラスを決定（自動的にフォントサイズ調整）。

    切れないギリギリの 1200x630 内 2 行収まり目安:
      - 〜24 文字  → デフォルト 50px
      - 25〜32 文字 → long 38px
      - 33 文字〜  → very-long 30px
    """
    if len(title) > 32:
        return "very-long"
    if len(title) > 24:
        return "long"
    return ""


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
    html = template.format(
        image_path=image_uri,
        title=title,
        category=category,
        brand=brand,
        title_size_class=_title_size_class(title),
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
