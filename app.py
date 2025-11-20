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
# PAGE CONFIG + THEME
# =============================================
st.set_page_config(
    page_title="Rujukan Standard FAMA",
    page_icon="rice",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Theme toggle
if "theme" not in st.session_state:
    st.session_state.theme = "light"

def toggle_theme():
    st.session_state.theme = "dark" if st.session_state.theme == "light" else "light"

theme = st.session_state.theme
bg = "#0f1117" if theme == "dark" else "#f8f9fa"
card_bg = "#1a1d2b" if theme == "dark" else "#ffffff"
text_color = "#e0e0e0" if theme == "dark" else "#212529"
primary = "#4CAF50"
accent = "#8BC34A"

# =============================================
# FOLDER & DB
# =============================================
DB_NAME = "fama_standards.db"
UPLOADS_DIR = "uploads"
THUMBNAILS_DIR = "thumbnails"
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(THUMBNAILS_DIR, exist_ok=True)

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
# UTILITI
# =============================================
def extract_text(file):
    data = file.read()
    file.seek(0)
    if file.name.lower().endswith(".pdf"):
        try: return "\n".join(p.extract_text() or "" for p in PyPDF2.PdfReader(io.BytesIO(data)).pages)
        except: return ""
    elif file.name.lower().endswith(".docx"):
        try: return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
        except: return ""
    return ""

def create_pdf_thumb(pdf_path, output_path):
    try:
        with tempfile.TemporaryDirectory():
            images = convert_from_path(pdf_path, dpi=150, first_page=1, last_page=1)
            if images:
                img = images[0].convert("RGB")
                img.thumbnail((320, 450))
                img.save(output_path, "JPEG", quality=92)
                return True
    except: pass
    return False

def generate_qr(doc_id):
    base_url = st.secrets.get("app_url", "https://your-fama-app.streamlit.app")
    url = f"{base_url}/?doc={doc_id}"
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color=primary, back_color="white")
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
# CUSTOM CSS (CANTIK GILAAA)
# =============================================
st.markdown(f"""
<style>
    .main {{background: {bg};}}
    .header {{background: linear-gradient(135deg, #1B5E20, #4CAF50); padding: 2rem; border-radius: 20px; text-align: center; color: white; box-shadow: 0 10px 30px rgba(0,0,0,0.3);}}
    .card {{background: {card_bg}; color: {text_color}; border-radius: 16px; padding: 1.5rem; margin: 1rem 0; box-shadow: 0 8px 25px rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.1);}}
    .stButton>button {{background: {primary}; color: white; border-radius: 12px; height: 3em; font-weight: bold;}}
    .stTextInput>div>div>input {{border-radius: 12px;}}
    .title {{font-size: 2.8rem; font-weight: 800; margin: 0;}}
    .subtitle {{font-size: 1.2rem; opacity: 0.9;}}
    .metric-card {{background: rgba(255,255,255,0.1); padding: 1rem; border-radius: 12px; text-align: center;}}
</style>
""", unsafe_allow_html=True)

# =============================================
# SIDEBAR
# =============================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png", width=150)
    st.markdown("<h2 style='color:#4CAF50; text-align:center;'>FAMA Standard</h2>", unsafe_allow_html=True)
    st.markdown("---")
    if st.button("Dark Mode" if theme == "light" else "Light Mode", use_container_width=True):
        toggle_theme()
        st.rerun()
    page = st.selectbox("Menu", ["Halaman Utama", "Admin Panel"], label_visibility="collapsed")

# =============================================
# HALAMAN UTAMA
# =============================================
if page == "Halaman Utama":
    st.markdown('<div class="header"><h1 class="title">RUJUKAN STANDARD FAMA</h1><p class="subtitle">Sistem Digital Rasmi Jabatan Pertanian Malaysia</p></div>', unsafe_allow_html=True)
    
    total = len(search_documents())
    col1, col2, col3 = st.columns(3)
    with col1: st.markdown(f"<div class='metric-card'><h3>{total}</h3><p>Dokumen</p></div>", unsafe_allow_html=True)
    with col2: st.markdown(f"<div class='metric-card'><h3>{len(CATEGORIES)}</h3><p>Kategori</p></div>", unsafe_allow_html=True)
    with col3: st.markdown(f"<div class='metric-card'><h3>2025</h3><p>Terkini</p></div>", unsafe_allow_html=True)

    st.markdown("### Cari Standard")
    col1, col2 = st.columns([3,1])
    with col1:
        query = st.text_input("", placeholder="Cari tajuk, komoditi, standard...", key="search")
    with col2:
        cat = st.selectbox("", ["Semua"] + CATEGORIES)

    results = search_documents(query, cat)
    st.markdown(f"**Ditemui: {len(results)} standard**")

    for doc in results:
        id_, title, category, fname, fpath, thumb, date, uploader = doc
        with st.container():
            st.markdown(f"<div class='card'>", unsafe_allow_html=True)
            c1, c2 = st.columns([1, 3])
            with c1:
                img = thumb if thumb and os.path.exists(thumb) else "https://via.placeholder.com/320x450.png?text=FAMA+STANDARD"
                st.image(img, use_column_width=True)
            with c2:
                st.markdown(f"<h3 style='margin:0; color:{primary};'>{title}</h3>", unsafe_allow_html=True)
                st.caption(f"{category} • {date[:10]} • {uploader}")
                if fpath and os.path.exists(fpath):
                    with open(fpath, "rb") as f:
                        st.download_button("Muat Turun Standard", f.read(), fname, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

# =============================================
# ADMIN PANEL — CANTIK + MUDAH GUNA
# =============================================
else:
    if not st.session_state.get("admin_logged_in"):
        st.markdown('<div class="header"><h1>ADMIN PANEL</h1><p>Hanya untuk pegawai yang dibenarkan</p></div>', unsafe_allow_html=True)
        col1, col2 = st.columns([1,1])
        with col1:
            user = st.text_input("Username")
        with col2:
            pw = st.text_input("Kata Laluan", type="password")
        if st.button("Log Masuk Admin", type="primary", use_container_width=True):
            h = hashlib.sha256(pw.encode()).hexdigest()
            conn = sqlite3.connect(DB_NAME)
            cur = conn.execute("SELECT username FROM admins WHERE username=? AND password_hash=?", (user, h))
            if cur.fetchone():
                st.session_state.admin_logged_in = True
                st.session_state.admin_user = user
                st.success("Berjaya log masuk!")
                st.rerun()
            else:
                st.error("Username atau kata laluan salah")
            conn.close()
        st.stop()

    st.markdown(f'<div class="header"><h1>Selamat Datang, {st.session_state.admin_user.upper()}!</h1></div>', unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["Upload Standard Baru", "Edit Thumbnail", "Senarai & QR Code"])

    with tab1:
        st.markdown("### Tambah Standard Baru")
        uploaded_file = st.file_uploader("Pilih fail PDF/DOCX", type=["pdf", "docx"])
        title = st.text_input("Tajuk Standard / Komoditi", placeholder="Contoh: Standard Pembungaan Ros")
        category = st.selectbox("Kategori", CATEGORIES)
        thumbnail = st.file_uploader("Thumbnail (Gambar Cantik)", type=["jpg","jpeg","png"], help="Pilih gambar menarik untuk preview")

        if uploaded_file and title:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("SIMPAN STANDARD SEKARANG", type="primary", use_container_width=True):
                    with st.spinner("Sedang memproses..."):
                        content = extract_text(uploaded_file)
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        ext = Path(uploaded_file.name).suffix.lower()
                        safe_name = f"{timestamp}_{Path(uploaded_file.name).stem}{ext}"
                        file_path = os.path.join(UPLOADS_DIR, safe_name)
                        with open(file_path, "wb") as f:
                            shutil.copyfileobj(uploaded_file, f)

                        thumb_path = None
                        if thumbnail:
                            thumb_name = f"thumb_{timestamp}.jpg"
                            thumb_path = os.path.join(THUMBNAILS_DIR, thumb_name)
                            img = Image.open(thumbnail).convert("RGB")
                            img.thumbnail((320, 450))
                            img.save(thumb_path, "JPEG", quality=92)
                        elif ext == ".pdf":
                            thumb_name = f"{Path(safe_name).stem}_auto.jpg"
                            thumb_path = os.path.join(THUMBNAILS_DIR, thumb_name)
                            create_pdf_thumb(file_path, thumb_path)

                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("""INSERT INTO documents 
                            (title, content, category, file_name, file_path, thumbnail_path, upload_date, uploaded_by)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                            (title, content, category, uploaded_file.name, file_path, thumb_path or "",
                             datetime.now().strftime("%Y-%m-%d %H:%M:%S"), st.session_state.admin_user))
                        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                        conn.commit()
                        conn.close()
                        rebuild_fts()
                        st.success(f"BERJAYA! Standard ID: **{new_id}**")
                        st.balloons()

    with tab2:
        st.markdown("### Edit Thumbnail Standard Lama")
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

    with tab3:
        docs = search_documents()
        for doc in docs:
            id_, title, cat, fname, fpath, thumb, date, uploader = doc
            with st.container():
                st.markdown(f"<div class='card'>", unsafe_allow_html=True)
                c1, c2, c3 = st.columns([1, 3, 1])
                with c1:
                    img = thumb if thumb and os.path.exists(thumb) else "https://via.placeholder.com/320x450.png?text=FAMA"
                    st.image(img, use_column_width=True)
                with c2:
                    st.markdown(f"<h4>ID: <code style='background:{primary};color:white;padding:4px 8px;border-radius:8px;'>{id_}</code> {title}</h4>", unsafe_allow_html=True)
                    st.caption(f"{cat} • {date[:10]} • {uploader}")
                with c3:
                    qr = generate_qr(id_)
                    st.image(qr, caption="Imbas QR")
                    st.download_button("QR", qr, f"QR_{id_}.png", "image/png", key=f"dl_{id_}")
                st.markdown("</div>", unsafe_allow_html=True)
