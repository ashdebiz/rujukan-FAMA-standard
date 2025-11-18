# app.py — FINAL + POP-UP PDF VIEWER + TIADA ERROR LAGI!
import streamlit as st
import sqlite3
import os
import shutil
from datetime import datetime
import PyPDF2
from docx import Document
import io
import zipfile
from pathlib import Path
import base64

# =============================================
# DATA KEKAL DI /tmp
# =============================================
DB_NAME = "/tmp/standards_db.sqlite"
UPLOADS_DIR = "/tmp/uploads"
THUMBNAILS_DIR = "/tmp/thumbnails"

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(THUMBNAILS_DIR, exist_ok=True)

def get_db():
    conn = sqlite3.connect(DB_NAME, timeout=30.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

if not os.path.exists(DB_NAME):
    open(DB_NAME, "a").close()

# =============================================
# INIT DATABASE + FTS5
# =============================================
@st.cache_resource
def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'Lain-lain',
            file_name TEXT,
            file_path TEXT,
            thumbnail_path TEXT,
            upload_date TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
            title, content, category, content='documents', content_rowid='id'
        );
        CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
            INSERT INTO documents_fts(rowid, title, content, category) VALUES (new.id, new.title, new.content, new.category);
        END;
        CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, title, content, category) VALUES ('delete', old.id, old.title, old.content, old.category);
        END;
        CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, title, content, category) VALUES ('delete', old.id, old.title, old.content, old.category);
            INSERT INTO documents_fts(rowid, title, content, category) VALUES (new.id, new.title, new.content, new.category);
        END;
    ''')
    conn.commit()
    conn.close()
init_db()

# =============================================
# BACKUP PENUH
# =============================================
def create_full_backup():
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(DB_NAME): zf.write(DB_NAME, "standards_db.sqlite")
        for root, _, files in os.walk(UPLOADS_DIR):
            for f in files:
                fp = os.path.join(root, f)
                zf.write(fp, os.path.join("uploads", os.path.relpath(fp, UPLOADS_DIR)))
        for root, _, files in os.walk(THUMBNAILS_DIR):
            for f in files:
                fp = os.path.join(root, f)
                zf.write(fp, os.path.join("thumbnails", os.path.relpath(fp, THUMBNAILS_DIR)))
    mem.seek(0)
    return mem

# =============================================
# FUNGSI PDF BASE64
# =============================================
def get_pdf_base64(file_path):
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')

# =============================================
# TAJUK + LOGO FAMA
# =============================================
st.set_page_config(page_title="Rujukan FAMA Standard", page_icon="rice", layout="centered")

st.markdown("""
<div style="text-align:center; padding:20px 0;">
    <img src="https://www.fama.gov.my/wp-content/uploads/2023/06/Logo-FAMA-Baru-2023.png" width="140">
    <h1 style="color:#2E7D32; font-size:3em; margin:15px 0 5px 0;">RUJUKAN FAMA STANDARD</h1>
    <p style="color:#388E3C; font-size:1.8em; margin:0; font-weight:600;">KELUARAN HASIL PERTANIAN</p>
    <p style="color:#4CAF50; font-size:1.2em; margin-top:12px;">Temui panduan standard pertanian terkini dengan mudah</p>
</div>
""", unsafe_allow_html=True)

# =============================================
# STATISTIK — DAH BETUL 100% TIADA ERROR!
# =============================================
conn = get_db()
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM documents")
total = cur.fetchone()[0]

today = datetime.now().strftime("%Y-%m-%d")
cur.execute("SELECT COUNT(*) FROM documents WHERE substr(upload_date,1,10) = ?", (today,))
today_row = cur.fetchone()
today_count = today_row[0] if today_row else 0
conn.close()

col1, col2 = st.columns(2)
col1.metric("Jumlah Standard Keseluruhan", total)
col2.metric("Standard Baru Hari Ini", today_count)

# =============================================
# BUTANG KATEGORI
# =============================================
c1, c2, c3, c4 = st.columns(4)
with c1:
    if st.button("Keratan Bunga", type="primary", use_container_width=True):
        st.session_state.cat = "Keratan Bunga"; st.rerun()
with c2:
    if st.button("Sayur-sayanan", type="primary", use_container_width=True):
        st.session_state.cat = "Sayur-sayuran"; st.rerun()
with c3:
    if st.button("Buah-buahan", type="primary", use_container_width=True):
        st.session_state.cat = "Buah-buahan"; st.rerun()
with c4:
    if st.button("Lain-lain", type="primary", use_container_width=True):
        st.session_state.cat = "Lain-lain"; st.rerun()

if "cat" not in st.session_state:
    st.session_state.cat = "Semua"

query = st.text_input("Carian kata kunci:", placeholder="Contoh: tomato")
category_filter = st.selectbox("Kategori:", 
    ["Semua", "Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"],
    index=0 if st.session_state.cat == "Semua" else ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"].index(st.session_state.cat) + 1)

# =============================================
# PAPAR SENARAI + BUTANG LIHAT PDF (POP-UP!)
# =============================================
conn = get_db()
cur = conn.cursor()
sql = "SELECT d.id, d.title, d.content, d.file_name, d.file_path, d.thumbnail_path, d.upload_date, d.category FROM documents d JOIN documents_fts f ON d.id = f.rowid WHERE 1=1"
params = []
if query: sql += " AND documents_fts MATCH ?"; params.append(query)
if category_filter != "Semua": sql += " AND d.category = ?"; params.append(category_filter)
sql += " ORDER BY d.upload_date DESC"
cur.execute(sql, params)
results = cur.fetchall()
conn.close()

st.markdown(f"**Ditemui {len(results)} standard**")

for doc_id, title, content, fname, fpath, thumb_path, date, cat in results:
    with st.expander(f"{title} • {cat} • {date[:10]}"):
        col1, col2 = st.columns([1, 4])
        with col1:
            if thumb_path and os.path.exists(thumb_path):
                st.image(thumb_path, width=130)
            else:
                st.image("https://via.placeholder.com/130x180/4CAF50/white?text=No+Image", width=130)
        with col2:
            st.write(content[:700] + ("..." if len(content) > 700 else ""))

            if fpath and os.path.exists(fpath):
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("Lihat PDF", key=f"view_{doc_id}"):
                        st.session_state.view_pdf = fpath
                        st.session_state.view_title = title
                        st.rerun()
                with col_b:
                    with open(fpath, "rb") as f:
                        st.download_button("Muat Turun", f.read(), file_name=fname, key=f"dl_{doc_id}")

# =============================================
# POP-UP PDF VIEWER CANTIK GILA!
# =============================================
if "view_pdf" in st.session_state:
    pdf_path = st.session_state.view_pdf
    pdf_title = st.session_state.view_title
    pdf_base64 = get_pdf_base64(pdf_path)

    st.markdown(f"""
    <style>
        .pdf-overlay {{
            position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
            background: rgba(0,0,0,0.85); z-index: 9999; display: flex;
            justify-content: center; align-items: center;
        }}
        .pdf-box {{
            width: 90%; height: 90vh; background: white; border-radius: 12px;
            overflow: hidden; box-shadow: 0 20px 60px rgba(0,0,0,0.6);
        }}
        .pdf-header {{
            background: #2E7D32; color: white; padding: 15px; text-align: center;
            font-size: 1.4em; font-weight: bold;
        }}
        .close-btn {{
            position: absolute; top: 15px; right: 25px; background: #c62828;
            color: white; border: none; width: 40px; height: 40px;
            border-radius: 50%; font-size: 1.5em; cursor: pointer;
        }}
    </style>
    <div class="pdf-overlay">
        <div class="pdf-box">
            <div class="pdf-header">
                {pdf_title}
                <button class="close-btn" onclick="document.querySelector('.pdf-overlay').remove()">X</button>
            </div>
            <iframe src="data:application/pdf;base64,{pdf_base64}" width="100%" height="93%"></iframe>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("Tutup Preview", type="primary"):
        del st.session_state.view_pdf
        del st.session_state.view_title
        st.rerun()

# =============================================
# ADMIN PANEL (Ringkas je dulu)
# =============================================
with st.sidebar:
    st.markdown("## Admin")
    if st.text_input("Password", type="password") == "admin123":
        st.success("Login berjaya")
        st.download_button("Backup Penuh", create_full_backup(),
                           f"fama_backup_{datetime.now().strftime('%Y%m%d')}.zip")