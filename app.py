import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
from datetime import datetime

# --- 1. Firebase初期化 ---
def init_firebase():
    if not firebase_admin._apps:
        key_dict = json.loads(st.secrets["firebase_key"])
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
    return firestore.client()

# --- 2. 認証・ユーザー管理ロジック ---
def check_auth(db):
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
        st.session_state["is_admin"] = False

    if not st.session_state["authenticated"]:
        st.title("🔒 ログイン")
        email = st.text_input("メールアドレス")
        pw = st.text_input("パスワード", type="password")
        
        if st.button("ログイン"):
            # A. 管理者チェック (Secrets参照)
            if email == st.secrets["auth"]["admin_user"] and pw == st.secrets["auth"]["password"]:
                st.session_state["authenticated"] = True
                st.session_state["is_admin"] = True
                st.session_state["user_email"] = email
                st.rerun()
            
            # B. 招待ユーザーチェック (Firestore参照)
            else:
                user_doc = db.collection("users").document(email).get()
                if user_doc.exists and pw == st.secrets["auth"]["password"]:
                    st.session_state["authenticated"] = True
                    st.session_state["is_admin"] = False
                    st.session_state["user_email"] = email
                    st.rerun()
                else:
                    st.error("権限がないか、情報が間違っています")
        return False
    return True

# --- 3. メイン処理 ---
db = init_firebase()

if check_auth(db):
    st.sidebar.write(f"Logged in as: {st.session_state['user_email']}")
    
    # 🌟 管理者専用メニュー (サイドバー)
    if st.session_state["is_admin"]:
        with st.sidebar.expander("👤 ユーザー管理 (管理者限定)"):
            new_user = st.text_input("招待するメアド")
            if st.button("招待を追加"):
                if new_user:
                    db.collection("users").document(new_user).set({
                        "added_at": datetime.now(),
                        "added_by": st.session_state["user_email"]
                    })
                    st.success(f"{new_user} を追加しました")
            
            st.write("---")
            st.write("現在の招待リスト:")
            users = db.collection("users").stream()
            for u in users:
                col_u1, col_u2 = st.columns([3, 1])
                col_u1.write(u.id)
                if col_u2.button("❌", key=u.id):
                    db.collection("users").document(u.id).delete()
                    st.rerun()

    if st.sidebar.button("ログアウト"):
        st.session_state["authenticated"] = False
        st.rerun()

    # --- アプリ本体 (これまでの機能をここに集約) ---
    st.title("📸 みんなの思い出帳")

    # (以下、これまでの投稿・表示コード)
    with st.container():
        st.subheader("新しい思い出を投稿")
        with st.form("add_form", clear_on_submit=True):
            target_date = st.date_input("いつの思い出？", value=datetime.now())
            new_comment = st.text_input("どんな思い出？")
            uploaded_file = st.file_uploader("写真を選んでね", type=["jpg", "png", "jpeg"])
            submit_add = st.form_submit_button("保存")
            
            if submit_add and new_comment:
                img_name = uploaded_file.name if uploaded_file else ""
                # ※注：写真はリセットで消えるため、今回はコメント保存を優先
                save_datetime = datetime.combine(target_date, datetime.now().time())
                db.collection("memories").add({
                    "comment": new_comment,
                    "image_name": img_name,
                    "date": save_datetime,
                    "author": st.session_state["user_email"]
                })
                st.success("保存しました！")
                st.rerun()

    st.divider()
    memories = db.collection("memories").order_by("date", direction=firestore.Query.DESCENDING).stream()
    for m in memories:
        data = m.to_dict()
        doc_id = m.id
        raw_date = data.get('date')
        date_str = raw_date.strftime('%Y/%m/%d') if hasattr(raw_date, 'strftime') else "日付なし"
        with st.expander(f"📌 {date_str}：{data.get('comment', '')[:15]}... (by {data.get('author', '不明')})"):
            st.write(data.get('comment'))
            if st.button("🗑️ 削除", key=f"del_{doc_id}"):
                db.collection("memories").document(doc_id).delete()
                st.rerun()
