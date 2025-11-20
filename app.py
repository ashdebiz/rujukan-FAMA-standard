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
# KONFIGURASI STREAMLIT + DARK MODE
# =============================================
st.set_page_config(page_title="Rujukan Standard FAMA", page_icon="rice", layout="centered")

# Dark mode toggle
if "theme" not in st.session_state:
    st.session_state.theme = "light"

def toggle_theme():
    st.session_state.theme = "dark" if st.session_state.theme == "light" else "light"

theme = st.session_state.theme
bg = "#121212" if theme == "dark" else "#FFFFFF"
text = "#FFFFFF" if theme == "dark" else "#000000"
card = "#1E1E1E" if theme == "dark" else "#F8F9FA"

# =============================================
# KONFIGURASI & FOLDER
# =============================================
DB_NAME = "fama_standards.db"
UPLOADS_DIR = "uploads"
THUMBNAILS_DIR = "thumbnails"
BACKUP_DIR = "backups"
CATEGORIES = ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"]
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

for d in [UPLOADS_DIR, THUMBNAILS_DIR, BACKUP_DIR]:
    os.makedirs(d, exist_ok=True)

# =============================================
# DATABASE INIT
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
        CREATE TABLE IF NOT EXISTS admins (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL
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
    # Default admin
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM admins")
    if cur.fetchone()[0] == 0:
        conn.execute("INSERT INTO admins VALUES ('admin', ?)", (hashlib.sha256("fama2025".encode()).hexdigest(),))
        conn.execute("INSERT INTO admins VALUES ('pengarah', ?)", (hashlib.sha256("fama123".encode()).hexdigest(),))
    conn.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
    conn.commit()
    conn.close()

init_db()

def log_activity(user, action, details=""):
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.execute("INSERT INTO activity_log (username, action, details, timestamp) VALUES (?, ?, ?, ?)",
                    (user, action, details, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
    except: pass

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
            reader = PyPDF2.PdfReader(io.BytesIO(data))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except: return ""
    elif file.name.lower().endswith(".docx"):
        try:
            doc = Document(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs)
        except: return ""
    return ""

def create_pdf_thumbnail(pdf_path, output_path):
    try:
        with tempfile.TemporaryDirectory():
            images = convert_from_path(pdf_path, dpi=150, first_page=1, last_page=1)
            if images:
                img = images[0].convert("RGB")
                img.thumbnail((300, 420))
                img.save(output_path, "JPEG", quality=90)
                return True
    except: pass
    return False

def generate_qr(doc_id):
    base_url = "https://your-fama-app.streamlit.app"
    if "app_url" in st.secrets:
        base_url = st.secrets["app_url"]
    url = f"{base_url}/?doc={doc_id}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#2E7D32", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def get_total_docs():
    conn = sqlite3.connect(DB_NAME)
    total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    conn.close()
    return total

# =============================================
# FUNGSI CRUD
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
        create_pdf_thumbnail(file_path, thumb_path)

    conn = sqlite3.connect(DB_NAME)
    conn.execute("""INSERT INTO documents 
        (title, content, category, file_name, file_path, thumbnail_path, upload_date, uploaded_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (title, content, category, uploaded_file.name, file_path, thumb_path or "",
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username))
    conn.commit()
    new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    rebuild_fts()
    log_activity(username, "upload", f"{title} (ID: {new_id})")
    return new_id

def upload_thumbnail(doc_id, image_file, username):
    thumb_path = os.path.join(THUMBNAILS_DIR, f"thumb_{doc_id}.jpg")
    img = Image.open(image_file).convert("RGB")
    img.thumbnail((300, 420))
    img.save(thumb_path, "JPEG", quality=90)
    conn = sqlite3.connect(DB_NAME)
    conn.execute("UPDATE documents SET thumbnail_path=? WHERE id=?", (thumb_path, int(doc_id)))
    conn.commit()
    conn.close()
    log_activity(username, "update_thumbnail", f"ID {doc_id}")
    st.success(f"Thumbnail berjaya dikemaskini untuk ID {doc_id}!")

def delete_document(doc_id, username):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT title, file_path, thumbnail_path FROM documents WHERE id=?", (doc_id,))
    row = cur.fetchone()
    if row:
        cur.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        conn.commit()
        for p in [row[1], row[2]]:
            if p and os.path.exists(p):
                try: os.remove(p)
                except: pass
        log_activity(username, "delete", f"{row[0]} (ID: {doc_id})")
        st.success("Dokumen dipadam.")
    conn.close()
    rebuild_fts()

def search_documents(query="", category="Semua"):
    conn = sqlite3.connect(DB_NAME)
    sql = """SELECT d.id, d.title, d.content, d.file_name, d.file_path, 
                    d.thumbnail_path, d.upload_date, d.category, d.uploaded_by 
             FROM documents d"""
    params = []
    where = []
    if query.strip():
        sql += " JOIN documents_fts f ON d.id = f.rowid"
        where.append("f MATCH ?")
        params.append(query)
    if category != "Semua":
        where.append("d.category = ?")
        params.append(category)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY d.upload_date DESC"
    cur = conn.execute(sql, params)
    results = cur.fetchall()
    conn.close()
    return results

# =============================================
# CSS & THEME
# =============================================
st.markdown(f"""
<style>
    .main {{background-color: {bg}; color: {text};}}
    .card {{background: {card}; padding: 1.5rem; border-radius: 12px; border: 1px solid #333; margin: 10px 0;}}
    .header {{text-align: center; padding: 2rem; background: linear-gradient(90deg, #2E7D32, #4CAF50); color: white; border-radius: 15px;}}
    .stButton>button {{background: #4CAF50; color: white; border-radius: 8px;}}
</style>
""", unsafe_allow_html=True)

# =============================================
# SIDEBAR
# =============================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png", width=130)
    st.markdown("## Rujukan Standard FAMA")
    if st.button("Dark Mode" if theme == "light" else "Light Mode"):
        toggle_theme()
        st.rerun()
    page = st.selectbox("Menu", ["Halaman Utama", "Admin Panel"])

# =============================================
# HALAMAN UTAMA (PENGGUNA)
# =============================================
if page == "Halaman Utama":
    st.markdown('<div class="header"><h1>RUJUKAN STANDARD FAMA</h1></div>', unsafe_allow_html=True)
    st.metric("Jumlah Standard", get_total_docs())

    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input("Cari standard...", placeholder="Contoh: tomato, bunga ros...")
    with col2:
        cat = st.selectbox("Kategori", ["Semua"] + CATEGORIES)

    results = search_documents(query, cat)

    st.write(f"**{len(results)} dokumen ditemui**")
    for doc in results:
        id_, title, content, fname, fpath, thumb, date, cat, uploader = doc
        with st.container():
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            c1, c2 = st.columns([1, 3])
            with c1:
                img = thumb if thumb and os.path.exists(thumb) else "https://via.placeholder.com/300x420.png?text=FAMA"
                st.image(img, use_column_width=True)
            with c2:
                st.subheader(title)
                st.caption(f"{cat} • {date[:10]} • {uploader}")
                st.write(content[:400] + ("..." if len(content) > 400 else ""))
                if fpath and os.path.exists(fpath):
                    with open(fpath, "rb") as f:
                        st.download_button("Muat Turun", f.read(), fname, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

# =============================================
# ADMIN PANEL
# =============================================
else:
    if not st.session_state.get("admin_logged_in"):
        st.title("Login Admin")
        user = st.text_input("Username")
        pw = st.text_input("Kata Laluan", type="password")
        if st.button("Log Masuk"):
            h = hashlib.sha256(pw.encode()).hexdigest()
            conn = sqlite3.connect(DB_NAME)
            cur = conn.execute("SELECT username FROM admins WHERE username=? AND password_hash=?", (user, h))
            if cur.fetchone():
                st.session_state.admin_logged_in = True
                st.session_state.admin_user = user
                log_activity(user, "login")
                st.success("Berjaya log masuk!")
                st.rerun()
            else:
                st.error("Salah username/kata laluan")
            conn.close()
        st.stop()

    st.title(f"Admin • {st.session_state.admin_user}")
    if st.button("Log Keluar"):
        log_activity(st.session_state.admin_user, "logout")
        st.session_state.admin_logged_in = False
        st.rerun()

    tab1, tab2, tab3, tab4 = st.tabs(["Upload Standard", "Upload Thumbnail", "Senarai & QR", "Log & Backup"])

    with tab1:
        st.subheader("Upload Standard Baru")
        uploaded = st.file_uploader("PDF/DOCX (max 10MB)", type=["pdf", "docx"])
        title = st.text_input("Tajuk Standard")
        cat = st.selectbox("Kategori", CATEGORIES)
        if uploaded and title:
            if uploaded.size > MAX_FILE_SIZE:
                st.error("Fail melebihi 10MB")
            else:
                content = extract_text(uploaded)
                if st.button("Simpan Dokumen", type="primary"):
                    uploaded.seek(0)
                    new_id = save_document(title, content, cat, uploaded, st.session_state.admin_user)
                    st.success(f"Berjaya! ID Standard: **{new_id}**")
                    st.info("Simpan ID ini untuk upload thumbnail kemudian")

    with tab2:
        st.subheader("Upload Thumbnail (Bila-bila Masa)")
        doc_id = st.number_input("ID Standard", min_value=1, step=1)
        thumb_file = st.file_uploader("Pilih gambar (JPG/PNG)", type=["jpg","jpeg","png"])
        if thumb_file and st.button("Upload Thumbnail", type="primary"):
            upload_thumbnail(doc_id, thumb_file, st.session_state.admin_user)
            st.rerun()

    with tab3:
        docs = search_documents()
        for doc in docs:
            id_, title, _, fname, fpath, thumb, date, cat, uploader = doc
            c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
            c1.write(f"**{title}** (ID: {id_})")
            c2.write(f"{cat} • {date[:10]}")
            if c3.button("QR", key=f"qr_{id_}"):
                st.session_state.qr_id = id_
            if c4.button("Padam", key=f"del_{id_}"):
                delete_document(id_, st.session_state.admin_user)
                st.rerun()

        if st.session_state.get("qr_id"):
            qr_img = generate_qr(st.session_state.qr_id)
            st.image(qr_img, caption=f"QR Code ID {st.session_state.qr_id}")
            st.download_button("Muat Turun QR", qr_img, f"QR_ID_{st.session_state.qr_id}.png", "image/png")

    with tab4:
        st.subheader("Log Aktiviti (50 terkini)")
        conn = sqlite3.connect(DB_NAME)
        logs = conn.execute("SELECT username, action, details, timestamp FROM activity_log ORDER BY timestamp DESC LIMIT 50").fetchall()
        conn.close()
        for u, a, d, t in logs:
            st.write(f"**{u}** → {a} {d} — _{t}_")

        st.subheader("Backup Database")
        if st.button("Buat Backup Sekarang"):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"fama_backup_{timestamp}.db"
            backup_path = os.path.join(BACKUP_DIR, backup_file)
            shutil.copy(DB_NAME, backup_path)
            with open(backup_path, "rb") as f:
                st.download_button("Muat Turun Backup", f.read(), backup_file)
