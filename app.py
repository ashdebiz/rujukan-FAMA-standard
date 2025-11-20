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
# TEMA CANTIK FAMA
# =============================================
st.set_page_config(page_title="Rujukan Standard FAMA", page_icon="rice", layout="centered")

st.markdown("""
<style>
    .main {background: #f8fff8;}
    [data-testid="stSidebar"] {background: linear-gradient(#1B5E20, #2E7D32);}
    .header-container {
        position: relative; overflow: hidden; border-radius: 25px;
        box-shadow: 0 15px 40px rgba(27,94,32,0.5); margin: 20px 0;
    }
    .card {background: white; border-radius: 20px; padding: 20px; 
            box-shadow: 0 10px 30px rgba(0,0,0,0.1); border: 1px solid #c8e6c9; margin: 15px 0;}
    .stButton>button {background: #4CAF50; color: white; font-weight: bold; 
                      border-radius: 15px; height: 50px; border: none;}
    h1,h2,h3 {color: #1B5E20;}
</style>
""", unsafe_allow_html=True)

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

def extract_text(file):
    if not file: return ""
    try:
        data = file.getvalue() if hasattr(file, 'getvalue') else file.read()
        if str(file.name).lower().endswith(".pdf"):
            return " ".join(p.extract_text() or "" for p in PyPDF2.PdfReader(io.BytesIO(data)).pages)
        elif str(file.name).lower().endswith(".docx"):
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

def get_docs():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.execute("SELECT id, title, category, file_name, file_path, thumbnail_path, upload_date, uploaded_by FROM documents ORDER BY id DESC")
    docs = cur.fetchall()
    conn.close()
    return docs

# =============================================
# SIDEBAR — LOGO FAMA KECIK TENGAH
# =============================================
with st.sidebar:
    st.markdown("""
    <div style="text-align: center; padding: 20px 0;">
        <img src="https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png" width="80">
        <h3 style="color:white; margin:15px 0 0 0; font-weight: bold;">FAMA STANDARD</h3>
        <p style="color:#c8e6c9; margin:5px 0 0 0; font-size:0.9rem;">Sistem Digital Rasmi</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")
    page = st.selectbox("Menu", ["Halaman Utama", "Admin Panel"], label_visibility="collapsed")

# =============================================
# HALAMAN UTAMA — GAMBAR BUAH & SAYUR CANTIK!
# =============================================
if page == "Halaman Utama":
    st.markdown(f'''
    <div class="header-container">
        <img src="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSKvm2dXTYvt4qaPW6NROuESTVo-RgjoV6s6W80Cp5Jv_rrixoxkS1HEJT_dRkPtT39OjM&usqp=CAU?w=1200&h=600&fit=crop&crop=center&q=90" 
             style="width:100%; height:280px; object-fit:cover; filter: brightness(0.9);">
        <div style="position:absolute; top:0; left:0; width:100%; height:100%; 
                    background: linear-gradient(to bottom, rgba(27,94,32,0.8), rgba(76,175,80,0.7));">
        </div>
        <div style="position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); text-align:center; width:100%;">
            <h1 style="color:white; font-size:3.2rem; font-weight:900; margin:0;
                       text-shadow: 3px 3px 12px rgba(0,0,0,0.8);">
                RUJUKAN STANDARD FAMA
            </h1>
            <p style="color:#e8f5e8; font-size:1.4rem; margin:20px 0 0;
                      text-shadow: 2px 2px 8px rgba(0,0,0,0.7);">
               Bahagian Regulasi Pasaran
            </p>
        </div>
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
# ADMIN PANEL — TETAP PAKAI LOGO FAMA
# =============================================
else:
    if not st.session_state.get("admin"):
        st.markdown(f'''
        <div class="header-container">
            <img src="https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png" width="90" >
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
