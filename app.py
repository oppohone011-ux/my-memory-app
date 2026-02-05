import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
from datetime import datetime

# --- 0. 外観の設定（矢印ボタンを残し、GitHubメニューだけ消す） ---
# ログイン画面をシュッとさせるために最初は centered、ログイン後は wide
if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.set_page_config(layout="centered")
else:
    st.set_page_config(layout="wide")

# 強力な「特定狙い撃ち」のCSS
hide_github_only = """
    <style>
    /* ヘッダー全体を消すのではなく、右側のメニューエリアだけを完全に消す */
    [data-testid="stToolbar"] {
        display: none !important;
    }
    /* ログイン画面でデカくなりすぎないよう調整 */
    .stTextInput {
        max-width: 500px;
        margin: 0 auto;
    }
    /* サイドバー開閉ボタン（矢印）は絶対に表示する */
    header button {
        visibility: visible !important;
    }
    </style>
    """
st.markdown(hide_github_only, unsafe_allow_html=True)

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
        
        if st.button("ログイン", use_container_width=True):
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
                    else:
                        st.error("アクセスできません")
                else:
                    st.error("登録されていません")
        return False
    return True

# --- 3. メイン処理 ---
db = init_firebase()

if check_auth(db):
    # サイドバー：ユーザー情報とログアウト
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
                if col2.button(label, key=f"t_{u.id}"):
                    db.collection("users").document(u.id).update({"is_enabled": not u_data.get("is_enabled", True)})
                    st.rerun()
                if col3.button("🗑️", key=f"d_{u.id}"):
                    db.collection("users").document(u.id).delete()
                    st.rerun()

    if st.sidebar.button("ログアウト", use_container_width=True):
        st.session_state["authenticated"] = False
        st.rerun()

    # --- アプリ本体 ---
    st.title("📸 みんなの思い出帳")

    with st.form("add_form", clear_on_submit=True):
        st.subheader("新しい思い出を投稿")
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
                st.success("保存完了！")
                st.rerun()

    st.divider()
    memories = db.collection("memories").order_by("date", direction=firestore.Query.DESCENDING).stream()
    for m in memories:
        data = m.to_dict()
        st.info(f"{data.get('date').strftime('%Y/%m/%d')} | {data.get('comment')} (by {data.get('author')})")
