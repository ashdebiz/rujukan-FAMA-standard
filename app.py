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
# TEMA CANTIK + LOGO KECIK TENGAH
# =============================================
st.set_page_config(page_title="Rujukan Standard FAMA", page_icon="rice", layout="centered")

st.markdown("""
<style>
    .main {background: #f8fff8;}
    [data-testid="stSidebar"] {background: linear-gradient(#1B5E20, #2E7D32);}
    .header-container {
        text-align: center; padding: 2rem 0; background: linear-gradient(135deg, #1B5E20, #4CAF50);
        border-radius: 25px; box-shadow: 0 15px 40px rgba(27,94,32,0.5); margin: 20px 0;
    }
    .fama-logo {width: 80px; margin-bottom: 12px; filter: drop-shadow(0 3px 6px rgba(0,0,0,0.4));}
    .header-title {color: white; font-size: 2.6rem; font-weight: 900; margin: 0; text-shadow: 2px 2px 8px rgba(0,0,0,0.5);}
    .header-subtitle {color: #c8e6c9; font-size: 1.2rem; margin: 8px 0 0;}
    .card {background: white; border-radius: 20px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); border: 1px solid #c8e6c9; margin: 15px 0;}
    .stButton>button {background: #4CAF50; color: white; font-weight: bold; border-radius: 15px; height: 50px; border: none;}
    h1,h2,h3 {color: #1B5E20;}
</style>
""", unsafe_allow_html=True)

# =============================================
# FOLDER & DB
# =============================================
os.makedirs("uploads", exist_ok=True)
os.makedirs("thumbnails", exist_ok=True)

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
    conn.execute("INSERT OR IGNORE INTO admins VALUES ('admin', ?)", (hashlib.sha256("fama2025".encode()).hexdigest(),))
    conn.execute("INSERT OR IGNORE INTO admins VALUES ('pengarah', ?)", (hashlib.sha256("fama123".encode()).hexdigest(),))
    conn.commit()
    conn.close()
init_db()

# =============================================
# FUNGSI
# =============================================
def extract_text(file):
    if not file: return ""
    try:
        data = file.getvalue() if hasattr(file, 'getvalue') else file.read()
        file.seek(0) if hasattr(file, 'seek') else None
        if str(file.name).lower().endswith(".pdf"):
            return "  ".join(p.extract_text() or "" for p in PyPDF2.PdfReader(io.BytesIO(data)).pages)
        elif str(file.name).lower().endswith(".docx"):
            return "  ".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
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

def get_docs():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.execute("SELECT id, title, category, file_name, file_path, thumbnail_path, upload_date, uploaded_by FROM documents ORDER BY id DESC")
    docs = cur.fetchall()
    conn.close()
    return docs

# =============================================
# SIDEBAR — LOGO + TEKS TENGAH CANTIK
# =============================================
with st.sidebar:
    st.markdown("""
    <div style="text-align: center; padding: 20px 0;">
        <img src="data:image/jpeg;base64,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" width="80">
        <h3 style="color:white; margin:15px 0 0 0; font-weight: bold;">FAMA STANDARD</h3>
        <p style="color:#c8e6c9; margin:5px 0 0 0; font-size:0.9rem;">Sistem Digital Rasmi • 2025</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    page = st.selectbox("Menu", ["Halaman Utama", "Admin Panel"], label_visibility="collapsed")

# =============================================
# HALAMAN UTAMA
# =============================================
if page == "Halaman Utama":
    st.markdown(f'''
    <div class="header-container">
        <img src="https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png" class="fama-logo">
        <h1 class="header-title">RUJUKAN STANDARD FAMA</h1>
        <p class="header-subtitle">Sistem Digital Rasmi • Jabatan Pertanian Malaysia</p>
    </div>
    ''', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3,1])
    with col1: cari = st.text_input("", placeholder="Cari tajuk standard...")
    with col2: kat = st.selectbox("", ["Semua"] + CATEGORIES)

    docs = get_docs()
    hasil = [d for d in docs if (kat == "Semua" or d[2] == kat) and (not cari or cari.lower() in d[1].lower())]

    st.markdown(f"**Ditemui: {len(hasil)} standard**")

    for d in hasil:
        id_, title, cat, fname, fpath, thumb, date, uploader = d
        with st.container():
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            c1, c2 = st.columns([1,3])
            with c1:
                img = thumb if thumb and os.path.exists(thumb) else "https://via.placeholder.com/350x500/4CAF50/white?text=FAMA"
                st.image(img, use_column_width=True)
            with c2:
                st.markdown(f"<h2>{title}</h2>", unsafe_allow_html=True)
                st.caption(f"{cat} • {date[:10]} • {uploader}")
                if fpath and os.path.exists(fpath):
                    with open(fpath, "rb") as f:
                        st.download_button("MUAT TURUN", f.read(), fname, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

# =============================================
# ADMIN PANEL — LENGKAP + KEMASKINI ATTACHMENT
# =============================================
else:
    if not st.session_state.get("admin"):
        st.markdown(f'''
        <div class="header-container">
            <img src="https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png" class="fama-logo">
            <h1 class="header-title">ADMIN PANEL</h1>
        </div>
        ''', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1: user = st.text_input("Username")
        with c2: pw = st.text_input("Kata Laluan", type="password")
        if st.button("LOG MASUK", type="primary", use_container_width=True):
            h = hashlib.sha256(pw.encode()).hexdigest()
            if (user == "admin" and h == hashlib.sha256("fama2025".encode()).hexdigest()) or \
               (user == "pengarah" and h == hashlib.sha256("fama123".encode()).hexdigest()):
                st.session_state.admin = True
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Salah username/kata laluan")
        st.stop()

    st.markdown(f'''
    <div class="header-container">
        <h1 class="header-title">Selamat Datang, {st.session_state.user.upper()}!</h1>
    </div>
    ''', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["Tambah Standard", "Senarai & Pengurusan"])

    with tab1:
        st.markdown("### Tambah Standard Baru")
        file = st.file_uploader("Pilih fail PDF/DOCX", type=["pdf","docx"])
        title = st.text_input("Tajuk Standard")
        cat = st.selectbox("Kategori", CATEGORIES)
        thumb = st.file_uploader("Gambar Thumbnail (Pilihan)", type=["jpg","jpeg","png"])

        if file and title:
            if st.button("SIMPAN STANDARD", type="primary", use_container_width=True):
                with st.spinner("Sedang simpan..."):
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    ext = Path(file.name).suffix
                    new_name = f"{ts}_{Path(file.name).stem}{ext}"
                    file_path = os.path.join("uploads", new_name)
                    with open(file_path, "wb") as f:
                        shutil.copyfileobj(file, f)

                    thumb_path = None
                    if thumb:
                        thumb_path = os.path.join("thumbnails", f"thumb_{ts}.jpg")
                        Image.open(thumb).convert("RGB").thumbnail((350, 500)).save(thumb_path, "JPEG", quality=95)

                    content = extract_text(file)
                    conn = sqlite3.connect(DB_NAME)
                    conn.execute("INSERT INTO documents VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (title, content, cat, file.name, file_path, thumb_path,
                         datetime.now().strftime("%Y-%m-%d %H:%M"), st.session_state.user))
                    conn.commit()
                    conn.close()
                    st.success("BERJAYA DISIMPAN!")
                    st.balloons()

    with tab2:
        for d in get_docs():
            id_, title, cat, fname, fpath, thumb, date, uploader = d
            with st.expander(f"ID {id_} • {title} • {cat}"):
                col1, col2 = st.columns([1, 2])
                with col1:
                    img = thumb if thumb and os.path.exists(thumb) else "https://via.placeholder.com/300x420.png?text=FAMA"
                    st.image(img, width=250)

                with col2:
                    new_title = st.text_input("Tajuk", value=title, key=f"t_{id_}")
                    new_cat = st.selectbox("Kategori", CATEGORIES, index=CATEGORIES.index(cat), key=f"c_{id_}")
                    new_thumb = st.file_uploader("Ganti Thumbnail", type=["jpg","jpeg","png"], key=f"th_{id_}")
                    new_file = st.file_uploader("Ganti Fail PDF/DOCX", type=["pdf","docx"], key=f"file_{id_}")

                    c1, c2, c3 = st.columns(3)
                    with c1:
                        if st.button("KEMASKINI", key=f"u_{id_}"):
                            new_fpath = fpath
                            new_fname = fname
                            new_content = None
                            if new_file:
                                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                                ext = Path(new_file.name).suffix
                                new_fname = new_file.name
                                new_fpath = os.path.join("uploads", f"{ts}_update_{Path(new_file.name).stem}{ext}")
                                with open(new_fpath, "wb") as f:
                                    shutil.copyfileobj(new_file, f)
                                new_content = extract_text(new_file)

                            new_tpath = thumb
                            if new_thumb:
                                new_tpath = os.path.join("thumbnails", f"thumb_edit_{id_}.jpg")
                                Image.open(new_thumb).convert("RGB").thumbnail((350,500)).save(new_tpath, "JPEG", quality=95)

                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("""UPDATE documents SET title=?, category=?, file_name=?, file_path=?, thumbnail_path=?, content=? WHERE id=?""",
                                        (new_title, new_cat, new_fname, new_fpath, new_tpath, new_content, id_))
                            conn.commit()
                            conn.close()
                            st.success("Kemaskini berjaya!")
                            st.rerun()

                    with c2:
                        st.download_button("QR Code", generate_qr(id_), f"QR_{id_}.png", "image/png", key=f"qr_{id_}")

                    with c3:
                        if st.button("PADAM", key=f"d_{id_}"):
                            if st.session_state.get(f"confirm_{id_}"):
                                if os.path.exists(fpath): os.remove(fpath)
                                if thumb and os.path.exists(thumb): os.remove(thumb)
                                conn = sqlite3.connect(DB_NAME)
                                conn.execute("DELETE FROM documents WHERE id=?", (id_,))
                                conn.commit()
                                conn.close()
                                st.success("Dipadam!")
                                st.rerun()
                            else:
                                st.session_state[f"confirm_{id_}"] = True
                                st.warning("Klik sekali lagi untuk sahkan")

    if st.button("Log Keluar"):
        st.session_state.admin = False
        st.rerun()
