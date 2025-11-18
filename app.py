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
# AUTO DETECT STREAMLIT CLOUD + PATH SELAMAT
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
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

# Pastikan DB wujud
Path(DB_NAME).parent.mkdir(parents=True, exist_ok=True)
if not os.path.exists(DB_NAME):
    open(DB_NAME, "a").close()

# =============================================
# KONFIGURASI STREAMLIT
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
# INIT DB + FTS5
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

        CREATE TRIGGER IF NOT EXISTS ai AFTER INSERT ON documents BEGIN
            INSERT INTO documents_fts(rowid, title, content, category)
            VALUES (new.id, new.title, new.content, new.category);
        END;
        CREATE TRIGGER IF NOT EXISTS ad AFTER DELETE ON documents BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, title, content, category)
            VALUES('delete', old.id, old.title, old.content, old.category);
        END;
        CREATE TRIGGER IF NOT EXISTS au AFTER UPDATE ON documents BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, title, content, category)
            VALUES('delete', old.id, old.title, old.content, old.category);
            INSERT INTO documents_fts(rowid, title, content, category)
            VALUES (new.id, new.title, new.content, new.category);
        END;
    ''')
    # Migrasi kolum lama
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(documents)")
    cols = [c[1] for c in cur.fetchall()]
    for col in ['category', 'file_name', 'file_path', 'thumbnail_path']:
        if col not in cols:
            conn.execute(f"ALTER TABLE documents ADD COLUMN {col} TEXT")
    conn.commit()
    conn.close()

init_db()

# =============================================
# BACKUP & RESTORE (BERFUNGSI DI CLOUD!)
# =============================================
def create_full_backup():
    memory_zip = io.BytesIO()
    with zipfile.ZipFile(memory_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Database
        if os.path.exists(DB_NAME):
            zf.write(DB_NAME, "standards_db.sqlite")
        # 2. Semua fail uploads
        for root, _, files in os.walk(UPLOADS_DIR):
            for f in files:
                fp = os.path.join(root, f)
                arcname = os.path.join("uploads", os.path.relpath(fp, UPLOADS_DIR))
                zf.write(fp, arcname)
        # 3. Semua thumbnail
        for root, _, files in os.walk(THUMBNAILS_DIR):
            for f in files:
                fp = os.path.join(root, f)
                arcname = os.path.join("thumbnails", os.path.relpath(fp, THUMBNAILS_DIR))
                zf.write(fp, arcname)
    memory_zip.seek(0)
    return memory_zip

def restore_full_backup(uploaded_zip):
    try:
        with zipfile.ZipFile(uploaded_zip) as zf:
            zf.extractall("/tmp/restore_temp")

        # Kosongkan folder sedia ada
        for folder in [UPLOADS_DIR, THUMBNAILS_DIR]:
            if os.path.exists(folder):
                shutil.rmtree(folder)
            os.makedirs(folder, exist_ok=True)

        # Salin balik
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
# FUNGSI LAIN (kekalkan kod kamu)
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
    cur.execute("SELECT id,title,content,category,file_name,file_path,thumbnail_path,upload_date FROM documents WHERE id=?", (doc_id,))
    row = cur.fetchone()
    conn.close()
    return row

def extract_text(file):
    file.seek(0)
    if file.name.endswith(".pdf"):
        try: return "\n".join(p.extract_text() or "" for p in PyPDF2.PdfReader(io.BytesIO(file.read())).pages)
        except: return ""
    elif file.name.endswith(".docx"):
        try: return "\n".join(p.text for p in Document(io.BytesIO(file.read())).paragraphs)
        except: return ""
    return ""

def save_document(title, content, category, uploaded_file, original_filename):
    if not title.strip(): 
        st.error("Tajuk tidak boleh kosong!"); return
    if uploaded_file.size > MAX_FILE_SIZE:
        st.error("Fail terlalu besar!"); return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = Path(original_filename).suffix
    safe_name = f"{timestamp}_{Path(original_filename).stem}{ext}"
    file_path = os.path.join(UPLOADS_DIR, safe_name)
    uploaded_file.seek(0)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(uploaded_file, f)

    conn = get_db()
    conn.execute("""INSERT INTO documents 
        (title, content, category, file_name, file_path, upload_date)
        VALUES (?,?,?, ?,?, datetime('now','localtime'))""",
        (title, content, category, original_filename, file_path))
    conn.commit()
    conn.close()
    st.success("Dokumen berjaya disimppkan!")

def delete_document(doc_id):
    doc = get_document_by_id(doc_id)
    if not doc: return
    conn = get_db()
    conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
    conn.commit()
    conn.close()
    for p in [doc[5], doc[6]]:  # file_path, thumbnail_path
        if p and os.path.exists(p): os.remove(p)
    st.success("Dokumen dipadam!")

def search_documents(query="", category=""):
    conn = get_db()
    cur = conn.cursor()
    sql = "SELECT d.title,d.content,d.file_name,d.file_path,d.thumbnail_path,d.upload_date,d.category FROM documents d"
    params = []
    if query or (category and category != "Semua"):
        sql += " WHERE documents_fts MATCH ?"
        params.append(query or "*")
        if category and category != "Semua":
            sql += " AND d.category = ?"
            params.append(category)
    sql += " ORDER BY d.upload_date DESC"
    cur.execute(sql, params)
    results = cur.fetchall()
    conn.close()
    return results

# =============================================
# CSS + UI (kekalkan yang cantik)
# =============================================
st.markdown("""
<style>
    .main-header {color: #2E7D32; font-size: 2.5em; text-align: center; font-weight: bold;}
    .stButton>button {background:#4CAF50; color:white; width:100%; padding:12px;}
    @media (max-width:768px) {.main-header{font-size:1.9em;}}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png", width=120)
    page = st.selectbox("Menu", ["Halaman Pengguna", "Halaman Admin"])

# =============================================
# HALAMAN PENGGUNA
# =============================================
if page == "Halaman Pengguna":
    st.markdown('<h1 class="main-header">RUJUKAN FAMA STANDARD</h1>', unsafe_allow_html=True)
    total, today = get_stats()
    c1, c2 = st.columns(2)
    c1.metric("Jumlah Standard", total)
    c2.metric("Baru Hari Ini", today)

    col1, col2, col3, col4 = st.columns(4)
    for col, cat in zip([col1,col2,col3,col4], CATEGORIES):
        with col:
            if st.button(cat):
                st.session_state.cat = cat
                st.rerun()

    if "cat" not in st.session_state: st.session_state.cat = "Semua"
    query = st.text_input("Cari standard...")
    cat_filter = st.selectbox("Kategori", ["Semua"]+CATEGORIES,
                              index=0 if st.session_state.cat=="Semua" else CATEGORIES.index(st.session_state.cat)+1)

    results = search_documents(query, cat_filter if cat_filter!="Semua" else "")
    st.write(f"**{len(results)} dokumen ditemui**")

    for title, content, fname, fpath, thumb, date, cat in results:
        with st.expander(f"{title} • {cat} • {date[:10]}"):
            if thumb and os.path.exists(thumb):
                st.image(thumb, width=150)
            st.write(content[:400] + ("..." if len(content)>400 else ""))
            if fpath and os.path.exists(fpath):
                with open(fpath, "rb") as f:
                    st.download_button("Muat Turun", f.read(), fname or "dokumen.pdf")

# =============================================
# HALAMAN ADMIN
# =============================================
else:
    if st.session_state.get("auth") != True:
        pw = st.text_input("Kata laluan", type="password")
        if st.button("Log Masuk"):
            if pw == ADMIN_PASSWORD:
                st.session_state.auth = True
                st.rerun()
            else: st.error("Salah")
        st.stop()

    st.success("Admin log masuk")
    if st.button("Log Keluar"): st.session_state.auth = False; st.rerun()

    # === BACKUP & RESTORE YANG BERFUNGSI DI CLOUD ===
    st.markdown("### Backup & Restore Database (Termasuk Semua Fail)")
    col1, col2 = st.columns(2)
    with col1:
        backup_data = create_full_backup()
        st.download_button(
            label="Download Backup Penuh (.zip)",
            data=backup_data,
            file_name=f"fama_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.zip",
            mime="application/zip"
        )
    with col2:
        restore_zip = st.file_uploader("Upload backup .zip untuk pulihkan", type=["zip"])
        if restore_zip and st.button("Restore dari Backup", type="primary"):
            restore_full_backup(restore_zip)

    st.markdown("---")

    # Upload dokumen
    file = st.file_uploader("Upload PDF/DOCX", type=["pdf","docx"])
    title = st.text_input("Tajuk Dokumen")
    cat = st.selectbox("Kategori", CATEGORIES)
    if file and title and st.button("Simpan Dokumen"):
        text = extract_text(file)
        save_document(title, text, cat, file, file.name)
        st.rerun()

    # Senarai & padam
    docs = search_documents()
    for _, title, _, fname, _, date, cat in docs:
        c1, c2 = st.columns([4,1])
        c1.write(f"**{title}** • {cat} • {date[:10]}")
        if c2.button("Padam", key=title):
            # Cari ID dari fail path (simple way)
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT id FROM documents WHERE title=?", (title,))
            row = cur.fetchone()
            conn.close()
            if row:
                delete_document(row[0])
                st.rerun()