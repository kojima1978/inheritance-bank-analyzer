import pandas as pd
import polars as pl
from typing import Optional

def load_csv(file) -> pd.DataFrame:
    """
    OCR済みCSVを読み込み、標準フォーマットに変換する
    想定CSVカラム: 銀行名,年月日,摘要,払戻,お預り,差引残高
    または: 銀行名,支店名,口座番号,年月日,摘要,払戻,お預り,差引残高
    """
    # Polarsで高速読み込み
    try:
        df_pl = pl.read_csv(file, encoding="utf-8-sig") # 典型的なShift-JIS/UTF-8 with BOM対策
        df = df_pl.to_pandas()
    except Exception:
         # Polarsで読めない場合のフォールバック
        df = pd.read_csv(file)

    # 元のカラム名を保存（エラーメッセージ用）
    original_columns = list(df.columns)

    # カラム名マッピング（表記揺れ吸収）
    rename_map = {
        "年月日": "date",
        "日付": "date",  # 追加
        "摘要": "description",
        "払戻": "amount_out",
        "払戻額": "amount_out",  # 追加
        "お預り": "amount_in",
        "お預り額": "amount_in",  # 追加
        "差引残高": "balance",
        "支店名": "branch_name",
        "口座番号": "account_number"
    }

    # 必要なカラムがあるかチェック
    # 簡易実装：部分一致でも許容するか、厳密にするか
    # ここでは厳密にチェックし、なければエラーとするか、柔軟に対応するか
    # 仕様書通り「銀行名,年月日,摘要,払戻,お預り,差引残高」前提

    df = df.rename(columns=rename_map)

    # 必須カラムのチェック
    required_columns = ["date", "description", "amount_out", "amount_in", "balance"]
    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        # エラーメッセージで実際のカラム名を表示
        raise ValueError(
            f"CSVに必要なカラムがありません。\n"
            f"不足: {missing_columns}\n"
            f"CSVのカラム（元データ）: {original_columns}\n"
            f"想定フォーマット: 銀行名,年月日,摘要,払戻,お預り,差引残高"
        )

    # CSVに銀行名がある場合は保持（後でaccount_id生成に使用）
    # CSVから読み取った銀行名等の情報を別カラムに保存
    csv_metadata = {}
    if "銀行名" in df.columns:
        csv_metadata["bank_name"] = str(df["銀行名"].iloc[0]) if len(df) > 0 else ""
    if "branch_name" in df.columns:
        csv_metadata["branch_name"] = str(df["branch_name"].iloc[0]) if len(df) > 0 else ""
    if "account_number" in df.columns:
        # 口座番号は数値型の可能性があるので文字列に変換
        csv_metadata["account_number"] = str(df["account_number"].iloc[0]) if len(df) > 0 else ""
    if "種別" in df.columns:
        # 口座種別（普通、当座など）
        csv_metadata["account_type"] = str(df["種別"].iloc[0]) if len(df) > 0 else ""

    # 和暦を西暦に変換する関数
    def convert_japanese_date(date_str):
        """和暦（H28.6.3など）を西暦に変換"""
        if pd.isna(date_str):
            return None

        date_str = str(date_str).strip()

        # 和暦のパターン
        era_map = {
            'M': 1868,  # 明治
            'T': 1912,  # 大正
            'S': 1926,  # 昭和
            'H': 1989,  # 平成
            'R': 2019   # 令和
        }

        # H28.6.3 や H28/6/3 形式
        import re
        match = re.match(r'([MTSHR])(\d+)[./](\d+)[./](\d+)', date_str)
        if match:
            era, year, month, day = match.groups()
            if era in era_map:
                year_ad = era_map[era] + int(year) - 1
                return f"{year_ad}-{int(month):02d}-{int(day):02d}"

        return date_str

    # データ型変換（変換前のデータを保存）
    date_before_conversion = df["date"].copy()

    # まず和暦変換を試みる
    df["date"] = df["date"].apply(convert_japanese_date)

    # その後、通常の日付変換
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # 日付変換失敗のチェック
    if df["date"].isna().any():
        # 変換前のデータを表示
        invalid_mask = df["date"].isna()
        invalid_dates_original = date_before_conversion[invalid_mask].head(5).tolist()
        raise ValueError(
            f"日付の変換に失敗しました。\n"
            f"変換できない日付の例（元データ）: {invalid_dates_original}\n"
            f"日付形式を確認してください（例: 2024-01-01, 2024/01/01, H28.6.3）"
        )

    for col in ["amount_out", "amount_in", "balance"]:
        if col in df.columns:
            # カンマ入り文字列除去など
            if df[col].dtype == object:
                df[col] = df[col].astype(str).str.replace(",", "").astype(float).fillna(0).astype(int)
            else:
                df[col] = df[col].fillna(0).astype(int)

    # 不要なカラムを削除（銀行名等はメタデータとして取得済み）
    # 必須カラム以外をすべて削除
    required_keep = ["date", "description", "amount_out", "amount_in", "balance"]
    cols_to_drop = [col for col in df.columns if col not in required_keep]
    df = df.drop(columns=cols_to_drop)

    # メタデータを返す方法がないので、DataFrameに一時的に保存
    # 呼び出し側でこの情報を使用できるようにする
    if csv_metadata:
        df.attrs["csv_metadata"] = csv_metadata

    return df

def validate_balance(df: pd.DataFrame) -> pd.DataFrame:
    """
    残高不整合チェック
    前行残高 + 入金 - 出金 = 今回残高
    不一致行にフラグを立てる等の処理（今回は検証結果として返すのみ）
    """
    # CSVの元の行順序を保存（同じ日付の取引の順序を保持するため）
    df = df.reset_index(drop=True)
    df["_original_order"] = df.index

    # 日付昇順、元の行順でソート（同じ日付の場合は元の順序を維持）
    df = df.sort_values(["date", "_original_order"]).reset_index(drop=True)
    
    check_results = []
    prev_balance = None
    
    # 計算列追加（検証用）
    df["calc_balance"] = 0
    df["is_balance_error"] = False

    # 最初の行はチェックできない（基準とする）
    if len(df) > 0:
        prev_balance = df.iloc[0]["balance"]
        df.at[0, "calc_balance"] = prev_balance

        for i in range(1, len(df)):
            current = df.iloc[i]
            expected = prev_balance + current["amount_in"] - current["amount_out"]
            
            df.at[i, "calc_balance"] = expected
            
            if expected != current["balance"]:
                df.at[i, "is_balance_error"] = True
                # エラーがあっても、CSVの残高を正として次へ進むか、計算値を正とするか
                # 通常はCSVが正。通帳の印字ミスは稀だがOCRミスはありうる。
                # ここではCSVの残高を次のprev_balanceにする（OCRの値を信じる）
                prev_balance = current["balance"]
            else:
                prev_balance = expected

    # 一時的に追加したカラムを削除
    if "_original_order" in df.columns:
        df = df.drop(columns=["_original_order"])

    return df
