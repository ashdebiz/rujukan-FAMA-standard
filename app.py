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
from pdf2image import convert_from_path
import tempfile

# =============================================
# KONFIGURASI
# =============================================
st.set_page_config(page_title="Rujukan FAMA Standard", page_icon="rice", layout="centered")

DB_NAME = "fama_standards.db"
UPLOADS_DIR = "uploads"
THUMBNAILS_DIR = "thumbnails"
BACKUP_DIR = "backups"
CATEGORIES = ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"]
MAX_FILE_SIZE = 10 * 1024 * 1024

for d in [UPLOADS_DIR, THUMBNAILS_DIR, BACKUP_DIR]:
    os.makedirs(d, exist_ok=True)

# Default admin (password: admin123, pengarah123, pegawai123)
DEFAULT_ADMINS = {
    "admin": hashlib.sha256("admin123".encode()).hexdigest(),
    "pengarah": hashlib.sha256("pengarah123".encode()).hexdigest(),
    "pegawai": hashlib.sha256("pegawai123".encode()).hexdigest()
}

# =============================================
# DATABASE
# =============================================
@st.cache_resource
def init_db():
    conn = sqlite3.connect(DB_NAME)
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT,
            file_name TEXT,
            file_path TEXT,
            thumbnail_path TEXT,
            upload_date TEXT,
            uploaded_by TEXT
        );
        CREATE TABLE IF NOT EXISTS admins (username TEXT PRIMARY KEY, password_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT, action TEXT, details TEXT, timestamp TEXT
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
            title, content, category, content='documents', content_rowid='id'
        );
    ''')
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM admins")
    if cur.fetchone()[0] == 0:
        for u, h in DEFAULT_ADMINS.items():
            conn.execute("INSERT INTO admins VALUES (?, ?)", (u, h))
    conn.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
    conn.commit()
    conn.close()

init_db()

def log_activity(user, action, details=""):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO activity_log (username, action, details, timestamp) VALUES (?, ?, ?, ?)",
                (user, action, details, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def rebuild_fts():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
    conn.commit()
    conn.close()

# =============================================
# UTILITI
# =============================================
def extract_text(file):
    data = file.read()
    file.seek(0)
    if file.name.lower().endswith(".pdf"):
        try:
            return "\n".join(p.extract_text() or "" for p in PyPDF2.PdfReader(io.BytesIO(data)).pages)
        except: return ""
    elif file.name.lower().endswith(".docx"):
        try:
            return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
        except: return ""
    return ""

def create_thumbnail(pdf_path, output_path):
    try:
        with tempfile.TemporaryDirectory():
            images = convert_from_path(pdf_path, dpi=120, first_page=1, last_page=1)
            if images:
                img = images[0].convert("RGB")
                img.thumbnail((300, 420))
                img.save(output_path, "JPEG", quality=90)
                return True
    except Exception as e:
        st.warning(f"Thumbnail gagal: {e}")
    return False

# QR Code yang stabil
def generate_qr_code(doc_id):
    base_url = "https://" + st.get_option("server.baseUrl") if st.get_option("server.baseUrl") else "https://your-fama-app.streamlit.app"
    if "app_url" in st.secrets:
        base_url = st.secrets["app_url"]
    url = f"{base_url}/?doc={doc_id}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#2E7D32", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return buffered.getvalue()

@st.cache_data(ttl=3600)
def get_stats():
    conn = sqlite3.connect(DB_NAME)
    total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    today = datetime.now().strftime("%Y-%m-%d")
    today_count = conn.execute("SELECT COUNT(*) FROM documents WHERE upload_date LIKE ?", (f"{today}%",)).fetchone()[0]
    conn.close()
    return total, today_count

# =============================================
# FUNGSI UTAMA
# =============================================
def save_document(title, content, category, uploaded_file, username):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = Path(uploaded_file.name).suffix.lower()
    safe_name = f"{timestamp}_{Path(uploaded_file.name).stem}{ext}"
    file_path = os.path.join(UPLOADS_DIR, safe_name)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(uploaded_file, f)

    thumb_path = None
    if ext == ".pdf":
        thumb_name = f"{Path(safe_name).stem}_thumb.jpg"
        thumb_path = os.path.join(THUMBNAILS_DIR, thumb_name)
        create_thumbnail(file_path, thumb_path)

    conn = sqlite3.connect(DB_NAME)
    conn.execute("""INSERT INTO documents 
        (title, content, category, file_name, file_path, thumbnail_path, upload_date, uploaded_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (title, content, category, uploaded_file.name, file_path, thumb_path or "", 
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username))
    conn.commit()
    conn.close()
    rebuild_fts()
    log_activity(username, "upload", title)
    st.success("Dokumen berjaya disimpan!")

def update_thumbnail(doc_id, image_file, username):
    if not image_file: return
    thumb_path = os.path.join(THUMBNAILS_DIR, f"custom_{doc_id}.jpg")
    img = Image.open(image_file).convert("RGB")
    img.thumbnail((300, 420))
    img.save(thumb_path, "JPEG", quality=90)
    conn = sqlite3.connect(DB_NAME)
    conn.execute("UPDATE documents SET thumbnail_path=? WHERE id=?", (thumb_path, doc_id))
    conn.commit()
    conn.close()
    log_activity(username, "update_thumbnail", f"ID {doc_id}")
    st.success("Thumbnail dikemas kini!")

def delete_document(doc_id, username):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT title, file_path, thumbnail_path FROM documents WHERE id=?", (doc_id,))
    row = cur.fetchone()
    if row:
        title = row[0]
        cur.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        conn.commit()
        for p in [row[1], row[2]]:
            if p and os.path.exists(p):
                try: os.remove(p)
                except: pass
        log_activity(username, "delete", title)
        st.success("Dokumen dipadam.")
    conn.close()
    rebuild_fts()

def search_documents(query="", category=""):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    sql = "SELECT d.id, d.title, d.content, d.file_name, d.file_path, d.thumbnail_path, d.upload_date, d.category, d.uploaded_by FROM documents d"
    params = []
    where = []
    if query.strip():
        sql += " JOIN documents_fts f ON d.id = f.rowid"
        where.append("f MATCH ?")
        params.append(query)
    if category and category != "Semua":
        where.append("d.category = ?")
        params.append(category)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY d.upload_date DESC"
    cur.execute(sql, params)
    results = cur.fetchall()
    conn.close()
    return results

# =============================================
# CSS & LAYOUT
# =============================================
st.markdown("""
<style>
    .card {background: #f9f9f9; padding: 1.5rem; border-radius: 12px; border: 1px solid #ddd; margin: 10px 0;}
    .header {text-align: center; padding: 2rem; background: linear-gradient(90deg, #2E7D32, #4CAF50); color: white; border-radius: 15px;}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png", width=130)
    st.markdown("## Rujukan FAMA Standard")
    page = st.selectbox("Menu", ["Halaman Utama", "Admin Panel"])

# =============================================
# HALAMAN PENGGUNA
# =============================================
if page == "Halaman Utama":
    st.markdown('<div class="header"><h1>RUJUKAN STANDARD FAMA</h1></div>', unsafe_allow_html=True)
    total, today = get_stats()
    c1, c2 = st.columns(2)
    c1.metric("Jumlah Standard", total)
    c2.metric("Baru Hari Ini", today)

    query = st.text_input("Cari standard...", key="q")
    cat = st.selectbox("Kategori", ["Semua"] + CATEGORIES)
    results = search_documents(query, cat if cat != "Semua" else "")

    for doc in results:
        id_, title, content, fname, fpath, thumb, date, cat, uploader = doc
        with st.expander(f"**{title}** • {cat} • {date[:10]}"):
            col1, col2 = st.columns([1, 3])
            with col1:
                # FIX: Pastikan thumbnail wujud
                if thumb and os.path.exists(thumb):
                    st.image(thumb, use_column_width=True)
                else:
                    st.image("https://via.placeholder.com/300x420.png?text=FAMA+Standard", use_column_width=True)
            with col2:
                st.write(content[:500] + ("..." if len(content) > 500 else ""))
                if fpath and os.path.exists(fpath):
                    with open(fpath, "rb") as f:
                        st.download_button("Muat Turun", f.read(), fname)

# =============================================
# ADMIN PANEL
# =============================================
else:
    if not st.session_state.get("admin_logged_in", False):
        st.title("Login Admin")
        user = st.text_input("Nama Pengguna")
        pw = st.text_input("Kata Laluan", type="password")
        if st.button("Log Masuk"):
            conn = sqlite3.connect(DB_NAME)
            cur = conn.execute("SELECT username FROM admins WHERE username=? AND password_hash=?", 
                              (user, hashlib.sha256(pw.encode()).hexdigest()))
            if cur.fetchone():
                st.session_state.admin_logged_in = True
                st.session_state.admin_user = user
                log_activity(user, "login")
                st.rerun()
            else:
                st.error("Salah username atau kata laluan")
        st.stop()

    st.title(f"Admin • {st.session_state.admin_user}")
    if st.button("Log Keluar"):
        log_activity(st.session_state.admin_user, "logout")
        st.session_state.admin_logged_in = False
        st.rerun()

    tab1, tab2 = st.tabs(["Upload Baru", "Senarai & Edit"])

    with tab1:
        st.subheader("Upload Dokumen")
        uploaded = st.file_uploader("PDF/DOCX", type=["pdf", "docx"])
        title = st.text_input("Tajuk Standard")
        cat = st.selectbox("Kategori", CATEGORIES)
        if uploaded and title:
            if uploaded.size > MAX_FILE_SIZE:
                st.error("Fail terlalu besar!")
            else:
                content = extract_text(uploaded)
                if st.button("Simpan", type="primary"):
                    uploaded.seek(0)
                    save_document(title, content, cat, uploaded, st.session_state.admin_user)
                    st.rerun()

    with tab2:
        docs = search_documents()
        for doc in docs:
            id_, title, _, _, _, thumb, date, cat, uploader = doc
            c1, c2, c3 = st.columns([4, 2, 1])
            c1.write(f"**{title}** • {cat} • {date[:10]}")
            c2.write(f"Uploader: {uploader}")
            if c3.button("Edit", key=f"edit_{id_}"):
                st.session_state.current_doc = id_
                st.rerun()

        if "current_doc" in st.session_state:
            doc_id = st.session_state.current_doc
            doc = next((d for d in docs if d[0] == doc_id), None)
            if doc:
                st.markdown("---")
                st.subheader(f"Edit: {doc[1]}")
                colL, colR = st.columns(2)
                with colL:
                    # FIX: Safe image display
                    current_thumb = doc[5] if doc[5] and os.path.exists(doc[5]) else None
                    if current_thumb:
                        st.image(current_thumb, caption="Thumbnail Sekarang")
                    else:
                        st.image("https://via.placeholder.com/300x420.png?text=No+Image", caption="Tiada Thumbnail")
                    
                    new_thumb = st.file_uploader("Ganti Thumbnail", type=["jpg","jpeg","png"], key=f"thumb_{doc_id}")
                    if new_thumb and st.button("Kemas Kini Thumbnail"):
                        update_thumbnail(doc_id, new_thumb, st.session_state.admin_user)
                        st.rerun()

                with colR:
                    st.markdown("### QR Code Akses Terus")
                    qr_img = generate_qr_code(doc_id)
                    st.image(qr_img)
                    st.download_button("Muat Turun QR Code", qr_img, f"QR_{doc[1]}.png", "image/png")
                    st.info(f"Link: `?doc={doc_id}`")

                if st.button("Padam Dokumen Ini", type="secondary"):
                    delete_document(doc_id, st.session_state.admin_user)
                    del st.session_state.current_doc
                    st.rerun()
