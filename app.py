import streamlit as st
import sqlite3
import os
import shutil
from datetime import datetime
from pathlib import Path
import PyPDF2
from docx import Document
import io
import mimetypes
from pdf2image import convert_from_path
from PIL import Image
import tempfile
import hashlib
import time

# =============================================
# KONFIGURASI STREAMLIT + DARK MODE
# =============================================
st.set_page_config(
    page_title="Rujukan FAMA Standard",
    page_icon="rice",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Dark mode toggle
if "theme" not in st.session_state:
    st.session_state.theme = "light"

def toggle_theme():
    st.session_state.theme = "dark" if st.session_state.theme == "light" else "light"

# Apply theme
theme = st.session_state.theme
bg_color = "#121212" if theme == "dark" else "#FFFFFF"
text_color = "#FFFFFF" if theme == "dark" else "#000000"
card_bg = "#1E1E1E" if theme == "dark" else "#F8F9FA"
border_color = "#333333" if theme == "dark" else "#DEE2E6"

# =============================================
# KONFIGURASI
# =============================================
DB_NAME = "fama_standards.db"
UPLOADS_DIR = "uploads"
THUMBNAILS_DIR = "thumbnails"
BACKUP_DIR = "backups"
CATEGORIES = ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"]
MAX_FILE_SIZE = 10 * 1024 * 1024

for d in [UPLOADS_DIR, THUMBNAILS_DIR, BACKUP_DIR]:
    os.makedirs(d, exist_ok=True)

# Default admin (hanya pertama kali)
DEFAULT_ADMINS = {
    "admin": hashlib.sha256("fama2025".encode()).hexdigest(),  # kata laluan: fama2025
    "pengarah": hashlib.sha256("fama123".encode()).hexdigest(),
    "pegawai1": hashlib.sha256("pegawai123".encode()).hexdigest()
}

# =============================================
# DATABASE & LOG
# =============================================
@st.cache_resource
def init_db():
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'Lain-lain',
                file_name TEXT,
                file_path TEXT,
                thumbnail_path TEXT,
                upload_date TEXT NOT NULL,
                uploaded_by TEXT
            );

            CREATE TABLE IF NOT EXISTS admins (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                full_name TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                action TEXT,
                details TEXT,
                timestamp TEXT
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                title, content, category, content='documents', content_rowid='id'
            );
        ''')

        # Cipta admin default jika tiada
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM admins")
        if cur.fetchone()[0] == 0:
            for username, hash_pass in DEFAULT_ADMINS.items():
                conn.execute("INSERT INTO admins (username, password_hash, full_name, created_at) VALUES (?, ?, ?, ?)",
                            (username, hash_pass, username.capitalize(), datetime.now().isoformat()))

        # Trigger FTS (drop dulu untuk elak error)
        conn.executescript('''
            DROP TRIGGER IF EXISTS doc_ai;
            DROP TRIGGER IF EXISTS doc_ad;
            CREATE TRIGGER doc_ai AFTER INSERT ON documents BEGIN
                INSERT INTO documents_fts(rowid, title, content, category)
                VALUES (new.id, new.title, new.content, new.category);
            END;
            CREATE TRIGGER doc_ad AFTER DELETE ON documents BEGIN
                INSERT INTO documents_fts(documents_fts, rowid, title, content, category)
                VALUES ('delete', old.id, old.title, old.content, old.category);
            END;
        ''')
        conn.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
        conn.commit()
    except sqlite3.Error as e:
        st.error(f"Error init DB: {e}")
    finally:
        conn.close()

init_db()

def log_activity(username, action, details=""):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO activity_log (username, action, details, timestamp) VALUES (?, ?, ?, ?)",
                (username, action, details, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
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
def hash_password(pw): return hashlib.sha256(pw.encode()).hexdigest()

def extract_text(file):
    data = file.read()
    file.seek(0)
    if file.name.lower().endswith(".pdf"):
        try:
            reader = PyPDF2.PdfReader(io.BytesIO(data))
            return "\n".join(p.extract_text() or "" for p in reader.pages)
        except: return ""
    elif file.name.lower().endswith(".docx"):
        try:
            doc = Document(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs)
        except: return ""
    return ""

def create_thumbnail(pdf_path, output_path):
    try:
        with tempfile.TemporaryDirectory():
            images = convert_from_path(pdf_path, dpi=120, first_page=1, last_page=1)
            if images:
                img = images[0].convert("RGB")
                img.thumbnail((280, 380))
                img.save(output_path, "JPEG", quality=90)
                return True
    except: pass
    return False

@st.cache_data(ttl=3600)
def get_stats():
    conn = sqlite3.connect(DB_NAME)
    total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    today = datetime.now().strftime("%Y-%m-%d")
    today_count = conn.execute("SELECT COUNT(*) FROM documents WHERE upload_date LIKE ?", (f"{today}%",)).fetchone()[0]
    conn.close()
    return total, today_count

# =============================================
# SAVE / DELETE
# =============================================
def save_document(title, content, category, uploaded_file, username):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = Path(uploaded_file.name).suffix.lower()
    safe_name = f"{timestamp}_{Path(uploaded_file.name).stem}{ext}"
    file_path = os.path.join(UPLOADS_DIR, safe_name)

    with open(file_path, "wb") as f:
        shutil.copyfileobj(uploaded_file, f)

    thumbnail_path = None
    if ext == ".pdf":
        thumb_name = f"{Path(safe_name).stem}_thumb.jpg"
        thumbnail_path = os.path.join(THUMBNAILS_DIR, thumb_name)
        create_thumbnail(file_path, thumbnail_path)

    conn = sqlite3.connect(DB_NAME)
    conn.execute("""INSERT INTO documents 
        (title, content, category, file_name, file_path, thumbnail_path, upload_date, uploaded_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (title, content, category, uploaded_file.name, file_path, thumbnail_path,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username))
    conn.commit()
    conn.close()
    rebuild_fts()
    log_activity(username, "upload", f"{title}")
    st.success(f"Berjaya disimpan oleh {username}!")

def delete_document(doc_id, username):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT title, file_path, thumbnail_path FROM documents WHERE id=?", (doc_id,))
    row = cur.fetchone()
    if row:
        title = row[0]
        cur.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        conn.commit()
        for p in row[1:]:
            if p and os.path.exists(p):
                try: os.remove(p)
                except: pass
        log_activity(username, "delete", title)
        st.success(f"Dokumen '{title}' dipadam.")
    conn.close()
    rebuild_fts()

# =============================================
# CARIAN (DIPERBAIKI - FIXED SQL ERROR)
# =============================================
def search_documents(query="", category=""):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    base_sql = "SELECT d.id, d.title, d.content, d.file_name, d.file_path, d.thumbnail_path, d.upload_date, d.category, d.uploaded_by FROM documents d"
    params = []
    where_conditions = []
    join_clause = ""
    
    if query.strip():
        join_clause = "JOIN documents_fts f ON d.id = f.rowid"
        where_conditions.append("f MATCH ?")
        params.append(query)
    
    if category and category != "Semua":
        where_conditions.append("d.category = ?")
        params.append(category)
    
    sql = base_sql + " " + join_clause
    if where_conditions:
        sql += " WHERE " + " AND ".join(where_conditions)
    sql += " ORDER BY d.upload_date DESC"
    
    try:
        cur.execute(sql, params)
        results = cur.fetchall()
    except sqlite3.Error as e:
        st.error(f"Error carian: {e}")
        results = []
    
    conn.close()
    return results

# =============================================
# BACKUP & RESTORE (Tambahan)
# =============================================
def backup_database():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"fama_backup_{timestamp}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_file)
    shutil.copy(DB_NAME, backup_path)
    with open(backup_path, "rb") as f:
        st.download_button("Muat Turun Backup", f.read(), backup_file, mime="application/octet-stream")
    log_activity(st.session_state.admin_user, "backup")

def restore_database(uploaded_file, username):
    if not uploaded_file.name.endswith(".db"):
        st.error("Fail mesti .db")
        return
    shutil.copy(DB_NAME, os.path.join(BACKUP_DIR, f"pre_restore_{datetime.now():%Y%m%d_%H%M%S}.db"))
    with open(DB_NAME, "wb") as f:
        f.write(uploaded_file.getbuffer())
    rebuild_fts()
    log_activity(username, "restore")
    st.success("Database dipulihkan!")
    st.rerun()

# =============================================
# CSS + HEADER
# =============================================
st.markdown(f"""
<style>
    .main {{background-color: {bg_color}; color: {text_color};}}
    .card {{background: {card_bg}; padding: 1.5rem; border-radius: 12px; border: 1px solid {border_color}; margin: 10px 0;}}
    .header {{text-align: center; padding: 2rem; background: linear-gradient(90deg, #2E7D32, #4CAF50); color: white; border-radius: 15px;}}
    .stButton>button {{background: #4CAF50; color: white; border-radius: 8px;}}
    .log-entry {{background: {card_bg}; padding: 0.8rem; border-left: 4px solid #4CAF50; margin: 5px 0; border-radius: 8px;}}
    .error {{color: #d32f2f;}}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png", width=130)
    st.markdown("## Rujukan Standard FAMA")
    if st.button(f"{'🌙 Dark' if theme == 'light' else '☀️ Light'} Mode"):
        toggle_theme()
        st.rerun()
    page = st.selectbox("Menu", ["Halaman Utama", "Carian", "Admin Panel"])

# =============================================
# HALAMAN UTAMA & CARIAN
# =============================================
if page in ["Halaman Utama", "Carian"]:
    st.markdown('<div class="header"><h1>RUJUKAN STANDARD FAMA</h1><p>Sistem Rujukan Digital Rasmi</p></div>', unsafe_allow_html=True)
    
    total, today = get_stats()
    col1, col2, col3 = st.columns(3)
    col1.metric("Jumlah Dokumen", total)
    col2.metric("Baru Hari Ini", today)
    col3.metric("Kategori", len(CATEGORIES))

    cols = st.columns(len(CATEGORIES))
    for col, cat in zip(cols, CATEGORIES):
        if col.button(cat, use_container_width=True):
            st.session_state.cat = cat
            st.rerun()

    query = st.text_input("Cari standard...", placeholder="Contoh: tomato, bunga ros, standard timun...", key="q")
    cat_filter = st.session_state.get("cat", "Semua")
    category = st.selectbox("Kategori", ["Semua"] + CATEGORIES, index=0 if cat_filter == "Semua" else CATEGORIES.index(cat_filter)+1)

    results = search_documents(query, category if category != "Semua" else "")

    st.markdown(f"### Ditemui: {len(results)} dokumen")
    for doc in results:
        id_, title, content, fname, fpath, thumb, date, cat, uploader = doc
        with st.container():
            st.markdown(f"<div class='card'>", unsafe_allow_html=True)
            col_a, col_b = st.columns([1, 3])
            with col_a:
                img = thumb if thumb and os.path.exists(thumb) else "https://via.placeholder.com/280x380.png?text=FAMA+Standard"
                st.image(img, use_column_width=True)
            with col_b:
                st.subheader(title)
                st.caption(f"{cat} • {date[:10]} • Oleh: {uploader}")
                st.write(content[:380] + ("..." if len(content) > 380 else ""))
                if fpath and os.path.exists(fpath):
                    with open(fpath, "rb") as f:
                        st.download_button("Muat Turun PDF/DOCX", f.read(), fname, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

# =============================================
# ADMIN PANEL (Multi-User + Log)
# =============================================
else:
    if not st.session_state.get("admin_logged_in"):
        st.title("Login Admin")
        username = st.text_input("Nama Pengguna")
        password = st.text_input("Kata Laluan", type="password")
        if st.button("Log Masuk"):
            conn = sqlite3.connect(DB_NAME)
            cur = conn.execute("SELECT username, full_name FROM admins WHERE username=? AND password_hash=?", 
                              (username, hash_password(password)))
            user = cur.fetchone()
            conn.close()
            if user:
                st.session_state.admin_logged_in = True
                st.session_state.admin_user = user[0]
                st.session_state.admin_name = user[1] or user[0]
                log_activity(user[0], "login")
                st.success(f"Selamat kembali, {st.session_state.admin_name}!")
                st.rerun()
            else:
                st.error("Nama pengguna atau kata laluan salah")
        st.stop()

    col1, col2 = st.columns([3,1])
    with col1:
        st.title(f"Admin Panel • {st.session_state.admin_name}")
    with col2:
        if st.button("Log Keluar"):
            log_activity(st.session_state.admin_user, "logout")
            st.session_state.admin_logged_in = False
            st.rerun()

    tab1, tab2, tab3, tab4 = st.tabs(["Upload", "Senarai", "Log Aktiviti", "Backup"])

    with tab1:
        st.subheader("Upload Dokumen Baru")
        uploaded = st.file_uploader("PDF atau DOCX (max 10MB)", type=["pdf", "docx"])
        title = st.text_input("Tajuk Standard")
        cat = st.selectbox("Kategori", CATEGORIES)
        if uploaded and title:
            if uploaded.size > MAX_FILE_SIZE:
                st.error("Fail terlalu besar!")
            else:
                content = extract_text(uploaded)
                if st.button("Simpan Dokumen", type="primary"):
                    uploaded.seek(0)
                    save_document(title, content, cat, uploaded, st.session_state.admin_user)
                    st.rerun()

    with tab2:
        docs = search_documents()
        for doc in docs:
            id_, title, _, fname, _, thumb, date, cat, uploader = doc
            c1, c2, c3 = st.columns([4,2,1])
            c1.write(f"**{title}** • {cat} • {date[:10]}")
            c2.write(f"Uploader: {uploader}")
            if c3.button("Padam", key=f"del_{id_}"):
                delete_document(id_, st.session_state.admin_user)
                st.rerun()

    with tab3:
        st.subheader("Log Aktiviti Terkini")
        conn = sqlite3.connect(DB_NAME)
        logs = conn.execute("SELECT username, action, details, timestamp FROM activity_log ORDER BY timestamp DESC LIMIT 50").fetchall()
        conn.close()
        for user, action, details, ts in logs:
            st.markdown(f"<div class='log-entry'><b>{user}</b> → {action} {details} <i>{ts}</i></div>", unsafe_allow_html=True)

    with tab4:
        st.subheader("Backup Database")
        if st.button("Buat Backup Sekarang"):
            backup_database()
        restore_file = st.file_uploader("Restore dari Backup (.db)", type=["db"])
        if st.button("Pulihkan Database") and restore_file:
            restore_database(restore_file, st.session_state.admin_user)
