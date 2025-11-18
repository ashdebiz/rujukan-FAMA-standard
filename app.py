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
# AUTO DETECT CLOUD + PATH SELAMAT (PENTING!)
# =============================================
if os.getenv("STREAMLIT_CLOUD") or "STREAMLIT" in os.environ:
    DB_NAME = "/tmp/standards_db.sqlite"
    UPLOADS_DIR = "/tmp/uploads"
    THUMBNAILS_DIR = "/tmp/thumbnails"
    BACKUP_DIR = "/tmp/backups"
else:
    DB_NAME = "standards_db.sqlite"
    UPLOADS_DIR = "uploads"
    THUMBNAILS_DIR = "thumbnails"
    BACKUP_DIR = "backups"

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(THUMBNAILS_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

# Sambungan DB dengan WAL (penting untuk Cloud!)
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
# KONFIGURASI STREAMLIT (100% SAMA MACAM KAMU)
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

# =============================================
# INISIALISASI DATABASE + FTS5 (SAMA)
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
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(documents)")
    columns = [col[1] for col in cursor.fetchall()]
    for col in ['category', 'file_name', 'file_path', 'thumbnail_path']:
        if col not in columns:
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
# BACKUP & RESTORE PENUH (BARU + BERFUNGSI DI CLOUD)
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

def restore_full_backup(zip_file):
    try:
        with zipfile.ZipFile(zip_file) as zf:
            zf.extractall("/tmp/restore_temp")
        for folder in [UPLOADS_DIR, THUMBNAILS_DIR]:
            if os.path.exists(folder): shutil.rmtree(folder)
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
# SEMUA FUNGSI LAIN (100% SAMA MACAM KAMU)
# =============================================
@st.cache_data(ttl=300)
def get_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    today = date.today().strftime("%Y-%m-%d")
    today_count = conn.execute("SELECT COUNT(*) FROM documents WHERE upload_date LIKE ?", (f"{today}%",)).fetchone()[0]
    conn.close()
    return total, today_count

def get_document_by_id(doc_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, title, content, category, file_name, file_path, thumbnail_path, upload_date FROM documents WHERE id = ?", (doc_id,))
    result = cur.fetchone()
    conn.close()
    return result

def extract_pdf_text(file):
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except:
        return ""

def extract_docx_text(file):
    try:
        doc = Document(io.BytesIO(file.read()))
        return "\n".join(p.text for p in doc.paragraphs)
    except:
        return ""

@st.cache_data
def get_file_data(file_path):
    with open(file_path, "rb") as f:
        data = f.read()
    mime = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    return data, mime

def save_document(title, content, category, uploaded_file, original_filename, thumbnail_path=None):
    if not title.strip():
        st.error("Tajuk tidak boleh kosong!")
        return
    uploaded_file.seek(0)
    if len(uploaded_file.read()) > MAX_FILE_SIZE:
        st.error("Fail terlalu besar (max 10MB)!")
        return
    uploaded_file.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = Path(original_filename).suffix
    safe_name = f"{timestamp}_{Path(original_filename).stem}{ext}"
    file_path = os.path.join(UPLOADS_DIR, safe_name)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(uploaded_file, f)
    conn = get_db()
    conn.execute("""
        INSERT INTO documents (title, content, category, file_name, file_path, thumbnail_path, upload_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (title, content, category, original_filename, file_path, thumbnail_path,
          datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    sync_fts()
    st.success(f"Dokumen '{title}' berjaya disimpan!")

def delete_document(doc_id):
    doc = get_document_by_id(doc_id)
    if not doc:
        return
    conn = get_db()
    conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()
    for path in [doc[5], doc[6]]:
        if path and os.path.exists(path):
            os.remove(path)
    sync_fts()
    st.success(f"Dokumen ID {doc_id} dipadam.")

def search_documents(query="", category=""):
    conn = get_db()
    cur = conn.cursor()
    sql = """
        SELECT d.title, d.content, d.file_name, d.file_path, d.thumbnail_path, d.upload_date, d.category
        FROM documents d
        JOIN documents_fts f ON d.id = f.rowid
    """
    params = []
    conds = []
    if query:
        conds.append("documents_fts MATCH ?")
        params.append(query)
    if category and category != "Semua":
        conds.append("d.category = ?")
        params.append(category)
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY d.upload_date DESC"
    cur.execute(sql, params)
    results = cur.fetchall()
    conn.close()
    return results

def search_documents_admin(query="", category=""):
    results = search_documents(query, category)
    conn = get_db()
    cur = conn.cursor()
    final = []
    for r in results:
        cur.execute("SELECT id FROM documents WHERE file_path = ?", (r[3],))
        doc_id = cur.fetchone()[0]
        final.append((doc_id, *r))
    conn.close()
    return final

# =============================================
# CSS CUSTOM (100% SAMA MACAM KAMU)
# =============================================
st.markdown("""
<style>
    .main-header {color: #2E7D32; font-size: 2.5em; text-align: center;}
    .stButton>button {width: 100%; margin: 0.3em 0;}
    @media (max-width: 768px) {
        .main-header {font-size: 1.8em;}
        [data-testid="column"] {width: 100% !important;}
    }
</style>
""", unsafe_allow_html=True)

# =============================================
# SIDEBAR & HALAMAN (100% SAMA MACAM KAMU)
# =============================================
with st.sidebar:
    st.markdown("## Navigasi")
    page = st.selectbox("Pilih Halaman", ["Halaman Pengguna", "Halaman Admin"])

# ---------- HALAMAN PENGGUNA ----------
if page == "Halaman Pengguna":
    st.markdown("""
        <div style="text-align:center;">
            <img src="https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png" width="80">
            <h1 class="main-header">RUJUKAN FAMA STANDARD</h1>
        </div>
    """, unsafe_allow_html=True)

    total, today = get_stats()
    c1, c2 = st.columns(2)
    c1.metric("Jumlah Standard", total)
    c2.metric("Baru Hari Ini", today)

    col1, col2, col3, col4 = st.columns(4)
    for col, cat in zip([col1, col2, col3, col4], CATEGORIES):
        with col:
            if st.button(cat, key=f"btn_{cat}"):
                st.session_state.cat_filter = cat
                st.rerun()

    if "cat_filter" not in st.session_state:
        st.session_state.cat_filter = "Semua"

    query = st.text_input("Cari standard...", placeholder="contoh: keratan bunga")
    category = st.selectbox("Kategori", ["Semua"] + CATEGORIES, 
                            index=0 if st.session_state.cat_filter == "Semua" else CATEGORIES.index(st.session_state.cat_filter)+1)

    results = search_documents(query, category if category != "Semua" else "")
    st.write(f"**{len(results)} dokumen ditemui**")

    for title, content, fname, fpath, thumb, date, cat in results:
        with st.expander(f"{title} ({cat}) – {date.split()[0]}"):
            if thumb and os.path.exists(thumb):
                st.image(thumb, width=150)
            st.write(content[:400] + ("..." if len(content)>400 else ""))
            if fpath and os.path.exists(fpath):
                data, mime = get_file_data(fpath)
                st.download_button("Muat Turun", data, file_name=fname or "dokumen.pdf", mime=mime)

# ---------- HALAMAN ADMIN ----------
else:
    st.title("Halaman Admin")
    if not st.session_state.get("authenticated", False):
        pw = st.text_input("Kata laluan", type="password")
        if st.button("Log Masuk"):
            if pw == ADMIN_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Salah kata laluan")
        st.stop()

    if st.button("Log Keluar"):
        st.session_state.authenticated = False
        st.rerun()

    # === BACKUP & RESTORE YANG BARU ===
    st.subheader("Backup & Restore Database (Termasuk Semua Fail)")
    colb1, colb2 = st.columns(2)
    with colb1:
        backup_zip = create_full_backup()
        st.download_button(
            label="Download Backup Penuh (.zip)",
            data=backup_zip,
            file_name=f"fama_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            mime="application/zip"
        )
    with colb2:
        uploaded_backup = st.file_uploader("Upload backup .zip untuk restore", type=["zip"])
        if uploaded_backup and st.button("Pulihkan dari Backup"):
            restore_full_backup(uploaded_backup)

    st.markdown("---")

    # Upload & senarai (sama macam kamu)
    st.subheader("Upload Dokumen Baru")
    uploaded_file = st.file_uploader("PDF/DOCX", type=["pdf", "docx"])
    title = st.text_input("Nama Komoditi / Tajuk")
    category = st.selectbox("Kategori", CATEGORIES)
    if uploaded_file and title:
        uploaded_file.seek(0)
        if len(uploaded_file.read()) > MAX_FILE_SIZE:
            st.error("Fail > 10MB")
        else:
            uploaded_file.seek(0)
            content = extract_pdf_text(uploaded_file) if uploaded_file.name.endswith(".pdf") else extract_docx_text(uploaded_file)
            if st.button("Simpan Dokumen"):
                save_document(title, content, category, uploaded_file, uploaded_file.name)
                st.rerun()

    st.markdown("---")
    st.subheader("Senarai Dokumen")
    admin_results = search_documents_admin()
    for doc_id, title, content, fname, fpath, thumb, date, cat, _ in admin_results:
        col1, col2, col3 = st.columns([4, 1, 1])
        col1.write(f"**{title}** ({cat})")
        if col2.button("Padam", key=f"del_{doc_id}"):
            delete_document(doc_id)
            st.rerun()
        col3.write(date.split()[0])