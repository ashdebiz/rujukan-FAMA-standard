# app.py — FINAL VERSION (Logo FAMA + Data Kekal + Backup + Upload + Carian)
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
# INISIALISASI DATABASE + FTS5 (CARIAN LAJU)
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
# BACKUP PENUH (DB + SEMUA FAIL)
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
                z type="primary", use_container_width=True):
                zf.write(fp, os.path.join("thumbnails", os.path.relpath(fp, THUMBNAILS_DIR)))
    mem.seek(0)
    return mem

# =============================================
# PAGE CONFIG & TAJUK CANTIK DENGAN LOGO FAMA
# =============================================
st.set_page_config(page_title="Rujukan FAMA Standard", page_icon="rice", layout="centered")

st.markdown("""
<div style="text-align:center; padding:20px 0; margin-bottom:10px;">
    <img src="https://www.fama.gov.my/wp-content/uploads/2023/06/Logo-FAMA-Baru-2023.png" width="140" style="border-radius:12px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
    <h1 style="color:#2E7D32; font-size:3em; margin:15px 0 5px 0; text-shadow: 2px 2px 4px rgba(0,0,0,0.1);">
        RUJUKAN FAMA STANDARD
    </h1>
    <p style="color:#388E3C; font-size:1.7em; margin:0; font-weight:600;">
        KELUARAN HASIL PERTANIAN
    </p>
    <p style="color:#4CAF50; font-size:1.2em; margin-top:12px;">
        Temui panduan standard pertanian terkini dengan mudah
    </p>
</div>
""", unsafe_allow_html=True)

# =============================================
# STATISTIK
# =============================================
conn = get_db()
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM documents")
total = cur.fetchone()[0]
today = datetime.now().strftime("%Y-%m-%d")
cur.execute("SELECT COUNT(*) FROM documents WHERE upload_date LIKE ?", (f"{today}%",))
today_count = cur.fetchone()[0]
conn.close()

col1, col2 = st.columns(2)
col1.metric("Jumlah Standard Keseluruhan", total)
col2.metric("Standard Baru Hari Ini", today_count)

# =============================================
# 4 BUTANG KATEGORI (HIJAU BULAT CANTIK)
# =============================================
st.markdown("<br>", unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)
with c1:
    if st.button("Keratan Bunga", type="primary", use_container_width=True):
        st.session_state.cat = "Keratan Bunga"; st.rerun()
with c2:
    if st.button("Sayur-sayuran", type="primary", use_container_width=True):
        st.session_state.cat = "Sayur-sayuran"; st.rerun()
with c3:
    if st.button("Buah-buahan", type="primary", use_container_width=True):
        st.session_state.cat = "Buah-buahan"; st.rerun()
with c4:
    if st.button("Lain-lain", type="primary", use_container_width=True):
        st.session_state.cat = "Lain-lain"; st.rerun()

if "cat" not in st.session_state:
    st.session_state.cat = "Semua"

# =============================================
# CARIAN & FILTER
# =============================================
st.markdown("<br>", unsafe_allow_html=True)
query = st.text_input("Masukkan kata kunci carian (opsional):", placeholder="Contoh: standard keratan bunga")
category_filter = st.selectbox("Filter Kategori:", 
                               ["Semua", "Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"],
                               index=0 if st.session_state.cat == "Semua" else ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"].index(st.session_state.cat) + 1)

# =============================================
# PENCARIAN DENGAN FTS5 (LAJU!)
# =============================================
conn = get_db()
cur = conn.cursor()
sql = "SELECT d.title, d.content, d.file_name, d.file_path, d.upload_date, d.category FROM documents d JOIN documents_fts f ON d.id = f.rowid WHERE 1=1"
params = []

if query:
    sql += " AND documents_fts MATCH ?"
    params.append(query)
if category_filter != "Semua":
    sql += " AND d.category = ?"
    params.append(category_filter)

sql += " ORDER BY d.upload_date DESC"
cur.execute(sql, params)
results = cur.fetchall()
conn.close()

st.markdown(f"**Ditemui {len(results)} dokumen**")

for title, content, fname, fpath, date, cat in results:
    with st.expander(f"{title} • {cat} • {date[:10]}"):
        st.write(content[:700] + ("..." if len(content) > 700 else ""))
        if fpath and os.path.exists(fpath):
            with open(fpath, "rb") as f:
                st.download_button("Muat Turun Dokumen", f.read(), file_name=fname or "dokumen.pdf", mime="application/pdf")

# =============================================
# ADMIN PANEL (DENGAN BACKUP + UPLOAD)
# =============================================
with st.sidebar:
    st.markdown("## Admin")
    password = st.text_input("Kata laluan", type="password")
    if password == "admin123":  # tukar kalau nak
        st.success("Log masuk berjaya!")

        # Backup satu klik
        backup_data = create_full_backup()
        st.download_button(
            label="Download Backup Penuh (.zip)",
            data=backup_data,
            file_name=f"fama_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            mime="application/zip"
        )

        st.markdown("---")
        st.subheader("Upload Dokumen Baru")
        uploaded_file = st.file_uploader("Pilih PDF/DOCX", type=["pdf", "docx"])
        title = st.text_input("Nama Komoditi / Tajuk")
        category = st.selectbox("Kategori", ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"])
        
        if uploaded_file and title and st.button("Simpan Dokumen"):
            # Simpan fail
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            ext = Path(uploaded_file.name).suffix
            safe_name = f"{timestamp}_{Path(uploaded_file.name).stem}{ext}"
            file_path = os.path.join(UPLOADS_DIR, safe_name)
            with open(file_path, "wb") as f:
                shutil.copyfileobj(uploaded_file, f)

            # Ekstrak teks
            uploaded_file.seek(0)
            if ext.lower() == ".pdf":
                reader = PyPDF2.PdfReader(uploaded_file)
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
            else:
                doc = Document(uploaded_file)
                text = "\n".join(p.text for p in doc.paragraphs)

            # Simpan ke DB
            conn = get_db()
            conn.execute("""
                INSERT INTO documents (title, content, category, file_name, file_path, upload_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (title, text, category, uploaded_file.name, file_path, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            conn.close()
            st.success("Dokumen berjaya disimpan!")
            st.rerun()