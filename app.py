import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
from datetime import datetime

# --- 追加：GitHubのリンクを隠し、矢印ボタンは残す設定 ---
st.set_page_config(layout="wide")
st.markdown("""
    <style>
    /* 右上のメニューボタン（GitHubリンク含む）を非表示 */
    div[data-testid="stToolbar"] { visibility: hidden; }
    /* 左側のサイドバー開閉ボタン（矢印）は表示 */
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
            # A. 管理者チェック
            if email == st.secrets["auth"]["admin_user"] and pw == st.secrets["auth"]["password"]:
                st.session_state.update({"authenticated": True, "is_admin": True, "user_email": email})
                st.rerun()
            # B. 招待ユーザーチェック (Firestore)
            else:
                user_doc = db.collection("users").document(email).get()
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    # ★「有効(enabled)」かつ「パスワード一致」かチェック
                    if user_data.get("is_enabled", True) and pw == st.secrets["auth"]["password"]:
                        st.session_state.update({"authenticated": True, "is_admin": False, "user_email": email})
                        st.rerun()
                    elif not user_data.get("is_enabled", True):
                        st.error("このアカウントは現在停止されています。管理者に連絡してください。")
                    else:
                        st.error("パスワードが違います")
                else:
                    st.error("アクセス権がありません")
        return False
    return True

# --- 3. メイン処理 ---
db = init_firebase()

if check_auth(db):
    # サイドバー：ユーザー情報とログアウト
    st.sidebar.write(f"👤 {st.session_state['user_email']}")
    
    # 🌟 スマートな管理画面 (管理者限定)
    if st.session_state["is_admin"]:
        with st.sidebar.expander("🛠️ ユーザー管理システム"):
            st.subheader("新規招待")
            new_user = st.text_input("メアドを入力")
            if st.button("招待を追加"):
                if new_user:
                    db.collection("users").document(new_user).set({
                        "is_enabled": True, # 初期状態は有効
                        "added_at": datetime.now()
                    })
                    st.toast(f"{new_user} を追加しました")
                    st.rerun()
            
            st.divider()
            st.subheader("管理リスト")
            users = db.collection("users").stream()
            for u in users:
                u_data = u.to_dict()
                u_email = u.id
                is_enabled = u_data.get("is_enabled", True)
                
                # GUIで「有効/無効」を切り替えるスイッチ
                col1, col2, col3 = st.columns([3, 2, 1])
                col1.caption(u_email)
                
                # 停止/再開ボタン
                label = "✅ 有効" if is_enabled else "🚫 停止中"
                if col2.button(label, key=f"toggle_{u_email}"):
                    db.collection("users").document(u_email).update({"is_enabled": not is_enabled})
                    st.rerun()
                
                # 完全に消すボタン
                if col3.button("🗑️", key=f"del_{u_email}"):
                    db.collection("users").document(u_email).delete()
                    st.rerun()

    if st.sidebar.button("ログアウト"):
        st.session_state["authenticated"] = False
        st.rerun()

    # --- アプリ本体 ---
    st.title("📸 みんなの思い出帳")

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
    memories = db.collection("memories").order_by("date", direction=firestore.Query.DESCENDING).stream()
    for m in memories:
        data = m.to_dict()
        st.info(f"{data.get('date').strftime('%Y/%m/%d')} | {data.get('comment')} (by {data.get('author')})")
