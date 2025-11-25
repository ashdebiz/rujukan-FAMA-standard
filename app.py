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
# KONFIGURASI & TEMA FAMA CANTIK
# =============================================
st.set_page_config(page_title="Rujukan Standard FAMA", page_icon="leaf", layout="centered", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .main {background: #f8fff8;}
    [data-testid="stSidebar"] {background: linear-gradient(#1B5E20, #2E7D32);}
    .card {background: white; border-radius: 20px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); border: 1px solid #c8e6c9; margin: 15px 0;}
    .qr-container {background: white; border-radius: 30px; padding: 40px; text-align: center; box-shadow: 0 20px 50px rgba(27,94,32,0.2); border: 4px solid #4CAF50; margin: 30px 0;}
    .big-warning {background: #ffebee; border-left: 8px solid #f44336; padding: 20px; border-radius: 12px; margin: 20px 0;}
    .stButton>button {background: #4CAF50; color: white; font-weight: bold; border-radius: 15px; height: 55px; border: none;}
    h1,h2,h3 {color: #1B5E20;}
    
    /* CENTER LOGO FAMA DI SIDEBAR */
    .sidebar-logo-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 30px 0;
        text-align: center;
    }
    .sidebar-logo-container img {
        width: 100px;
        margin-bottom: 15px;
    }
    .sidebar-title {
        color: white;
        font-size: 1.8rem;
        font-weight: 900;
        margin: 0;
        text-shadow: 2px 2px 8px rgba(0,0,0,0.5);
    }
    .sidebar-subtitle {
        color: #c8e6c9;
        font-size: 0.95rem;
        margin: 5px 0 0;
    }
</style>
""", unsafe_allow_html=True)

# Folder
for f in ["uploads", "thumbnails", "backups"]:
    os.makedirs(f, exist_ok=True)

DB_NAME = "fama_standards.db"
CATEGORIES = ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"]

ADMIN_CREDENTIALS = {
    "admin": hashlib.sha256("fama2025".encode()).hexdigest(),
    "pengarah": hashlib.sha256("fama123".encode()).hexdigest()
}

# =============================================
# INIT DB
# =============================================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''
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
        )
    ''')
    cur.execute('''CREATE TABLE IF NOT EXISTS admins (username TEXT PRIMARY KEY, password_hash TEXT)''')
    try: cur.execute("SELECT content FROM documents LIMIT 1")
    except sqlite3.OperationalError: cur.execute("ALTER TABLE documents ADD COLUMN content TEXT")
    for u, h in ADMIN_CREDENTIALS.items():
        cur.execute("INSERT OR IGNORE INTO admins VALUES (?, ?)", (u, h))
    conn.commit()
    conn.close()

if not os.path.exists(DB_NAME):
    init_db()

# =============================================
# FUNGSI UTAMA
# =============================================
def save_thumbnail_safely(file, prefix="thumb"):
    if not file: return None
    try:
        img = Image.open(io.BytesIO(file.getvalue()))
        if img.format not in ["JPEG", "JPG", "PNG", "WEBP"]: return None
        if img.mode != "RGB": img = img.convert("RGB")
        img.thumbnail((350, 500), Image.Resampling.LANCZOS)
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

def get_docs():
    if not os.path.exists(DB_NAME): return []
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM documents ORDER BY upload_date DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# =============================================
# STATISTIK
# =============================================
def show_stats():
    docs = get_docs()
    total = len(docs)
    baru = len([d for d in docs if d['upload_date'][:10] >= (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")]) if docs else 0
    latest = max((d['upload_date'][:10] for d in docs), default="Belum ada") if docs else "Belum ada"
    cat_count = {c: sum(1 for d in docs if d['category'] == c) for c in CATEGORIES}

    st.markdown(f"""
    <div style="background:linear-gradient(to bottom, #0066ff 0%, #0099ff 100%); border-radius:25px; padding:25px; color:white;">
        <h2 style="text-align:center;">STATISTIK RUJUKAN FAMA STANDARD</h2>
        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:20px; text-align:center;">
            <div style="background:rgba(255,255,255,0.15); border-radius:18px; padding:18px;">
                <h1 style="margin:0; font-size:2rem;">{total}</h1><p>JUMLAH</p>
            </div>
            <div style="background:rgba(255,255,255,0.15); border-radius:18px; padding:18px;">
                <h1 style="margin:0; font-size:2rem;">{baru}</h1><p>BARU (30 HARI)</p>
            </div>
            <div style="background:rgba(255,255,255,0.15); border-radius:18px; padding:18px;">
                <h1 style="margin:0; font-size:1.5rem;">{latest}</h1><p>TERKINI</p>
            </div>
        </div>
        <div style="margin-top:25px; display:grid; grid-template-columns: repeat(4,1fr); gap:15px;">
            {''.join(f'<div style="background:rgba(255,255,255,0.1); border-radius:12px; padding:12px;"><strong>{c}</strong><br>{cat_count[c]}</div>' for c in CATEGORIES)}
        </div>
    </div>
    """, unsafe_allow_html=True)

# =============================================
# SIDEBAR — LOGO FAMA 100% CENTER!
# =============================================
with st.sidebar:
    st.markdown("""
    <div class="sidebar-logo-container">
        <img src="https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png" alt="FAMA Logo">
        <h3 class="sidebar-title">FAMA STANDARD</h3>
        <p class="sidebar-subtitle">Menu</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    page = st.selectbox("Menu", ["Halaman Utama", "Papar QR Code", "Admin Panel"], label_visibility="collapsed")

# =============================================
# HALAMAN UTAMA & QR (sama)
# =============================================
if page == "Halaman Utama":
    st.markdown(f'''
    <div style="position:relative; border-radius:25px; overflow:hidden; box-shadow:0 15px 40px rgba(27,94,32,0.5); margin:20px 0;">
        <img src="w7.pngwing.com/pngs/34/259/png-transparent-fruits-and-vegetables.png?w=1400&h=500&fit=crop" style="width:100%; height:300px; object-fit:cover;">
        <div style="position:absolute; top:0; left:0; width:100%; height:100%; background: linear-gradient(135deg, rgba(27,94,32,0.85), rgba(76,175,80,0.75));"></div>
        <div style="position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); text-align:center;">
            <h1 style="color:white; font-size:3.3rem; font-weight:900;">RUJUKAN FAMA STANDARD</h1>
            <p style="color:#e8f5e8; font-size:1.5rem;">Keluaran Hasil Pertanian Tempatan</p>
        </div>
    </div>
    ''', unsafe_allow_html=True)

    show_stats()
    col1, col2 = st.columns([3,1])
    with col1: cari = st.text_input("", placeholder="Cari tajuk standard...")
    with col2: kat = st.selectbox("", ["Semua"] + CATEGORIES)

    docs = get_docs()
    hasil = [d for d in docs if (kat == "Semua" or d['category'] == kat) and (not cari or cari.lower() in d['title'].lower())]
    st.markdown(f"<h3>Ditemui {len(hasil)} Standard</h3>", unsafe_allow_html=True)

    for d in hasil:
        with st.container():
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            c1, c2 = st.columns([1,3])
            with c1:
                img = d['thumbnail_path'] if d['thumbnail_path'] and os.path.exists(d['thumbnail_path']) else "https://via.placeholder.com/350x500/4CAF50/white?text=FAMA"
                st.image(img, use_container_width=True)
            with c2:
                st.markdown(f"<h2 style='margin:0; color:#1B5E20;'>{d['title']}</h2>", unsafe_allow_html=True)
                st.caption(f"**{d['category']}** • {d['upload_date'][:10]} • {d['uploaded_by']}")
                if d['file_path'] and os.path.exists(d['file_path']):
                    with open(d['file_path'], "rb") as f:
                        st.download_button("MUAT TURUN", f.read(), d['file_name'], use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

elif page == "Papar QR Code":
    st.markdown("<h1 style='text-align:center; color:#1B5E20;'>CARI & PAPAR QR CODE</h1>", unsafe_allow_html=True)
    show_stats()
    search = st.text_input("", placeholder="Taip nama standard...").strip()
    if not search:
        st.info("Taip nama standard untuk papar QR Code")
        st.stop()

    matches = [d for d in get_docs() if search.lower() in d['title'].lower() or search.lower() in d['category'].lower()]
    if not matches:
        st.warning("Tiada padanan")
        st.stop()

    if len(matches) == 1:
        d = matches[0]
        qr = base64.b64encode(generate_qr(d['id'])).decode()
        st.markdown(f"""
        <div class="qr-container">
            <h2 style="color:#1B5E20;">{d['title']}</h2>
            <p style="color:#4CAF50;"><strong>{d['category']}</strong></p>
            <img src="data:image/png;base64,{qr}" width="420">
        </div>
        """, unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1: st.download_button("QR CODE", generate_qr(d['id']), f"QR_{d['id']}.png", "image/png")
        with c2:
            if os.path.exists(d['file_path']):
                with open(d['file_path'], "rb") as f:
                    st.download_button("FAIL PDF", f.read(), d['file_name'])
    else:
        cols = st.columns(3)
        for i, d in enumerate(matches):
            with cols[i % 3]:
                qr = base64.b64encode(generate_qr(d['id'])).decode()
                st.markdown(f"""
                <div style="background:white; border-radius:25px; padding:20px; text-align:center; box-shadow:0 10px 30px rgba(0,0,0,0.1); border:3px solid #4CAF50;">
                    <p style="font-weight:bold; color:#1B5E20;">{d['title'][:40]}{'...' if len(d['title'])>40 else ''}</p>
                    <p style="color:#4CAF50;"><strong>{d['category']}</strong></p>
                    <img src="data:image/png;base64,{qr}" width="180">
                    <p><small>ID: {d['id']}</small></p>
                </div>
                """, unsafe_allow_html=True)

# =============================================
# ADMIN PANEL — FULL EDIT + BACKUP
# =============================================
else:
    if not st.session_state.get("logged_in"):
        st.markdown("<h1 style='text-align:center; color:#1B5E20;'>ADMIN PANEL</h1>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1: username = st.text_input("Username")
        with c2: password = st.text_input("Kata Laluan", type="password")
        if st.button("LOG MASUK"):
            h = hashlib.sha256(password.encode()).hexdigest()
            if username in ADMIN_CREDENTIALS and ADMIN_CREDENTIALS[username] == h:
                st.session_state.logged_in = True
                st.session_state.user = username
                st.rerun()
            else:
                st.error("Salah!")
        st.stop()

    st.success(f"Selamat Datang, {st.session_state.user.upper()}")

    tab1, tab2, tab3 = st.tabs(["Tambah Standard", "Senarai & Edit", "Backup & Recovery"])

    with tab1:
        file = st.file_uploader("PDF/DOCX", type=["pdf","docx"])
        title = st.text_input("Tajuk Standard")
        cat = st.selectbox("Kategori", CATEGORIES)
        thumb = st.file_uploader("Thumbnail (pilihan)", type=["jpg","jpeg","png"])
        if file and title:
            if st.button("SIMPAN STANDARD", type="primary"):
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                ext = Path(file.name).suffix
                fpath = f"uploads/{ts}_{Path(file.name).stem}{ext}"
                with open(fpath, "wb") as f: f.write(file.getvalue())
                tpath = save_thumbnail_safely(thumb, "new")
                content = extract_text(file)
                conn = sqlite3.connect(DB_NAME)
                conn.execute("INSERT INTO documents (title, content, category, file_name, file_path, thumbnail_path, upload_date, uploaded_by) VALUES (?,?,?,?,?,?,?,?)",
                             (title, content, cat, file.name, fpath, tpath, datetime.now().strftime("%Y-%m-%d %H:%M"), st.session_state.user))
                conn.commit(); conn.close()
                st.success("Berjaya disimpan!"); st.balloons()

    with tab2:
        for d in get_docs():
            with st.expander(f"ID {d['id']} • {d['title']} • {d['category']}"):
                col1, col2 = st.columns([1, 3])
                with col1:
                    current_img = d['thumbnail_path'] if d['thumbnail_path'] and os.path.exists(d['thumbnail_path']) else "https://via.placeholder.com/300x420/4CAF50/white?text=FAMA"
                    st.image(current_img, caption="Thumbnail Semasa", width=250)
                with col2:
                    new_title = st.text_input("Tajuk", value=d['title'], key=f"title_{d['id']}")
                    new_cat = st.selectbox("Kategori", CATEGORIES, index=CATEGORIES.index(d['category']), key=f"cat_{d['id']}")
                    new_file = st.file_uploader("Ganti Fail PDF/DOCX (pilihan)", type=["pdf","docx"], key=f"file_{d['id']}")
                    new_thumb = st.file_uploader("Ganti Thumbnail (pilihan)", type=["jpg","jpeg","png"], key=f"thumb_{d['id']}")

                    if st.button("KEMASKINI STANDARD", key=f"update_{d['id']}", type="primary"):
                        updated = False
                        new_fpath = d['file_path']
                        new_fname = d['file_name']
                        new_content = d.get('content', '')
                        new_tpath = d['thumbnail_path']

                        if new_file:
                            if os.path.exists(d['file_path']): os.remove(d['file_path'])
                            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                            ext = Path(new_file.name).suffix
                            new_fpath = f"uploads/{ts}_update_{Path(new_file.name).stem}{ext}"
                            with open(new_fpath, "wb") as f: f.write(new_file.getvalue())
                            new_fname = new_file.name
                            new_content = extract_text(new_file)
                            updated = True

                        if new_thumb:
                            if d['thumbnail_path'] and os.path.exists(d['thumbnail_path']): os.remove(d['thumbnail_path'])
                            new_tpath = save_thumbnail_safely(new_thumb, f"edit_{d['id']}")
                            updated = True

                        conn = sqlite3.connect(DB_NAME)
                        if updated:
                            conn.execute("""UPDATE documents SET title=?, category=?, file_name=?, file_path=?, thumbnail_path=?, content=? WHERE id=?""",
                                         (new_title, new_cat, new_fname, new_fpath, new_tpath, new_content, d['id']))
                        else:
                            conn.execute("UPDATE documents SET title=?, category=? WHERE id=?", (new_title, new_cat, d['id']))
                        conn.commit()
                        conn.close()
                        st.success("Berjaya dikemaskini!")
                        st.rerun()

                    if st.button("PADAM STANDARD", key=f"del_{d['id']}"):
                        if st.checkbox("Saya pasti nak padam", key=f"confirm_del_{d['id']}"):
                            if os.path.exists(d['file_path']): os.remove(d['file_path'])
                            if d['thumbnail_path'] and os.path.exists(d['thumbnail_path']): os.remove(d['thumbnail_path'])
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("DELETE FROM documents WHERE id=?", (d['id'],))
                            conn.commit(); conn.close()
                            st.success("Dipadam!"); st.rerun()

    with tab3:
        st.markdown("## Backup & Recovery (Anti-Hilang)")
        if not os.path.exists(DB_NAME) or len(get_docs()) == 0:
            st.markdown("<div class='big-warning'><h3>DATA HILANG! Upload backup .db di bawah</h3></div>", unsafe_allow_html=True)

        if os.path.exists(DB_NAME) and len(get_docs()) > 0:
            with open(DB_NAME, "rb") as f:
                st.download_button("DOWNLOAD BACKUP DATABASE SEKARANG", f.read(),
                                 f"FAMA_BACKUP_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                                 mime="application/octet-stream", type="primary", use_container_width=True)

        uploaded_db = st.file_uploader("Upload backup .db untuk pulihkan data", type=["db"])
        if uploaded_db and st.button("RESTORE DATABASE SEKARANG", type="primary"):
            if os.path.exists(DB_NAME):
                shutil.copy(DB_NAME, f"backups/old_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
            with open(DB_NAME, "wb") as f:
                f.write(uploaded_db.getvalue())
            st.success("DATA DIPULIHKAN 100%!"); st.balloons(); st.rerun()

    if st.button("Log Keluar"):
        st.session_state.clear()
        st.rerun()
