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
# AUTO DETECT STREAMLIT CLOUD — PENTING!
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

# Sambungan DB selamat untuk Cloud
def get_db():
    conn = sqlite3.connect(DB_NAME, timeout=30.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

# Pastikan DB wujud
Path(DB_NAME).parent.mkdir(parents=True, exist_ok=True)
if not os.path.exists(DB_NAME):
    open(DB_NAME, "a").close()

# =============================================
# KONFIGURASI & INIT DB (100% SAMA MACAM KAMU)
# =============================================
st.set_page_config(
    page_title="Rujukan FAMA Standard",
    page_icon="rice",
    layout="centered",
    initial_sidebar_state="collapsed"
)

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

# =============================================
# BACKUP & RESTORE PENUH (BARU!)
# =============================================
def create_full_backup():
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED) as zf:
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
    memory.seek(0)
    return memory

def restore_full_backup(uploaded_zip):
    try:
        with zipfile.ZipFile(uploaded_zip) as zf:
            zf.extractall("/tmp/restore_temp")
        for folder in [UPLOADS_DIR, THUMBNAILS_DIR]:
            if os.path.exists(folder):
                shutil.rmtree(folder)
            os.makedirs(folder, exist_ok=True)
        if os.path.exists("/tmp/restore_temp/standards_db.sqlite"):
            shutil.copy2("/tmp/restore_temp/standards_db.sqlite", DB_NAME)
        if os.path.exists("/tmp/restore_temp/uploads"):
            shutil.copytree("/tmp/restore_temp/uploads", UPLOADS_DIR, dirs_exist_ok=True)
        if os.path.exists("/tmp/restore_temp/thumbnails"):
            shutil.copytree("/tmp/restore_temp/thumbnails", THUMBNAILS_DIR, dirs_exist_ok=True)
        shutil.rmtree("/tmp/restore_temp")
        st.success("Backup berjaya dipulihkan! App akan reload...")
        st.rerun()
    except Exception as e:
        st.error(f"Gagal restore: {e}")

# =============================================
# SEMUA FUNGSI ASAL KAMU (100% SAMA)
# =============================================
@st.cache_data(ttl=300)
def get_stats():
    conn = get_db()
    cursor = conn.cursor()
    total_docs = cursor.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    today = date.today().strftime("%Y-%m-%d")
    today_docs = cursor.execute("SELECT COUNT(*) FROM documents WHERE upload_date LIKE ?", (f"{today}%",)).fetchone()[0]
    conn.close()
    return total_docs, today_docs

def get_document_by_id(doc_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, content, category, file_name, file_path, thumbnail_path, upload_date FROM documents WHERE id = ?", (doc_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def extract_pdf_text(file):
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        st.error(f"Ralat ekstrak PDF: {e}")
        return ""

def extract_docx_text(file):
    try:
        doc = Document(io.BytesIO(file.read()))
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    except Exception as e:
        st.error(f"Ralat ekstrak DOCX: {e}")
        return ""

def save_document(title, content, category, uploaded_file, original_filename, thumbnail_path=None):
    if not title.strip():
        st.error("Nama komoditi / tajuk dokumen tidak boleh kosong!")
        return
    uploaded_file.seek(0)
    if len(uploaded_file.read()) > MAX_FILE_SIZE:
        st.error("Fail terlalu besar! Maksimum 10MB.")
        return
    uploaded_file.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_ext = Path(original_filename).suffix
    safe_filename = f"{timestamp}_{Path(original_filename).stem}{file_ext}"
    file_path = os.path.join(UPLOADS_DIR, safe_filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(uploaded_file, f)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO documents (title, content, category, file_name, file_path, thumbnail_path, upload_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (title, content, category, original_filename, file_path, thumbnail_path, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    sync_fts()
    st.success(f"Dokumen '{title}' (Kategori: {category}) berjaya disimpan!")

def edit_document(doc_id, title, content, category, new_attachment_file=None, current_file_path=None, current_file_name=None, new_thumbnail_file=None, current_thumbnail_path=None):
    # (fungsi penuh edit — sama macam kod kamu)
    if not title.strip():
        st.error("Nama komoditi / tajuk tidak boleh kosong!")
        return
    new_file_path = current_file_path
    new_file_name = current_file_name
    new_content = content
    if new_attachment_file is not None:
        new_attachment_file.seek(0)
        if len(new_attachment_file.read()) > MAX_FILE_SIZE:
            st.error("Fail attachment terlalu besar! Maksimum 10MB.")
            return
        new_attachment_file.seek(0)
        if new_attachment_file.name.endswith('.pdf'):
            new_content = extract_pdf_text(new_attachment_file)
        elif new_attachment_file.name.endswith('.docx'):
            new_content = extract_docx_text(new_attachment_file)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_ext = Path(new_attachment_file.name).suffix
        safe_filename = f"{timestamp}_{Path(new_attachment_file.name).stem}{file_ext}"
        new_file_path = os.path.join(UPLOADS_DIR, safe_filename)
        new_file_name = new_attachment_file.name
        with open(new_file_path, "wb") as f:
            shutil.copyfileobj(new_attachment_file, f)
        if current_file_path and os.path.exists(current_file_path):
            os.remove(current_file_path)
    new_thumbnail_path = current_thumbnail_path
    if new_thumbnail_file is not None:
        new_thumbnail_file.seek(0)
        if len(new_thumbnail_file.read()) > MAX_FILE_SIZE / 10:
            st.error("Thumbnail terlalu besar!")
            return
        new_thumbnail_file.seek(0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_ext = Path(new_thumbnail_file.name).suffix
        safe_filename = f"{timestamp}_thumb{file_ext}"
        new_thumbnail_path = os.path.join(THUMBNAILS_DIR, safe_filename)
        with open(new_thumbnail_path, "wb") as f:
            shutil.copyfileobj(new_thumbnail_file, f)
        if current_thumbnail_path and os.path.exists(current_thumbnail_path):
            os.remove(current_thumbnail_path)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE documents SET title = ?, content = ?, category = ?, file_name = ?, file_path = ?, thumbnail_path = ?
        WHERE id = ?
    """, (title, new_content, category, new_file_name, new_file_path, new_thumbnail_path, doc_id))
    conn.commit()
    conn.close()
    sync_fts()
    st.success(f"Dokumen ID {doc_id} berjaya dikemaskini!")

def save_thumbnail(doc_id, thumbnail_file):
    # sama macam kod kamu
    thumbnail_file.seek(0)
    if len(thumbnail_file.read()) > MAX_FILE_SIZE / 10:
        st.error("Thumbnail terlalu besar!")
        return
    thumbnail_file.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_ext = Path(thumbnail_file.name).suffix
    safe_filename = f"{timestamp}_thumb{file_ext}"
    thumbnail_path = os.path.join(THUMBNAILS_DIR, safe_filename)
    with open(thumbnail_path, "wb") as f:
        shutil.copyfileobj(thumbnail_file, f)
    doc_data = get_document_by_id(doc_id)
    if doc_data and doc_data[6] and os.path.exists(doc_data[6]):
        os.remove(doc_data[6])
    conn = get_db()
    conn.execute("UPDATE documents SET thumbnail_path = ? WHERE id = ?", (thumbnail_path, doc_id))
    conn.commit()
    conn.close()
    sync_fts()
    st.success(f"Thumbnail berjaya dikemaskini untuk dokumen ID {doc_id}!")

def delete_document(doc_id, file_path, thumbnail_path):
    conn = get_db()
    conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()
    if file_path and os.path.exists(file_path):
        os.remove(file_path)
    if thumbnail_path and os.path.exists(thumbnail_path):
        os.remove(thumbnail_path)
    sync_fts()
    st.success(f"Dokumen dengan ID {doc_id} berjaya dipadam!")

def search_documents(query, category_filter=""):
    conn = get_db()
    cursor = conn.cursor()
    sql = "SELECT d.title, d.content, d.file_name, d.file_path, d.thumbnail_path, d.upload_date, d.category FROM documents d JOIN documents_fts f ON d.id = f.rowid WHERE "
    params = []
    conditions = []
    if query:
        conditions.append("documents_fts MATCH ?")
        params.append(query)
    if category_filter and category_filter != "Semua":
        conditions.append("d.category = ?")
        params.append(category_filter)
    if not conditions:
        sql = sql.replace("WHERE ", "")
    else:
        sql += " AND ".join(conditions)
    sql += " ORDER BY d.upload_date DESC"
    cursor.execute(sql, params)
    results = cursor.fetchall()
    conn.close()
    return results

def search_documents_admin(query="", category_filter=""):
    conn = get_db()
    cursor = conn.cursor()
    sql = "SELECT d.id, d.title, d.upload_date, d.file_name, d.file_path, d.thumbnail_path, d.category, d.content FROM documents d JOIN documents_fts f ON d.id = f.rowid"
    params = []
    conditions = []
    if query:
        conditions.append("documents_fts MATCH ?")
        params.append(query)
    if category_filter and category_filter != "Semua":
        conditions.append("d.category = ?")
        params.append(category_filter)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY d.upload_date DESC"
    cursor.execute(sql, params)
    results = cursor.fetchall()
    conn.close()
    return results

@st.cache_data
def get_file_data(file_path):
    with open(file_path, "rb") as f:
        return f.read(), mimetypes.guess_type(file_path)[0] or "application/octet-stream"

def get_all_documents(category_filter=""):
    return search_documents_admin(category_filter=category_filter)

# =============================================
# CSS & UI — 100% SAMA MACAM KOD ASAL KAMU
# =============================================
st.markdown("""
    <style>
    .main-header {color: #2E7D32; font-size: 2.5em; text-align: center; margin-bottom: 0.5em;}
    .search-box {background-color: #E8F5E8; padding: 1em; border-radius: 10px; border-left: 5px solid #4CAF50;}
    .result-card {background-color: #F1F8E9; padding: 1em; border-radius: 10px; margin: 0.5em 0; border-left: 4px solid #66BB6A;}
    .category-filter {background-color: #E3F2FD; padding: 0.5em; border-radius: 5px; margin: 0.5em 0;}
    .stButton > button {width: 100%; margin: 0.2em 0; padding: 0.5em;}
    .header-container { text-align: center; margin-bottom: 1em; }
    .header-logo { display: block; margin: 0 auto 0.5em; }
    @media (max-width: 768px) {
        .main-header { font-size: 1.8em; margin-bottom: 0.3em; }
        .stButton > button { font-size: 1em; padding: 0.8em; margin: 0.3em 0; }
        [data-testid="column"] { width: 100% !important; }
    }
    @media (max-width: 480px) {
        .main-header { font-size: 1.5em; }
        .header-logo { width: 120px !important; }
    }
    @media (min-width: 769px) {
        .main-header { font-size: 2.8em; }
    }
    </style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## Navigasi")
    page = st.selectbox("Pilih Halaman", ["Halaman Pengguna (Carian)", "Halaman Admin (Upload)"])

# =============================================
# HALAMAN PENGGUNA — 100% SAMA
# =============================================
if page == "Halaman Pengguna (Carian)":
    st.markdown("""
        <div class="header-container">
            <img src="https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png" alt="Logo FAMA" class="header-logo" width="80">
            <h1 class="main-header">RUJUKAN FAMA STANDARD KELUARAN HASIL PERTANIAN</h1>
        </div>
    """, unsafe_allow_html=True)
    # ... (semua kod pengguna kamu — tak ubah langsung) ...
    # (Untuk pendekkan, aku letak tanda ... — tapi kamu boleh copy dari kod asal kamu)
    # Pastikan semua kod dari st.subheader sampai akhir halaman pengguna kekal sama

# =============================================
# HALAMAN ADMIN — TAMBAH BACKUP JE
# =============================================
else:
    st.title("Halaman Admin - Upload Dokumen Standard")
    
    if not st.session_state.get("authenticated", False):
        pw = st.text_input("Masukkan kata laluan admin:", type="password")
        if st.button("Log Masuk"):
            if pw == ADMIN_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Kata laluan salah!")
        st.stop()

    if st.button("Log Keluar"):
        st.session_state.authenticated = False
        st.rerun()

    st.success("Log masuk berjaya!")

    # === INI JE YANG BARU: BACKUP & RESTORE ===
    st.markdown("### Backup & Restore Database (Termasuk Semua Fail)")
    c1, c2 = st.columns(2)
    with c1:
        backup_zip = create_full_backup()
        st.download_button(
            label="Download Backup Penuh (.zip)",
            data=backup_zip,
            file_name=f"fama_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            mime="application/zip"
        )
    with c2:
        restore_zip = st.file_uploader("Upload backup .zip untuk restore", type=["zip"])
        if restore_zip and st.button("Restore Sekarang", type="primary"):
            restore_full_backup(restore_zip)

    st.markdown("---")

    # === SEMUA KOD ADMIN ASAL KAMU (upload, edit, padam, thumbnail) — 100% SAMA ===
    # Copy semua dari sini sampai habis dari kod asal kamu