import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from lib import db_manager

st.set_page_config(page_title="分析・表示", page_icon="📊", layout="wide")
st.title("📊 分析結果")

if "current_case" not in st.session_state:
    st.warning("まずは「案件一覧」から案件を選択してください。")
    st.stop()

current_case = st.session_state["current_case"]
st.info(f"対象案件: **{current_case}**")

# データロード
df = db_manager.load_transactions(current_case)

if df.empty:
    st.warning("データがありません。「CSVインポート」からデータを取り込んでください。")
    st.stop()

# 日付型変換（DBから読み込むと文字列になるため）
# 日付型変換（DBから読み込むと文字列になるため）
df["date"] = pd.to_datetime(df["date"]).dt.date

# 必要なカラムがない場合のチェック
required_cols = ["is_large", "is_transfer", "transfer_to"]
missing_cols = [col for col in required_cols if col not in df.columns]

# categoryカラムがない場合はNoneで追加（スキーママイグレーション前のデータ対策）
if "category" not in df.columns:
    df["category"] = None
    
if missing_cols:
    st.error(f"データベースに必要なカラムがありません: {', '.join(missing_cols)}")
    st.info("「CSVインポート」から再度データをインポートしてください。")
    st.stop()

# AI分析モジュール
from lib import llm_classifier

# サイドバーに分析実行ボタン
with st.sidebar:
    st.markdown("### 🤖 形質分析")
    if st.button("AI分類を実行", type="primary"):
        with st.spinner("AIが取引内容を分析中... (Ollama)"):
            try:
                # 分類実行
                df = llm_classifier.classify_transactions(df)
                # DB保存
                db_manager.save_transactions(current_case, df)
                st.success("分析完了！")
                st.rerun()
            except Exception as e:
                st.error(f"エラー: {e}")

# 口座サマリーを表示
st.markdown("### 📋 登録口座一覧")
with st.container(border=True):
    accounts = df.groupby(['account_id', 'holder']).agg(
        取引件数=('date', 'count'),
        最終取引日=('date', 'max')
    ).reset_index()

    for _, row in accounts.iterrows():
        # account_idから銀行名と口座番号を抽出
        parts = row['account_id'].rsplit('_', 1)
        if len(parts) == 2:
            bank_name = parts[0]
            account_num = parts[1]

            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
            with col1:
                st.markdown(f"**🏦 {bank_name}**")
            with col2:
                st.markdown(f"口座番号: `{account_num}`")
            with col3:
                st.markdown(f"名義: {row['holder']}")
            with col4:
                st.markdown(f"取引件数: {row['取引件数']}件")
        else:
            st.markdown(f"・{row['account_id']} / 名義: {row['holder']} / 取引件数: {row['取引件数']}件")

st.markdown("---")

# タブ切り替え
tab1, tab2, tab3 = st.tabs(["資金移動フロー", "多額取引", "全取引一覧"])

with tab1:
    st.subheader("資金移動の分析")
    # 資金移動フラグがあるもののみ抽出
    transfers = df[df["is_transfer"] == True]
    
    if transfers.empty:
        st.info("検知された資金移動はありません。")
    else:
        # 出金側のみを見る（ペアの片方）
        out_transfers = transfers[transfers["amount_out"] > 0].copy()
        
        if out_transfers.empty:
             st.info("表示可能な資金移動フローがありません。")
        else:
            # データ加工
            out_transfers["target_account"] = out_transfers["transfer_to"].apply(lambda x: x.split(" ")[0] if x else "Unknown")
            out_transfers["flow_label"] = out_transfers["account_id"] + " ➡ " + out_transfers["target_account"]
            
            # 1. 集計テーブル表示
            st.markdown("#### 📋 口座間移動 集計表")
            summary_df = out_transfers.groupby(["account_id", "target_account"]).agg(
                count=("amount_out", "count"),
                total_amount=("amount_out", "sum")
            ).reset_index()
            summary_df.columns = ["出金元口座", "入金先口座", "回数", "合計金額"]
            st.dataframe(summary_df, use_container_width=True)

            # 2. タイムライン・散布図
            st.markdown("#### 📅 資金移動タイムライン")
            st.caption("いつ、どの口座間で、どれくらいの金額が動いたかを時系列で表示します。")
            
            fig = px.scatter(
                out_transfers,
                x="date",
                y="amount_out",
                color="flow_label",
                size="amount_out",
                hover_data=["description", "balance"],
                labels={"date": "日付", "amount_out": "移動金額", "flow_label": "移動ルート"},
                title="資金移動の時系列分布"
            )
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("多額出金・入金リスト")
    large_tx = df[df["is_large"] == True].sort_values("date", ascending=False)

    if large_tx.empty:
        st.info("設定閾値を超える取引はありません。")
    else:
        # カラム名を日本語に変換
        display_large = large_tx[["date", "account_id", "holder", "description", "amount_out", "amount_in", "balance"]].copy()
        display_large.columns = ["日付", "口座ID", "名義人", "摘要", "払戻", "お預り", "残高"]

        st.dataframe(
            display_large,
            width="stretch"
        )

with tab3:
    st.subheader("取引一覧")
    
    # フィルタ
    col1, col2 = st.columns(2)
    with col1:
        filter_account = st.multiselect("口座絞り込み", df["account_id"].unique())
    with col2:
        keyword = st.text_input("摘要検索")
        
    filtered_df = df.copy()
    if filter_account:
        filtered_df = filtered_df[filtered_df["account_id"].isin(filter_account)]
    if keyword:
        filtered_df = filtered_df[filtered_df["description"].str.contains(keyword, na=False)]
        
    # カラム名を日本語に変換
    display_df = filtered_df[["date", "category", "account_id", "holder", "description", "amount_out", "amount_in", "balance", "is_large", "is_transfer", "transfer_to"]].copy()
    display_df.columns = ["日付", "分類", "口座ID", "名義人", "摘要", "払戻", "お預り", "残高", "多額取引", "資金移動", "移動先"]

    st.dataframe(
        display_df,
        width="stretch"
    )
