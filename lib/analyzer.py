import pandas as pd
from . import config

def analyze_large_amounts(df: pd.DataFrame) -> pd.DataFrame:
    """
    多額出金・入金のフラグ付け
    """
    df["is_large"] = (df["amount_out"] >= config.LARGE_AMOUNT_THRESHOLD) | \
                     (df["amount_in"] >= config.LARGE_AMOUNT_THRESHOLD)
    return df

def analyze_transfers(df: pd.DataFrame) -> pd.DataFrame:
    """
    資金移動の自動ペアリング
    口座跨ぎの移動を検知したいが、現状のSQLite構造だと全データをメモリに載せて比較する必要がある。
    案件単位の全取引dfが渡される前提。
    """
    # 日付型に変換（DBから読み込むと文字列の可能性）
    df["date"] = pd.to_datetime(df["date"])

    # 日付でソート
    df = df.sort_values("date").reset_index(drop=True)
    
    df["is_transfer"] = False
    df["transfer_to"] = None
    
    # 出金データと入金データを分離
    out_df = df[df["amount_out"] > 0].copy()
    in_df = df[df["amount_in"] > 0].copy()
    
    # シンプルな総当たりに近いマッチング（データ量少ない前提）
    # 出金レコード毎に、近接日付の入金を探索
    for idx_out, row_out in out_df.iterrows():
        target_amount = row_out["amount_out"]
        target_date = row_out["date"]
        source_account = row_out["account_id"]
        
        # 候補検索: 口座が異なり、金額が近似、日付が近い
        candidates = in_df[
            (in_df["account_id"] != source_account) &
            (in_df["amount_in"] >= target_amount - config.TRANSFER_AMOUNT_TOLERANCE) &
            (in_df["amount_in"] <= target_amount + config.TRANSFER_AMOUNT_TOLERANCE) &
            ((in_df["date"] - target_date).abs().dt.days <= config.TRANSFER_DAYS_WINDOW)
        ]
        
        if not candidates.empty:
            # マッチした相手（最初の1件だけ採用する簡易ロジック）
            match = candidates.iloc[0]
            
            # フラグ更新
            # 元のdfのインデックスを参照するために、indexを保持しておく必要があるが
            # ここでは簡易的に処理。実際はGlobal ID的キーがあると良い。
            # pandasのindexが生きていればそれを使う
            
            df.at[idx_out, "is_transfer"] = True
            df.at[idx_out, "transfer_to"] = f"{match['account_id']} ({match['date'].date()})"
            
            # 相手方も更新（重複マッチのリスクはあるが許容）
            df.at[match.name, "is_transfer"] = True
            df.at[match.name, "transfer_to"] = f"{source_account} ({target_date.date()})"
            
    return df
