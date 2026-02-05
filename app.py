import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
from datetime import datetime

# --- 追加：GitHubのリンクだけを隠す設定 ---
st.markdown("""
    <style>
    div[data-testid="stToolbar"] { visibility: hidden; }
    button[data-testid="stSidebarCollapseButton"] { visibility: visible !important; }
    </style>
    """, unsafe_allow_html=True)

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
        st.session_state.update({"authenticated": False, "is_admin": False, "user_email": ""})

    if not st.session_state["authenticated"]:
        st.title("🔒 ログイン")
        email = st.text_input("メールアドレス")
        pw = st.text_input("パスワード", type="password")
        
        if st.button("ログイン"):
            if email == st.secrets["auth"]["admin_user"] and pw == st.secrets["auth"]["password"]:
                st.session_state.update({"authenticated": True, "is_admin": True, "user_email": email})
                st.rerun()
            else:
                user_doc = db.collection("users").document(email).get()
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    if user_data.get("is_enabled", True) and pw == st.secrets["auth"]["password"]:
                        st.session_state.update({"authenticated": True, "is_admin": False, "user_email": email})
                        st.rerun()
                    elif not user_data.get("is_enabled", True):
                        st.error("このアカウントは現在停止されています。")
                    else:
                        st.error("パスワードが違います")
                else:
                    st.error("アクセス権がありません")
        return False
    return True

# --- 3. メイン処理 ---
db = init_firebase()

if check_auth(db):
    st.sidebar.write(f"👤 {st.session_state['user_email']}")
    
    if st.session_state["is_admin"]:
        with st.sidebar.expander("🛠️ ユーザー管理システム"):
            st.subheader("新規招待")
            new_user = st.text_input("メアドを入力")
            if st.button("招待を追加"):
                if new_user:
                    db.collection("users").document(new_user).set({"is_enabled": True, "added_at": datetime.now()})
                    st.rerun()
            
            st.divider()
            users = db.collection("users").stream()
            for u in users:
                u_data = u.to_dict()
                col1, col2, col3 = st.columns([3, 2, 1])
                col1.caption(u.id)
                label = "✅" if u_data.get("is_enabled", True) else "🚫"
                if col2.button(label, key=f"user_t_{u.id}"):
                    db.collection("users").document(u.id).update({"is_enabled": not u_data.get("is_enabled", True)})
                    st.rerun()
                if col3.button("🗑️", key=f"user_d_{u.id}"):
                    db.collection("users").document(u.id).delete()
                    st.rerun()

    if st.sidebar.button("ログアウト"):
        st.session_state["authenticated"] = False
        st.rerun()

    st.title("📸 みんなの思い出帳")

    # 新規投稿フォーム
    with st.container():
        st.subheader("新しい思い出を投稿")
        with st.form("add_form", clear_on_submit=True):
            target_date = st.date_input("日付", datetime.now())
            new_comment = st.text_input("内容")
            uploaded_file = st.file_uploader("写真", type=["jpg", "png", "jpeg"])
            if st.form_submit_button("保存"):
                if new_comment:
                    db.collection("memories").add({
                        "comment": new_comment,
                        "date": datetime.combine(target_date, datetime.now().time()),
                        "author": st.session_state["user_email"]
                    })
                    st.success("保存しました！")
                    st.rerun()

    st.divider()

    # 投稿一覧（更新・削除機能付き）
    memories = db.collection("memories").order_by("date", direction=firestore.Query.DESCENDING).stream()
    for m in memories:
        data = m.to_dict()
        m_id = m.id
        date_str = data.get('date').strftime('%Y/%m/%d')
        comment = data.get('comment')
        author = data.get('author')

        # 投稿表示エリア
        with st.expander(f"📅 {date_str} | {comment} (by {author})", expanded=False):
            # 編集モードの管理
            edit_key = f"edit_{m_id}"
            if edit_key not in st.session_state:
                st.session_state[edit_key] = False

            if not st.session_state[edit_key]:
                col1, col2 = st.columns(2)
                if col1.button("✏️ 編集", key=f"btn_edit_{m_id}"):
                    st.session_state[edit_key] = True
                    st.rerun()
                
                # 削除ボタン（確認用）
                if col2.button("🗑️ 削除", key=f"btn_del_{m_id}"):
                    db.collection("memories").document(m_id).delete()
                    st.success("削除しました")
                    st.rerun()
            else:
                # 編集フォーム
                with st.form(f"form_edit_{m_id}"):
                    new_val = st.text_input("内容を修正", value=comment)
                    c1, c2 = st.columns(2)
                    if c1.form_submit_button("更新"):
                        db.collection("memories").document(m_id).update({"comment": new_val})
                        st.session_state[edit_key] = False
                        st.rerun()
                    if c2.form_submit_button("キャンセル"):
                        st.session_state[edit_key] = False
                        st.rerun()
