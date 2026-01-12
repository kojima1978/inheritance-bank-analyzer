import streamlit as st
import os
import json
from pathlib import Path

st.set_page_config(page_title="設定", page_icon="⚙️", layout="wide")

st.title("⚙️ 設定")

# 設定ファイルのパス
CONFIG_FILE = Path(__file__).parent.parent / "data" / "user_settings.json"

def load_settings():
    """設定ファイルから読み込み"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_settings(settings):
    """設定ファイルに保存"""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

# 現在の設定を読み込み
current_settings = load_settings()

st.markdown("---")

# 多額取引の設定
st.subheader("🔍 多額取引の検出設定")

col1, col2 = st.columns(2)

with col1:
    large_amount = st.number_input(
        "多額取引の閾値（円）",
        min_value=100_000,
        max_value=100_000_000,
        value=current_settings.get("LARGE_AMOUNT_THRESHOLD", 1_000_000),
        step=100_000,
        help="この金額以上の取引を「多額取引」として検出します"
    )

with col2:
    st.metric(
        label="現在の設定",
        value=f"{large_amount:,}円"
    )

st.markdown("---")

# 資金移動の検出設定
st.subheader("🔄 資金移動の検出設定")

col1, col2, col3 = st.columns(3)

with col1:
    transfer_days = st.number_input(
        "検出期間（日）",
        min_value=1,
        max_value=30,
        value=current_settings.get("TRANSFER_DAYS_WINDOW", 3),
        step=1,
        help="この期間内で出金と入金のペアを資金移動として検出します"
    )

with col2:
    transfer_tolerance = st.number_input(
        "金額の許容誤差（円）",
        min_value=0,
        max_value=10_000,
        value=current_settings.get("TRANSFER_AMOUNT_TOLERANCE", 500),
        step=100,
        help="出金額と入金額の差がこの範囲内であれば資金移動として判定します"
    )

with col3:
    st.info(f"**検出条件**\n\n{transfer_days}日以内に\n±{transfer_tolerance:,}円の範囲で\n出金・入金のペアを検出")

st.markdown("---")

# AI分類の設定
st.subheader("🤖 AI分類の設定")

col1, col2 = st.columns(2)

with col1:
    ollama_model = st.selectbox(
        "使用するモデル",
        options=["gemma2:2b", "llama3", "mistral", "gemma"],
        index=["gemma2:2b", "llama3", "mistral", "gemma"].index(
            current_settings.get("OLLAMA_MODEL", "llama3")
        ),
        help="AI分類に使用するOllamaモデルを選択"
    )

    st.caption("**推奨**: gemma2:2b（軽量・高速・CPU動作可能）")

with col2:
    ollama_url = st.text_input(
        "Ollama APIのURL",
        value=current_settings.get("OLLAMA_BASE_URL", "http://localhost:11434/api/generate"),
        help="OllamaのAPIエンドポイント（通常は変更不要）"
    )

st.markdown("---")

# 保存ボタン
col1, col2, col3 = st.columns([2, 1, 2])

with col2:
    if st.button("💾 設定を保存", type="primary", use_container_width=True):
        new_settings = {
            "LARGE_AMOUNT_THRESHOLD": large_amount,
            "TRANSFER_DAYS_WINDOW": transfer_days,
            "TRANSFER_AMOUNT_TOLERANCE": transfer_tolerance,
            "OLLAMA_MODEL": ollama_model,
            "OLLAMA_BASE_URL": ollama_url
        }

        save_settings(new_settings)

        # 環境変数にも設定（現在のセッションのみ有効）
        os.environ["LARGE_AMOUNT_THRESHOLD"] = str(large_amount)
        os.environ["TRANSFER_DAYS_WINDOW"] = str(transfer_days)
        os.environ["TRANSFER_AMOUNT_TOLERANCE"] = str(transfer_tolerance)
        os.environ["OLLAMA_MODEL"] = ollama_model
        os.environ["OLLAMA_BASE_URL"] = ollama_url

        st.success("✅ 設定を保存しました！変更を反映するにはアプリを再起動してください。")
        st.info("💡 再起動方法: ターミナルで `Ctrl+C` を押してアプリを停止し、再度 `streamlit run アプリ.py` を実行")

st.markdown("---")

# 現在の設定を表示
with st.expander("📋 現在の設定値を確認"):
    st.json({
        "多額取引の閾値": f"{large_amount:,}円",
        "資金移動検出期間": f"{transfer_days}日",
        "金額の許容誤差": f"{transfer_tolerance:,}円",
        "Ollamaモデル": ollama_model,
        "Ollama API URL": ollama_url
    })

# ヘルプセクション
st.markdown("---")
st.subheader("❓ 設定のヒント")

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    **多額取引の閾値**
    - 相続税調査では通常 100万円以上が注目される
    - 被相続人の資産規模に応じて調整可能
    - 小さくしすぎると検出数が多くなりすぎる
    """)

    st.markdown("""
    **資金移動の検出**
    - 一般的には 1〜3日以内の移動が多い
    - 許容誤差は振込手数料を考慮
    - 期間を長くしすぎると誤検出が増える
    """)

with col2:
    st.markdown("""
    **Ollamaモデルの選択**
    - **gemma2:2b**: 軽量、CPU動作、分類精度十分（推奨）
    - **llama3**: 高精度だが重い（GPU推奨）
    - **mistral**: バランス型
    - 初回実行時に自動ダウンロードされる
    """)
