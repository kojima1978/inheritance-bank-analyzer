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

    # カラム名マッピング（表記揺れ吸収は今後拡張）
    rename_map = {
        "年月日": "date",
        "摘要": "description",
        "払戻": "amount_out",
        "お預り": "amount_in",
        "差引残高": "balance",
        "支店名": "branch_name",
        "口座番号": "account_number"
    }

    # 必要なカラムがあるかチェック
    # 簡易実装：部分一致でも許容するか、厳密にするか
    # ここでは厳密にチェックし、なければエラーとするか、柔軟に対応するか
    # 仕様書通り「銀行名,年月日,摘要,払戻,お預り,差引残高」前提

    df = df.rename(columns=rename_map)

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

    # データ型変換
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    
    for col in ["amount_out", "amount_in", "balance"]:
        if col in df.columns:
            # カンマ入り文字列除去など
            if df[col].dtype == object:
                df[col] = df[col].astype(str).str.replace(",", "").astype(float).fillna(0).astype(int)
            else:
                df[col] = df[col].fillna(0).astype(int)

    # 不要なカラムを削除（銀行名等はメタデータとして取得済み）
    cols_to_drop = ["銀行名", "branch_name", "account_number"]
    df = df.drop(columns=[col for col in cols_to_drop if col in df.columns])

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
    # 日付昇順ソート
    df = df.sort_values("date").reset_index(drop=True)
    
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
                
    return df
