import os

import markdown as md_lib
import requests


class WordPressError(RuntimeError):
    pass


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


def create_draft_post(
    *,
    title: str,
    body_markdown: str,
    timeout_seconds: int = 60,
) -> dict:
    """WordPress に下書きとして投稿する。

    返り値: {"post_id": int, "link": str, "edit_link": str}
    """
    site_url = os.environ["WP_SITE_URL"].rstrip("/")
    username = os.environ["WP_USERNAME"]
    app_password = os.environ["WP_APP_PASSWORD"].replace(" ", "")

    body_html = md_lib.markdown(
        body_markdown,
        extensions=["tables", "fenced_code", "sane_lists"],
    )

    response = requests.post(
        f"{site_url}/wp-json/wp/v2/posts",
        auth=(username, app_password),
        json={
            "title": title,
            "content": body_html,
            "status": "draft",
        },
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
