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
# KONFIGURASI
# =============================================
st.set_page_config(
    page_title="Rujukan Standard FAMA",
    page_icon="rice",
    layout="centered",
    initial_sidebar_state="expanded"
)

DB_NAME = "fama_standards.db"
UPLOADS_DIR = "uploads"
THUMBNAILS_DIR = "thumbnails"
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(THUMBNAILS_DIR, exist_ok=True)

CATEGORIES = ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"]

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
        # Default: admin/fama2025  |  pengarah/fama123
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
# UTILITI
# =============================================
def extract_text(file):
    data = file.read()
    file.seek(0)
    try:
        if file.name.lower().endswith(".pdf"):
            reader = PyPDF2.PdfReader(io.BytesIO(data))
            return "\n".join(p.extract_text() or "" for p in reader.pages)
        elif file.name.lower().endswith(".docx"):
            doc = Document(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs)
    except:
        return ""
    return ""

def generate_qr(doc_id):
    base_url = st.secrets.get("app_url", "https://rujukan-fama-standard.streamlit.app")
    url = f"{base_url}/?doc={doc_id}"
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#2E7D32", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def search_documents(query="", category="Semua"):
    conn = sqlite3.connect(DB_NAME)
    sql = """SELECT d.id, d.title, d.category, d.file_name, d.file_path, 
                    d.thumbnail_path, d.upload_date, d.uploaded_by 
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
# CSS CANTIK
# =============================================
st.markdown("""
<style>
    .main {background: #f8f9fa;}
    .header {background: linear-gradient(90deg, #1B5E20, #4CAF50); padding: 2.5rem; border-radius: 20px; text-align: center; color: white; box-shadow: 0 10px 30px rgba(0,0,0,0.3);}
    .card {background: white; border-radius: 16px; padding: 1.5rem; margin: 1rem 0; box-shadow: 0 8px 25px rgba(0,0,0,0.15);}
    .stButton>button {background: #4CAF50; color: white; border-radius: 12px; font-weight: bold;}
    h1, h2, h3 {color: #1B5E20;}
</style>
""", unsafe_allow_html=True)

# =============================================
# SIDEBAR
# =============================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png", width=150)
    st.markdown("## Rujukan Standard FAMA")
    st.markdown("### Menu")
    page = st.selectbox("Pilih", ["Halaman Utama", "Admin Panel"], label_visibility="collapsed")

# =============================================
# HALAMAN UTAMA
# =============================================
if page == "Halaman Utama":
    st.markdown('<div class="header"><h1>RUJUKAN STANDARD FAMA</h1><p>Sistem Digital Rasmi</p></div>', unsafe_allow_html=True)

    col1, col2 = st.columns([3,1])
    with col1:
        query = st.text_input("", placeholder="Cari tajuk, komoditi, standard...")
    with col2:
        cat = st.selectbox("", ["Semua"] + CATEGORIES)

    results = search_documents(query, cat)
    st.write(f"**Ditemui: {len(results)} standard**")

    for doc in results:
        id_, title, cat, fname, fpath, thumb, date, uploader = doc
        with st.container():
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            c1, c2 = st.columns([1, 3])
            with c1:
                img = thumb if thumb and os.path.exists(thumb) else "https://via.placeholder.com/320x450/4CAF50/white?text=FAMA"
                st.image(img, use_column_width=True)
            with c2:
                st.subheader(title)
                st.caption(f"{cat} • {date[:10]} • {uploader}")
                if fpath and os.path.exists(fpath):
                    with open(fpath, "rb") as f:
                        st.download_button("Muat Turun PDF/DOCX", f.read(), fname, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

# =============================================
# ADMIN PANEL (SEPERTI ASAL — TAPI LEBIH BAIK)
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
                st.error("Username atau kata laluan salah")
        st.stop()

    st.markdown(f'<div class="header"><h1>Selamat Datang, {st.session_state.admin_user.upper()}!</h1></div>', unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["Upload Standard", "Edit Thumbnail", "Senarai & QR"])

    # ==================== UPLOAD STANDARD + THUMBNAIL SEKALIGUS ====================
    with tab1:
        st.subheader("Tambah Standard Baru")
        uploaded_file = st.file_uploader("Pilih PDF atau DOCX", type=["pdf", "docx"])
        title = st.text_input("Tajuk Standard")
        category = st.selectbox("Kategori", CATEGORIES)
        thumbnail = st.file_uploader("Thumbnail (Gambar Depan)", type=["jpg", "jpeg", "png"])

        if uploaded_file and title and thumbnail:
            if st.button("SIMPAN STANDARD", type="primary", use_container_width=True):
                with st.spinner("Sedang memproses..."):
                    content = extract_text(uploaded_file)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    ext = Path(uploaded_file.name).suffix.lower()
                    safe_name = f"{timestamp}_{Path(uploaded_file.name).stem}{ext}"
                    file_path = os.path.join(UPLOADS_DIR, safe_name)
                    with open(file_path, "wb") as f:
                        shutil.copyfileobj(uploaded_file, f)

                    # Simpan thumbnail
                    thumb_name = f"thumb_{timestamp}.jpg"
                    thumb_path = os.path.join(THUMBNAILS_DIR, thumb_name)
                    img = Image.open(thumbnail).convert("RGB")
                    img.thumbnail((320, 450))
                    img.save(thumb_path, "JPEG", quality=92)

                    conn = sqlite3.connect(DB_NAME)
                    conn.execute("""INSERT INTO documents 
                        (title, content, category, file_name, file_path, thumbnail_path, upload_date, uploaded_by)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (title, content, category, uploaded_file.name, file_path, thumb_path,
                         datetime.now().strftime("%Y-%m-%d %H:%M:%S"), st.session_state.admin_user))
                    new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    conn.commit()
                    conn.close()
                    rebuild_fts()
                    st.success(f"BERJAYA DISIMPAN! ID Standard: **{new_id}**")
                    st.balloons()

    # ==================== EDIT THUMBNAIL KEMUDIAN ====================
    with tab2:
        st.subheader("Kemaskini Thumbnail Standard Lama")
        doc_id = st.number_input("Masukkan ID Standard", min_value=1, step=1)
        new_thumb = st.file_uploader("Pilih gambar baru", type=["jpg","jpeg","png"])
        if new_thumb and st.button("Kemaskini Thumbnail", type="primary"):
            thumb_path = os.path.join(THUMBNAILS_DIR, f"thumb_{doc_id}.jpg")
            img = Image.open(new_thumb).convert("RGB")
            img.thumbnail((320, 450))
            img.save(thumb_path, "JPEG", quality=92)
            conn = sqlite3.connect(DB_NAME)
            conn.execute("UPDATE documents SET thumbnail_path=? WHERE id=?", (thumb_path, doc_id))
            conn.commit()
            conn.close()
            st.success(f"Thumbnail ID {doc_id} berjaya dikemaskini!")

    # ==================== SENARAI + QR CODE ====================
    with tab3:
        docs = search_documents()
        for doc in docs:
            id_, title, cat, fname, fpath, thumb, date, uploader = doc
            with st.expander(f"ID {id_} - {title} • {cat}"):
                col1, col2 = st.columns([1, 2])
                with col1:
                    img = thumb if thumb and os.path.exists(thumb) else "https://via.placeholder.com/320x450.png?text=FAMA"
                    st.image(img)
                with col2:
                    st.write(f"**Uploader:** {uploader}")
                    st.write(f"**Tarikh:** {date[:10]}")
                    qr = generate_qr(id_)
                    st.image(qr, caption="Imbas QR untuk akses terus")
                    st.download_button("Muat Turun QR Code", qr, f"QR_ID_{id_}.png", "image/png")

    if st.button("Log Keluar"):
        st.session_state.admin_logged_in = False
        st.rerun()
