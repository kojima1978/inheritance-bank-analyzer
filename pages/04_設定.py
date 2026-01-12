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
        min_value=10_000,
        max_value=100_000_000,
        value=current_settings.get("LARGE_AMOUNT_THRESHOLD", 50_000),
        step=50_000,
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
        value=current_settings.get("TRANSFER_AMOUNT_TOLERANCE", 1_000),
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

# ルールベース分類のパターン設定
st.subheader("📝 ルールベース分類のパターン設定")

st.info("💡 キーワードを追加・編集して、自動分類の精度を向上させることができます")

# デフォルトのパターン
default_patterns = {
    "生活費": [
        "イオン", "セブン", "ローソン", "ファミマ", "スーパー", "マート",
        "電気", "ガス", "水道", "東京電力", "東電", "関西電力", "関電",
        "NTT", "ドコモ", "DOCOMO", "ソフトバンク", "au", "通信", "電話",
        "NHK", "薬局", "ドラッグ", "病院", "医院", "クリニック", "介護",
        "ガソリン", "ENEOS", "出光", "昭和シェル",
        "マクドナルド", "スターバックス", "スタバ", "コンビニ"
    ],
    "贈与": [
        "フリコミ", "振込", "送金"
    ],
    "関連会社": [
        "商事", "物産", "興業", "実業", "有限会社", "株式会社" 
    ],
    "銀行": [
        "定期預金", "定期", "積立"
    ],
    "証券会社": [
        "証券", "野村", "大和", "SMBC", "みずほ証券", "楽天証券", "SBI",
        "投資信託", "株式", "債券", "ファンド"
    ],
    "保険会社": [
        "生命保険", "損保", "保険", "共済", "かんぽ", "日本生命", "第一生命"
    ],
    "その他": [
        "手数料", "利息", "ATM", "時間外", "引出", "預入"
    ]
}

# 現在のパターンを読み込み（設定ファイルになければデフォルト）
current_patterns = current_settings.get("CLASSIFICATION_PATTERNS", default_patterns)

# タブでカテゴリーごとに編集（順序定義）
category_order = ["生活費", "贈与", "関連会社", "銀行", "証券会社", "保険会社", "その他"]
pattern_tabs = st.tabs(category_order)

edited_patterns = {}

with pattern_tabs[0]:
    st.markdown("**生活費のキーワード**")
    st.caption("スーパー、コンビニ、水道光熱費、通信費、医療費など")
    life_keywords = st.text_area(
        "キーワード（カンマ区切り）",
        value=", ".join(current_patterns.get("生活費", default_patterns["生活費"])),
        height=150,
        key="life"
    )
    edited_patterns["生活費"] = [kw.strip() for kw in life_keywords.split(",") if kw.strip()]

with pattern_tabs[1]:
    st.markdown("**贈与のキーワード**")
    st.caption("振込、送金など（100万円以上の場合に適用されます。少額の場合は保留または生活費とみなされることがあります）")
    gift_keywords = st.text_area(
        "キーワード（カンマ区切り）",
        value=", ".join(current_patterns.get("贈与", default_patterns["贈与"])),
        height=100,
        key="gift"
    )
    edited_patterns["贈与"] = [kw.strip() for kw in gift_keywords.split(",") if kw.strip()]

with pattern_tabs[2]:
    st.markdown("**関連会社のキーワード**")
    st.caption("同族会社、取引先などの法人名キーワード")
    rel_keywords = st.text_area(
        "キーワード（カンマ区切り）",
        value=", ".join(current_patterns.get("関連会社", default_patterns["関連会社"])),
        height=100,
        key="related"
    )
    edited_patterns["関連会社"] = [kw.strip() for kw in rel_keywords.split(",") if kw.strip()]

with pattern_tabs[3]:
    st.markdown("**銀行（定期・積立）のキーワード**")
    st.caption("定期預金、積立など、通常の入出金以外の銀行取引")
    bank_keywords = st.text_area(
        "キーワード（カンマ区切り）",
        value=", ".join(current_patterns.get("銀行", default_patterns["銀行"])),
        height=100,
        key="bank"
    )
    edited_patterns["銀行"] = [kw.strip() for kw in bank_keywords.split(",") if kw.strip()]

with pattern_tabs[4]:
    st.markdown("**証券会社のキーワード**")
    st.caption("証券会社名、投資関連用語など")
    sec_keywords = st.text_area(
        "キーワード（カンマ区切り）",
        value=", ".join(current_patterns.get("証券会社", default_patterns["証券会社"])),
        height=100,
        key="securities"
    )
    edited_patterns["証券会社"] = [kw.strip() for kw in sec_keywords.split(",") if kw.strip()]

with pattern_tabs[5]:
    st.markdown("**保険会社のキーワード**")
    st.caption("保険会社名、共済など")
    ins_keywords = st.text_area(
        "キーワード（カンマ区切り）",
        value=", ".join(current_patterns.get("保険会社", default_patterns["保険会社"])),
        height=100,
        key="insurance"
    )
    edited_patterns["保険会社"] = [kw.strip() for kw in ins_keywords.split(",") if kw.strip()]

with pattern_tabs[6]:
    st.markdown("**その他のキーワード**")
    st.caption("手数料、利息、ATMなど")
    other_keywords = st.text_area(
        "キーワード（カンマ区切り）",
        value=", ".join(current_patterns.get("その他", default_patterns["その他"])),
        height=100,
        key="other"
    )
    edited_patterns["その他"] = [kw.strip() for kw in other_keywords.split(",") if kw.strip()]

# デフォルトに戻すボタン
if st.button("🔄 デフォルトパターンに戻す"):
    edited_patterns = default_patterns
    st.success("デフォルトパターンに戻しました。「設定を保存」ボタンを押して保存してください。")
    st.rerun()

st.markdown("---")

# 保存ボタン（全設定を保存）
col1, col2, col3 = st.columns([2, 1, 2])

with col2:
    if st.button("💾 設定を保存", type="primary", use_container_width=True):
        new_settings = {
            "LARGE_AMOUNT_THRESHOLD": large_amount,
            "TRANSFER_DAYS_WINDOW": transfer_days,
            "TRANSFER_AMOUNT_TOLERANCE": transfer_tolerance,
            "OLLAMA_MODEL": ollama_model,
            "OLLAMA_BASE_URL": ollama_url,
            "CLASSIFICATION_PATTERNS": edited_patterns
        }

        save_settings(new_settings)

        # 環境変数にも設定（現在のセッションのみ有効）
        os.environ["LARGE_AMOUNT_THRESHOLD"] = str(large_amount)
        os.environ["TRANSFER_DAYS_WINDOW"] = str(transfer_days)
        os.environ["TRANSFER_AMOUNT_TOLERANCE"] = str(transfer_tolerance)
        os.environ["OLLAMA_MODEL"] = ollama_model
        os.environ["OLLAMA_BASE_URL"] = ollama_url

        st.success("✅ 設定を保存しました！変更を反映するにはアプリを再起動してください。")
        st.info("💡 再起動方法: ターミナルで `Ctrl+C` を押してアプリを停止し、再度 `streamlit run main.py` を実行")

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

    st.markdown("""
    **分類パターンのカスタマイズ**
    - よく使う店舗名や固有名詞を追加
    - 部分一致で検索されます
    - カンマで区切って複数登録可能
    """)
