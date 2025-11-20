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

# =============================================
# KONFIGURASI ASAS
# =============================================
st.set_page_config(page_title="Rujukan Standard FAMA", page_icon="rice", layout="centered")

# Folder
UPLOADS_DIR = "uploads"
THUMBNAILS_DIR = "thumbnails"
for folder in [UPLOADS_DIR, THUMBNAILS_DIR]:
    os.makedirs(folder, exist_ok=True)

DB_NAME = "fama_standards.db"
CATEGORIES = ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"]

# =============================================
# DATABASE (100% SELAMAT)
# =============================================
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
    ''')
    # Default admin
    conn.execute("INSERT OR IGNORE INTO admins VALUES ('admin', ?)", 
                (hashlib.sha256("fama2025".encode()).hexdigest(),))
    conn.execute("INSERT OR IGNORE INTO admins VALUES ('pengarah', ?)", 
                (hashlib.sha256("fama123".encode()).hexdigest(),))
    conn.commit()
    conn.close()

init_db()

# =============================================
# FUNGSI UTAMA
# =============================================
def extract_text(file):
    data = file.read()
    file.seek(0)
    try:
        if file.name.lower().endswith(".pdf"):
            reader = PyPDF2.PdfReader(io.BytesIO(data))
            return " ".join(page.extract_text() or "" for page in reader.pages)
        elif file.name.lower().endswith(".docx"):
            doc = Document(io.BytesIO(data))
            return " ".join(p.text for p in doc.paragraphs)
    except:
        pass
    return ""

def generate_qr(doc_id):
    url = f"https://rujukan-fama-standard.streamlit.app/?doc={doc_id}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#2E7D32", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def search_documents(query="", category="Semua"):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    sql = "SELECT id, title, category, file_name, file_path, thumbnail_path, upload_date, uploaded_by FROM documents"
    params = []
    where = []
    if query:
        sql += " WHERE title LIKE ? OR content LIKE ?"
        params.extend([f"%{query}%", f"%{query}%"])
    if category != "Semua":
        where.append("category = ?")
        params.append(category)
    if where:
        sql += " AND " + " AND ".join(where) if query else " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC"
    cur.execute(sql, params)
    results = cur.fetchall()
    conn.close()
    return results

# =============================================
# CSS CANTIK & RINGAN
# =============================================
st.markdown("""
<style>
    .main {background: #f8f9fa; padding: 20px;}
    .header {background: linear-gradient(90deg, #1B5E20, #4CAF50); padding: 2rem; border-radius: 20px; text-align: center; color: white; margin-bottom: 2rem;}
    .card {background: white; padding: 1.5rem; border-radius: 16px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); margin: 1rem 0;}
    .stButton>button {background: #4CAF50; color: white; border-radius: 12px; font-weight: bold; width: 100%; height: 3rem;}
    h1, h2, h3 {color: #1B5E20;}
</style>
""", unsafe_allow_html=True)

# =============================================
# SIDEBAR
# =============================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png", width=140)
    st.markdown("## Rujukan Standard FAMA")
    page = st.selectbox("Menu", ["Halaman Utama", "Admin Panel"])

# =============================================
# HALAMAN UTAMA
# =============================================
if page == "Halaman Utama":
    st.markdown('<div class="header"><h1>RUJUKAN STANDARD FAMA</h1><p>Sistem Digital Rasmi • 2025</p></div>', unsafe_allow_html=True)

    query = st.text_input("Cari standard...", placeholder="Contoh: tomato, ros, timun...")
    cat = st.selectbox("Kategori", ["Semua"] + CATEGORIES)
    
    results = search_documents(query, cat)
    st.write(f"**Ditemui: {len(results)} dokumen**")

    for doc in results:
        id_, title, cat, fname, fpath, thumb, date, uploader = doc
        with st.container():
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            col1, col2 = st.columns([1, 3])
            with col1:
                img_path = thumb if thumb and os.path.exists(thumb) else "https://via.placeholder.com/300x420/4CAF50/white?text=FAMA+STANDARD"
                st.image(img_path, use_column_width=True)
            with col2:
                st.subheader(title)
                st.caption(f"{cat} • {date[:10]} • {uploader}")
                if os.path.exists(fpath):
                    with open(fpath, "rb") as f:
                        st.download_button("Muat Turun", f.read(), fname, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

# =============================================
# ADMIN PANEL (SENANG GUNA!)
# =============================================
else:
    if not st.session_state.get("logged_in"):
        st.markdown('<div class="header"><h1>ADMIN PANEL</h1></div>', unsafe_allow_html=True)
        username = st.text_input("Username")
        password = st.text_input("Kata Laluan", type="password")
        if st.button("Log Masuk", type="primary"):
            if username in ["admin", "pengarah"] and hashlib.sha256(password.encode()).hexdigest() in [
                hashlib.sha256("fama2025".encode()).hexdigest(),
                hashlib.sha256("fama123".encode()).hexdigest()
            ]:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success("Berjaya log masuk!")
                st.rerun()
            else:
                st.error("Username atau kata laluan salah")
        st.stop()

    st.markdown(f'<div class="header"><h1>Selamat Datang, {st.session_state.username.upper()}!</h1></div>', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Tambah Standard", "Senarai Standard"])

    with tab1:
        st.subheader("Tambah Standard Baru")
        file = st.file_uploader("Pilih PDF/DOCX", type=["pdf", "docx"])
        title = st.text_input("Tajuk Standard")
        category = st.selectbox("Kategori", CATEGORIES)
        thumbnail = st.file_uploader("Gambar Thumbnail", type=["jpg", "jpeg", "png"])

        if file and title and thumbnail:
            if st.button("SIMPAN STANDARD", type="primary"):
                with st.spinner("Sedang simpan..."):
                    # Simpan fail
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    ext = Path(file.name).suffix
                    new_name = f"{timestamp}_{Path(file.name).stem}{ext}"
                    file_path = os.path.join(UPLOADS_DIR, new_name)
                    with open(file_path, "wb") as f:
                        shutil.copyfileobj(file, f)

                    # Simpan thumbnail
                    thumb_name = f"thumb_{timestamp}.jpg"
                    thumb_path = os.path.join(THUMBNAILS_DIR, thumb_name)
                    img = Image.open(thumbnail).convert("RGB")
                    img.thumbnail((300, 420))
                    img.save(thumb_path, "JPEG")

                    # Simpan ke DB
                    content = extract_text(file)
                    conn = sqlite3.connect(DB_NAME)
                    conn.execute("""INSERT INTO documents 
                        (title, content, category, file_name, file_path, thumbnail_path, upload_date, uploaded_by)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (title, content, category, file.name, file_path, thumb_path,
                         datetime.now().strftime("%Y-%m-%d %H:%M"), st.session_state.username))
                    conn.commit()
                    new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    conn.close()

                    st.success(f"BERJAYA! ID Standard: **{new_id}**")
                    st.balloons()

    with tab2:
        docs = search_documents()
        for doc in docs:
            id_, title, cat, fname, fpath, thumb, date, uploader = doc
            with st.expander(f"ID {id_} • {title} • {cat}"):
                col1, col2 = st.columns(2)
                with col1:
                    img = thumb if thumb and os.path.exists(thumb) else "https://via.placeholder.com/300x420.png?text=FAMA"
                    st.image(img, width=200)
                with col2:
                    st.write(f"**Uploader:** {uploader}")
                    st.write(f"**Tarikh:** {date}")
                    qr = generate_qr(id_)
                    st.image(qr, width=150)
                    st.download_button("QR Code", qr, f"QR_{id_}.png", "image/png", key=f"qr_{id_}")

    if st.button("Log Keluar"):
        st.session_state.logged_in = False
        st.rerun()
