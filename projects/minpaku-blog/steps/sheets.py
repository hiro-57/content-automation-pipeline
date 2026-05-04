from datetime import datetime
from pathlib import Path

import gspread

CREDENTIALS_PATH = Path(__file__).resolve().parent.parent / "google-credentials.json"
PROCESSED_STATUS = "処理済"


class SheetSchemaError(RuntimeError):
    pass


def _open_worksheet(spreadsheet_id: str, sheet_name: str | None = None):
    gc = gspread.service_account(filename=str(CREDENTIALS_PATH))
    spreadsheet = gc.open_by_key(spreadsheet_id)
    return spreadsheet.worksheet(sheet_name) if sheet_name else spreadsheet.sheet1


def _column_index(headers: list[str], name: str) -> int:
    try:
        return headers.index(name) + 1
    except ValueError as exc:
        raise SheetSchemaError(
            f"列 '{name}' がヘッダー行に見つかりません。実際のヘッダー: {headers}"
        ) from exc


def get_unprocessed_keyword(
    spreadsheet_id: str, sheet_name: str | None = None
) -> dict | None:
    """未処理（status が '処理済' 以外）の最初のキーワード行を返す。

    返り値: {"row_number": int (1-indexed), "keyword": str} または None。
    """
    ws = _open_worksheet(spreadsheet_id, sheet_name)
    rows = ws.get_all_values()
    if len(rows) < 2:
        return None

    headers = rows[0]
    keyword_col = _column_index(headers, "keyword")
    status_col = _column_index(headers, "status")

    for row_index, row in enumerate(rows[1:], start=2):
        padded = row + [""] * (len(headers) - len(row))
        keyword = padded[keyword_col - 1].strip()
        status = padded[status_col - 1].strip()
        if not keyword:
            continue
        if status == PROCESSED_STATUS:
            continue
        return {"row_number": row_index, "keyword": keyword}

    return None


def mark_processed(
    spreadsheet_id: str,
    row_number: int,
    *,
    article_url: str | None = None,
    sheet_name: str | None = None,
) -> None:
    """指定行の status を '処理済' に更新する。

    article_url 列・published_at 列が存在すれば併せて埋める（無くても無視）。
    """
    ws = _open_worksheet(spreadsheet_id, sheet_name)
    headers = ws.row_values(1)

    ws.update_cell(row_number, _column_index(headers, "status"), PROCESSED_STATUS)

    if article_url is not None and "article_url" in headers:
        ws.update_cell(row_number, _column_index(headers, "article_url"), article_url)

    if "published_at" in headers:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ws.update_cell(row_number, _column_index(headers, "published_at"), now)
