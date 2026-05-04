import os
import re
from pathlib import Path

import markdown as md_lib
import requests


class WordPressError(RuntimeError):
    pass


_CONTENT_TYPE_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def split_title_from_markdown(text: str) -> tuple[str | None, str]:
    """先頭の H1 行をタイトルとして抽出し、残りを本文として返す。

    H1 が無い場合は (None, text) を返す。
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            remaining = "\n".join(lines[i + 1 :]).strip()
            return title, remaining
        return None, text
    return None, text


def upload_media(
    image_path: Path,
    *,
    alt_text: str = "",
    timeout_seconds: int = 120,
) -> dict:
    """WordPress にメディア（画像）をアップロードする。

    返り値: {"media_id": int, "source_url": str}
    """
    site_url = os.environ["WP_SITE_URL"].rstrip("/")
    username = os.environ["WP_USERNAME"]
    app_password = os.environ["WP_APP_PASSWORD"].replace(" ", "")

    image_path = Path(image_path)
    if not image_path.exists():
        raise WordPressError(f"画像が見つかりません: {image_path}")

    suffix = image_path.suffix.lower()
    content_type = _CONTENT_TYPE_BY_SUFFIX.get(suffix)
    if not content_type:
        raise WordPressError(f"未対応のファイル形式: {suffix}")

    image_data = image_path.read_bytes()

    # HTTP ヘッダーは Latin-1 エンコーディング前提のため、
    # ファイル名から非 ASCII 文字を除去する（WP 側の slug 生成は別途行われる）
    ascii_stem = re.sub(r"[^\x00-\x7F]", "", image_path.stem).strip("_-. ")
    if not ascii_stem:
        ascii_stem = "image"
    ascii_filename = f"{ascii_stem}{image_path.suffix}"

    response = requests.post(
        f"{site_url}/wp-json/wp/v2/media",
        auth=(username, app_password),
        headers={
            "Content-Type": content_type,
            "Content-Disposition": f'attachment; filename="{ascii_filename}"',
        },
        data=image_data,
        timeout=timeout_seconds,
    )
    if not response.ok:
        raise WordPressError(
            f"WP media upload {response.status_code}: {response.text[:300]}"
        )
    data = response.json()
    media_id = data["id"]

    # alt text は別リクエストで PATCH（投稿時に同梱できないため）
    if alt_text:
        try:
            requests.post(
                f"{site_url}/wp-json/wp/v2/media/{media_id}",
                auth=(username, app_password),
                json={"alt_text": alt_text},
                timeout=30,
            )
        except Exception:
            # alt text 設定失敗してもメディアアップロード自体は成功なので許容
            pass

    return {
        "media_id": media_id,
        "source_url": data.get("source_url", ""),
    }


def create_draft_post(
    *,
    title: str,
    body_markdown: str,
    featured_media: int | None = None,
    timeout_seconds: int = 60,
) -> dict:
    """WordPress に下書きとして投稿する。

    Args:
        title: 記事タイトル
        body_markdown: 本文（Markdown）
        featured_media: アイキャッチ画像のメディア ID（任意）

    返り値: {"post_id": int, "link": str, "edit_link": str}
    """
    site_url = os.environ["WP_SITE_URL"].rstrip("/")
    username = os.environ["WP_USERNAME"]
    app_password = os.environ["WP_APP_PASSWORD"].replace(" ", "")

    body_html = md_lib.markdown(
        body_markdown,
        extensions=["tables", "fenced_code", "sane_lists"],
    )

    payload: dict = {
        "title": title,
        "content": body_html,
        "status": "draft",
    }
    if featured_media:
        payload["featured_media"] = int(featured_media)

    response = requests.post(
        f"{site_url}/wp-json/wp/v2/posts",
        auth=(username, app_password),
        json=payload,
        timeout=timeout_seconds,
    )
    if not response.ok:
        raise WordPressError(f"WP API {response.status_code}: {response.text}")

    data = response.json()
    return {
        "post_id": data["id"],
        "link": data["link"],
        "edit_link": f"{site_url}/wp-admin/post.php?post={data['id']}&action=edit",
    }
