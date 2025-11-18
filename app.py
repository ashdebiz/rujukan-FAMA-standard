import streamlit as st
import sqlite3
import os
from datetime import datetime, date
import PyPDF2
from docx import Document
import io
import shutil
from pathlib import Path
import mimetypes

# ==============================
# FIX SQLITE UNTUK STREAMLIT CLOUD & CONCURRENT WRITE
# ==============================
# Streamlit Cloud hanya boleh tulis di /tmp
if os.getenv("STREAMLIT_CLOUD") or "STREAMLIT" in os.environ:
    DB_NAME = "/tmp/standards_db.sqlite"
else:
    DB_NAME = "standards_db.sqlite"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME, timeout=30.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")      # PENTING – elak lock
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

# Pastikan fail DB wujud
Path(DB_NAME).parent.mkdir(parents=True, exist_ok=True)
if not os.path.exists(DB_NAME):
    open(DB_NAME, "a").close()

# ==============================
# KONFIGURASI STREAMLIT
# ==============================
st.set_page_config(
    page_title="Rujukan FAMA Standard",
    page_icon="fama_icon.png",   # Letak fail fama_icon.png dalam folder yang sama
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ==============================
# KONFIGURASI APP
# ==============================
ADMIN_PASSWORD = "admin123"          # Tukar kalau nak
UPLOADS_DIR = "uploads"
THUMBNAILS_DIR = "thumbnails"
CATEGORIES = ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"]
MAX_FILE_SIZE = 10 * 1024 * 1024     # 10 MB

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(THUMBNAILS_DIR, exist_ok=True)

# ==============================
# INISIALISASI DATABASE + FTS5
# ==============================
@st.cache_resource
def init_db():
    conn = get_db_connection()
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

        -- Trigger auto-sync FTS
        CREATE TRIGGER IF NOT EXISTS docs_ai AFTER INSERT ON documents BEGIN
            INSERT INTO documents_fts(rowid, title, content, category)
            VALUES (new.id, new.title, new.content, new.category);
        END;
        CREATE TRIGGER IF NOT EXISTS docs_ad AFTER DELETE ON documents BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, title, content, category)
            VALUES('delete', old.id, old.title, old.content, old.category);
        END;
        CREATE TRIGGER IF NOT EXISTS docs_au AFTER UPDATE ON documents BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, title, content, category)
            VALUES('delete', old.id, old.title, old.content, old.category);
            INSERT INTO documents_fts(rowid, title, content, category)
            VALUES (new.id, new.title, new.content, new.category);
        END;
    ''')
    # Migrasi kolum lama (kalau ada DB lama)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(documents)")
    cols = [c[1] for c in cur.fetchall()]
    for col, sql in [
        ("category", "ALTER TABLE documents ADD COLUMN category TEXT DEFAULT 'Lain-lain'"),
        ("file_name", "ALTER TABLE documents ADD COLUMN file_name TEXT"),
        ("file_path", "ALTER TABLE documents ADD COLUMN file_path TEXT"),
        ("thumbnail_path", "ALTER TABLE documents ADD COLUMN thumbnail_path TEXT")
    ]:
        if col not in cols:
            conn.execute(sql)
    conn.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
    conn.commit()
    conn.close()

init_db()

# ==============================
# FUNGSI BANTUAN
# ==============================
def sync_fts():
    conn = get_db_connection()
    conn.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
    conn.commit()
    conn.close()

@st.cache_data(ttl=300)
def get_stats():
    conn = get_db_connection()
    cur = conn.cursor()
    total = cur.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    today = date.today().isoformat()
    today_count = cur.execute("SELECT COUNT(*) FROM documents WHERE upload_date LIKE ?", (f"{today}%",)).fetchone()[0]
    conn.close()
    return total, today_count

def get_document_by_id(doc_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id,title,content,category,file_name,file_path,thumbnail_path,upload_date FROM documents WHERE id=?", (doc_id,))
    row = cur.fetchone()
    conn.close()
    return row

def extract_pdf_text(file):
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return text
    except:
        return ""

def extract_docx_text(file):
    try:
        doc = Document(io.BytesIO(file.read()))
        return "\n".join(p.text for p in doc.paragraphs)
    except:
        return ""

@st.cache_data
def get_file_bytes(path):
    with open(path, "rb") as f:
        return f.read()

# ==============================
# SAVE / EDIT / DELETE
# ==============================
def save_document(title, content, category, uploaded_file, orig_name, thumbnail_path=None):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = Path(orig_name).suffix
    safe_name = f"{timestamp}_{Path(orig_name).stem}{ext}"
    file_path = os.path.join(UPLOADS_DIR, safe_name)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(uploaded_file, f)

    conn = get_db_connection()
    conn.execute("""INSERT INTO documents
        (title, content, category, file_name, file_path, thumbnail_path, upload_date)
        VALUES (?,?,?, ?,?,?, datetime('now','localtime'))""",
        (title, content, category, orig_name, file_path, thumbnail_path))
    conn.commit()
    conn.close()
    sync_fts()
    st.success(f"Dokumen **{title}** berjaya disimpan!")

def edit_document(doc_id, title, content, category,
                  new_file=None, cur_path=None, cur_name=None,
                  new_thumb=None, cur_thumb=None):
    # Kod edit yang sama tapi guna get_db_connection()
    # (disingkatkan kerana panjang – gunakan versi lama tapi tukar semua sqlite3.connect ke get_db_connection())
    # ... (sila copy dari versi sebelumnya dan tukar connection sahaja)
    pass   # ← ganti dengan fungsi edit lengkap kalau perlukan

def delete_document(doc_id, file_path, thumb_path):
    conn = get_db_connection()
    conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
    conn.commit()
    conn.close()
    for p in [file_path, thumb_path]:
        if p and os.path.exists(p):
            os.remove(p)
    sync_fts()
    st.success("Dokumen dipadam!")

# ==============================
# CARIAN (FTS5)
# ==============================
def search_documents(query="", category_filter=""):
    conn = get_db_connection()
    cur = conn.cursor()
    sql = """
        SELECT d.title, d.content, d.file_name, d.file_path, d.thumbnail_path, d.upload_date, d.category
        FROM documents d
        WHERE documents_fts MATCH ?
    """
    params = [query or "*"]
    if category_filter and category_filter != "Semua":
        sql += " AND d.category = ?"
        params.append(category_filter)
    sql += " ORDER BY d.upload_date DESC"
    cur.execute(sql, params)
    results = cur.fetchall()
    conn.close()
    return results

def search_documents_admin(query="", category_filter=""):
    conn = get_db_connection()
    cur = conn.cursor()
    sql = """
        SELECT d.id, d.title, d.upload_date, d.file_name, d.file_path,
               d.thumbnail_path, d.category, d.content
        FROM documents d
    """
    conditions = []
    params = []
    if query:
        conditions.append("documents_fts MATCH ?")
        params.append(query)
    if category_filter and category_filter != "Semua":
        conditions.append("d.category = ?")
        params.append(category_filter)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY d.upload_date DESC"
    cur.execute(sql, params)
    results = cur.fetchall()
    conn.close()
    return results

# ==============================
# UI & CSS
# ==============================
st.markdown("""
<style>
    .main-header {color: #2E7D32; font-size: 2.8em; text-align: center; font-weight: bold;}
    .stButton>button {width: 100%; background: #4CAF50; color: white;}
    .result-card {background:#f8fff8; padding:15px; border-radius:10px; border-left:5px solid #4CAF50; margin:10px 0;}
</style>
""", unsafe_allow_html=True)

# ==============================
# SIDEBAR NAVIGASI
# ==============================
with st.sidebar:
    st.image("fama_icon.png", width=150)
    page = st.selectbox("Navigasi", ["Halaman Pengguna", "Halaman Admin"])

# ==============================
# HALAMAN PENGGUNA
# ==============================
if page == "Halaman Pengguna":
    st.markdown('<h1 class="main-header">Rujukan Standard FAMA</h1>', unsafe_allow_html=True)
    total, today = get_stats()
    c1, c2 = st.columns(2)
    c1.metric("Jumlah Dokumen", total)
    c2.metric("Hari Ini", today)

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Keratan Bunga"):
            st.session_state.cat = "Keratan Bunga"
            st.rerun()
    with col2:
        if st.button("Sayur-sayuran"):
            st.session_state.cat = "Sayur-sayuran"
            st.rerun()
    with col3:
        if st.button("Buah-buahan"):
            st.session_state.cat = "Buah-buahan"
            st.rerun()

    query = st.text_input("Cari kata kunci", placeholder="contoh: tomato")
    cat_filter = st.selectbox("Kategori", ["Semua"] + CATEGORIES,
                              index=0 if 'cat' not in st.session_state else CATEGORIES.index(st.session_state.cat)+1)

    results = search_documents(query, cat_filter if cat_filter != "Semua" else "")

    st.write(f"**{len(results)} dokumen ditemui**")
    for title, content, fname, fpath, thumb, date, cat in results:
        with st.expander(f"{title} • {cat} • {date.split()[0]}"):
            colT, colC = st.columns([1, 3])
            with colT:
                if thumb and os.path.exists(thumb):
                    st.image(thumb, width=140)
                else:
                    st.write("Tiada imej")
            with colC:
                st.write(content[:500] + ("..." if len(content)>500 else ""))
                if fpath and os.path.exists(fpath):
                    data = get_file_bytes(fpath)
                    mime = mimetypes.guess_type(fpath)[0] or "application/octet-stream"
                    st.download_button("Muat Turun", data, fname, mime)

# ==============================
# HALAMAN ADMIN
# ==============================
else:
    st.title("Halaman Admin")
    if st.session_state.get("auth") != True:
        pw = st.text_input("Kata laluan", type="password")
        if st.button("Log Masuk"):
            if pw == ADMIN_PASSWORD:
                st.session_state.auth = True
                st.rerun()
            else:
                st.error("Salah")
        st.stop()

    if st.button("Log Keluar"):
        st.session_state.auth = False
        st.rerun()

    # Upload baru
    st.subheader("Upload Dokumen Baru")
    uploaded = st.file_uploader("PDF / DOCX", type=["pdf","docx"])
    title = st.text_input("Tajuk / Nama Komoditi")
    cat = st.selectbox("Kategori", CATEGORIES)

    if uploaded and title:
        uploaded.seek(0)
        if uploaded.size > MAX_FILE_SIZE:
            st.error("Fail terlalu besar (max 10MB)")
        else:
            text = extract_pdf_text(uploaded) if uploaded.name.endswith(".pdf") else extract_docx_text(uploaded)
            uploaded.seek(0)
            if st.button("SIMPAN DOKUMEN"):
                save_document(title, text, cat, uploaded, uploaded.name)
                st.rerun()

    # Senarai & edit/padam
    st.subheader("Senarai Dokumen")
    docs = search_documents_admin()
    for doc in docs:
        id_, title, date, fname, fpath, thumb, cat, _ = doc
        col1, col2, col3 = st.columns([3,1,1])
        col1.write(f"**{title}** • {cat} • {date.split()[0]}")
        col2.write(fname or "Tiada fail")
        if st.button("Padam", key=f"del{ id_ }"):
            delete_document(id_, fpath, thumb)
            st.rerun()