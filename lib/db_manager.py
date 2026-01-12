import sqlite3
import pandas as pd
import os
from . import config

def get_case_db_path(case_name: str) -> str:
    case_dir = os.path.join(config.DATA_DIR, case_name)
    os.makedirs(case_dir, exist_ok=True)
    return os.path.join(case_dir, "transactions.db")

def init_db(case_name: str):
    db_path = get_case_db_path(case_name)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        description TEXT,
        amount_out INTEGER DEFAULT 0,
        amount_in INTEGER DEFAULT 0,
        balance INTEGER,
        account_id TEXT,
        holder TEXT,
        is_large BOOLEAN DEFAULT 0,
        is_transfer BOOLEAN DEFAULT 0,
        transfer_to TEXT,
        category TEXT
    )
    """)
    
    # migration: categoryカラムがない場合は追加
    try:
        cursor.execute("SELECT category FROM transactions LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE transactions ADD COLUMN category TEXT")
        
    conn.commit()
    conn.close()

def save_transactions(case_name: str, df: pd.DataFrame):
    db_path = get_case_db_path(case_name)
    conn = sqlite3.connect(db_path)
    conn.text_factory = str  # UTF-8対応

    # 既存データを削除して洗い替え（シンプル運用のため）
    # 本番運用では追記ロジックなどを検討
    cursor = conn.cursor()
    
    # migration: categoryカラムがない場合は追加（保存前チェック）
    try:
        cursor.execute("SELECT category FROM transactions LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE transactions ADD COLUMN category TEXT")

    cursor.execute("DELETE FROM transactions") # 全件削除

    df.to_sql("transactions", conn, if_exists="append", index=False)
    conn.commit()
    conn.close()

def load_transactions(case_name: str) -> pd.DataFrame:
    db_path = get_case_db_path(case_name)
    if not os.path.exists(db_path):
        return pd.DataFrame()

    conn = sqlite3.connect(db_path)
    conn.text_factory = str  # UTF-8対応
    df = pd.read_sql("SELECT * FROM transactions", conn)
    conn.close()

    # 日付カラムをdatetime型に変換
    if 'date' in df.columns and len(df) > 0:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')

    return df

def get_all_cases() -> list[str]:
    if not os.path.exists(config.DATA_DIR):
        return []
    return [d for d in os.listdir(config.DATA_DIR) if os.path.isdir(os.path.join(config.DATA_DIR, d))]

def delete_case(case_name: str) -> bool:
    """案件全体を削除する（フォルダごと削除）"""
    import shutil
    case_dir = os.path.join(config.DATA_DIR, case_name)
    if os.path.exists(case_dir):
        try:
            shutil.rmtree(case_dir)
            return True
        except Exception as e:
            print(f"案件削除エラー: {e}")
            return False
    return False

def delete_account_transactions(case_name: str, account_id: str) -> bool:
    """特定の口座の取引データを削除する"""
    db_path = get_case_db_path(case_name)
    if not os.path.exists(db_path):
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM transactions WHERE account_id = ?", (account_id,))
        conn.commit()
        deleted_count = cursor.rowcount
        conn.close()
        return deleted_count > 0
    except Exception as e:
        print(f"口座削除エラー: {e}")
        return False
