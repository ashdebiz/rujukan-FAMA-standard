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
# PAKSA TEMA CANTIK FAMA (PUTIH + HIJAU)
# =============================================
st.set_page_config(
    page_title="Rujukan Standard FAMA",
    page_icon="rice",
    layout="centered",
    initial_sidebar_state="expanded"
)

# PAKSA BACKGROUND PUTIH & HIJAU FAMA
st.markdown("""
<style>
    .main {background: linear-gradient(135deg, #f8fff8, #e8f5e8) !important;}
    .stApp {background: transparent !important;}
    header {visibility: hidden;}
    [data-testid="stSidebar"] {background: linear-gradient(#1B5E20, #2E7D32);}
    .css-1d391kg, .css-1y0tugs {background: transparent !important;}
    .stTextInput > div > div > input {background: white; border: 2px solid #4CAF50; border-radius: 12px;}
    .stSelectbox > div > div {background: white; border-radius: 12px;}
    .card {background: white; border-radius: 20px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); border: 1px solid #c8e6c9; margin: 15px 0;}
    .header-box {background: linear-gradient(135deg, #1B5E20, #4CAF50); border-radius: 20px; padding: 2rem; text-align: center; color: white; box-shadow: 0 15px 35px rgba(27,94,32,0.4);}
    .btn-green {background: #4CAF50; color: white; font-weight: bold; border-radius: 15px; height: 50px;}
    .stButton>button {background: #4CAF50; color: white; font-weight: bold; border-radius: 15px; height: 50px; border: none;}
    h1, h2, h3 {color: #1B5E20; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

# =============================================
# FOLDER & DB
# =============================================
for folder in ["uploads", "thumbnails"]:
    os.makedirs(folder, exist_ok=True)

DB_NAME = "fama_standards.db"
CATEGORIES = ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"]

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
            return " ".join(p.extract_text() or "" for p in PyPDF2.PdfReader(io.BytesIO(data)).pages)
        elif file.name.lower().endswith(".docx"):
            return " ".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
    except: pass
    return ""

def generate_qr(id_):
    url = f"https://rujukan-fama-standard.streamlit.app/?doc={id_}"
    qr = qrcode.QRCode(box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1B5E20", back_color="white")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()

def get_all_docs():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.execute("SELECT id, title, category, file_name, file_path, thumbnail_path, upload_date, uploaded_by FROM documents ORDER BY id DESC")
    docs = cur.fetchall()
    conn.close()
    return docs

# =============================================
# SIDEBAR CANTIK
# =============================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png", width=180)
    st.markdown("<h2 style='color:white; text-align:center;'>FAMA STANDARD</h2>", unsafe_allow_html=True)
    st.markdown("---")
    page = st.selectbox("Menu", ["Halaman Utama", "Admin Panel"], label_visibility="collapsed")

# =============================================
# HALAMAN UTAMA (SUPER INTERAKTIF!)
# =============================================
if page == "Halaman Utama":
    st.markdown('<div class="header-box"><h1>RUJUKAN STANDARD FAMA</h1><h3>Sistem Digital Rasmi Jabatan Pertanian Malaysia • 2025</h3></div>', unsafe_allow_html=True)
    
    st.markdown("### Cari Standard Anda")
    col1, col2 = st.columns([3,1])
    with col1:
        search = st.text_input("", placeholder="Cari nama komoditi, tajuk standard...", key="search")
    with col2:
        kategori = st.selectbox("", ["Semua"] + CATEGORIES)

    docs = get_all_docs()
    filtered = []
    for doc in docs:
        id_, title, cat, fname, fpath, thumb, date, uploader = doc
        if (kategori == "Semua" or cat == kategori) and (not search or search.lower() in title.lower()):
            filtered.append(doc)

    st.markdown(f"**Ditemui {len(filtered)} standard**")

    for doc in filtered:
        id_, title, cat, fname, fpath, thumb, date, uploader = doc
        with st.container():
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            c1, c2 = st.columns([1, 3])
            with c1:
                img = thumb if thumb and os.path.exists(thumb) else "https://via.placeholder.com/350x500/4CAF50/white?text=FAMA+STANDARD"
                st.image(img, use_column_width=True)
            with c2:
                st.markdown(f"<h2 style='color:#1B5E20; margin:0;'>{title}</h2>", unsafe_allow_html=True)
                st.markdown(f"**Kategori:** {cat} • **Tarikh:** {date[:10]} • **Oleh:** {uploader}")
                if os.path.exists(fpath):
                    with open(fpath, "rb") as f:
                        st.download_button("MUAT TURUN STANDARD", f.read(), fname, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

# =============================================
# ADMIN PANEL (MUDAH & CANTIK!)
# =============================================
else:
    if not st.session_state.get("admin"):
        st.markdown('<div class="header-box"><h1>ADMIN PANEL</h1><p>Hanya untuk pegawai yang dibenarkan</p></div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1: user = st.text_input("Username")
        with col2: pw = st.text_input("Kata Laluan", type="password")
        if st.button("LOG MASUK ADMIN", type="primary", use_container_width=True):
            h = hashlib.sha256(pw.encode()).hexdigest()
            if (user == "admin" and h == hashlib.sha256("fama2025".encode()).hexdigest()) or \
               (user == "pengarah" and h == hashlib.sha256("fama123".encode()).hexdigest()):
                st.session_state.admin = True
                st.session_state.user = user
                st.success("Berjaya log masuk!")
                st.balloons()
                st.rerun()
            else:
                st.error("Username atau kata laluan salah")
        st.stop()

    st.markdown(f'<div class="header-box"><h1>Selamat Datang, {st.session_state.user.upper()}!</h1></div>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["Tambah Standard Baru", "Senarai & QR Code"])

    with tab1:
        st.markdown("### Tambah Standard Baru")
        uploaded_file = st.file_uploader("Pilih fail PDF/DOCX", type=["pdf", "docx"])
        title = st.text_input("Tajuk Standard (contoh: Standard Pembungaan Ros)")
        category = st.selectbox("Pilih Kategori", CATEGORIES)
        thumbnail = st.file_uploader("Gambar Thumbnail (WAJIB)", type=["jpg","jpeg","png"])

        if uploaded_file and title and thumbnail:
            if st.button("SIMPAN STANDARD SEKARANG", type="primary", use_container_width=True):
                with st.spinner("Sedang memproses..."):
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    ext = Path(uploaded_file.name).suffix
                    new_name = f"{ts}_{Path(uploaded_file.name).stem}{ext}"
                    file_path = os.path.join("uploads", new_name)
                    with open(file_path, "wb") as f:
                        shutil.copyfileobj(uploaded_file, f)

                    thumb_path = os.path.join("thumbnails", f"thumb_{ts}.jpg")
                    Image.open(thumbnail).convert("RGB").thumbnail((350,500)).save(thumb_path, "JPEG", quality=95)

                    content = extract_text(uploaded_file)
                    conn = sqlite3.connect(DB_NAME)
                    conn.execute("""INSERT INTO documents 
                        (title, content, category, file_name, file_path, thumbnail_path, upload_date, uploaded_by)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (title, content, category, uploaded_file.name, file_path, thumb_path,
                         datetime.now().strftime("%Y-%m-%d %H:%M"), st.session_state.user))
                    conn.commit()
                    new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    conn.close()
                    st.success(f"BERJAYA! ID Standard: **{new_id}**")
                    st.balloons()

    with tab2:
        for doc in get_all_docs():
            id_, title, cat, fname, fpath, thumb, date, uploader = doc
            with st.expander(f"ID {id_} • {title} • {cat}"):
                c1, c2 = st.columns(2)
                with c1:
                    img = thumb if thumb and os.path.exists(thumb) else "https://via.placeholder.com/300x420.png?text=FAMA"
                    st.image(img, width=250)
                with c2:
                    st.write(f"**Uploader:** {uploader}")
                    st.write(f"**Tarikh:** {date[:10]}")
                    qr = generate_qr(id_)
                    st.image(qr, width=200)
                    st.download_button("Muat Turun QR Code", qr, f"QR_{title[:20]}_{id_}.png", "image/png")

    if st.button("Log Keluar"):
        st.session_state.admin = False
        st.rerun()
