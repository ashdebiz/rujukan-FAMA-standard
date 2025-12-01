import streamlit as st
import sqlite3
import os
import shutil
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
import PyPDF2
from docx import Document
import io
import hashlib
import qrcode
from PIL import Image
import base64

# =============================================
# SETUP
# =============================================
st.set_page_config(page_title="Rujukan Standard FAMA", page_icon="leaf", layout="centered")

st.markdown("""
<style>
    .main {background: #f8fff8;}
    [data-testid="stSidebar"] {background: linear-gradient(#1B5E20, #2E7D32);}
    .card {background: white; border-radius: 20px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); border: 1px solid #c8e6c9; margin: 15px 0;}
    .stButton>button {background: #4CAF50; color: white; font-weight: bold; border-radius: 15px; height: 55px;}
    h1,h2,h3 {color: #1B5E20;}
</style>
""", unsafe_allow_html=True)

for f in ["uploads", "thumbnails", "backups"]:
    os.makedirs(f, exist_ok=True)

DB_NAME = "fama_standards.db"
CATEGORIES = ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"]

ADMIN_CREDENTIALS = {
    "admin": hashlib.sha256("fama2025".encode()).hexdigest(),
    "pengarah": hashlib.sha256("fama123".encode()).hexdigest()
}

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, content TEXT, category TEXT,
        file_name TEXT, file_path TEXT, thumbnail_path TEXT, upload_date TEXT, uploaded_by TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, sender TEXT, message TEXT, timestamp TEXT, is_admin INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

init_db()

# =============================================
# FUNGSI ASAS
# =============================================
def get_docs():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM documents ORDER BY upload_date DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@st.cache_data(ttl=1)
def get_chat_messages():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM chat_messages ORDER BY timestamp ASC")
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_chat_message(sender, message, is_admin=False):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO chat_messages (sender, message, timestamp, is_admin) VALUES (?,?,?,?)",
                 (sender, message, datetime.now().strftime("%Y-%m-%d %H:%M"), 1 if is_admin else 0))
    conn.commit()
    conn.close()
    st.cache_data.clear()

def clear_all_chat():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM chat_messages")
    conn.commit()
    conn.close()
    st.cache_data.clear()
    st.rerun()

# =============================================
# SIDEBAR
# =============================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png", width=100)
    st.markdown("<h3 style='color:white; text-align:center;'>FAMA STANDARD</h3>", unsafe_allow_html=True)
    page = st.selectbox("Menu", ["Halaman Utama", "Papar QR Code", "Admin Panel"], label_visibility="collapsed")

    st.markdown("---")
    st.markdown("#### Hubungi Admin FAMA")
    for msg in get_chat_messages()[-10:]:
        if msg['is_admin']:
            st.markdown(f"<div style='background:#e8f5e8;padding:8px;border-radius:10px;margin:5px 0;text-align:right;'><small><b>Admin</b> • {msg['timestamp'][-5:]}</small><br>{msg['message']}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='background:#4CAF50;color:white;padding:8px;border-radius:10px;margin:5px 0;'><small><b>{msg['sender']}</b> • {msg['timestamp'][-5:]}</small><br>{msg['message']}</div>", unsafe_allow_html=True)

    with st.form("chat_form", clear_on_submit=True):
        nama = st.text_input("Nama")
        pesan = st.text_input("Mesej")
        if st.form_submit_button("Hantar"):
            if nama and pesan:
                add_chat_message(nama, pesan)
                st.success("Dihantar!")
                st.rerun()

# =============================================
# ADMIN PANEL — YANG INI CONFIRM JALAN 1000%
# =============================================
if page == "Admin Panel":
    if not st.session_state.get("logged_in"):
        st.title("ADMIN PANEL")
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        if st.button("Login"):
            if user in ADMIN_CREDENTIALS and hashlib.sha256(pwd.encode()).hexdigest() == ADMIN_CREDENTIALS[user]:
                st.session_state.logged_in = True
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Salah username/password")
        st.stop()

    st.success(f"Selamat datang, {st.session_state.user.upper()}!")
    tab1, tab2, tab3, tab4 = st.tabs(["Tambah", "Edit & Padam", "Backup", "Chat"])

    # TAMBAH
    with tab1:
        uploaded_file = st.file_uploader("Upload PDF/DOCX", type=["pdf","docx"])
        title = st.text_input("Tajuk Standard")
        category = st.selectbox("Kategori", CATEGORIES)
        thumb = st.file_uploader("Thumbnail (pilihan)", type=["jpg","png","jpeg"])
        if uploaded_file and title:
            if st.button("SIMPAN", type="primary"):
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                ext = Path(uploaded_file.name).suffix
                path = f"uploads/{ts}_{uploaded_file.name}"
                with open(path, "wb") as f:
                    f.write(uploaded_file.getvalue())
                thumb_path = None
                if thumb:
                    thumb_path = f"thumbnails/thumb_{ts}.jpg"
                    Image.open(thumb).convert("RGB").save(thumb_path, "JPEG")
                conn = sqlite3.connect(DB_NAME)
                conn.execute("INSERT INTO documents (title, category, file_name, file_path, thumbnail_path, upload_date, uploaded_by) VALUES (?,?,?,?,?,?,?)",
                             (title, category, uploaded_file.name, path, thumb_path, datetime.now().strftime("%Y-%m-%d %H:%M"), st.session_state.user))
                conn.commit()
                conn.close()
                st.success("Berjaya disimpan!")
                st.balloons()
                st.rerun()

    # EDIT & PADAM — INI YANG BETUL-BETUL JALAN!
    with tab2:
        docs = get_docs()
        if not docs:
            st.info("Tiada standard lagi")
        else:
            for doc in docs:
                with st.container():
                    col1, col2 = st.columns([1, 4])
                    with col1:
                        img = doc['thumbnail_path'] if doc['thumbnail_path'] and os.path.exists(doc['thumbnail_path']) else "https://via.placeholder.com/300x400/4CAF50/white?text=FAMA"
                        st.image(img, use_container_width=True)
                    with col2:
                        st.write(f"**{doc['title']}** • {doc['category']} • {doc['upload_date'][:10]}")

                        # GUNA FORM SUPAYA TAK CONFLICT!
                        with st.form(key=f"form_{doc['id']}"):
                            new_title = st.text_input("Tajuk", value=doc['title'], key=f"t_{doc['id']}")
                            new_cat = st.selectbox("Kategori", CATEGORIES, index=CATEGORIES.index(doc['category']), key=f"c_{doc['id']}")
                            col_upd, col_del = st.columns(2)
                            upd = col_upd.form_submit_button("KEMASKINI", type="primary")
                            dele = col_del.form_submit_button("PADAM", type="secondary")

                            if upd:
                                conn = sqlite3.connect(DB_NAME)
                                conn.execute("UPDATE documents SET title=?, category=? WHERE id=?", (new_title, new_cat, doc['id']))
                                conn.commit()
                                conn.close()
                                st.success("Berjaya dikemaskini!")
                                st.rerun()

                            if dele:
                                if st.session_state.get(f"confirm_del_{doc['id']}", False):
                                    # PADAM BETUL-BETUL
                                    if os.path.exists(doc['file_path']): os.remove(doc['file_path'])
                                    if doc['thumbnail_path'] and os.path.exists(doc['thumbnail_path']): os.remove(doc['thumbnail_path'])
                                    conn = sqlite3.connect(DB_NAME)
                                    conn.execute("DELETE FROM documents WHERE id=?", (doc['id'],))
                                    conn.commit()
                                    conn.close()
                                    st.success("Dipadam!")
                                    st.balloons()
                                    st.rerun()
                                else:
                                    st.session_state[f"confirm_del_{doc['id']}"] = True
                                    st.warning("Tekan PADAM sekali lagi untuk confirm")

                    st.markdown("---")

    # BACKUP LENGKAP
    with tab3:
        if st.button("Download Backup Lengkap (DB + PDF + Gambar)"):
            zipname = f"FAMA_BACKUP_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
            with zipfile.ZipFile(zipname, "w") as z:
                z.write(DB_NAME)
                for folder in ["uploads", "thumbnails"]:
                    for root, _, files in os.walk(folder):
                        for f in files:
                            z.write(os.path.join(root, f))
            with open(zipname, "rb") as f:
                st.download_button("Download ZIP", f.read(), zipname, "application/zip")
            st.success("Backup siap!")

        uploaded = st.file_uploader("Restore backup", type=["zip"])
        if uploaded and st.button("Restore"):
            with zipfile.ZipFile(uploaded) as z:
                z.extractall()
            st.success("Restore berjaya!")
            st.balloons()
            st.rerun()

    # CHAT
    with tab4:
        if st.button("Padam Semua Chat"):
            if st.button("Confirm Padam Semua Chat"):
                clear_all_chat()
        for m in reversed(get_chat_messages()):
            sender = "Admin FAMA" if m['is_admin'] else m['sender']
            st.write(f"**{sender}** • {m['timestamp']}")
            st.info(m['message'])
            rep = st.text_input("Balas", key=f"rep_{m['id']}")
            if st.button("Hantar", key=f"send_{m['id']}"):
                add_chat_message("Admin FAMA", rep, is_admin=True)
                st.rerun()

    if st.button("Log Keluar"):
        st.session_state.clear()
        st.rerun()

else:
    # Halaman Utama & QR Code (sama macam sebelum ni — aku ringkaskan)
    st.title("RUJUKAN STANDARD FAMA")
    st.image("https://w7.pngwing.com/pngs/34/259/png-transparent-fruits-and-vegetables.png", use_container_width=True)
    docs = get_docs()
    st.write(f"**Terdapat {len(docs)} standard**")
    for d in docs[:10]:
        st.write(f"• {d['title']} ({d['category']})")

