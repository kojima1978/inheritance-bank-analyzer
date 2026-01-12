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
        # "未分類"がDBに含まれている場合があるので重複排除
        unique_options = sorted(list(set(["未分類"] + available_categories)), key=lambda x: (x != "未分類", x))
        
        filter_category = st.multiselect("分類絞り込み", unique_options)

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
                # 未分類 (NaN or "未分類") OR 指定カテゴリー
                filtered_df = filtered_df[
                    filtered_df["category"].isna() |
                    (filtered_df["category"] == "未分類") |
                    filtered_df["category"].isin(other_categories)
                ]
            else:
                # 未分類のみ (NaN or "未分類")
                filtered_df = filtered_df[
                    filtered_df["category"].isna() | 
                    (filtered_df["category"] == "未分類")
                ]
        else:
            # 指定カテゴリーのみ
            filtered_df = filtered_df[filtered_df["category"].isin(filter_category)]
    if keyword:
        filtered_df = filtered_df[filtered_df["description"].str.contains(keyword, na=False)]

    # 分類修正UI（取引一覧の上部に配置）
    st.markdown("### ✏️ 分類修正")

    # 取引一覧を表形式で表示し、各行に修正ボタンを配置
    if not filtered_df.empty:
        # すべての表示対象取引を編集可能にする（未分類含む）
        editable_df = filtered_df.copy()

        if not editable_df.empty:
            st.markdown(f"**修正可能な取引: {len(editable_df)}件**")

            # ページネーション設定
            items_per_page = 20
            total_pages = (len(editable_df) - 1) // items_per_page + 1

            # ページ選択
            if total_pages > 1:
                page = st.number_input("ページ", min_value=1, max_value=total_pages, value=1, step=1)
                start_idx = (page - 1) * items_per_page
                end_idx = min(start_idx + items_per_page, len(editable_df))
                page_df = editable_df.iloc[start_idx:end_idx]
                st.caption(f"表示中: {start_idx + 1}～{end_idx}件 / 全{len(editable_df)}件")
            else:
                page_df = editable_df

            # 各取引を表示
            for idx, row in page_df.iterrows():
                tx_id_key = row['id']
                with st.container(border=True):
                    col1, col2, col3, col4 = st.columns([2, 3, 2, 1])

                    with col1:
                        st.markdown(f"**{row['date']}**")
                        st.caption(f"{row['account_id'][:20]}...")

                    with col2:
                        # 摘要を表示（長い場合は省略）
                        desc_short = row['description'][:40] + "..." if len(row['description']) > 40 else row['description']
                        st.markdown(f"📝 {desc_short}")

                        # 金額表示
                        if row['amount_out'] > 0:
                            st.caption(f"払戻: ¥{int(row['amount_out']):,}")
                        if row['amount_in'] > 0:
                            st.caption(f"お預り: ¥{int(row['amount_in']):,}")

                    with col3:
                        # 現在の分類を表示
                        category_emoji = {
                            "生活費": "🛒",
                            "贈与": "🎁",
                            "関連会社": "🏢",
                            "銀行": "🏦",
                            "証券会社": "📈",
                            "保険会社": "🛡️",
                            "未分類": "❓",
                            "その他": "📄",
                            # 旧カテゴリのフォールバック
                            "資産形成": "💰",
                            "贈与疑い": "⚠️"
                        }
                        current_cat = row['category']
                        
                        if pd.isna(current_cat) or current_cat == "未分類":
                            display_cat = "未分類"
                            emoji = "❓"
                            # データ上がNoneなら未分類として扱う
                            if pd.isna(current_cat):
                                current_cat = "未分類" 
                        else:
                            display_cat = current_cat
                            emoji = category_emoji.get(current_cat, "📄")
                            
                        st.markdown(f"現在: {emoji} **{display_cat}**")

                    with col4:
                        # 修正ボタン
                        if st.button("✏️ 修正", key=f"edit_{tx_id_key}"):
                            st.session_state[f"editing_tx_{tx_id_key}"] = True
                            st.rerun()

                    # 修正フォーム（ボタンクリック時に表示）
                    if st.session_state.get(f"editing_tx_{tx_id_key}", False):
                        st.markdown("---")

                        # 同じ摘要を持つ取引数を表示
                        matching_count = len(df[df["description"] == row["description"]])
                        if matching_count > 1:
                            st.info(f"💡 この摘要を持つ取引が **{matching_count}件** あります。すべて一括で修正されます。")

                        st.markdown("**分類を修正:**")

                        col_cat, col_btn = st.columns([3, 1])

                        with col_cat:
                            # ユーザー指定のカテゴリリスト
                            categories = [
                                "生活費", "贈与", "関連会社", "銀行", 
                                "証券会社", "保険会社", "未分類", "その他"
                            ]
                            # current_catがリストにない場合（旧カテゴリなど）は先頭を選択状態に
                            current_index = categories.index(current_cat) if current_cat in categories else 0
                            new_category = st.selectbox(
                                "正しい分類",
                                options=categories,
                                index=current_index,
                                key=f"cat_select_{tx_id_key}"
                            )

                        with col_btn:
                            st.write("")  # スペース調整
                            st.write("")  # スペース調整
                            if st.button("💾 保存", key=f"save_{tx_id_key}", type="primary"):
                                # 同じ摘要の取引をすべて更新
                                matching_txs = df[df["description"] == row["description"]]
                                success_count = 0

                                for match_idx in matching_txs.index:
                                    target_tx_id = df.loc[match_idx, "id"]
                                    result = db_manager.update_transaction_category(current_case, target_tx_id, new_category)
                                    if result:
                                        success_count += 1

                                # 編集状態をクリア
                                if f"editing_tx_{tx_id_key}" in st.session_state:
                                    del st.session_state[f"editing_tx_{tx_id_key}"]

                                # 成功メッセージをsession_stateに保存
                                st.session_state["category_update_success"] = f"✅ {success_count}件の取引を「{new_category}」に修正しました！"

                                # データベースから再読み込みして即座に反映
                                st.rerun()

                        # キャンセルボタン
                        if st.button("✖️ キャンセル", key=f"cancel_{tx_id_key}"):
                            if f"editing_tx_{tx_id_key}" in st.session_state:
                                del st.session_state[f"editing_tx_{tx_id_key}"]
                            st.rerun()
        else:
            st.info("修正可能な取引がありません。")
    else:
        st.info("表示する取引がありません。")

    # 全取引一覧（参照用）
    st.markdown("---")
    st.markdown("### 📊 全取引一覧（参照用）")
    display_df = filtered_df[["date", "category", "account_id", "holder", "description", "amount_out", "amount_in", "balance", "is_large", "is_transfer", "transfer_to"]].copy()
    display_df.columns = ["日付", "分類", "口座ID", "名義人", "摘要", "払戻", "お預り", "残高", "多額取引", "資金移動", "移動先"]

    st.dataframe(
        display_df,
        width="stretch"
    )
