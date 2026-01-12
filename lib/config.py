import os
import json
from pathlib import Path

# パス設定
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_FILE = Path(DATA_DIR) / "user_settings.json"

# 確保
os.makedirs(DATA_DIR, exist_ok=True)

# ユーザー設定ファイルから読み込み
def load_user_settings():
    """ユーザー設定ファイルから設定を読み込む"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

# 設定を読み込み
user_settings = load_user_settings()

# 閾値設定（優先順位: 環境変数 > ユーザー設定ファイル > デフォルト値）
LARGE_AMOUNT_THRESHOLD = int(os.getenv(
    "LARGE_AMOUNT_THRESHOLD",
    user_settings.get("LARGE_AMOUNT_THRESHOLD", 1_000_000)
))  # 円

TRANSFER_DAYS_WINDOW = int(os.getenv(
    "TRANSFER_DAYS_WINDOW",
    user_settings.get("TRANSFER_DAYS_WINDOW", 3)
))  # 日

TRANSFER_AMOUNT_TOLERANCE = int(os.getenv(
    "TRANSFER_AMOUNT_TOLERANCE",
    user_settings.get("TRANSFER_AMOUNT_TOLERANCE", 500)
))  # 円

# Ollama設定
OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    user_settings.get("OLLAMA_BASE_URL", "http://localhost:11434/api/generate")
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    user_settings.get("OLLAMA_MODEL", "llama3")
)
