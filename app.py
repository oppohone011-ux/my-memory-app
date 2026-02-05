import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import json
from datetime import datetime

# --- 0. 画面設定 ---
st.set_page_config(
    page_title="みんなの思い出帳",
    layout="centered",      
    initial_sidebar_state="expanded" 
)

# ダークモード対策 ＆ GitHubボタン隠し
hide_style = """
            <style>
            #MainMenu {visibility: hidden;}
            header {visibility: hidden;}
            footer {visibility: hidden;}
            /* サイドバー内の文字色を強制的に白くする */
            [data-testid="stSidebar"] .stMarkdown p {
                color: #FFFFFF !important;
            }
            </style>
            """
st.markdown(hide_style, unsafe_allow_html=True)

# --- 1. Firebase初期化 ---
def init_firebase():
    if not firebase_admin._apps:
        key_dict = json.loads(st.secrets["firebase_key"])
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
    return firestore.client()

# --- 2. 認証ロジック ---
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
    # --- サイドバー：ログイン状況 ＆ 管理機能 ---
    st.sidebar.markdown("### 👤 ログイン状況")
    st.sidebar.write(f"**{st.session_state['user_email']}**")
    
    if st.sidebar.button("ログアウト", use_container_width=True):
        st.session_state["authenticated"] = False
        st.rerun()

    st.sidebar.divider()

    # 🌟 管理者権限がある場合のみ表示される「管理リスト」
    if st.session_state["is_admin"]:
        st.sidebar.subheader("🛠️ ユーザー管理")
        
        # 新規追加
        new_user = st.text_input("新規招待メアド", key="new_user_input")
        if st.sidebar.button("追加実行"):
            if new_user:
                db.collection("users").document(new_user).set({
                    "is_enabled": True,
                    "added_at": datetime.now()
                })
                st.toast(f"{new_user}を追加しました")
                st.rerun()
        
        st.sidebar.divider()
        st.sidebar.write("【登録済みリスト】")
        
        # ★ここを復活させました！ユーザーの有効/停止/削除
        users = db.collection("users").stream()
        for u in users:
            u_data = u.to_dict()
            u_email = u.id
            is_enabled = u_data.get("is_enabled", True)
            
            # メールアドレス表示
            st.sidebar.caption(u_email)
            
            col1, col2 = st.sidebar.columns([2, 1])
            # 有効・停止の切り替えボタン
            label = "✅ 有効" if is_enabled else "🚫 停止"
            if col1.button(label, key=f"toggle_{u_email}"):
                db.collection("users").document(u_email).update({"is_enabled": not is_enabled})
                st.rerun()
            
            # 削除ボタン
            if col2.button("🗑️", key=f"del_{u_email}"):
                db.collection("users").document(u_email).delete()
                st.rerun()
            st.sidebar.write("---")

    # --- アプリ本体 ---
    st.title("📸 みんなの思い出帳")

    # 投稿フォーム
    with st.form("add_form", clear_on_submit=True):
        st.subheader("新しい思い出を投稿")
        target_date = st.date_input("日付", datetime.now())
        new_comment = st.text_input("内容")
        uploaded_file = st.file_uploader("写真を選択", type=["jpg", "png", "jpeg"]) 
        
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
    # 投稿一覧
    memories = db.collection("memories").order_by("date", direction=firestore.Query.DESCENDING).stream()
    for m in memories:
        data = m.to_dict()
        d = data.get('date')
        date_str = d.strftime('%Y/%m/%d') if d else ""
        st.info(f"{date_str} | {data.get('comment')} (by {data.get('author')})")
