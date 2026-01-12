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
    st.markdown("### 🤖 自動分類")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🤖 AI分類", type="primary", use_container_width=True):
            # Ollama利用可能かチェック
            ollama_available = llm_classifier.check_ollama_available()

            if ollama_available:
                with st.spinner("AI分類実行中..."):
                    try:
                        # AI分類実行（Ollama使用）
                        df = llm_classifier.classify_transactions(df, use_ollama=True)
                        # DB保存
                        db_manager.save_transactions(current_case, df)
                        st.success("✅ AI分類完了！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"エラー: {e}")
            else:
                st.warning("⚠️ Ollamaが起動していません。ルールベース分類を使用してください。")

    with col2:
        if st.button("📝 ルール分類", use_container_width=True):
            with st.spinner("ルールベース分類実行中..."):
                try:
                    # ルールベース分類実行（Ollama不使用）
                    df = llm_classifier.classify_transactions(df, use_ollama=False)
                    # DB保存
                    db_manager.save_transactions(current_case, df)
                    st.success("✅ ルールベース分類完了！")
                    st.rerun()
                except Exception as e:
                    st.error(f"エラー: {e}")

    st.caption("**🤖 AI分類**: Ollama使用（高精度・要起動）")
    st.caption("**📝 ルール分類**: 設定パターン使用（高速・安定）")

# 口座サマリーを表示
st.markdown("### 📋 登録口座一覧")
with st.container(border=True):
    accounts = df.groupby(['account_id', 'holder']).agg(
        取引件数=('date', 'count'),
        最終取引日=('date', 'max')
    ).reset_index()

    for idx, row in accounts.iterrows():
        # account_idから銀行名と口座番号を抽出
        parts = row['account_id'].rsplit('_', 1)
        if len(parts) == 2:
            bank_name = parts[0]
            account_num = parts[1]

            col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 1])
            with col1:
                st.markdown(f"**🏦 {bank_name}**")
            with col2:
                st.markdown(f"口座番号: `{account_num}`")
            with col3:
                st.markdown(f"名義: {row['holder']}")
            with col4:
                st.markdown(f"取引件数: {row['取引件数']}件")
            with col5:
                if st.button("🗑️", key=f"del_acc_{row['account_id']}", help="この口座のデータを削除"):
                    st.session_state[f"confirm_delete_account_{row['account_id']}"] = True
                    st.rerun()
        else:
            col1, col2 = st.columns([9, 1])
            with col1:
                st.markdown(f"・{row['account_id']} / 名義: {row['holder']} / 取引件数: {row['取引件数']}件")
            with col2:
                if st.button("🗑️", key=f"del_acc_{row['account_id']}", help="この口座のデータを削除"):
                    st.session_state[f"confirm_delete_account_{row['account_id']}"] = True
                    st.rerun()

        # 削除確認ダイアログ
        if st.session_state.get(f"confirm_delete_account_{row['account_id']}", False):
            st.warning(f"⚠️ 口座「{row['account_id']}」のデータを削除しますか？")
            st.caption("この操作は取り消せません。")

            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("削除", key=f"confirm_yes_{row['account_id']}", type="primary"):
                    if db_manager.delete_account_transactions(current_case, row['account_id']):
                        del st.session_state[f"confirm_delete_account_{row['account_id']}"]
                        st.success(f"口座「{row['account_id']}」を削除しました。")
                        st.rerun()
                    else:
                        st.error("削除に失敗しました。")
            with col_no:
                if st.button("キャンセル", key=f"confirm_no_{row['account_id']}"):
                    del st.session_state[f"confirm_delete_account_{row['account_id']}"]
                    st.rerun()

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

            # 1. 個別取引リスト表示
            st.markdown("#### 📋 口座間移動 取引一覧")
            st.caption(f"検出された資金移動: {len(out_transfers)}件")

            # ペアの入金取引情報を取得
            display_list = []
            for idx, out_row in out_transfers.iterrows():
                # 入金側の取引を検索
                transfer_info = out_row["transfer_to"]
                if transfer_info and " " in transfer_info:
                    parts = transfer_info.split(" ")
                    in_account = parts[0]
                    in_date_str = " ".join(parts[1:])

                    # 入金側の取引を探す（日付の型を統一）
                    in_tx = df[
                        (df["account_id"] == in_account) &
                        (df["date"] == out_row["date"]) &
                        (df["amount_in"] > 0)
                    ]

                    if not in_tx.empty:
                        in_row = in_tx.iloc[0]
                        display_list.append({
                            "日付": out_row["date"],
                            "出金元口座": out_row["account_id"],
                            "出金額": f"{int(out_row['amount_out']):,}",
                            "出金摘要": out_row["description"],
                            "入金先口座": in_account,
                            "入金額": f"{int(in_row['amount_in']):,}",
                            "入金摘要": in_row["description"],
                            "名義人": out_row["holder"]
                        })
                    else:
                        # 入金側が見つからない場合
                        display_list.append({
                            "日付": out_row["date"],
                            "出金元口座": out_row["account_id"],
                            "出金額": f"{int(out_row['amount_out']):,}",
                            "出金摘要": out_row["description"],
                            "入金先口座": in_account,
                            "入金額": "未検出",
                            "入金摘要": "未検出",
                            "名義人": out_row["holder"]
                        })

            if display_list:
                display_transfers = pd.DataFrame(display_list)
                # 日付降順でソート
                display_transfers = display_transfers.sort_values("日付", ascending=False)

                st.dataframe(
                    display_transfers,
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("表示可能な資金移動がありません。")

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
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_account = st.multiselect("口座絞り込み", df["account_id"].unique())
    with col2:
        # カテゴリーフィルタ（分類済みのもののみ）
        available_categories = df[df["category"].notna()]["category"].unique().tolist()
        if available_categories:
            filter_category = st.multiselect("分類絞り込み", ["未分類"] + sorted(available_categories))
        else:
            filter_category = []
            st.caption("分類を実行すると絞り込みできます")
    with col3:
        keyword = st.text_input("摘要検索")

    filtered_df = df.copy()
    if filter_account:
        filtered_df = filtered_df[filtered_df["account_id"].isin(filter_account)]
    if filter_category:
        # 「未分類」が選択されている場合
        if "未分類" in filter_category:
            # 未分類のみ、または未分類+他のカテゴリー
            other_categories = [c for c in filter_category if c != "未分類"]
            if other_categories:
                # 未分類 OR 指定カテゴリー
                filtered_df = filtered_df[
                    filtered_df["category"].isna() |
                    filtered_df["category"].isin(other_categories)
                ]
            else:
                # 未分類のみ
                filtered_df = filtered_df[filtered_df["category"].isna()]
        else:
            # 指定カテゴリーのみ
            filtered_df = filtered_df[filtered_df["category"].isin(filter_category)]
    if keyword:
        filtered_df = filtered_df[filtered_df["description"].str.contains(keyword, na=False)]
        
    # カラム名を日本語に変換
    display_df = filtered_df[["date", "category", "account_id", "holder", "description", "amount_out", "amount_in", "balance", "is_large", "is_transfer", "transfer_to"]].copy()
    display_df.columns = ["日付", "分類", "口座ID", "名義人", "摘要", "払戻", "お預り", "残高", "多額取引", "資金移動", "移動先"]

    st.dataframe(
        display_df,
        width="stretch"
    )
