import os

import requests


class DifyError(RuntimeError):
    pass


def generate_article(keyword: str, *, timeout_seconds: int = 180) -> dict:
    """Dify Workflow を呼んで記事を生成する。

    返り値の dict には以下が入る:
      - text:           生成された記事本文（Markdown）
      - elapsed_seconds: 実行時間（秒）
      - tokens:         消費トークン数
      - steps:          実行ステップ数
    """
    api_key = os.environ["DIFY_API_KEY"]
    base_url = os.environ.get("DIFY_API_BASE_URL", "https://api.dify.ai/v1")

    response = requests.post(
        f"{base_url}/workflows/run",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "inputs": {"keyword": keyword},
            "response_mode": "blocking",
            "user": "minpaku-blog-pipeline",
        },
        timeout=timeout_seconds,
    )
    if not response.ok:
        raise DifyError(f"Dify API {response.status_code}: {response.text}")

    payload = response.json()
    data = payload.get("data", {})
    status = data.get("status")
    if status != "succeeded":
        raise DifyError(f"Dify workflow status={status}, error={data.get('error')}")

    text = data.get("outputs", {}).get("text", "")
    if not text:
        raise DifyError("Dify response did not contain outputs.text")

    return {
        "text": text,
        "elapsed_seconds": data.get("elapsed_time"),
        "tokens": data.get("total_tokens"),
        "steps": data.get("total_steps"),
    }
