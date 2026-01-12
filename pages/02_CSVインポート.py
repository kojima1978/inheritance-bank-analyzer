import streamlit as st
import pandas as pd
from lib import db_manager, importer, analyzer

st.set_page_config(page_title="CSVインポート", page_icon="📥")
st.title("📥 CSVインポート")

if "current_case" not in st.session_state:
    st.warning("まずは「案件一覧」から案件を選択してください。")
    st.stop()

current_case = st.session_state["current_case"]
st.info(f"対象案件: **{current_case}**")

# ステップ1: CSVファイルアップロード
st.subheader("ステップ1: CSVファイルをアップロード")
uploaded_file = st.file_uploader("通帳CSVを選択", type=["csv"], key="csv_uploader")

if uploaded_file is not None:
    try:
        # CSVを読み込み
        df = importer.load_csv(uploaded_file)
        csv_metadata = df.attrs.get("csv_metadata", {})

        st.success(f"✅ CSVを読み込みました（{len(df)}件）")

        # CSVから取得した情報を表示
        if csv_metadata:
            st.info("CSVから以下の情報を読み取りました：")
            if "bank_name" in csv_metadata and csv_metadata["bank_name"]:
                st.write(f"- 銀行名: {csv_metadata['bank_name']}")
            if "branch_name" in csv_metadata and csv_metadata["branch_name"]:
                st.write(f"- 支店名: {csv_metadata['branch_name']}")
            if "account_number" in csv_metadata and csv_metadata["account_number"]:
                st.write(f"- 口座番号: {csv_metadata['account_number']}")

        # ステップ2: 口座情報入力
        st.subheader("ステップ2: 口座情報を確認・入力")
        st.write("CSVから読み取れなかった情報、または修正が必要な情報を入力してください。")

        with st.form("account_info_form"):
            col1, col2 = st.columns(2)
            with col1:
                bank_name = st.text_input(
                    "銀行名",
                    value=csv_metadata.get("bank_name", ""),
                    placeholder="例: 三菱UFJ銀行"
                )
                branch_name = st.text_input(
                    "支店名",
                    value=csv_metadata.get("branch_name", ""),
                    placeholder="例: 青山支店"
                )
            with col2:
                account_type = st.selectbox("口座種別", ["普通", "定期", "当座"])
                account_num = st.text_input(
                    "口座番号",
                    value=csv_metadata.get("account_number", ""),
                    placeholder="半角数字"
                )
                holder_name = st.text_input("名義人", placeholder="例: 山田太郎")

            submitted = st.form_submit_button("読み込み・検証")

        if submitted:
            if not (bank_name and account_num and holder_name):
                st.error("銀行名、口座番号、名義人は必須です")
            else:
                # 口座情報の付与
                account_id = f"{bank_name}_{account_num}"
                df["account_id"] = account_id
                df["holder"] = holder_name

                # 検証（残高チェック）
                df = importer.validate_balance(df)

                error_rows = df[df["is_balance_error"] == True]
                if not error_rows.empty:
                    st.warning(f"⚠️ {len(error_rows)} 件の残高不整合があります。CSVを確認してください。")
                    st.dataframe(error_rows[["date", "description", "amount_out", "amount_in", "balance", "calc_balance"]])
                else:
                    st.success("✅ 残高整合性チェックOK")

                # プレビュー
                st.subheader("データプレビュー")
                preview_cols = ["date", "description", "amount_out", "amount_in", "balance", "account_id", "holder"]
                st.dataframe(df[preview_cols].head(10))

                # セッションステートに保存
                st.session_state["preview_df"] = df
                st.session_state["account_info"] = {
                    "bank_name": bank_name,
                    "branch_name": branch_name,
                    "account_type": account_type,
                    "account_num": account_num,
                    "holder_name": holder_name
                }

    except Exception as e:
        st.error(f"CSVの読み込みエラー: {e}")
        import traceback
        st.code(traceback.format_exc())

# ステップ3: データ登録
if "preview_df" in st.session_state and "account_info" in st.session_state:
    st.subheader("ステップ3: データを登録")
    account_info = st.session_state["account_info"]
    st.write(f"**銀行名:** {account_info['bank_name']}")
    st.write(f"**支店名:** {account_info.get('branch_name', '(未入力)')}")
    st.write(f"**口座種別:** {account_info['account_type']}")
    st.write(f"**口座番号:** {account_info['account_num']}")
    st.write(f"**名義人:** {account_info['holder_name']}")

    if st.button("このデータを登録して分析を実行する", type="primary"):
        df = st.session_state["preview_df"]

        try:
            # 既存データのロード
            existing_df = db_manager.load_transactions(current_case)
            if not existing_df.empty:
                # 結合
                combined_df = pd.concat([existing_df, df], ignore_index=True)
            else:
                combined_df = df

            # 検証用カラムを削除（DBに保存する前に）
            cols_to_drop = ["calc_balance", "is_balance_error"]
            combined_df = combined_df.drop(columns=[col for col in cols_to_drop if col in combined_df.columns])

            # 分析実行（全体に対して再分析）
            combined_df = analyzer.analyze_large_amounts(combined_df)
            combined_df = analyzer.analyze_transfers(combined_df)

            # 保存
            db_manager.save_transactions(current_case, combined_df)

            st.success("✅ 保存と分析が完了しました。「分析・表示」メニューで結果を確認してください。")

            # クリア
            del st.session_state["preview_df"]
            del st.session_state["account_info"]
            st.rerun()

        except Exception as e:
            st.error(f"保存中にエラーが発生しました: {e}")
            import traceback
            st.code(traceback.format_exc())
