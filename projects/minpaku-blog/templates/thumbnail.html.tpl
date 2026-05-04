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

.gradient {{
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 70%;
    background: linear-gradient(
        to bottom,
        rgba(0, 0, 0, 0) 0%,
        rgba(0, 0, 0, 0.55) 55%,
        rgba(0, 0, 0, 0.92) 100%
    );
}}

.category {{
    position: absolute;
    top: 36px;
    left: 44px;
    background: #d97706;
    color: white;
    padding: 9px 22px;
    border-radius: 4px;
    font-size: 20px;
    font-weight: 700;
    letter-spacing: 0.12em;
    box-shadow: 0 3px 10px rgba(0, 0, 0, 0.35);
}}

.brand {{
    position: absolute;
    top: 40px;
    right: 44px;
    color: rgba(255, 255, 255, 0.85);
    font-size: 16px;
    font-weight: 700;
    letter-spacing: 0.18em;
    text-shadow: 1px 1px 6px rgba(0, 0, 0, 0.6);
}}

.title-block {{
    position: absolute;
    bottom: 56px;
    left: 50px;
    right: 50px;
    color: white;
}}

.title {{
    font-size: 54px;
    line-height: 1.32;
    font-weight: 900;
    text-shadow: 2px 2px 14px rgba(0, 0, 0, 0.65);
    letter-spacing: 0.015em;
    margin: 0;
}}

.title.long {{
    font-size: 44px;
    line-height: 1.36;
}}

.title.very-long {{
    font-size: 38px;
    line-height: 1.4;
}}

.accent-bar {{
    width: 64px;
    height: 5px;
    background: #d97706;
    margin-bottom: 20px;
    border-radius: 2px;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
}}
</style>
</head>
<body>
<div class="thumbnail">
    <div class="gradient"></div>
    <div class="category">{category}</div>
    <div class="brand">{brand}</div>
    <div class="title-block">
        <div class="accent-bar"></div>
        <h1 class="title {title_size_class}">{title}</h1>
    </div>
</div>
</body>
</html>
