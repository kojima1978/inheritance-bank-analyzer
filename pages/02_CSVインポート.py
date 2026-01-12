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
            if "account_type" in csv_metadata and csv_metadata["account_type"]:
                st.write(f"- 口座種別: {csv_metadata['account_type']}")

        # ステップ2: 口座情報入力
        st.subheader("ステップ2: 口座情報を確認・入力")
        st.write("CSVから読み取れなかった情報、または修正が必要な情報を入力してください。")

        # 名義人を「本人」にするボタン（フォームの外に配置）
        col_btn, _ = st.columns([1, 3])
        with col_btn:
            if st.button("名義人を「本人」に設定"):
                st.session_state["holder_name_input"] = "本人"

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
                # 口座種別をCSVから自動設定
                default_account_type = csv_metadata.get("account_type", "普通")
                account_type_options = ["普通", "定期", "当座", "貯蓄"]
                if default_account_type in account_type_options:
                    default_index = account_type_options.index(default_account_type)
                else:
                    default_index = 0

                account_type = st.selectbox("口座種別", account_type_options, index=default_index)
                account_num = st.text_input(
                    "口座番号",
                    value=csv_metadata.get("account_number", ""),
                    placeholder="半角数字"
                )
                
                holder_name = st.text_input(
                    "名義人",
                    placeholder="例: 山田太郎",
                    key="holder_name_input"
                ) 


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
                    st.warning(f"⚠️ {len(error_rows)} 件の残高不整合があります。")
                    st.caption("残高不整合は、OCRの読み取りミスや、データの欠損が原因の可能性があります。")

                    # 詳細な不一致情報を表示
                    with st.expander("📋 残高不整合の詳細を表示", expanded=True):
                        # 不一致の差分を計算
                        error_display = error_rows.copy()
                        error_display["差分"] = error_display["balance"] - error_display["calc_balance"]
                        error_display["前行残高"] = error_display["calc_balance"] - error_display["amount_in"] + error_display["amount_out"]

                        # カラム名を日本語に
                        display_cols = {
                            "date": "日付",
                            "description": "摘要",
                            "amount_out": "払戻",
                            "amount_in": "お預り",
                            "balance": "CSV残高",
                            "calc_balance": "計算残高",
                            "差分": "差分"
                        }

                        error_display_formatted = error_display[list(display_cols.keys())].rename(columns=display_cols)

                        # フォーマット：金額をカンマ区切りに
                        for col in ["払戻", "お預り", "CSV残高", "計算残高", "差分"]:
                            error_display_formatted[col] = error_display_formatted[col].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "")

                        st.dataframe(
                            error_display_formatted,
                            use_container_width=True,
                            height=min(400, len(error_display_formatted) * 35 + 38)
                        )

                        # 説明
                        st.markdown("""
                        **各カラムの説明:**
                        - **払戻**: 出金額
                        - **お預り**: 入金額
                        - **CSV残高**: CSVファイルに記載されている残高
                        - **計算残高**: 前行残高 + お預り - 払戻 で計算した残高
                        - **差分**: CSV残高 - 計算残高（プラスの場合、計算より実際が多い）
                        """)

                        # 統計情報
                        st.markdown("**不一致の統計:**")
                        col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                        with col_stat1:
                            st.metric("不一致件数", f"{len(error_rows)}件")
                        with col_stat2:
                            max_diff = error_display["差分"].abs().max()
                            st.metric("最大差分", f"¥{int(max_diff):,}")
                        with col_stat3:
                            avg_diff = error_display["差分"].abs().mean()
                            st.metric("平均差分", f"¥{int(avg_diff):,}")
                        with col_stat4:
                            # 同一日付の取引数を確認
                            duplicate_dates = df[df.duplicated(subset=['date'], keep=False)].groupby('date').size()
                            if len(duplicate_dates) > 0:
                                st.metric("同日取引数", f"最大{duplicate_dates.max()}件")
                            else:
                                st.metric("同日取引", "なし")

                        # 同じ日付の取引に関する注意
                        duplicate_dates = df[df.duplicated(subset=['date'], keep=False)]
                        if len(duplicate_dates) > 0:
                            st.info(
                                f"ℹ️ 同じ日付に複数の取引があります。CSVの行順序が通帳と一致していることを確認してください。\n\n"
                                f"同日に複数取引がある日付: {duplicate_dates['date'].nunique()}日"
                            )
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
