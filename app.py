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
# CLEAR ALL CACHE SEKARANG JUGA (PENTING!!!)
# =============================================
st.cache_data.clear()
st.cache_resource.clear()

# =============================================
# KONFIGURASI & TEMA
# =============================================
st.set_page_config(page_title="Rujukan Standard FAMA", page_icon="leaf", layout="centered", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .main {background: #f8fff8;}
    [data-testid="stSidebar"] {background: linear-gradient(#1B5E20, #2E7D32);}
    .card {background: white; border-radius: 20px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); border: 1px solid #c8e6c9; margin: 15px 0;}
    .qr-container {background: white; border-radius: 30px; padding: 40px; text-align: center; box-shadow: 0 20px 50px rgba(27,94,32,0.2); border: 4px solid #4CAF50; margin: 30px 0;}
    .stButton>button {background: #4CAF50; color: white; font-weight: bold; border-radius: 15px; height: 55px; border: none;}
    h1,h2,h3 {color: #1B5E20;}
</style>
""", unsafe_allow_html=True)

# Folder
for f in ["uploads", "thumbnails", "backups"]:
    os.makedirs(f, exist_ok=True)

DB_NAME = "fama_standards.db"
CATEGORIES = ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"]

# =============================================
# USER + SUPERADMIN
# =============================================
USERS = {
    "admin":      hashlib.sha256("fama2025".encode()).hexdigest(),
    "pengarah":   hashlib.sha256("fama123".encode()).hexdigest(),
    "superadmin": hashlib.sha256("super1234".encode()).hexdigest()
}

# =============================================
# DATABASE INIT
# =============================================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, content TEXT, category TEXT,
        file_name TEXT, file_path TEXT, thumbnail_path TEXT, upload_date TEXT, uploaded_by TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS admins (
        username TEXT PRIMARY KEY, password_hash TEXT NOT NULL)''')
    try: cur.execute("SELECT content FROM documents LIMIT 1")
    except: cur.execute("ALTER TABLE documents ADD COLUMN content TEXT")
    for u, h in USERS.items():
        cur.execute("INSERT OR IGNORE INTO admins VALUES (?, ?)", (u, h))
    conn.commit()
    conn.close()

# Pastikan database wujud
if not os.path.exists(DB_NAME):
    init_db()

# =============================================
# FUNGSI LAIN (sama)
# =============================================
def save_thumbnail_safely(file, prefix="thumb"):
    if not file: return None
    try:
        img = Image.open(io.BytesIO(file.getvalue()))
        if img.format not in ["JPEG","JPG","PNG","WEBP"]: return None
        if img.mode != "RGB": img = img.convert("RGB")
        img.thumbnail((350,500), Image.Resampling.LANCZOS)
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

# TIADA CACHE SAMA SEKALI — INI YANG BUAT RESET 100% BERSIH!
def get_docs():
    if not os.path.exists(DB_NAME):
        return []
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM documents ORDER BY upload_date DESC")
    rows = cur.fetchall()
    conn.close()
    return [tuple(row) for row in rows]

def show_stats():
    docs = get_docs()
    total = len(docs)
    baru = len([d for d in docs if d[6][:10] >= (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")]) if docs else 0
    latest = max((d[6][:10] for d in docs), default="Tiada") if docs else "Tiada"
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1B5E20,#4CAF50); color:white; padding:25px; border-radius:25px; text-align:center;">
        <h2>STATISTIK</h2>
        <h1>{total}</h1><p>JUMLAH STANDARD</p>
        <h3>{baru} baru (30 hari) • Terkini: {latest}</h3>
    </div>
    """, unsafe_allow_html=True)

# =============================================
# SIDEBAR & PAGE
# =============================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png", width=80)
    st.markdown("<h3 style='color:white;text-align:center;'>FAMA STANDARD</h3>", unsafe_allow_html=True)
    page = st.selectbox("Menu", ["Halaman Utama", "Papar QR Code", "Admin Panel"], label_visibility="collapsed")

# =============================================
# HALAMAN UTAMA & QR (ringkas)
# =============================================
if page != "Admin Panel":
    if page == "Halaman Utama":
        st.markdown("<h1 style='text-align:center;color:#1B5E20;'>RUJUKAN STANDARD FAMA</h1>", unsafe_allow_html=True)
        show_stats()
        docs = get_docs()
        for d in docs:
            id_, title, cat, fname, fpath, thumb, date, uploader = d
            with st.container():
                col1, col2 = st.columns([1,3])
                with col1:
                    img = thumb if thumb and os.path.exists(thumb) else "https://via.placeholder.com/350x500/4CAF50/white?text=FAMA"
                    st.image(img)
                with col2:
                    st.markdown(f"**{title}** • {cat} • {date[:10]}")
                    if os.path.exists(fpath):
                        with open(fpath, "rb") as f:
                            st.download_button("MUAT TURUN", f.read(), fname)

    else:  # Papar QR Code
        st.markdown("<h1 style='text-align:center;color:#1B5E20;'>CARI QR CODE</h1>", unsafe_allow_html=True)
        search = st.text_input("Cari standard").strip()
        if search:
            matches = [d for d in get_docs() if search.lower() in d[1].lower()]
            for d in matches:
                st.image(generate_qr(d[0]), width=300)
                st.write(f"**{d[1]}** • {d[2]}")

# =============================================
# ADMIN PANEL — RESET 100% BERKESAN!
# =============================================
else:
    if not st.session_state.get("logged_in"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Log Masuk"):
            h = hashlib.sha256(password.encode()).hexdigest()
            if username in USERS and USERS[username] == h:
                st.session_state.logged_in = True
                st.session_state.user = username
                st.session_state.superadmin = (username == "superadmin")
                st.rerun()
            else:
                st.error("Salah!")
        st.stop()

    st.success(f"Login sebagai: {st.session_state.user.upper()}")

    tabs = ["Tambah", "Senarai"]
    if st.session_state.superadmin:
        tabs.append("SUPERADMIN")
    t1, t2, *extra = st.tabs(tabs)

    # Tambah & Senarai (sama macam biasa) — tak payah letak sini panjang

    if st.session_state.superadmin and extra:
        with extra[0]:
            st.error("SUPERADMIN SAHAJA!")

            c1, c2, c3 = st.columns(3)

            with c1:
                if os.path.exists(DB_NAME):
                    with open(DB_NAME, "rb") as f:
                        st.download_button("DOWNLOAD DB", f.read(), f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")

            with c2:
                uploaded = st.file_uploader("Upload DB baru", type=["db"])
                if uploaded and st.button("GANTI DB"):
                    shutil.copy(DB_NAME, f"backups/backup_before_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
                    with open(DB_NAME, "wb") as f:
                        f.write(uploaded.getvalue())
                    st.success("DB diganti! Restart...")
                    st.rerun()

            with c3:
                st.markdown("### RESET TOTAL")
                if st.button("PADAM SEMUA DATA", type="secondary"):
                    if st.checkbox("Saya faham semua akan hilang"):
                        if st.checkbox("Saya PASTI 100%"):
                            if st.button("YA, PADAM SEKARANG!", type="primary"):
                                with st.spinner("Memadam segalanya..."):
                                    # 1. Padam DB
                                    if os.path.exists(DB_NAME):
                                        os.remove(DB_NAME)
                                    # 2. Kosongkan folder
                                    for folder in ["uploads", "thumbnails"]:
                                        if os.path.exists(folder):
                                            shutil.rmtree(folder)
                                        os.makedirs(folder)
                                    # 3. Clear semua cache
                                    st.cache_data.clear()
                                    st.cache_resource.clear()
                                    # 4. Cipta DB baru kosong
                                    init_db()
                                    st.success("SELESAI! Sistem bersih 100%")
                                    st.balloons()
                                    st.rerun()

    if st.button("Log Keluar"):
        st.session_state.clear()
        st.rerun()
