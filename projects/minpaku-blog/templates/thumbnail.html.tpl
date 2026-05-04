<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>thumbnail</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@700;900&display=swap');

* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

html, body {{
    width: 1200px;
    height: 630px;
    font-family: 'Noto Sans JP', 'Yu Gothic', 'Meiryo', sans-serif;
    overflow: hidden;
    background: #1a1a1a;
}}

.thumbnail {{
    width: 1200px;
    height: 630px;
    position: relative;
    background-image: url('{image_path}');
    background-size: cover;
    background-position: center;
}}

/* ビネット: 四隅を軽く暗くして写真として締まる */
.vignette {{
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: radial-gradient(
        ellipse at center,
        transparent 50%,
        rgba(0, 0, 0, 0.35) 100%
    );
    pointer-events: none;
}}

/* メインの暗いグラデーション: 下半分以降を強めに暗くしてタイトルを際立たせる */
.gradient {{
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 80%;
    background: linear-gradient(
        to bottom,
        rgba(0, 0, 0, 0) 0%,
        rgba(0, 0, 0, 0.25) 30%,
        rgba(0, 0, 0, 0.7) 65%,
        rgba(0, 0, 0, 0.95) 100%
    );
}}

/* 底部のカラーアクセントライン（ブランドカラーで締める） */
.bottom-accent {{
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 6px;
    background: linear-gradient(
        to right,
        #d97706 0%,
        #f59e0b 50%,
        #d97706 100%
    );
}}

.category {{
    position: absolute;
    top: 36px;
    left: 44px;
    background: #d97706;
    color: white;
    padding: 10px 24px 10px 22px;
    border-radius: 4px;
    font-size: 20px;
    font-weight: 700;
    letter-spacing: 0.12em;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.4);
    /* 左に小さい白いアイコン風の三角バー */
    border-left: 4px solid rgba(255, 255, 255, 0.9);
}}

.brand {{
    position: absolute;
    top: 40px;
    right: 44px;
    color: rgba(255, 255, 255, 0.9);
    font-size: 16px;
    font-weight: 700;
    letter-spacing: 0.2em;
    text-shadow: 1px 1px 8px rgba(0, 0, 0, 0.7);
}}

/* タイトル左の縦の太い装飾ライン（雑誌風） */
.title-block {{
    position: absolute;
    bottom: 80px;
    left: 64px;
    right: 50px;
    color: white;
    padding-left: 28px;
    border-left: 5px solid #d97706;
}}

.title {{
    font-size: 54px;
    line-height: 1.3;
    font-weight: 900;
    text-shadow: 2px 3px 16px rgba(0, 0, 0, 0.8);
    letter-spacing: 0.015em;
    margin: 0;
}}

.title.long {{
    font-size: 42px;
    line-height: 1.35;
}}

.title.very-long {{
    font-size: 36px;
    line-height: 1.4;
}}

/* タイトルブロック内の上部に小さなアクセント要素 */
.accent-bar {{
    display: none;  /* 縦の border-left に置き換えたため非表示 */
}}

/* タイトル上に小さな装飾テキスト（カテゴリ系の補足） */
.kicker {{
    color: #fbbf24;
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 0.25em;
    margin-bottom: 12px;
    text-shadow: 1px 1px 4px rgba(0, 0, 0, 0.6);
}}
</style>
</head>
<body>
<div class="thumbnail">
    <div class="gradient"></div>
    <div class="vignette"></div>
    <div class="category">{category}</div>
    <div class="brand">{brand}</div>
    <div class="title-block">
        <h1 class="title {title_size_class}">{title}</h1>
    </div>
    <div class="bottom-accent"></div>
</div>
</body>
</html>
