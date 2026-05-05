---
name: codex-monthly-audit
description: minpaku-blog パイプライン全体を OpenAI Codex CLI で監査し、評価レポートを `projects/minpaku-blog/audits/YYYY-MM.md` に保存するスキル。担当者が「月次監査」「Codex 監査」「コード健康診断」「プロジェクト全体レビュー」「定期監査」「audit」と発言した時、または「全体を別の AI でも見てほしい」「セカンドオピニオン欲しい」「コードに見落としないか確認したい」と言った時に**積極的に発動**する。Codex は Claude が書いたコードに対して GPT 視点で忌憚ない指摘を出すので、Claude 単独では見落としがちな盲点を炙り出せる。月 1 回程度の定例監査として運用することで、コード品質・運用リスク・ KB 充実度・目標達成度のドリフトを早期発見する。Make sure to use this skill whenever the user wants a comprehensive review of the pipeline by Codex — even if they don't say "monthly" explicitly. Treat single-file reviews and ad-hoc code questions as out-of-scope (those use other tools).
---

# Codex 月次監査スキル

`projects/minpaku-blog` パイプライン全体を OpenAI Codex CLI で監査し、構造化されたレポートを保存する。

## なぜこのスキルがあるか

Claude Code（私）が書いたコードに対して、私自身が客観的に評価するのは難しい。**自己採点バイアス**が必ず入る。Codex（GPT 系）は別ベンダーの別モデルなので:

- 私が見落とす盲点（同じ訓練分布の弱点）を拾える
- アーキテクチャ判断への第三者視点が得られる
- KB 充実度・目標達成度のドリフトを定量的に追える

このスキルは、**Codex CLI を月 1 回呼び出して構造化監査を実行 → 履歴として蓄積**する仕組みを実装する。

## 前提条件

- Codex CLI が PC にインストール済み（`codex --version` で確認可能）
- Codex CLI が `codex login` 済み（ChatGPT 認証 or OpenAI API）
- Windows + PowerShell 環境（Edge ヘッドレスは別件で使用、Codex は PS 経由で起動）

これらが満たされていない場合は、担当者にセットアップを促してから中断する。

## 発動時の進行

### Step 1 — 環境確認 + 月次ディレクトリ準備

1. `codex --version` で Codex CLI 利用可能か確認。エラーならユーザーに `npm install -g @openai/codex` を促して終了。
2. 当月の年月（YYYY-MM 形式）を `date` 関連コマンドで取得。
3. `projects/minpaku-blog/audits/` ディレクトリを `mkdir -p` で確保。
4. 当月分のファイル `audits/{YYYY-MM}.md` が既に存在するか確認:
   - 存在 → ユーザーに「今月分の監査は既に実行済みです（{path}）。再実行しますか？」と確認
   - 存在しない → そのまま進行

### Step 2 — 過去監査の収集（前月差分用）

`projects/minpaku-blog/audits/` 内の既存 `.md` ファイルを最新 3 件まで取得。Codex への指示で「過去レポートと比較し、改善が反映されているか」を判定させる。

### Step 3 — 監査プロンプト生成

英語のプロンプトを `projects/minpaku-blog/outputs/_audit_prompt_{YYYY-MM}.txt` に書き出す（debug 用の一時ファイルなので outputs/ で OK・gitignore 対象）。日本語プロンプトは PowerShell 経由で文字化けするので**必ず英語**にする（教訓）。

プロンプトテンプレート:

```
You are auditing the minpaku-blog pipeline at projects/minpaku-blog/. Read the codebase and assess current state.

This is the {Nth} monthly audit. Previous reports (most recent first):
{list of past audit files with paths, or "first audit" if none}

## Files to review

- main.py, replenish_keywords.py, extract_kb.py, make_pdf.py
- steps/*.py (all)
- prompts/*.md
- knowledge/*.md (especially personal_experiences.md and industry_facts.md — check fill rate)
- templates/thumbnail.html.tpl
- 手順書.md

## Evaluation axes (5 each: 良い点 / 懸念点 / 改善提案)

1. Technology choices — Anthropic Claude API, Replicate Flux, Edge headless, gspread, WordPress REST API
2. Architecture — module boundaries, error handling, idempotency, retry, logging, observability, scaling
3. Code quality — readability, maintainability, separation of concerns, type annotations, tests
4. Overlooked risks — credentials, failure modes, ToS compliance, scaling bottlenecks, gitignore coverage
5. Goal fit — KB fill rate, "human-surpassing" quality lever, evaluation gate effectiveness, prompt iteration evidence

## Compare with previous audits (if any)

For each axis, note whether the previously flagged issues have been addressed. Flag regressions. Identify new issues that didn't exist before.

## Output format

Markdown in Japanese. Use ## headers for each axis. Each item should cite file:line where relevant. End with:
- Overall score out of 10 (decimal allowed, e.g., 6.7)
- The single most decisive improvement to make in the next month
- A delta summary vs the previous audit (if any): what improved, what regressed, what's new

Be honest, blunt, and specific. Vague praise is useless.
```

`{Nth}` と `{list of past audit files...}` は Step 2 の結果で埋める。

### Step 4 — Codex 実行（バックグラウンド）

PowerShell から以下のパターンで実行（過去のセッションで判明した正解の組合せ）:

```powershell
$env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","User") + ";" + [System.Environment]::GetEnvironmentVariable("PATH","Machine")
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
cd "C:\Users\hongj\OneDrive\ドキュメント\content-automation-pipeline\projects\minpaku-blog"
Get-Content -Raw -Encoding UTF8 outputs\_audit_prompt_{YYYY-MM}.txt | codex exec --sandbox read-only --color never --skip-git-repo-check 2>&1 | Out-File -FilePath outputs\_audit_raw_{YYYY-MM}.txt -Encoding utf8
```

重要ポイント:
- `--sandbox read-only`: 監査は読み取りのみ
- `--color never`: ANSI エスケープ混入回避
- `--skip-git-repo-check`: 親ディレクトリの git で動作
- `Get-Content -Raw -Encoding UTF8`: stdin 経由でプロンプトを Codex に渡す（複数行プロンプト引数渡しは PowerShell から動かない）
- `2>&1 | Out-File ... -Encoding utf8`: 出力を UTF-8 で保存
- run_in_background: true（5 分前後かかる）

実行後、ユーザーに「Codex 監査を開始しました（5 分前後）」と伝え、完了通知を待つ。

### Step 5 — 完了後、レポート整形

Codex の生出力（`_audit_raw_{YYYY-MM}.txt`）には:
- exec ログ（ファイル読み込み履歴）
- 最後に整形された Markdown 監査レポート

が混在する。レポート部分のみを抽出して `{YYYY-MM}.md` に保存する。

抽出ルール:
1. ファイル全体を読む
2. 最初に出現する `## ` または `# ` から、`tokens used` または ファイル末尾までを抽出
3. 抽出した内容を `audits/{YYYY-MM}.md` に保存
4. 元の生ファイル（`_audit_raw_*.txt`、`_audit_prompt_*.txt`）は debug 用に残す（次回上書きされる）

### Step 6 — サマリ提示 + 改善提案の確認

ユーザーに以下を提示:

1. レポートの保存先パス
2. 抽出した「総合評価スコア」と「決定的改善 1 つ」
3. 過去監査がある場合、デルタサマリ（改善された項目 / 退行した項目）

その後、以下を確認:

> 改善提案のうち、**今月対応するもの**を選んでください。
>
> - (a) 決定的改善 1 つだけ実装
> - (b) 改善提案 TOP 3 を選んで実装
> - (c) 全部見て自分で選ぶ（レポートを開いて確認）
> - (d) 今月は読むだけで実装は来月以降

(a)(b) を選ばれたら、私（Claude Code）が実装する。Codex に再委譲する場合は別途 codex-implement 系スキル（未実装）を使うが、現状は Claude 実装を優先（複数ファイル変更は私の領域）。

## 重要な姿勢

1. **5 分待ってから処理を始めない**: バックグラウンド実行を必ず使う。同期実行で待つと体感が悪い。
2. **過去監査と比較する**: 単発の監査より、トレンドの方が価値がある。「KB 充実度が前月から改善したか」「指摘した冪等性問題は実装されたか」を必ず照合する。
3. **Codex の指摘を鵜呑みにしない**: Codex も間違える（前回も "5 件 vs 6 件" の誤読があった）。実装前にユーザー判断を仰ぐ。
4. **コスト**: ChatGPT Plus 認証なら追加課金 0。OpenAI API キー認証なら 1 回 $0.10〜0.30 程度。
5. **失敗時のリカバリ**: Codex がハング・エラー終了した場合、`tasks/{task-id}.output` を確認し、エンコーディング・サンドボックス・プロンプト引数のいずれかが原因か診断する。

## トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| Codex が `Reading additional input from stdin...` で固まる | プロンプトが引数として渡らず stdin 待ち | `Get-Content -Raw \| codex exec` の stdin パイプ方式に統一 |
| 出力が `?????` だらけ（文字化け） | プロンプトが日本語で PS が UTF-8 → cp932 で破損 | プロンプトを必ず英語で書く（出力指示で「Japanese で出力」と明示） |
| Codex が「workspace-write なのに read-only として動作」と言う | `codex exec` の非対話モードでは write 系操作が approval 不可で fallback | 監査は read-only で良いので問題なし。実装作業は手動で diff 適用 |
| `codex --version` がエラー | Codex CLI 未インストール or PATH 未通過 | `npm install -g @openai/codex`、その後新しい PowerShell を起動 |

## 出力例

`audits/2026-05.md` の典型的構造:

```markdown
## 1. 技術選定
### 良い点
- ...（file:line 引用つき）
### 懸念点
- ...
### 改善提案
- ...

## 2. アーキテクチャ
... (同上)

## 3. コード品質
...

## 4. 見落としリスク
...

## 5. 目標適合
...

## デルタサマリ（前月比）
- 改善された項目: ...
- 退行した項目: ...
- 新規発見: ...

**総合評価: 7.2 / 10**

最初にやるべき決定的改善: ...
```
