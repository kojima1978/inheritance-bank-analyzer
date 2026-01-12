import requests
import json
import pandas as pd
from . import config

def classify_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ollamaを使用して摘要（description）からカテゴリを判定する
    """
    if df.empty or "description" not in df.columns:
        return df

    # まだ分類されていない、かつ摘要があるものを抽出
    # (再実行も考慮して、categoryがnullまたはunknownのものを対象にするなど仕様によるが、
    #  ここではシンプルに「全件」または「カテゴリ未設定」を対象にする)
    
    # カテゴリカラムがなければ追加
    if "category" not in df.columns:
        df["category"] = None
        
    # 対象抽出: descriptionがあり、categoryがNaNのもの
    target_mask = (df["description"].notna()) & (df["description"] != "") & (df["category"].isna())
    target_df = df[target_mask]
    
    if target_df.empty:
        return df
        
    print(f"Classifying {len(target_df)} transactions via Ollama...")

    # ユニークな摘要のみを分類してマージする（APIコール削減）
    unique_descriptions = target_df["description"].unique()
    
    # バッチ処理（数件ずつ送るか、1件ずつか）
    # Ollamaはローカルなので1件ずつでもそこそこ速いが、プロンプトに複数記述して一括判定させる方が効率的
    
    classification_map = {}
    
    for desc in unique_descriptions:
        category = call_ollama(desc)
        classification_map[desc] = category
        
    # 結果をマッピング
    df.loc[target_mask, "category"] = df.loc[target_mask, "description"].map(classification_map)
    
    return df

def call_ollama(text: str) -> str:
    """
    単一の摘要に対してカテゴリを返す
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
