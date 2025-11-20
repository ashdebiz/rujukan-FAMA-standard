import streamlit as st
import sqlite3
import os
import shutil
from datetime import datetime
from pathlib import Path
import PyPDF2
from docx import Document
import io
import hashlib
import qrcode
from PIL import Image

# =============================================
# TEMA CANTIK FAMA
# =============================================
st.set_page_config(page_title="Rujukan Standard FAMA", page_icon="rice", layout="centered")

st.markdown("""
<style>
    .main {background: #f8fff8;}
    [data-testid="stSidebar"] {background: linear-gradient(#1B5E20, #2E7D32);}
    .header-container {
        position: relative; overflow: hidden; border-radius: 25px;
        box-shadow: 0 15px 40px rgba(27,94,32,0.5); margin: 20px 0;
    }
    .card {background: white; border-radius: 20px; padding: 20px; 
            box-shadow: 0 10px 30px rgba(0,0,0,0.1); border: 1px solid #c8e6c9; margin: 15px 0;}
    .stButton>button {background: #4CAF50; color: white; font-weight: bold; 
                      border-radius: 15px; height: 50px; border: none;}
    h1,h2,h3 {color: #1B5E20;}
</style>
""", unsafe_allow_html=True)

os.makedirs("uploads", exist_ok=True)
os.makedirs("thumbnails", exist_ok=True)

DB_NAME = "fama_standards.db"
CATEGORIES = ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"]

def init_db():
    conn = sqlite3.connect(DB_NAME)
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT,
            category TEXT,
            file_name TEXT,
            file_path TEXT,
            thumbnail_path TEXT,
            upload_date TEXT,
            uploaded_by TEXT
        );
        CREATE TABLE IF NOT EXISTS admins (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL
        );
    ''')
    conn.execute("INSERT OR IGNORE INTO admins VALUES ('admin', ?)", (hashlib.sha256("fama2025".encode()).hexdigest(),))
    conn.execute("INSERT OR IGNORE INTO admins VALUES ('pengarah', ?)", (hashlib.sha256("fama123".encode()).hexdigest(),))
    conn.commit()
    conn.close()
init_db()

def extract_text(file):
    if not file: return ""
    try:
        data = file.getvalue() if hasattr(file, 'getvalue') else file.read()
        if str(file.name).lower().endswith(".pdf"):
            return " ".join(p.extract_text() or "" for p in PyPDF2.PdfReader(io.BytesIO(data)).pages)
        elif str(file.name).lower().endswith(".docx"):
            return " ".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
    except: pass
    return ""

def generate_qr(id_):
    url = f"https://rujukan-fama-standard.streamlit.app/?doc={id_}"
    qr = qrcode.QRCode(box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1B5E20", back_color="white")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()

def get_docs():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.execute("SELECT id, title, category, file_name, file_path, thumbnail_path, upload_date, uploaded_by FROM documents ORDER BY id DESC")
    docs = cur.fetchall()
    conn.close()
    return docs

# =============================================
# SIDEBAR — LOGO FAMA KECIK TENGAH
# =============================================
with st.sidebar:
    st.markdown("""
    <div style="text-align: center; padding: 20px 0;">
        <img src="https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png" width="80">
        <h3 style="color:white; margin:15px 0 0 0; font-weight: bold;">FAMA STANDARD</h3>
        <p style="color:#c8e6c9; margin:5px 0 0 0; font-size:0.9rem;">Sistem Digital Rasmi</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")
    page = st.selectbox("Menu", ["Halaman Utama", "Admin Panel"], label_visibility="collapsed")

# =============================================
# HALAMAN UTAMA — GAMBAR BUAH & SAYUR CANTIK!
# =============================================
if page == "Halaman Utama":
    st.markdown(f'''
    <div class="header-container">
        <img src="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSKvm2dXTYvt4qaPW6NROuESTVo-RgjoV6s6W80Cp5Jv_rrixoxkS1HEJT_dRkPtT39OjM&usqp=CAU?w=1200&h=600&fit=crop&crop=center&q=90" 
             style="width:100%; height:280px; object-fit:cover; filter: brightness(0.9);">
        <div style="position:absolute; top:0; left:0; width:100%; height:100%; 
                    background: linear-gradient(to bottom, rgba(27,94,32,0.8), rgba(76,175,80,0.7));">
        </div>
        <div style="position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); text-align:center; width:100%;">
            <h1 style="color:white; font-size:3.2rem; font-weight:900; margin:0;
                       text-shadow: 3px 3px 12px rgba(0,0,0,0.8);">
                RUJUKAN STANDARD FAMA
            </h1>
            <p style="color:#e8f5e8; font-size:1.4rem; margin:20px 0 0;
                      text-shadow: 2px 2px 8px rgba(0,0,0,0.7);">
               Bahagian Regulasi Pasaran
            </p>
        </div>
    </div>
    ''', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3,1])
    with col1: cari = st.text_input("", placeholder="Cari tajuk standard...")
    with col2: kat = st.selectbox("", ["Semua"] + CATEGORIES)

    docs = get_docs()
    hasil = [d for d in docs if (kat == "Semua" or d[2] == kat) and (not cari or cari.lower() in d[1].lower())]

    st.markdown(f"**Ditemui: {len(hasil)} standard**")

    for d in hasil:
        id_, title, cat, fname, fpath, thumb, date, uploader = d
        with st.container():
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            c1, c2 = st.columns([1,3])
            with c1:
                img = thumb if thumb and os.path.exists(thumb) else "https://via.placeholder.com/350x500/4CAF50/white?text=FAMA"
                st.image(img, use_column_width=True)
            with c2:
                st.markdown(f"<h2>{title}</h2>", unsafe_allow_html=True)
                st.caption(f"{cat} • {date[:10]} • {uploader}")
                if fpath and os.path.exists(fpath):
                    with open(fpath, "rb") as f:
                        st.download_button("MUAT TURUN", f.read(), fname, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

# =============================================
# ADMIN PANEL — TETAP PAKAI LOGO FAMA
# =============================================
else:
    if not st.session_state.get("admin"):
        st.markdown(f'''
        <div class="header-container">
            <img src="https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png" width="80" style="display:block; margin:0 auto 15px;">
            <h1 style="color:black; text-align:center; font-size:2.8rem; margin:0; text-shadow: 2px 2px 8px black;">
                ADMIN PANEL
            </h1>
        </div>
        ''', unsafe_allow_html=True)
        # ... (login code sama macam sebelum ni)
