import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
from datetime import datetime

# --- 1. Firebaseの初期化関数 ---
def init_firebase():
    if not firebase_admin._apps:
        key_dict = json.loads(st.secrets["firebase_key"])
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
    return firestore.client()

# --- 2. 承認済みユーザーのみ通す認証機能 ---
def check_auth():
    """Secretsに登録されたメアドとパスワードで認証する"""
    def login_form():
        st.title("🔒 関係者専用ログイン")
        st.info("このアプリを利用するにはログインが必要です。")
        email = st.text_input("メールアドレス")
        password = st.text_input("パスワード", type="password")
        if st.button("ログイン"):
            # Secretsに登録した情報を照合
            if email in st.secrets["auth"]["allowed_users"] and password == st.secrets["auth"]["password"]:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("メールアドレスまたはパスワードが正しくありません。")

    if "authenticated" not in st.session_state:
        login_form()
        return False
    return True

# --- 3. メインアプリの処理 ---
if check_auth():
    # 認証された場合のみFirebaseに接続
    db = init_firebase()

    # 写真保存用のローカルフォルダ準備
    UPLOAD_DIR = "uploads"
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)

    st.set_page_config(page_title="思い出マネージャー", page_icon="📸")
    
    # サイドバーにログアウトボタンを設置
    if st.sidebar.button("ログアウト"):
        del st.session_state["authenticated"]
        st.rerun()

    st.title("📸 写真と日付が選べる思い出帳")

    # --- 入力エリア ---
    with st.container():
        st.subheader("新しい思い出を投稿")
        with st.form("add_form", clear_on_submit=True):
            target_date = st.date_input("いつの思い出？", value=datetime.now())
            new_comment = st.text_input("どんな思い出？")
            uploaded_file = st.file_uploader("写真を選んでね", type=["jpg", "png", "jpeg"])
            
            submit_add = st.form_submit_button("保存")
            
            if submit_add and new_comment:
                img_name = ""
                if uploaded_file:
                    img_name = uploaded_file.name
                    file_path = os.path.join(UPLOAD_DIR, img_name)
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                
                save_datetime = datetime.combine(target_date, datetime.now().time())
                db.collection("memories").add({
                    "comment": new_comment,
                    "image_name": img_name,
                    "date": save_datetime
                })
                st.success("保存しました！")
                st.rerun()

    st.divider()

    # --- 表示・操作エリア ---
    st.subheader("🎞️ 思い出リスト")

    memories = db.collection("memories").order_by("date", direction=firestore.Query.DESCENDING).stream()

    for m in memories:
        data = m.to_dict()
        doc_id = m.id
        
        raw_date = data.get('date')
        date_str = raw_date.strftime('%Y/%m/%d') if hasattr(raw_date, 'strftime') else "日付なし"

        with st.expander(f"📌 {date_str}：{data.get('comment', '')[:15]}..."):
            edit_comment = st.text_input("内容を修正", value=data.get("comment", ""), key=f"edit_{doc_id}")
            
            img_name = data.get("image_name")
            if img_name:
                img_path = os.path.join(UPLOAD_DIR, img_name)
                if os.path.exists(img_path):
                    st.image(img_path, width=200)
                else:
                    st.warning("画像ファイルが見つかりません（再起動で消えた可能性があります）")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("更新", key=f"update_{doc_id}"):
                    db.collection("memories").document(doc_id).update({"comment": edit_comment})
                    st.toast("更新しました")
                    st.rerun()
            with col2:
                if st.button("🗑️ 削除", key=f"delete_{doc_id}"):
                    db.collection("memories").document(doc_id).delete()
                    st.toast("削除しました")
                    st.rerun()
