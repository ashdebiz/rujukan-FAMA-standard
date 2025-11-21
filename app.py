import streamlit as st
import sqlite3
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import PyPDF2
from docx import Document
import io
import hashlib
import qrcode
from PIL import Image
import base64

# =============================================
# KONFIGURASI & TEMA
# =============================================
st.set_page_config(page_title="Rujukan Standard FAMA", page_icon="leaf", layout="centered", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .main {background: #f8fff8;}
    [data-testid="stSidebar"] {background: linear-gradient(#1B5E20, #2E7D32);}
    .card {background: white; border-radius: 20px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); border: 1px solid #c8e6c9; margin: 15px 0;}
    .qr-container {background: white; border-radius: 30px; padding: 40px; text-align: center; box-shadow: 0 20px 50px rgba(27,94,32,0.2); border: 4px solid #4CAF50; margin: 30px 0;}
    .stButton>button {background: #4CAF50; color: white; font-weight: bold; border-radius: 15px; height: 55px; border: none;}
    h1,h2,h3 {color: #1B5E20;}
</style>
""", unsafe_allow_html=True)

# Folder
for f in ["uploads", "thumbnails", "backups"]:
    os.makedirs(f, exist_ok=True)

DB_NAME = "fama_standards.db"
CATEGORIES = ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"]

# =============================================
# USER
# =============================================
USERS = {
    "admin": hashlib.sha256("fama2025".encode()).hexdigest(),
    "pengarah": hashlib.sha256("fama123".encode()).hexdigest(),
    "superadmin": hashlib.sha256("super1234".encode()).hexdigest()
}

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, content TEXT, category TEXT,
        file_name TEXT, file_path TEXT, thumbnail_path TEXT, upload_date TEXT, uploaded_by TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS admins (
        username TEXT PRIMARY KEY, password_hash TEXT NOT NULL)''')
    try: cur.execute("SELECT content FROM documents LIMIT 1")
    except: cur.execute("ALTER TABLE documents ADD COLUMN content TEXT")
    for u, h in USERS.items():
        cur.execute("INSERT OR IGNORE INTO admins VALUES (?, ?)", (u, h))
    conn.commit()
    conn.close()

init_db()

# =============================================
# FUNGSI SELAMAT
# =============================================
def save_thumbnail_safely(file, prefix="thumb"):
    if not file: return None
    try:
        data = file.getvalue()
        if len(data) > 5_000_000: return None
        img = Image.open(io.BytesIO(data))
        if img.format not in ["JPEG","JPG","PNG","WEBP"]: return None
        if img.mode != "RGB": img = img.convert("RGB")
        img.thumbnail((350,500), Image.Resampling.LANCZOS)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"thumbnails/{prefix}_{ts}.jpg"
        img.save(path, "JPEG", quality=90)
        return path
    except: return None

def extract_text(file):
    if not file: return ""
    try:
        data = file.getvalue()
        if file.name.lower().endswith(".pdf"):
            return " ".join(p.extract_text() or "" for p in PyPDF2.PdfReader(io.BytesIO(data)).pages)
        elif file.name.lower().endswith(".docx"):
            return " ".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
    except: pass
    return ""

def generate_qr(id_):
    url = f"https://rujukan-fama-standard.streamlit.app/?doc={id_}"
    qr = qrcode.QRCode(box_size=15, border=8)
    qr.add_data(url); qr.make(fit=True)
    img = qr.make_image(fill_color="#1B5E20", back_color="white")
    buf = io.BytesIO(); img.save(buf, "PNG")
    return buf.getvalue()

# BETULKAN get_docs — GUNA SELECT * + DICTIONARY UNPACKING
def get_docs():
    if not os.path.exists(DB_NAME):
        return []
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Kembali dict-like
    cur = conn.cursor()
    cur.execute("SELECT * FROM documents ORDER BY upload_date DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]  # Return list of dict

def show_stats():
    docs = get_docs()
    total = len(docs)
    baru = len([d for d in docs if d['upload_date'][:10] >= (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")]) if docs else 0
    latest = max((d['upload_date'][:10] for d in docs), default="Belum ada") if docs else "Belum ada"
    cat_count = {c: sum(1 for d in docs if d['category'] == c) for c in CATEGORIES}
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1B5E20,#4CAF50); color:white; padding:25px; border-radius:25px;">
        <h2 style="text-align:center;">STATISTIK RUJUKAN STANDARD FAMA</h2>
        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:20px; text-align:center;">
            <div style="background:rgba(255,255,255,0.15); border-radius:18px; padding:18px;">
                <h1 style="margin:0; font-size:3rem;">{total}</h1><p>JUMLAH STANDARD</p>
            </div>
            <div style="background:rgba(255,255,255,0.15); border-radius:18px; padding:18px;">
                <h1 style="margin:0; font-size:3rem;">{baru}</h1><p>BARU (30 HARI)</p>
            </div>
            <div style="background:rgba(255,255,255,0.15); border-radius:18px; padding:18px;">
                <h1 style="margin:0; font-size:2rem;">{latest}</h1><p>TERKINI</p>
            </div>
        </div>
        <div style="margin-top:20px; display:grid; grid-template-columns: repeat(4,1fr); gap:10px;">
            {''.join(f'<div style="background:rgba(255,255,255,0.1); border-radius:12px; padding:10px;"><strong>{c}</strong><br>{cat_count[c]}</div>' for c in CATEGORIES)}
        </div>
    </div>
    """, unsafe_allow_html=True)

# =============================================
# SIDEBAR
# =============================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png", width=80)
    st.markdown("<h3 style='color:white; text-align:center;'>FAMA STANDARD</h3>", unsafe_allow_html=True)
    st.markdown("<p style='color:#c8e6c9; text-align:center;'>Sistem Digital Rasmi</p>", unsafe_allow_html=True)
    st.markdown("---")
    page = st.selectbox("Menu", ["Halaman Utama", "Papar QR Code", "Admin Panel"], label_visibility="collapsed")

# =============================================
# HALAMAN UTAMA & QR (pakai dict unpacking)
# =============================================
if page == "Halaman Utama":
    st.markdown("<h1 style='text-align:center; color:#1B5E20;'>RUJUKAN STANDARD FAMA</h1>", unsafe_allow_html=True)
    show_stats()
    col1, col2 = st.columns([3,1])
    with col1: cari = st.text_input("", placeholder="Cari tajuk standard...")
    with col2: kat = st.selectbox("", ["Semua"] + CATEGORIES)
    docs = get_docs()
    hasil = [d for d in docs if (kat == "Semua" or d['category'] == kat) and (not cari or cari.lower() in d['title'].lower())]
    st.markdown(f"<h3>Ditemui {len(hasil)} Standard</h3>", unsafe_allow_html=True)
    for d in hasil:
        id_ = d['id']
        title = d['title']
        cat = d['category']
        fname = d['file_name']
        fpath = d['file_path']
        thumb = d['thumbnail_path']
        date = d['upload_date']
        uploader = d['uploaded_by']
        with st.container():
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            c1, c2 = st.columns([1,3])
            with c1:
                img = thumb if thumb and os.path.exists(thumb) else "https://via.placeholder.com/350x500/4CAF50/white?text=FAMA"
                st.image(img)
            with c2:
                st.markdown(f"<h2 style='margin:0; color:#1B5E20;'>{title}</h2>", unsafe_allow_html=True)
                st.caption(f"**{cat}** • {date[:10]} • {uploader}")
                if fpath and os.path.exists(fpath):
                    with open(fpath, "rb") as f:
                        st.download_button("MUAT TURUN", f.read(), fname)
            st.markdown("</div>", unsafe_allow_html=True)

elif page == "Papar QR Code":
    st.markdown("<h1 style='text-align:center; color:#1B5E20;'>CARI QR CODE</h1>", unsafe_allow_html=True)
    show_stats()
    search = st.text_input("Cari standard").strip()
    if search:
        matches = [d for d in get_docs() if search.lower() in d['title'].lower() or search.lower() in d['category'].lower()]
        for d in matches:
            id_ = d['id']
            title = d['title']
            cat = d['category']
            st.image(generate_qr(id_), width=300)
            st.write(f"**{title}** • {cat}")

# =============================================
# ADMIN PANEL — HANYA SUPERADMIN BOLEH RESET
# =============================================
else:
    if not st.session_state.get("logged_in"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Log Masuk"):
            h = hashlib.sha256(password.encode()).hexdigest()
            if username in USERS and USERS[username] == h:
                st.session_state.logged_in = True
                st.session_state.user = username
                st.session_state.superadmin = (username == "superadmin")
                st.rerun()
            else:
                st.error("Salah!")
        st.stop()

    role = "SUPERADMIN" if st.session_state.superadmin else "ADMIN"
    st.markdown(f"<h1 style='text-align:center;'>Selamat Datang, {st.session_state.user.upper()} ({role})</h1>", unsafe_allow_html=True)

    tabs = ["Tambah", "Senarai"]
    if st.session_state.superadmin:
        tabs.append("SUPERADMIN")
    t1, t2, *extra = st.tabs(tabs)

    # Tambah & Senarai — ringkas
    with t1:
        file = st.file_uploader("PDF/DOCX", type=["pdf","docx"])
        title = st.text_input("Tajuk")
        cat = st.selectbox("Kategori", CATEGORIES)
        thumb = st.file_uploader("Thumbnail", type=["jpg","png"])
        if file and title:
            if st.button("SIMPAN"):
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                ext = Path(file.name).suffix
                path = f"uploads/{ts}_{Path(file.name).stem}{ext}"
                with open(path, "wb") as f: f.write(file.getvalue())
                tpath = save_thumbnail_safely(thumb, "new")
                content = extract_text(file)
                conn = sqlite3.connect(DB_NAME)
                conn.execute("INSERT INTO documents (title, content, category, file_name, file_path, thumbnail_path, upload_date, uploaded_by) VALUES (?,?,?, ?,?,?,?,?)",
                             (title, content, cat, file.name, path, tpath, datetime.now().strftime("%Y-%m-%d %H:%M"), st.session_state.user))
                conn.commit(); conn.close()
                st.success("Disimpan!"); st.balloons()

    with t2:
        for d in get_docs():
            with st.expander(f"ID {d['id']} • {d['title']} • {d['category']}"):
                new_title = st.text_input("Tajuk", d['title'], key=f"t{d['id']}")
                new_cat = st.selectbox("Kategori", CATEGORIES, CATEGORIES.index(d['category']), key=f"c{d['id']}")
                new_thumb = st.file_uploader("Ganti Thumbnail", type=["jpg","png"], key=f"th{d['id']}")
                if st.button("KEMASKINI", key=f"u{d['id']}"):
                    new_tpath = d['thumbnail_path']
                    if new_thumb:
                        new_tpath = save_thumbnail_safely(new_thumb, f"edit_{d['id']}")
                    conn = sqlite3.connect(DB_NAME)
                    conn.execute("UPDATE documents SET title=?, category=?, thumbnail_path=? WHERE id=?", 
                                 (new_title, new_cat, new_tpath, d['id']))
                    conn.commit(); conn.close()
                    st.success("Dikemaskini!"); st.rerun()

    # SUPERADMIN TAB
    if st.session_state.superadmin and extra:
        with extra[0]:
            st.markdown("### PENGURUSAN DATABASE")
            st.error("HANYA SUPERADMIN BOLEH GUNA!")
            c1, c2, c3 = st.columns(3)
            with c1:
                if os.path.exists(DB_NAME):
                    with open(DB_NAME, "rb") as f:
                        st.download_button("DOWNLOAD DB", f.read(), f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
            with c2:
                uploaded = st.file_uploader("Upload DB baru", type=["db"])
                if uploaded and st.button("GANTI DB"):
                    shutil.copy(DB_NAME, f"backups/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
                    with open(DB_NAME, "wb") as f: f.write(uploaded.getvalue())
                    st.success("DB diganti! Restart...")
                    st.rerun()
            with c3:
                if st.button("RESET TOTAL", type="secondary"):
                    if st.checkbox("Padam semua data"):
                        if st.button("YA, RESET!", type="primary"):
                            with st.spinner("Reset..."):
                                if os.path.exists(DB_NAME): os.remove(DB_NAME)
                                for folder in ["uploads", "thumbnails"]:
                                    if os.path.exists(folder): shutil.rmtree(folder)
                                    os.makedirs(folder)
                                st.cache_data.clear()
                                st.cache_resource.clear()
                                init_db()
                                st.success("RESET BERJAYA! Kosong 100%")
                                st.rerun()

    if st.button("Log Keluar"):
        st.session_state.clear()
        st.rerun()
