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
import tempfile

# =============================================
# PAGE CONFIG + THEME
# =============================================
st.set_page_config(page_title="Rujukan Standard FAMA", page_icon="rice", layout="centered")

# Dark mode
if "theme" not in st.session_state:
    st.session_state.theme = "light"
def toggle_theme():
    st.session_state.theme = "dark" if st.session_state.theme == "light" else "light"

theme = st.session_state.theme
bg = "#121212" if theme == "dark" else "#ffffff"
text = "#ffffff" if theme == "dark" else "#000000"
card = "#1e1e1e" if theme == "dark" else "#ffffff"

# =============================================
# FOLDER & DB
# =============================================
DB_NAME = "fama_standards.db"
UPLOADS_DIR = "uploads"
THUMBNAILS_DIR = "thumbnails"
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(THUMBNAILS_DIR, exist_ok=True)

CATEGORIES = ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"]

@st.cache_resource
def init_db():
    conn = sqlite3.connect(DB_NAME)
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT,
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
        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
            title, content, category, content='documents', content_rowid='id'
        );
    ''')
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM admins")
    if cur.fetchone()[0] == 0:
        conn.execute("INSERT INTO admins VALUES ('admin', ?)", (hashlib.sha256("fama2025".encode()).hexdigest(),))
        conn.execute("INSERT INTO admins VALUES ('pengarah', ?)", (hashlib.sha256("fama123".encode()).hexdigest(),))
    conn.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
    conn.commit()
    conn.close()
init_db()

def rebuild_fts():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
    conn.commit()
    conn.close()

# =============================================
# UTILITI (TANPA pdf2image!)
# =============================================
def extract_text(file):
    data = file.read()
    file.seek(0)
    try:
        if file.name.lower().endswith(".pdf"):
            reader = PyPDF2.PdfReader(io.BytesIO(data))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        elif file.name.lower().endswith(".docx"):
            doc = Document(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs)
    except:
        pass
    return ""

def generate_qr(doc_id):
    base_url = st.secrets.get("app_url", "https://your-fama-app.streamlit.app")
    url = f"{base_url}/?doc={doc_id}"
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#4CAF50", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def search_documents(query="", category="Semua"):
    conn = sqlite3.connect(DB_NAME)
    sql = "SELECT d.id, d.title, d.category, d.file_name, d.file_path, d.thumbnail_path, d.upload_date, d.uploaded_by FROM documents d"
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
# CSS CANTIK
# =============================================
st.markdown(f"""
<style>
    .main {{background: {bg}; color: {text};}}
    .header {{background: linear-gradient(135deg, #1B5E20, #4CAF50); padding: 2.5rem; border-radius: 20px; text-align: center; color: white; box-shadow: 0 10px 30px rgba(0,0,0,0.4);}}
    .card {{background: {card}; border-radius: 16px; padding: 1.5rem; margin: 1rem 0; box-shadow: 0 8px 25px rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.1);}}
    .stButton>button {{background: #4CAF50; color: white; border-radius: 12px; font-weight: bold;}}
</style>
""", unsafe_allow_html=True)

# =============================================
# SIDEBAR
# =============================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png", width=150)
    st.markdown("## FAMA Standard")
    if st.button("Dark Mode" if theme == "light" else "Light Mode"):
        toggle_theme()
        st.rerun()
    page = st.selectbox("Menu", ["Halaman Utama", "Admin Panel"])

# =============================================
# HALAMAN UTAMA
# =============================================
if page == "Halaman Utama":
    st.markdown('<div class="header"><h1>RUJUKAN STANDARD FAMA</h1><p>Sistem Digital Rasmi</p></div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3,1])
    with col1: query = st.text_input("", placeholder="Cari standard...")
    with col2: cat = st.selectbox("", ["Semua"]+CATEGORIES)

    results = search_documents(query, cat)
    st.write(f"**{len(results)} standard ditemui**")

    for doc in results:
        id_, title, cat, fname, fpath, thumb, date, uploader = doc
        with st.container():
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            c1, c2 = st.columns([1,3])
            with c1:
                img = thumb if thumb and os.path.exists(thumb) else "https://via.placeholder.com/320x450/4CAF50/white?text=FAMA+STANDARD"
                st.image(img, use_column_width=True)
            with c2:
                st.subheader(title)
                st.caption(f"{cat} • {date[:10]} • {uploader}")
                if fpath and os.path.exists(fpath):
                    with open(fpath, "rb") as f:
                        st.download_button("Muat Turun", f.read(), fname, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

# =============================================
# ADMIN PANEL (PALING MUDAH!)
# =============================================
else:
    if not st.session_state.get("admin_logged_in"):
        st.markdown('<div class="header"><h1>ADMIN PANEL</h1></div>', unsafe_allow_html=True)
        user = st.text_input("Username")
        pw = st.text_input("Kata Laluan", type="password")
        if st.button("Log Masuk", type="primary"):
            h = hashlib.sha256(pw.encode()).hexdigest()
            conn = sqlite3.connect(DB_NAME)
            cur = conn.execute("SELECT username FROM admins WHERE username=? AND password_hash=?", (user, h))
            if cur.fetchone():
                st.session_state.admin_logged_in = True
                st.session_state.admin_user = user
                st.rerun()
            else:
                st.error("Salah username/kata laluan")
        st.stop()

    st.markdown(f'<div class="header"><h1>Selamat Datang, {st.session_state.admin_user.upper()}!</h1></div>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["Upload Standard + Thumbnail", "Senarai & QR"])

    with tab1:
        st.markdown("### Tambah Standard Baru")
        file = st.file_uploader("Fail PDF/DOCX", type=["pdf","docx"])
        title = st.text_input("Tajuk Standard")
        cat = st.selectbox("Kategori", CATEGORIES)
        thumb = st.file_uploader("Thumbnail (WAJIB SEKARANG)", type=["jpg","jpeg","png"])

        if file and title and thumb:
            if st.button("SIMPAN STANDARD", type="primary", use_container_width=True):
                with st.spinner("Sedang simpan..."):
                    content = extract_text(file)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    ext = Path(file.name).suffix.lower()
                    safe_name = f"{timestamp}_{Path(file.name).stem}{ext}"
                    file_path = os.path.join(UPLOADS_DIR, safe_name)
                    with open(file_path, "wb") as f:
                        shutil.copyfileobj(file, f)

                    thumb_name = f"thumb_{timestamp}.jpg"
                    thumb_path = os.path.join(THUMBNAILS_DIR, thumb_name)
                    img = Image.open(thumb).convert("RGB")
                    img.thumbnail((320, 450))
                    img.save(thumb_path, "JPEG", quality=92)

                    conn = sqlite3.connect(DB_NAME)
                    conn.execute("""INSERT INTO documents 
                        (title, content, category, file_name, file_path, thumbnail_path, upload_date, uploaded_by)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (title, content, cat, file.name, file_path, thumb_path,
                         datetime.now().strftime("%Y-%m-%d %H:%M:%S"), st.session_state.admin_user))
                    new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    conn.commit()
                    conn.close()
                    rebuild_fts()
                    st.success(f"BERJAYA! ID Standard: **{new_id}**")
                    st.balloons()

    with tab2:
        docs = search_documents()
        for doc in docs:
            id_, title, cat, fname, fpath, thumb, date, uploader = doc
            with st.expander(f"ID {id_} - {title} • {cat}"):
                c1, c2 = st.columns([1,2])
                with c1:
                    img = thumb if thumb and os.path.exists(thumb) else "https://via.placeholder.com/320x450.png?text=FAMA"
                    st.image(img)
                with c2:
                    st.write(f"**Uploader:** {uploader} | {date[:10]}")
                    qr = generate_qr(id_)
                    st.image(qr, caption="QR Code")
                    st.download_button("Muat Turun QR", qr, f"QR_{id_}.png", "image/png", key=f"qr_{id_}")

    if st.button("Log Keluar"):
        st.session_state.admin_logged_in = False
        st.rerun()
