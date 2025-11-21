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
# KONFIGURASI & TEMA CANTIK FAMA
# =============================================
st.set_page_config(
    page_title="Rujukan Standard FAMA",
    page_icon="leaf",
    layout="centered",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main {background: #f8fff8;}
    [data-testid="stSidebar"] {background: linear-gradient(#1B5E20, #2E7D32);}
    .card {background: white; border-radius: 20px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); border: 1px solid #c8e6c9; margin: 15px 0;}
    .qr-container {
        background: white; border-radius: 30px; padding: 40px; text-align: center;
        box-shadow: 0 20px 50px rgba(27,94,32,0.2); border: 4px solid #4CAF50; margin: 30px 0;
    }
    .qr-title {color: #1B5E20; font-size: 2.3rem; font-weight: 900; margin: 10px 0;}
    .qr-cat {color: #4CAF50; font-weight: bold; font-size: 1.4rem; margin: 10px 0;}
    .stButton>button {background: #4CAF50; color: white; font-weight: bold; border-radius: 15px; height: 55px; border: none;}
    h1,h2,h3 {color: #1B5E20;}
</style>
""", unsafe_allow_html=True)

# =============================================
# FOLDER & DATABASE
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
# FUNGSI UTAMA
# =============================================
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
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1B5E20", back_color="white")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()

def get_docs():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.execute("SELECT id, title, category, file_name, file_path, thumbnail_path, upload_date, uploaded_by FROM documents ORDER BY upload_date DESC")
    docs = cur.fetchall()
    conn.close()
    return docs

# =============================================
# STATISTIK CANTIK (BARU!)
# =============================================
def show_stats():
    docs = get_docs()
    total = len(docs)
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    baru = len([d for d in docs if d[6] >= thirty_days_ago]) if docs else 0
    latest = max((d[6][:10] for d in docs), default="Belum ada") if docs else "Belum ada"
    
    cat_count = {"Keratan Bunga": 0, "Sayur-sayuran": 0, "Buah-buahan": 0, "Lain-lain": 0}
    for d in docs:
        if d[2] in cat_count:
            cat_count[d[2]] += 1

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1B5E20,#4CAF50); border-radius:25px; padding:25px; 
                box-shadow:0 15px 40px rgba(27,94,32,0.4); margin:20px 0; color:white;">
        <h2 style="text-align:center; margin:0 0 14px 0; font-size:2.3rem;">STATISTIK RUJUKAN FAMA STANDARD</h2>
        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:20px; text-align:center;">
            <div style="background:rgba(255,255,255,0.15); border-radius:18px; padding:18px;">
                <h1 style="margin:0; font-size:3rem; color:#e8f5e8;">{total}</h1>
                <p style="margin:5px 0 0; font-size:1.1rem;">JUMLAH STANDARD</p>
            </div>
            <div style="background:rgba(255,255,255,0.15); border-radius:18px; padding:18px;">
                <h1 style="margin:0; font-size:3rem; color:#b9f6ca;">{baru}</h1>
                <p style="margin:5px 0 0; font-size:1.1rem;">BARU (30 HARI)</p>
            </div>
            <div style="background:rgba(255,255,255,0.15); border-radius:18px; padding:18px;">
                <h1 style="margin:0; font-size:2.2rem; color:#c8e6c9;">{latest}</h1>
                <p style="margin:5px 0 0; font-size:1rem;">TERKINI DIUPLOAD</p>
            </div>
        </div>
        <div style="margin-top:25px; display:grid; grid-template-columns: repeat(4, 1fr); gap:15px; font-size:0.95rem;">
            <div style="background:rgba(255,255,255,0.1); border-radius:12px; padding:12px;">
                <strong>Keratan Bunga</strong><br>{cat_count["Keratan Bunga"]}
            </div>
            <div style="background:rgba(255,255,255,0.1); border-radius:12px; padding:12px;">
                <strong>Sayur-sayuran</strong><br>{cat_count["Sayur-sayuran"]}
            </div>
            <div style="background:rgba(255,255,255,0.1); border-radius:12px; padding:12px;">
                <strong>Buah-buahan</strong><br>{cat_count["Buah-buahan"]}
            </div>
            <div style="background:rgba(255,255,255,0.1); border-radius:12px; padding:12px;">
                <strong>Lain-lain</strong><br>{cat_count["Lain-lain"]}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# =============================================
# SIDEBAR
# =============================================
with st.sidebar:
    st.markdown("""
    <div style="text-align: center; padding: 30px 0;">
        <img src="https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png" width="80">
        <h3 style="color:white; margin:15px 0 5px 0; font-weight: bold;">FAMA STANDARD</h3>
        <p style="color:#c8e6c9; margin:0; font-size:0.95rem;">Bahagian Regulasi Pasaran</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")
    page = st.selectbox("Menu", ["Halaman Utama", "Papar QR Code", "Admin Panel"], label_visibility="collapsed")

# =============================================
# HALAMAN UTAMA
# =============================================
if page == "Halaman Utama":
    st.markdown(f'''
    <div style="position:relative; border-radius:25px; overflow:hidden; box-shadow:0 15px 40px rgba(27,94,32,0.5); margin:20px 0;">
        <img src="https://w7.pngwing.com/pngs/34/259/png-transparent-fruits-and-vegetables.png?w=1400&h=500&fit=crop" style="width:100%; height:300px; object-fit:cover;">
        <div style="position:absolute; top:0; left:0; width:100%; height:100%; background: linear-gradient(135deg, rgba(27,94,32,0.85), rgba(76,175,80,0.75));"></div>
        <div style="position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); text-align:center; width:100%;">
            <h1 style="color:white; font-size:3.3rem; font-weight:900; margin:0; text-shadow: 4px 4px 15px rgba(0,0,0,0.8);">
                RUJUKAN FAMA STANDARD 
            </h1>
            <p style="color:#e8f5e8; font-size:1.5rem; margin:20px 0 0; text-shadow: 2px 2px 8px rgba(0,0,0,0.7);">
                Hasil Keluaran Pertanian Tempatan
            </p>
        </div>
    </div>
    ''', unsafe_allow_html=True)

    show_stats()  # STATISTIK CANTIK

    col1, col2 = st.columns([3,1])
    with col1: cari = st.text_input("", placeholder="Cari tajuk standard...")
    with col2: kat = st.selectbox("", ["Semua"] + CATEGORIES)

    docs = get_docs()
    hasil = [d for d in docs if (kat == "Semua" or d[2] == kat) and (not cari or cari.lower() in d[1].lower())]

    st.markdown(f"<h3 style='color:#1B5E20;'>Ditemui {len(hasil)} Standard</h3>", unsafe_allow_html=True)

    for d in hasil:
        id_, title, cat, fname, fpath, thumb, date, uploader = d
        with st.container():
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            c1, c2 = st.columns([1,3])
            with c1:
                img = thumb if thumb and os.path.exists(thumb) else "https://via.placeholder.com/350x500/4CAF50/white?text=FAMA"
                st.image(img, use_container_width=True)
            with c2:
                st.markdown(f"<h2 style='margin:0; color:#1B5E20;'>{title}</h2>", unsafe_allow_html=True)
                st.caption(f"**{cat}** • {date[:10]} • {uploader}")
                if fpath and os.path.exists(fpath):
                    with open(fpath, "rb") as f:
                        st.download_button("MUAT TURUN", f.read(), fname, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

# =============================================
# PAPAR QR CODE — CARI LANGSUNG + STATISTIK
# =============================================
elif page == "Papar QR Code":
    st.markdown(f'''
    <div style="text-align:center; padding:30px; background:linear-gradient(135deg,#1B5E20,#4CAF50); 
                border-radius:25px; margin:20px 0; box-shadow:0 15px 40px rgba(27,94,32,0.5);">
        <h1 style="color:white; margin:0; font-size:2.8rem;">CARI & PAPAR QR CODE</h1>
        <p style="color:#c8e6c9; margin:10px 0 0; font-size:1.2rem;">Taip nama standard untuk papar QR</p>
    </div>
    ''', unsafe_allow_html=True)

    show_stats()  # STATISTIK SINI JUGA

    docs = get_docs()
    if not docs:
        st.info("Belum ada standard. Sila tambah di Admin Panel.")
        st.stop()

    search = st.text_input("", placeholder="Contoh: timun, durian, ros, standard sayur...", label_visibility="collapsed").strip()

    if not search:
        st.info("Taip nama standard untuk papar QR Code")
        st.stop()

    matches = [d for d in docs if search.lower() in d[1].lower() or search.lower() in d[2].lower()]

    if not matches:
        st.warning(f"Tiada standard ditemui untuk \"{search}\"")
        st.stop()

    st.success(f"Ditemui {len(matches)} standard")

    if len(matches) == 1:
        doc = matches[0]
        id_, title, cat, fname, fpath, thumb, date, uploader = doc
        qr_b64 = base64.b64encode(generate_qr(id_)).decode()

        st.markdown(f"""
        <div class="qr-container">
            <h2 class="qr-title">{title}</h2>
            <p class="qr-cat">{cat}</p>
            <img src="data:image/png;base64,{qr_b64}" width="420">
            <p style="margin:30px 0 10px; font-size:1.4rem; color:#333;"><strong>Scan untuk muat turun</strong></p>
            <p style="color:#666;">ID: {id_} • {date[:10]} • {uploader}</p>
        </div>
        """, unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            st.download_button("MUAT TURUN QR", generate_qr(id_), f"QR_ID{id_}_{title[:30]}.png", "image/png", use_container_width=True)
        with c2:
            if os.path.exists(fpath):
                with open(fpath, "rb") as f:
                    st.download_button("MUAT TURUN FAIL", f.read(), fname, use_container_width=True)
    else:
        cols = st.columns(3)
        for i, doc in enumerate(matches):
            id_, title, cat, fname, fpath, thumb, date, uploader = doc
            qr_b64 = base64.b64encode(generate_qr(id_)).decode()

            with cols[i % 3]:
                st.markdown(f"""
                <div style="background:white; border-radius:25px; padding:20px; text-align:center; 
                            box-shadow:0 15px 40px rgba(27,94,32,0.15); border:4px solid #4CAF50; margin:20px 0;">
                    <p style="font-weight:bold; color:#1B5E20; margin:8px 0 12px; font-size:1.1rem;">
                        {title[:45]}{'...' if len(title)>45 else ''}
                    </p>
                    <p style="color:#4CAF50; font-weight:bold; margin:5px 0 15px;">{cat}</p>
                    <img src="data:image/png;base64,{qr_b64}" width="200">
                    <p style="margin:15px 0 8px; color:#333; font-size:0.95rem;"><strong>ID: {id_}</strong></p>
                    <p style="color:#666; font-size:0.8rem; margin:5px 0;">{uploader}</p>
                    <a href="?doc={id_}" target="_blank">
                        <button style="background:#4CAF50; color:white; border:none; padding:10px 18px; 
                                       border-radius:12px; font-weight:bold; cursor:pointer;">
                            Buka Standard
                        </button>
                    </a>
                </div>
                """, unsafe_allow_html=True)

# =============================================
# ADMIN PANEL (100% STABIL)
# =============================================
else:
    if not st.session_state.get("admin_logged_in", False):
        st.markdown(f'''
        <div style="text-align:center; padding:2rem; background:linear-gradient(135deg,#1B5E20,#4CAF50); 
                    border-radius:25px; box-shadow:0 10px 10px rgba(27,94,32,0.5); margin:20px 0;">
            <img src="https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png" width="80">
            <h1 style="color:white; margin:15px 0 0;">ADMIN PANEL</h1>
        </div>
        ''', unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1: username = st.text_input("Username")
        with c2: password = st.text_input("Kata Laluan", type="password")

        if st.button("LOG MASUK", type="primary", use_container_width=True):
            h = hashlib.sha256(password.encode()).hexdigest()
            if (username == "admin" and h == hashlib.sha256("fama2025".encode()).hexdigest()) or \
               (username == "pengarah" and h == hashlib.sha256("fama123".encode()).hexdigest()):
                st.session_state.admin_logged_in = True
                st.session_state.user = username
                st.rerun()
            else:
                st.error("Salah username/kata laluan")
        st.stop()

    st.markdown(f"<h1 style='text-align:center; color:#1B5E20;'>Selamat Datang, {st.session_state.user.upper()}!</h1>", unsafe_allow_html=True)
    st.markdown("### Tambah Standard Baru")
    uploaded_file = st.file_uploader("Pilih fail PDF/DOCX", type=["pdf","docx"])
    title = st.text_input("Tajuk Standard")
    category = st.selectbox("Kategori", CATEGORIES)
    thumbnail = st.file_uploader("Thumbnail (Pilihan)", type=["jpg","jpeg","png"])

    if uploaded_file and title:
        if st.button("SIMPAN STANDARD", type="primary", use_container_width=True):
            with st.spinner("Sedang simpan..."):
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                ext = Path(uploaded_file.name).suffix
                new_name = f"{ts}_{Path(uploaded_file.name).stem}{ext}"
                file_path = os.path.join("uploads", new_name)
                with open(file_path, "wb") as f:
                    shutil.copyfileobj(uploaded_file, f)

                thumb_path = None
                if thumbnail:
                    try:
                        thumb_path = os.path.join("thumbnails", f"thumb_{ts}.jpg")
                        Image.open(thumbnail).convert("RGB").thumbnail((350,500)).save(thumb_path, "JPEG", quality=95)
                    except: pass

                content = extract_text(uploaded_file)
                conn = sqlite3.connect(DB_NAME)
                conn.execute("INSERT INTO documents VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (title, content, category, uploaded_file.name, file_path, thumb_path,
                     datetime.now().strftime("%Y-%m-%d %H:%M"), st.session_state.user))
                conn.commit()
                conn.close()
                st.success("BERJAYA DISIMPAN!")
                st.balloons()

    st.markdown("### Senarai & Edit")
    for doc in get_docs():
        id_, title, cat, fname, fpath, thumb, date, uploader = doc
        with st.expander(f"ID {id_} • {title} • {cat}"):
            col1, col2 = st.columns([1,2])
            with col1:
                img = thumb if thumb and os.path.exists(thumb) else "https://via.placeholder.com/300x420.png?text=FAMA"
                st.image(img, width=250)
            with col2:
                new_title = st.text_input("Tajuk", value=title, key=f"t{id_}")
                new_cat = st.selectbox("Kategori", CATEGORIES, index=CATEGORIES.index(cat), key=f"c{id_}")
                new_thumb = st.file_uploader("Ganti Thumbnail", type=["jpg","jpeg","png"], key=f"th{id_}")
                new_file = st.file_uploader("Ganti Fail", type=["pdf","docx"], key=f"f{id_}")

                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("KEMASKINI", key=f"u{id_}"):
                        final_fpath = fpath
                        final_fname = fname
                        if new_file:
                            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                            ext = Path(new_file.name).suffix
                            final_fname = new_file.name
                            final_fpath = os.path.join("uploads", f"{ts}_update_{Path(new_file.name).stem}{ext}")
                            with open(final_fpath, "wb") as f:
                                shutil.copyfileobj(new_file, f)
                        final_thumb = thumb
                        if new_thumb:
                            final_thumb = os.path.join("thumbnails", f"thumb_edit_{id_}.jpg")
                            Image.open(new_thumb).convert("RGB").thumbnail((350,500)).save(final_thumb, "JPEG", quality=95)

                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("UPDATE documents SET title=?, category=?, file_name=?, file_path=?, thumbnail_path=? WHERE id=?",
                                    (new_title, new_cat, final_fname, final_fpath, final_thumb, id_))
                        conn.commit()
                        conn.close()
                        st.success("Kemaskini berjaya!")
                        st.rerun()

                with c2:
                    st.download_button("QR Code", generate_qr(id_), f"QR_{id_}.png", "image/png", key=f"qr{id_}")

                with c3:
                    if st.button("PADAM", key=f"d{id_}"):
                        if st.session_state.get(f"confirm{id_}"):
                            if os.path.exists(fpath): os.remove(fpath)
                            if thumb and os.path.exists(thumb): os.remove(thumb)
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("DELETE FROM documents WHERE id=?", (id_,))
                            conn.commit()
                            conn.close()
                            st.success("Dipadam!")
                            st.rerun()
                        else:
                            st.session_state[f"confirm{id_}"] = True
                            st.warning("Klik sekali lagi untuk padam")

    if st.button("Log Keluar"):
        st.session_state.admin_logged_in = False
        st.rerun()
