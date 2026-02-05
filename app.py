import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import os
from datetime import datetime

# 1. Firebaseの初期化
if not firebase_admin._apps:
　import json
　key_dict = json.loads(st.secrets["firebase_key"])
　cred = credentials.Certificate(key_dict)
　firebase_admin.initialize_app(cred)

db = firestore.client()

# 写真保存用のローカルフォルダ準備
UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

st.set_page_config(page_title="思い出マネージャー", page_icon="📸")
st.title("📸 写真と日付が選べる思い出帳")

# --- 入力エリア ---
with st.container():
    st.subheader("新しい思い出を投稿")
    with st.form("add_form", clear_on_submit=True):
        # 【復活】日付選択
        target_date = st.date_input("いつの思い出？", value=datetime.now())
        # コメント入力
        new_comment = st.text_input("どんな思い出？")
        # 【復活】写真選択
        uploaded_file = st.file_uploader("写真を選んでね", type=["jpg", "png", "jpeg"])
        
        submit_add = st.form_submit_button("保存")
        
        if submit_add and new_comment:
            img_name = ""
            # 写真があれば保存処理
            if uploaded_file:
                img_name = uploaded_file.name
                file_path = os.path.join(UPLOAD_DIR, img_name)
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
            
            # Firestoreに保存（日付は時間を合わせて保存）
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
    
    # 日付の安全な表示
    raw_date = data.get('date')
    date_str = raw_date.strftime('%Y/%m/%d') if hasattr(raw_date, 'strftime') else "日付なし"

    with st.expander(f"📌 {date_str}：{data.get('comment', '')[:15]}..."):
        # 編集モード
        edit_comment = st.text_input("内容を修正", value=data.get("comment", ""), key=f"edit_{doc_id}")
        
        # 画像の表示（PCにファイルがあれば）
        img_name = data.get("image_name")
        if img_name:
            img_path = os.path.join(UPLOAD_DIR, img_name)
            if os.path.exists(img_path):
                st.image(img_path, width=200)
            else:
                st.warning("画像ファイルがPC内に見つかりません")

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
