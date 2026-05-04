import json
import sys

from dotenv import load_dotenv

from steps.dify import generate_article

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()


def main() -> None:
    keyword = "民泊 大阪 おすすめ"
    print(f"キーワード: {keyword}")
    print("Dify に記事生成をリクエスト中...")

    result = generate_article(keyword)

    print("--- Dify レスポンス（生データ） ---")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
