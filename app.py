import streamlit as st
import sqlite3
import os
import shutil
from datetime import datetime
import zipfile
import io
import PyPDF2
from docx import Document
from pathlib import Path
import mimetypes

# ====================== PATH UNTUK STREAMLIT CLOUD ======================
if os.getenv("STREAMLIT_CLOUD") or "STREAMLIT" in os.environ:
    DB_NAME = "/tmp/standards_db.sqlite"
    UPLOADS_DIR = "/tmp/uploads"
    THUMBNAILS_DIR = "/tmp/thumbnails"
else:
    DB_NAME = "standards_db.sqlite"
    UPLOADS_DIR = "uploads"
    THUMBNAILS_DIR = "thumbnails"

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(THUMBNAILS_DIR, exist_ok=True)

def get_db():
    conn = sqlite3.connect(DB_NAME, timeout=30.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

Path(DB_NAME).parent.mkdir(parents=True, exist_ok=True)
if not os.path.exists(DB_NAME):
    open(DB_NAME, "a").close()

# ====================== KONFIGURASI ======================
st.set_page_config(page_title="Rujukan FAMA Standard", page_icon="rice", layout="centered")
ADMIN_PASSWORD = "admin123"  # Tukar kalau nak
CATEGORIES = ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"]
MAX_FILE_SIZE = 10 * 1024 * 1024

# ====================== INIT DB ======================
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
    conn.close()
init_db()

# ====================== FUNGSI BACKUP & RESTORE ======================
def create_backup_zip():
    backup_bytes = io.BytesIO()
    with zipfile.ZipFile(backup_bytes, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Tambah database
        if os.path.exists(DB_NAME):
            zf.write(DB_NAME, "standards_db.sqlite")
        # Tambah semua fail uploads
        for root, _, files in os.walk(UPLOADS_DIR):
            for f in files:
                fp = os.path.join(root, f)
                arcname = os.path.join("uploads", os.path.relpath(fp, UPLOADS_DIR))
                zf.write(fp, arcname)
        # Tambah semua thumbnail
        for root, _, files in os.walk(THUMBNAILS_DIR):
            for f in files:
                fp = os.path.join(root, f)
                arcname = os.path.join("thumbnails", os.path.relpath(fp, THUMBNAILS_DIR))
                zf.write(fp, arcname)
    backup_bytes.seek(0)
    return backup_bytes

def restore_from_backup(uploaded_zip):
    try:
        with zipfile.ZipFile(uploaded_zip) as zf:
            zf.extractall("/tmp/restore_temp")
        
        # Kosongkan folder sedia ada
        for folder in [UPLOADS_DIR, THUMBNAILS_DIR]:
            if os.path.exists(folder):
                shutil.rmtree(folder)
            os.makedirs(folder, exist_ok=True)
        
        # Salin balik dari temp
        if os.path.exists("/tmp/restore_temp/standards_db.sqlite"):
            shutil.copy2("/tmp/restore_temp/standards_db.sqlite", DB_NAME)
        if os.path.exists("/tmp/restore_temp/uploads"):
            shutil.copytree("/tmp/restore_temp/uploads", UPLOADS_DIR, dirs_exist_ok=True)
        if os.path.exists("/tmp/restore_temp/thumbnails sulla"):
            shutil.copytree("/tmp/restore_temp/thumbnails", THUMBNAILS_DIR, dirs_exist_ok=True)
        
        shutil.rmtree("/tmp/restore_temp")
        st.success("Backup berjaya dipulihkan! App akan refresh...")
        st.rerun()
    except Exception as e:
        st.error(f"Gagal restore: {e}")

# ====================== FUNGSI LAIN ======================
def extract_text(file):
    file.seek(0)
    if file.name.endswith(".pdf"):
        try: return "\n".join(p.extract_text() or "" for p in PyPDF2.PdfReader(io.BytesIO(file.read())).pages)
        except: return ""
    elif file.name.endswith(".docx"):
        try: return "\n".join(p.text for p in Document(io.BytesIO(file.read())).paragraphs)
        except: return ""
    return ""

def save_doc(title, content, category, file, filename):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = Path(filename).suffix
    safe_name = f"{timestamp}_{Path(filename).stem}{ext}"
    path = os.path.join(UPLOADS_DIR, safe_name)
    file.seek(0)
    with open(path, "wb") as f:
        shutil.copyfileobj(file, f)
    conn = get_db()
    conn.execute("""INSERT INTO documents (title, content, category, file_name, file_path, upload_date)
                    VALUES (?,?,?, ?,?, datetime('now','localtime'))""",
                 (title, content, category, filename, path))
    conn.commit()
    conn.close()
    st.success("Dokumen berjaya disimpan!")

def delete_doc(doc_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT file_path FROM documents WHERE id=?", (doc_id,))
    row = cur.fetchone()
    conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
    conn.commit()
    conn.close()
    if row and row[0] and os.path.exists(row[0]):
        os.remove(row[0])
    st.success("Dokumen dipadam!")

def search(q="", cat=""):
    conn = get_db()
    cur = conn.cursor()
    sql = "SELECT d.title,d.content,d.file_name,d.file_path,d.upload_date,d.category,d.id FROM documents d"
    params = []
    if q or (cat and cat != "Semua"):
        sql += " WHERE documents_fts MATCH ?"
        params.append(q or "*")
        if cat and cat != "Semua":
            sql += " AND d.category = ?"
            params.append(cat)
    sql += " ORDER BY d.upload_date DESC"
    cur.execute(sql, params)
    r = cur.fetchall()
    conn.close()
    return r

# ====================== UI ======================
st.markdown("<h1 style='text-align:center;color:#2E7D32;'>Rujukan FAMA Standard</h1>", unsafe_allow_html=True)

with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png", width=130)
    page = st.selectbox("Menu", ["Pengguna", "Admin"])

if page == "Pengguna":
    col1, col2, col3, col4 = st.columns(4)
    for col, label, cat in zip([col1,col2,col3,col4],
                               ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"],
                               CATEGORIES):
        with col:
            if st.button(label):
                st.session_state.cat = cat
                st.rerun()

    query = st.text_input("Cari standard", placeholder="contoh: tomato")
    cat_f = st.selectbox("Kategori", ["Semua"]+CATEGORIES,
                         index=0 if st.session_state.get("cat") not in CATEGORIES else CATEGORIES.index(st.session_state.cat)+1)

    results = search(query, cat_f if cat_f != "Semua" else "")
    st.write(f"**{len(results)} dokumen ditemui**")

    for title, content, fname, fpath, date, cat, _ in results:
        with st.expander(f"{title} • {cat} • {date[:10]}"):
            st.write(content[:500] + ("..." if len(content)>500 else ""))
            if fpath and os.path.exists(fpath):
                with open(fpath, "rb") as f:
                    st.download_button("Muat Turun", f.read(), fname)

else:  # Admin
    if st.session_state.get("auth") != True:
        pw = st.text_input("Kata laluan admin", type="password")
        if st.button("Log Masuk"):
            if pw == ADMIN_PASSWORD:
                st.session_state.auth = True
                st.rerun()
            else: st.error("Salah")
        st.stop()

    st.success("Admin berjaya log masuk")
    if st.button("Log Keluar"): st.session_state.auth = False; st.rerun()

    # ====================== BACKUP & RESTORE ======================
    st.markdown("### Backup & Restore Database")
    colb1, colb2 = st.columns(2)
    with colb1:
        backup_data = create_backup_zip()
        st.download_button(
            label="Download Backup Sekarang (.zip)",
            data=backup_data,
            file_name=f"fama_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.zip",
            mime="application/zip"
        )
    with colb2:
        restore_file = st.file_uploader("Upload backup untuk pulihkan", type=["zip"])
        if restore_file and st.button("Restore dari Backup", type="primary"):
            restore_from_backup(restore_file)

    st.markdown("---")

    # Upload dokumen
    file = st.file_uploader("Upload PDF/DOCX", type=["pdf","docx"])
    title = st.text_input("Tajuk Dokumen")
    cat = st.selectbox("Kategori", CATEGORIES)
    if file and title and st.button("Simpan Dokumen"):
        text = extract_text(file)
        save_doc(title, text, cat, file, file.name)
        st.rerun()

    # Senarai dokumen
    docs = search()
    for _, title, _, fname, _, cat, id_ in docs:
        c1, c2 = st.columns([4,1])
        c1.write(f"**{title}** • {cat} • {fname or 'Tiada fail'}")
        if c2.button("Padam", key=id_):
            delete_doc(id_)
            st.rerun()