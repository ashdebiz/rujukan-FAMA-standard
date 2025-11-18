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
# AUTO DETECT STREAMLIT CLOUD (PENTING!)
# =============================================
if "STREAMLIT_CLOUD" in os.environ or "STREAMLIT" in os.environ:
    DB_NAME = "/tmp/standards_db.sqlite"
    UPLOADS_DIR = "/tmp/uploads"
    THUMBNAILS_DIR = "/tmp/thumbnails"
else:
    DB_NAME = "standards_db.sqlite"
    UPLOADS_DIR = "uploads"
    THUMBNAILS_DIR = "thumbnails"

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(THUMBNAILS_DIR, exist_ok=True)

# Sambungan DB dengan WAL (selamat untuk Cloud)
def get_db():
    conn = sqlite3.connect(DB_NAME, timeout=30.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

# Pastikan DB wujud
if not os.path.exists(DB_NAME):
    open(DB_NAME, "a").close()

# =============================================
# SEMUA KOD ASAL KAMU (100% KEKAL)
# =============================================
st.set_page_config(page_title="Rujukan FAMA Standard", page_icon="rice", layout="centered", initial_sidebar_state="collapsed")

ADMIN_PASSWORD = "admin123"
CATEGORIES = ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"]
MAX_FILE_SIZE = 10 * 1024 * 1024

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
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(documents)")
    cols = [c[1] for c in cur.fetchall()]
    for col in ['category','file_name','file_path','thumbnail_path']:
        if col not in cols:
            conn.execute(f"ALTER TABLE documents ADD COLUMN {col} TEXT")
    conn.commit()
    conn.close()
init_db()

def sync_fts():
    conn = get_db()
    conn.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
    conn.commit()
    conn.close()

# === BACKUP & RESTORE PENUH (BARU!) ===
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

def restore_full_backup(zip_file):
    try:
        with zipfile.ZipFile(zip_file) as zf:
            zf.extractall("/tmp/restore_temp")
        for d in [UPLOADS_DIR, THUMBNAILS_DIR]:
            if os.path.exists(d): shutil.rmtree(d)
            os.makedirs(d, exist_ok=True)
        if os.path.exists("/tmp/restore_temp/standards_db.sqlite"):
            shutil.copy2("/tmp/restore_temp/standards_db.sqlite", DB_NAME)
        if os.path.exists("/tmp/restore_temp/uploads"):
            shutil.copytree("/tmp/restore_temp/uploads", UPLOADS_DIR, dirs_exist_ok=True)
        if os.path.exists("/tmp/restore_temp/thumbnails"):
            shutil.copytree("/tmp/restore_temp/thumbnails", THUMBNAILS_DIR, dirs_exist_ok=True)
        shutil.rmtree("/tmp/restore_temp")
        st.success("Restore berjaya! App akan reload...")
        st.rerun()
    except Exception as e:
        st.error(f"Gagal restore: {e}")

# === SEMUA FUNGSI ASAL KAMU (tak sentuh langsung) ===
@st.cache_data(ttl=300)
def get_stats(): ...  # kekal sama

def get_document_by_id(doc_id): ...  # kekal sama
def extract_pdf_text(file): ...     # kekal sama
def extract_docx_text(file): ...    # kekal sama
def save_document(...): ...         # kekal sama
def edit_document(...): ...         # kekal sama
def save_thumbnail(...): ...        # kekal sama
def delete_document(...): ...       # kekal sama
def search_documents(...): ...      # kekal sama
def search_documents_admin(...): ...# kekal sama
@st.cache_data
def get_file_data(file_path): ...   # kekal sama
def get_all_documents(...): ...     # kekal sama

# === CSS ASAL KAMU (100% SAMA) ===
st.markdown(""" ...seluruh CSS kamu... """, unsafe_allow_html=True)

# === SIDEBAR & HALAMAN ASAL KAMU (100% SAMA) ===
with st.sidebar: ...  # sama

if page == "Halaman Pengguna (Carian)": ...  # 100% sama macam kod kamu

elif page == "Halaman Admin (Upload)":
    st.title("Halaman Admin - Upload Dokumen Standard")
    
    # Login (sama)
    if not st.session_state.get("authenticated", False): ...  # sama

    st.success("Log masuk berjaya! Anda boleh upload dokumen sekarang.")
    if st.button("Log Keluar", ...): ...  # sama

    # === TAMBAHAN BACKUP & RESTORE DI ADMIN (hanya ini yang baru!) ===
    st.markdown("### Backup & Restore Database (Termasuk Semua Fail & Thumbnail)")
    b1, b2 = st.columns(2)
    with b1:
        backup_data = create_full_backup()
        st.download_button(
            label="Download Backup Penuh (.zip)",
            data=backup_data,
            file_name=f"fama_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            mime="application/zip"
        )
    with b2:
        restore_file = st.file_uploader("Upload backup .zip untuk restore", type=["zip"])
        if restore_file and st.button("Restore dari Backup", type="primary"):
            restore_full_backup(restore_file)

    st.markdown("---")

    # === SEMUA BAHAGIAN ADMIN YANG ASAL (upload, edit, padam) — 100% SAMA ===
    # ...semua kod admin kamu dari sini sampai habis...