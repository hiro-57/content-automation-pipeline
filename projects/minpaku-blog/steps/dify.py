import os

import requests


class DifyError(RuntimeError):
    pass


def generate_article(keyword: str, *, timeout_seconds: int = 180) -> dict:
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
    return response.json()
