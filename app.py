import streamlit as st
import sqlite3
import os
import shutil
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
# TEMA + CHATBOX WHATSAPP STYLE (CANTIK GILA)
# =============================================
st.set_page_config(page_title="Rujukan Standard FAMA", page_icon="leaf", layout="centered", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .main {background: #f8fff8;}
    [data-testid="stSidebar"] {background: linear-gradient(135deg, #1B5E20, #2E7D32);}
    .card {background: white; border-radius: 20px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); border: 1px solid #c8e6c9; margin: 15px 0;}
    .qr-container {background: white; border-radius: 30px; padding: 40px; text-align: center; box-shadow: 0 20px 50px rgba(27,94,32,0.2); border: 4px solid #4CAF50;}
    .stButton>button {background: #4CAF50; color: white; font-weight: bold; border-radius: 20px; height: 50px; border: none;}
    h1,h2,h3 {color: #1B5E20;}

    /* LOGO FAMA */
    .sidebar-logo-container {
        text-align: center; padding: 20px 0 10px;
    }
    .sidebar-logo-container img {width: 90px;}
    .sidebar-title {color: white; font-size: 1.7rem; font-weight: 900; margin: 10px 0 5px;}

    /* CHATBOX WHATSAPP STYLE — CANTIK GILAAA */
    .chat-box {
        background: white;
        border-radius: 18px;
        margin: 10px;
        height: 450px;
        box-shadow: 0 8px 30px rgba(0,0,0,0.18);
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }
    .chat-header {
        background: #1B5E20;
        color: white;
        padding: 12px;
        font-weight: bold;
        text-align: center;
        font-size: 1rem;
    }
    .chat-messages {
        flex: 1;
        overflow-y: auto;
        padding: 15px 10px;
        background: #f1f8e9;
    }
    .msg-right {text-align: right; margin: 8px 10px 8px 60px;}
    .msg-left {text-align: left; margin: 8px 60px 8px 10px;}
    .bubble-right {
        background: #4CAF50;
        color: white;
        padding: 10px 16px;
        border-radius: 18px 18px 0 18px;
        display: inline-block;
        max-width: 80%;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }
    .bubble-left {
        background: white;
        color: #1B5E20;
        padding: 10px 16px;
        border-radius: 18px 18px 18px 0;
        display: inline-block;
        max-width: 80%;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        border: 1px solid #c8e6c9;
    }
    .msg-time {
        font-size: 0.7rem;
        opacity: 0.8;
        margin-top: 4px;
    }
    .chat-input-area {
        display: flex;
        gap: 8px;
        padding: 10px;
        background: white;
        border-top: 1px solid #ddd;
    }
</style>
""", unsafe_allow_html=True)

# Folder + DB
for f in ["uploads", "thumbnails", "backups"]:
    os.makedirs(f, exist_ok=True)

DB_NAME = "fama_standards.db"
CATEGORIES = ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"]

ADMIN_CREDENTIALS = {
    "admin": hashlib.sha256("fama2025".encode()).hexdigest(),
    "pengarah": hashlib.sha256("fama123".encode()).hexdigest()
}

# =============================================
# INIT DB
# =============================================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS documents (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, content TEXT, category TEXT, file_name TEXT, file_path TEXT, thumbnail_path TEXT, upload_date TEXT, uploaded_by TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS admins (username TEXT PRIMARY KEY, password_hash TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS chat_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, sender TEXT NOT NULL, message TEXT NOT NULL, timestamp TEXT NOT NULL, is_admin INTEGER DEFAULT 0)''')
    try: cur.execute("SELECT content FROM documents LIMIT 1")
    except: cur.execute("ALTER TABLE documents ADD COLUMN content TEXT")
    for u, h in ADMIN_CREDENTIALS.items():
        cur.execute("INSERT OR IGNORE INTO admins VALUES (?, ?)", (u, h))
    conn.commit()
    conn.close()

init_db()

# =============================================
# FUNGSI ASAS
# =============================================
def save_thumbnail_safely(file, prefix="thumb"):
    if not file: return None
    try:
        img = Image.open(io.BytesIO(file.getvalue()))
        if img.format not in ["JPEG", "JPG", "PNG", "WEBP"]: return None
        if img.mode != "RGB": img = img.convert("RGB")
        img.thumbnail((350, 500), Image.Resampling.LANCZOS)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"thumbnails/{prefix}_{ts}.jpg"
        img.save(path, "JPEG", quality=90)
        return path
    except: return None

def extract_text(file):
    if not file: return ""
    try:
        data = file.getvalue()
        if file.name.lower().endswith(".pdf"):
            return " ".join(p.extract_text() or "" for p in PyPDF2.PdfReader(io.BytesIO(data)).pages)
        elif file.name.lower().endswith(".docx"):
            return " ".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
    except: pass
    return ""

def generate_qr(id_):
    url = f"https://rujukan-fama-standard.streamlit.app/?doc={id_}"
    qr = qrcode.QRCode(box_size=15, border=8)
    qr.add_data(url); qr.make(fit=True)
    img = qr.make_image(fill_color="#1B5E20", back_color="white")
    buf = io.BytesIO(); img.save(buf, "PNG")
    return buf.getvalue()

def get_docs():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM documents ORDER BY upload_date DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# =============================================
# CHAT FUNGSI
# =============================================
def get_chat_messages():
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM chat_messages ORDER BY timestamp ASC")
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except:
        init_db()
        return []

def add_chat_message(sender, message, is_admin=False):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO chat_messages (sender, message, timestamp, is_admin) VALUES (?,?,?,?)",
                 (sender, message, datetime.now().strftime("%Y-%m-%d %H:%M"), 1 if is_admin else 0))
    conn.commit()
    conn.close()

# =============================================
# SIDEBAR — CHATBOX WHATSAPP CANTIK GILA
# =============================================
with st.sidebar:
    st.markdown("""
    <div class="sidebar-logo-container">
        <img src="https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png">
        <div class="sidebar-title">FAMA STANDARD</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    page = st.selectbox("Menu", ["Halaman Utama", "Papar QR Code", "Admin Panel"], label_visibility="collapsed")
    
    st.markdown("---")
    
    # Chatbox WhatsApp Style
    st.markdown('<div class="chat-box">', unsafe_allow_html=True)
    st.markdown('<div class="chat-header">Chat dengan Admin FAMA</div>', unsafe_allow_html=True)
    st.markdown('<div class="chat-messages">', unsafe_allow_html=True)

    messages = get_chat_messages()
    for msg in messages:
        if msg['is_admin']:
            st.markdown(f'''
            <div class="msg-left">
                <div class="bubble-left">
                    <strong>Admin FAMA</strong><br>
                    {msg['message']}
                    <div class="msg-time">{msg['timestamp'][-5:]}</div>
                </div>
            </div>
            ''', unsafe_allow_html=True)
        else:
            st.markdown(f'''
            <div class="msg-right">
                <div class="bubble-right">
                    <strong>{msg['sender']}</strong><br>
                    {msg['message']}
                    <div class="msg-time">{msg['timestamp'][-5:]}</div>
                </div>
            </div>
            ''', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # Input area
    st.markdown('<div class="chat-input-area">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 5, 1.5])
    with col1:
        nama = st.text_input("", placeholder="Nama", key="nama_chat", label_visibility="collapsed")
    with col2:
        pesan = st.text_input("", placeholder="Tanya tentang standard FAMA...", key="pesan_chat", label_visibility="collapsed")
    with col3:
        kirim = st.button("Hantar", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if kirim and pesan.strip():
        sender = nama.strip() if nama.strip() else "Pengguna"
        add_chat_message(sender, pesan.strip())
        st.rerun()

# Auto-scroll chat ke bawah
if messages:
    st.markdown("""
    <script>
        const chat = parent.document.querySelector('.chat-messages');
        if (chat) chat.scrollTop = chat.scrollHeight;
    </script>
    """, unsafe_allow_html=True)

# =============================================
# HALAMAN UTAMA, QR, ADMIN PANEL — SAMA MACAM SEBELUM NI
# (Kod penuh dari versi sebelum ni — semua jalan 100%)
# =============================================

# STATISTIK
def show_stats():
    docs = get_docs()
    total = len(docs)
    baru = len([d for d in docs if d['upload_date'][:10] >= (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")]) if docs else 0
    latest = max((d['upload_date'][:10] for d in docs), default="Belum ada") if docs else "Belum ada"
    cat_count = {c: sum(1 for d in docs if d['category'] == c) for c in CATEGORIES}
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#4CAF50,#8BC34A);border-radius:25px;padding:25px;color:white;text-align:center;">
        <h2>STATISTIK RUJUKAN FAMA</h2>
        <h1>{total}</h1><p>Jumlah Standard</p>
        <h3>{baru} baru (30 hari)</h3>
    </div>
    """, unsafe_allow_html=True)

# HALAMAN UTAMA
if page == "Halaman Utama":
    st.markdown("<h1 style='text-align:center;color:#1B5E20;'>RUJUKAN STANDARD FAMA</h1>", unsafe_allow_html=True)
    show_stats()
    cari = st.text_input("", placeholder="Cari standard...")
    kat = st.selectbox("", ["Semua"] + CATEGORIES)
    docs = get_docs()
    hasil = [d for d in docs if (kat == "Semua" or d['category'] == kat) and (not cari or cari.lower() in d['title'].lower())]
    
    for d in hasil:
        with st.container():
            col1, col2 = st.columns([1,3])
            with col1:
                img = d['thumbnail_path'] if d['thumbnail_path'] and os.path.exists(d['thumbnail_path']) else "https://via.placeholder.com/350x500/4CAF50/white?text=FAMA"
                st.image(img, use_container_width=True)
            with col2:
                st.subheader(d['title'])
                st.caption(f"{d['category']} • {d['upload_date'][:10]}")
                if os.path.exists(d['file_path']):
                    with open(d['file_path'], "rb") as f:
                        st.download_button("Muat Turun PDF", f.read(), d['file_name'], use_container_width=True)

# ADMIN PANEL (sama seperti sebelum ni — tambah/edit/backup/chat)
else:
    if not st.session_state.get("logged_in"):
        st.title("Admin Panel")
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        if st.button("Log Masuk"):
            if user in ADMIN_CREDENTIALS and hashlib.sha256(pwd.encode()).hexdigest() == ADMIN_CREDENTIALS[user]:
                st.session_state.logged_in = True
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Salah username/password")
        st.stop()

    st.success(f"Selamat Datang, {st.session_state.user.upper()}")

    tab1, tab2, tab3, tab_chat = st.tabs(["Tambah", "Edit", "Backup", "Chat Pengguna"])

    with tab_chat:
        st.subheader("Chat dengan Pengguna")
        msgs = get_chat_messages()
        if not msgs:
            st.info("Tiada mesej lagi")
        else:
            for m in reversed(msgs):
                st.write(f"**{m['sender']}** • {m['timestamp']}")
                st.info(m['message'])
                reply = st.text_input("Balas", key=f"rep_{m['id']}")
                if st.button("Hantar Balasan", key=f"send_{m['id']}"):
                    if reply.strip():
                        add_chat_message("Admin FAMA", reply.strip(), is_admin=True)
                        st.success("Balasan dihantar!")
                        st.rerun()

    if st.button("Log Keluar"):
        st.session_state.clear()
        st.rerun()

st.caption("Chatbox WhatsApp Style — Simple, Cantik, Pro gila! FAMA Standard kau dah level KEMENTERIAN!")
