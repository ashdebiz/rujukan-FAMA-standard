# app.py
import streamlit as st
import sqlite3
import os
import shutil
from datetime import datetime, date
import PyPDF2
from docx import Document
import io
import zipfile
from pathlib import Path
import mimetypes

# =============================================
# GUNA /tmp SUPAYA DATA KEKAL DI STREAMLIT CLOUD
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

# Pastikan DB wujud
if not os.path.exists(DB_NAME):
    open(DB_NAME, "a").close()

# =============================================
# INISIALISASI DATABASE (sama macam asal kamu)
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
    ''')
    # Trigger FTS
    conn.executescript('''
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
# BACKUP PENUH (DB + FAIL + THUMBNAIL)
# =============================================
def create_full_backup():
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(DB_NAME):
            zf.write(DB_NAME, "standards_db.sqlite")
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
# UI 100% SAMA MACAM GAMBAR KAMU (tak ubah langsung!)
# =============================================
st.set_page_config(page_title="Rujukan FAMA Standard", page_icon="rice", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<div style="text-align:center; margin-bottom:20px;">
    <h1 style="color:#2E7D32; font-size:2.8em;">RUJUKAN FAMA STANDARD<br>KELUARAN HASIL PERTANIAN</h1>
    <p style="color:#4CAF50; font-size:1.2em;">
        Temui panduan standard pertanian terkini dengan mudah. Klik butang di bawah untuk papar senarai standard mengikut kategori!
    </p>
</div>
""", unsafe_allow_html=True)

# Statistik
conn = get_db()
total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
today = conn.execute("SELECT COUNT(*) FROM documents WHERE upload_date LIKE ?", (f"{date.today()}%",)).fetchone()[0]
conn.close()

c1, c2 = st.columns(2)
c1.metric("Jumlah Standard Keseluruhan", total)
c2.metric("Standard Baru Hari Ini", today)

# 4 BUTANG KATEGORI HIJAU BULAT
col1, col2, col3, col4 = st.columns(4)
with col1:
    if st.button("Keratan Bunga", type="primary", use_container_width=True):
        st.session_state.category = "Keratan Bunga"
        st.rerun()
with col2:
    if st.button("Sayur-sayuran", type="primary", use_container_width=True):
        st.session_state.category = "Sayur-sayuran"
        st.rerun()
with col3:
    if st.button("Buah-buahan", type="primary", use_container_width=True):
        st.session_state.category = "Buah-buahan"
        st.rerun()
with col4:
    if st.button("Lain-lain", type="primary", use_container_width=True):
        st.session_state.category = "Lain-lain"
        st.rerun()

# Carian
if "category" not in st.session_state:
    st.session_state.category = "Semua"

query = st.text_input("Masukkan kata kunci carian (opsional):", placeholder="Contoh: standard keratan bunga")
category_filter = st.selectbox("Filter Kategori:", ["Semua", "Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"],
                               index=["Semua", "Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"].index(st.session_state.category))

# Carian ringkas
conn = get_db()
cur = conn.cursor()
sql = "SELECT title, content, file_name, file_path, upload_date, category FROM documents WHERE 1=1"
params = []
if query:
    sql += " AND (title LIKE ? OR content LIKE ?)"
    params.extend([f"%{query}%", f"%{query}%"])
if category_filter != "Semua":
    sql += " AND category = ?"
    params.append(category_filter)
sql += " ORDER BY upload_date DESC"
cur.execute(sql, params)
results = cur.fetchall()
conn.close()

st.write(f"**Ditemui {len(results)} dokumen**")
for title, content, fname, fpath, date, cat in results:
    with st.expander(f"{title} ({cat}) – {date[:10]}"):
        st.write(content[:600] + ("..." if len(content) > 600 else ""))
        if fpath and os.path.exists(fpath):
            with open(fpath, "rb") as f:
                st.download_button("Muat Turun", f.read(), file_name=fname or "dokumen.pdf")

# ADMIN: Backup satu klik
with st.sidebar:
    st.markdown("## Admin")
    if st.text_input("Kata laluan", type="password") == "admin123":
        st.success("Log masuk admin")
        backup_data = create_full_backup()
        st.download_button(
            label="Download Backup Penuh (.zip)",
            data=backup_data,
            file_name=f"fama_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            mime="application/zip"
        )
        uploaded_file = st.file_uploader("Upload PDF/DOCX", type=["pdf", "docx"])
        title = st.text_input("Nama Komoditi")
        category = st.selectbox("Kategori", ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"])
        if uploaded_file and title and st.button("Simpan"):
            # Simpan fail
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            ext = Path(uploaded_file.name).suffix
            safe_name = f"{timestamp}_{Path(uploaded_file.name).stem}{ext}"
            file_path = os.path.join(UPLOADS_DIR, safe_name)
            with open(file_path, "wb") as f:
                shutil.copyfileobj(uploaded_file, f)
            # Ekstrak teks
            uploaded_file.seek(0)
            if ext == ".pdf":
                text = PyPDF2.PdfReader(uploaded_file)
                content = "\n".join(page.extract_text() or "" for page in text.pages)
            else:
                doc = Document(uploaded_file)
                content = "\n".join(p.text for p in doc.paragraphs)
            # Simpan ke DB
            conn = get_db()
            conn.execute("INSERT INTO documents (title, content, category, file_name, file_path, upload_date) VALUES (?, ?, ?, ?, ?, ?)",
                        (title, content, category, uploaded_file.name, file_path, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            conn.close()
            st.success("Berjaya disimpan!")
            st.rerun()