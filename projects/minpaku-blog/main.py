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

    elapsed = result["elapsed_seconds"]
    tokens = result["tokens"]
    steps = result["steps"]
    print(f"✓ 完了（{elapsed:.1f}秒 / {tokens:,}トークン / {steps}ステップ）")
    print()
    print("────── 記事本文 ──────")
    print(result["text"])
    print("────── ここまで ──────")


if __name__ == "__main__":
    main()
