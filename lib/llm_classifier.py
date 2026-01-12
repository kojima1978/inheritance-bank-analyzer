import requests
import json
import pandas as pd
from . import config

def load_classification_patterns():
    """
    設定ファイルから分類パターンを読み込む
    """
    default_patterns = {
        "生活費": [
            "イオン", "セブン", "ローソン", "ファミマ", "スーパー", "マート",
            "電気", "ガス", "水道", "東京電力", "東電", "関西電力", "関電",
            "NTT", "ドコモ", "DOCOMO", "ソフトバンク", "au", "通信", "電話",
            "NHK", "薬局", "ドラッグ", "病院", "医院", "クリニック", "介護",
            "ガソリン", "ENEOS", "出光", "昭和シェル",
            "マクドナルド", "スターバックス", "スタバ", "コンビニ"
        ],
        "資産形成": [
            "証券", "野村", "大和", "SMBC", "みずほ証券", "楽天証券", "SBI",
            "投資信託", "株式", "債券", "ファンド",
            "生命保険", "損保", "保険", "共済", "かんぽ", "日本生命", "第一生命",
            "定期預金", "定期", "積立"
        ],
        "贈与疑い": [
            "フリコミ", "振込", "送金"
        ],
        "その他": [
            "手数料", "利息", "ATM", "時間外", "引出", "預入"
        ]
    }

    # 設定ファイルから読み込み
    if hasattr(config, 'CONFIG_FILE'):
        try:
            if config.CONFIG_FILE.exists():
                import json
                with open(config.CONFIG_FILE, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    return settings.get("CLASSIFICATION_PATTERNS", default_patterns)
        except:
            pass

    return default_patterns

def classify_by_rules(text: str, amount_out: int, amount_in: int) -> str:
    """
    ルールベースで分類（Ollama不要、高速）
    """
    text_lower = text.lower()

    # 設定ファイルからパターンを読み込み
    patterns = load_classification_patterns()

    life_keywords = patterns.get("生活費", [])
    asset_keywords = patterns.get("資産形成", [])
    gift_keywords = patterns.get("贈与疑い", [])
    other_keywords = patterns.get("その他", [])

    # カテゴリ判定
    for keyword in life_keywords:
        if keyword in text:
            return "生活費"

    for keyword in asset_keywords:
        if keyword in text:
            return "資産形成"

    # 振込の場合、金額で判断
    if any(kw in text for kw in gift_keywords):
        if amount_out >= 1_000_000:  # 100万円以上の振込
            return "贈与疑い"
        else:
            return "生活費"

    for keyword in other_keywords:
        if keyword in text:
            return "その他"

    # どれにも該当しない場合はその他
    return "その他"

def check_ollama_available() -> bool:
    """
    Ollamaが利用可能かチェック
    """
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except:
        return False

def classify_transactions(df: pd.DataFrame, use_ollama: bool = None) -> pd.DataFrame:
    """
    取引を分類する（Ollama利用可能ならAI分類、そうでなければルールベース分類）

    Args:
        df: 分類対象のDataFrame
        use_ollama: True=Ollama使用, False=ルールベース, None=自動判定
    """
    if df.empty or "description" not in df.columns:
        return df

    # カテゴリカラムがなければ追加
    if "category" not in df.columns:
        df["category"] = None

    # 対象抽出: descriptionがあり、categoryがNaNのもの
    target_mask = (df["description"].notna()) & (df["description"] != "") & (df["category"].isna())
    target_df = df[target_mask]

    if target_df.empty:
        return df

    # Ollama使用判定
    if use_ollama is None:
        use_ollama = check_ollama_available()

    if use_ollama:
        print(f"AI分類を実行中... (対象: {len(target_df)}件)")
        classification_map = {}
        unique_descriptions = target_df["description"].unique()

        for desc in unique_descriptions:
            # まずルールベースで試す
            row = target_df[target_df["description"] == desc].iloc[0]
            rule_category = classify_by_rules(desc, row["amount_out"], row["amount_in"])

            # ルールベースで「その他」になった場合のみAI分類
            if rule_category == "その他":
                category = call_ollama(desc)
            else:
                category = rule_category

            classification_map[desc] = category
    else:
        print(f"ルールベース分類を実行中... (対象: {len(target_df)}件)")
        classification_map = {}

        for idx in target_df.index:
            row = target_df.loc[idx]
            category = classify_by_rules(
                row["description"],
                row["amount_out"],
                row["amount_in"]
            )
            classification_map[row["description"]] = category

    # 結果をマッピング
    df.loc[target_mask, "category"] = df.loc[target_mask, "description"].map(classification_map)

    return df

def call_ollama(text: str) -> str:
    """
    単一の摘要に対してカテゴリを返す（Ollama使用）
    """
    prompt = f"""
    あなたは相続税調査の専門家です。以下の銀行取引の摘要欄のテキストから、最も適切なカテゴリを1つだけ選んで回答してください。
    回答はカテゴリ名のみを返し、それ以外の文章は一切含めないでください。

    カテゴリ候補:
    - 生活費 (スーパー、コンビニ、水道光熱費、通信費、NHKなど)
    - 資産形成 (証券会社、定期預金作成、保険料など)
    - 贈与疑い (家族名義への振込、使途不明な個人への送金など)
    - その他 (手数料、利息、不明なもの)

    摘要: {text}
    """

    payload = {
        "model": config.OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False
    }

    try:
        response = requests.post(config.OLLAMA_BASE_URL, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json().get("response", "").strip()
            # 想定外の回答が含まれていないか簡易チェック
            valid_categories = ["生活費", "資産形成", "贈与疑い", "その他"]
            for cat in valid_categories:
                if cat in result:
                    return cat
            return "その他"
        else:
            print(f"Ollama API Error: {response.status_code}")
            return "その他"
    except Exception as e:
        print(f"Ollama Connection Error: {e}")
        return "その他"
