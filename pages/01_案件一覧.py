import streamlit as st
import os
import shutil
from lib import config, db_manager

st.set_page_config(page_title="案件一覧", page_icon="📂")
st.title("📂 案件一覧")

# 新規作成
with st.expander("新規案件作成", expanded=True):
    new_case_name = st.text_input("案件名（例：山田太郎_相続）")
    if st.button("作成"):
        if new_case_name:
            if new_case_name in db_manager.get_all_cases():
                st.error("その案件名は既に存在します")
            else:
                db_manager.init_db(new_case_name)
                st.success(f"案件「{new_case_name}」を作成しました")
                st.rerun()

# 一覧表示
st.subheader("既存の案件")
cases = db_manager.get_all_cases()

if not cases:
    st.info("案件がまだありません。")
else:
    for case in cases:
        with st.container(border=True):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"📁 **{case}**")

                # 口座情報を取得して表示
                df = db_manager.load_transactions(case)
                if not df.empty and 'account_id' in df.columns and 'holder' in df.columns:
                    # 口座情報を抽出
                    accounts = df.groupby(['account_id', 'holder']).size().reset_index()[['account_id', 'holder']]

                    if not accounts.empty:
                        st.caption("📊 登録口座:")
                        for _, row in accounts.iterrows():
                            # account_idから銀行名と口座番号を抽出
                            parts = row['account_id'].rsplit('_', 1)
                            if len(parts) == 2:
                                bank_name = parts[0]
                                account_num = parts[1]
                                st.markdown(f"　・**{bank_name}** / 口座番号: {account_num} / 名義: {row['holder']}")
                            else:
                                st.markdown(f"　・{row['account_id']} / 名義: {row['holder']}")
                else:
                    st.caption("データ未登録")

            with col2:
                if st.button("選択", key=f"select_{case}", type="primary"):
                     st.session_state["current_case"] = case
                     st.success(f"「{case}」を選択しました。メニューから作業を進めてください。")

                # 削除ボタン
                if st.button("🗑️ 削除", key=f"delete_{case}", type="secondary"):
                    st.session_state[f"confirm_delete_{case}"] = True
                    st.rerun()

            # 削除確認ダイアログ
            if st.session_state.get(f"confirm_delete_{case}", False):
                st.warning(f"⚠️ 案件「**{case}**」を削除しますか？")
                st.caption("この操作は取り消せません。すべての口座データと取引履歴が削除されます。")

                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("はい、削除します", key=f"confirm_yes_{case}", type="primary"):
                        # 案件フォルダを削除
                        case_dir = os.path.join(config.DATA_DIR, case)
                        if os.path.exists(case_dir):
                            shutil.rmtree(case_dir)

                        # 現在選択中の案件が削除対象の場合、セッション状態をクリア
                        if st.session_state.get("current_case") == case:
                            del st.session_state["current_case"]

                        # 確認フラグをクリア
                        del st.session_state[f"confirm_delete_{case}"]

                        st.success(f"案件「{case}」を削除しました。")
                        st.rerun()

                with col_no:
                    if st.button("キャンセル", key=f"confirm_no_{case}"):
                        del st.session_state[f"confirm_delete_{case}"]
                        st.rerun()

if "current_case" in st.session_state:
    st.markdown(f"---")
    st.info(f"現在選択中の案件: **{st.session_state['current_case']}**")
