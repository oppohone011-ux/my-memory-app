import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import json
from datetime import datetime

# --- 0. 画面設定 ---
st.set_page_config(
    page_title="みんなの思い出帳",
    layout="centered",      
    initial_sidebar_state="auto" # ログイン後は自動で最適な状態に
)

# ダークモードでも見やすく、かつGitHubボタンを隠す設定
hide_style = """
            <style>
            #MainMenu {visibility: hidden;}
            header {visibility: hidden;}
            footer {visibility: hidden;}
            /* ダークモードでの視認性アップ */
            .stApp {
                background-color: #0E1117;
            }
            /* 入力欄の枠線を少し強調 */
            .stTextInput>div>div>input {
                border-color: #4E4E4E;
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

# --- 2. 認証・ユーザー管理ロジック ---
def check_auth(db):
    if "authenticated" not in st.session_state:
        st.session_state.update({"authenticated": False, "is_admin": False, "user_email": ""})

    if not st.session_state["authenticated"]:
        # ログイン前はサイドバーを完全に消して中央に集中させる
        st.markdown("<style>section[data-testid='stSidebar'] {display: none;}</style>", unsafe_allow_html=True)
        
        st.title("🔒 ログイン")
        st.write("メールアドレスとパスワードを入力してください")
        
        email = st.text_input("メールアドレス")
        pw = st.text_input("パスワード", type="password")
        
        if st.button("ログインして開始", use_container_width=True):
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
                        st.error("パスワードが違うか、アカウントが無効です")
                else:
                    st.error("アクセス権がありません")
        return False
    return True

# --- 3. メイン処理 ---
db = init_firebase()

if check_auth(db):
    # --- ログイン後：サイドバーを復活させる ---
    # ここでメニューを折り畳めるように表示
    st.sidebar.title("👤 ユーザー設定")
    st.sidebar.info(f"ログイン中:\n{st.session_state['user_email']}")
    
    if st.session_state["is_admin"]:
        with st.sidebar.expander("🛠️ ユーザー管理"):
            new_user = st.text_input("招待するメアド")
            if st.button("追加"):
                if new_user:
                    db.collection("users").document(new_user).set({
                        "is_enabled": True,
                        "added_at": datetime.now()
                    })
                    st.toast("追加完了！")
                    st.rerun()
            
            st.divider()
            users = db.collection("users").stream()
            for u in users:
                u_data = u.to_dict()
                col1, col2 = st.columns([2, 1])
                col1.caption(u.id)
                if col2.button("🗑️", key=f"del_{u.id}"):
                    db.collection("users").document(u.id).delete()
                    st.rerun()

    if st.sidebar.button("ログアウト", use_container_width=True):
        st.session_state["authenticated"] = False
        st.rerun()

    # --- アプリ本体 ---
    st.title("📸 みんなの思い出帳")

    with st.expander("📝 新しい思い出を投稿する", expanded=False):
        with st.form("add_form", clear_on_submit=True):
            target_date = st.date_input("日付", datetime.now())
            new_comment = st.text_input("内容を入力")
            if st.form_submit_button("思い出を保存"):
                if new_comment:
                    db.collection("memories").add({
                        "comment": new_comment,
                        "date": datetime.combine(target_date, datetime.now().time()),
                        "author": st.session_state["user_email"]
                    })
                    st.success("保存完了！")
                    st.rerun()

    st.divider()
    # 投稿一覧
    memories = db.collection("memories").order_by("date", direction=firestore.Query.DESCENDING).stream()
    for m in memories:
        data = m.to_dict()
        d = data.get('date')
        date_str = d.strftime('%Y/%m/%d') if d else "不明"
        st.info(f"📅 {date_str} | {data.get('comment')}\n(by {data.get('author')})")
