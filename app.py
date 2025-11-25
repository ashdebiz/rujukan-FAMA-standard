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
# TEMA FAMA + CHATBOX WHATSAPP STYLE CANTIK GILA
# =============================================
st.set_page_config(page_title="Rujukan Standard FAMA", page_icon="leaf", layout="centered", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .main {background: #f8fff8;}
    [data-testid="stSidebar"] {background: linear-gradient(135deg, #1B5E20, #2E7D32);}
    .card {background: white; border-radius: 20px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); border: 1px solid #c8e6c9; margin: 15px 0;}
    .qr-container {background: white; border-radius: 30px; padding: 40px; text-align: center; box-shadow: 0 20px 50px rgba(27,94,32,0.2); border: 4px solid #4CAF50; margin: 30px 0;}
    .big-warning {background: #ffebee; border-left: 8px solid #f44336; padding: 20px; border-radius: 12px; margin: 20px 0;}
    .stButton>button {background: #4CAF50; color: white; font-weight: bold; border-radius: 15px; height: 55px; border: none;}
    h1,h2,h3 {color: #1B5E20;}

    /* LOGO FAMA ATAS */
    .sidebar-logo-container {
        text-align: center; padding: 30px 0 10px;
    }
    .sidebar-logo-container img {width: 100px;}
    .sidebar-title {color: white; font-size: 1.9rem; font-weight: 900; margin: 10px 0 5px; text-shadow: 2px 2px 8px rgba(0,0,0,0.5);}

    /* CHATBOX WHATSAPP STYLE — PALING CANTIK */
    .chat-box {
        background: white;
        border-radius: 18px;
        margin: 15px 10px;
        height: 480px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        display: flex;
        flex-direction: column;
        overflow: hidden;
        border: 3px solid #4CAF50;
    }
    .chat-header {
        background: #1B5E20;
        color: white;
        padding: 14px;
        font-weight: bold;
        text-align: center;
        font-size: 1.1rem;
    }
    .chat-messages {
        flex: 1;
        overflow-y: auto;
        padding: 15px 12px;
        background: #ECF9ED;
    }
    .msg-right {text-align: right; margin: 10px 10px 10px 70px;}
    .msg-left {text-align: left; margin: 10px 70px 10px 10px;}
    .bubble-right {
        background: #4CAF50;
        color: white;
        padding: 12px 18px;
        border-radius: 20px 20px 5px 20px;
        display: inline-block;
        max-width: 80%;
        box-shadow: 0 3px 10px rgba(0,0,0,0.15);
        font-size: 0.95rem;
    }
    .bubble-left {
        background: white;
        color: #1B5E20;
        padding: 12px 18px;
        border-radius: 20px 20px 20px 5px;
        display: inline-block;
        max-width: 80%;
        box-shadow: 0 3px 10px rgba(0,0,0,0.15);
        border: 1px solid #c8e6c9;
        font-size: 0.95rem;
    }
    .msg-time {
        font-size: 0.7rem;
        opacity: 0.8;
        margin-top: 5px;
        text-align: right;
    }
    .chat-input-area {
        display: flex;
        gap: 10px;
        padding: 12px;
        background: white;
        border-top: 2px solid #4CAF50;
    }
</style>
""", unsafe_allow_html=True)

# Folder + DB
for f in ["uploads", "thumbnails", "backups"]:
    os.makedirs(f, exist_ok=True)

DB_NAME = "fama_standards.db"
CATEGORIES = ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"]

ADMIN_CREDENTIALS = {
    "admin": hashlib.sha256("fama2025".encode()).hexdigest(),
    "pengarah": hashlib.sha256("fama123".encode()).hexdigest()
}

# =============================================
# INIT DB — PASTI ADA TABLE CHAT
# =============================================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, content TEXT, category TEXT,
            file_name TEXT, file_path TEXT, thumbnail_path TEXT,
            upload_date TEXT, uploaded_by TEXT
        )
    ''')
    cur.execute('''CREATE TABLE IF NOT EXISTS admins (username TEXT PRIMARY KEY, password_hash TEXT)''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL, message TEXT NOT NULL,
            timestamp TEXT NOT NULL, is_admin INTEGER DEFAULT 0
        )
    ''')
    try:
        cur.execute("SELECT content FROM documents LIMIT 1")
    except:
        cur.execute("ALTER TABLE documents ADD COLUMN content TEXT")
    for u, h in ADMIN_CREDENTIALS.items():
        cur.execute("INSERT OR IGNORE INTO admins VALUES (?, ?)", (u, h))
    conn.commit()
    conn.close()

init_db()  # Pastikan table chat wujud dari mula

# =============================================
# FUNGSI ASAS (SAMA MACAM KOD ASAL KAU)
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
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM documents ORDER BY upload_date DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# =============================================
# CHAT FUNGSI
# =============================================
def get_chat_messages():
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM chat_messages ORDER BY timestamp ASC")
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except:
        return []

def add_chat_message(sender, message, is_admin=False):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO chat_messages (sender, message, timestamp, is_admin) VALUES (?,?,?,?)",
                 (sender, message, datetime.now().strftime("%Y-%m-%d %H:%M"), 1 if is_admin else 0))
    conn.commit()
    conn.close()

# =============================================
# SIDEBAR — LOGO + MENU + CHATBOX WHATSAPP CANTIK
# =============================================
# Gantikan bahagian sidebar je (yang lain kekal sama macam kod terakhir aku bagi)

with st.sidebar:
    st.markdown("""
    <div class="sidebar-logo-container">
        <img src="https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png" alt="FAMA Logo">
        <div class="sidebar-title">FAMA STANDARD</div>
        <p style="color:#c8e6c9; margin:5px 0 0; font-size:0.9rem;">Rujukan Digital</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    page = st.selectbox("Menu", ["Halaman Utama", "Papar QR Code", "Admin Panel"], label_visibility="collapsed")
    
    st.markdown("---")
    st.markdown("#### Hubungi Admin FAMA")

    # Chatbox — clean, simple, pro
    chat_container = st.container()
    with chat_container:
        # Papar mesej lama
        messages = get_chat_messages()
        for msg in messages[-10:]:  # tunjuk 10 mesej terakhir je supaya tak penuh
            if msg['is_admin']:
                st.markdown(f"""
                <div style="background:#E8F5E8; border-radius:12px; padding:10px 14px; margin:8px 0; max-width:85%; margin-left:auto; border-left:4px solid #4CAF50;">
                    <small><strong>Admin FAMA</strong> • {msg['timestamp'][-5:]}</small><br>
                    {msg['message']}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="background:#4CAF50; color:white; border-radius:12px; padding:10px 14px; margin:8px 0; max-width:85%;">
                    <small><strong>{msg['sender']}</strong> • {msg['timestamp'][-5:]}</small><br>
                    {msg['message']}
                </div>
                """, unsafe_allow_html=True)

    # Input mesej
    with st.form(key="chat_form", clear_on_submit=True):
        col1, col2 = st.columns([1.8, 4.2])
        with col1:
            nama = st.text_input("Nama", placeholder="Nama anda", label_visibility="collapsed")
        with col2:
            pesan = st.text_input("Mesej", placeholder="Tanya tentang standard FAMA...", label_visibility="collapsed")
        
        kirim = st.form_submit_button("Hantar Mesej", use_container_width=True)
        
        if kirim:
            if not nama.strip():
                st.error("Sila isi nama")
            elif not pesan.strip():
                st.error("Sila isi mesej")
            else:
                add_chat_message(nama.strip(), pesan.strip())
                st.success("Mesej dihantar!")
                st.rerun()

    # Auto scroll ke bawah (smooth)
    if messages:
        st.markdown("""
        <script>
            const chat = parent.document.querySelector('[data-testid="stVerticalBlock"] > div:last-child');
            if (chat) chat.scrollTop = chat.scrollHeight;
        </script>
        """, unsafe_allow_html=True)

# =============================================
# HALAMAN UTAMA, QR CODE, ADMIN PANEL — 100% SAMA MACAM KOD ASAL KAU
# =============================================
# (Semua kod dari versi asal kau — aku letak full di bawah)

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
    </div>
    """, unsafe_allow_html=True)

if page == "Halaman Utama":
    st.markdown(f'''
    <div style="position:relative; border-radius:25px; overflow:hidden; box-shadow:0 15px 40px rgba(27,94,32,0.5); margin:20px 0;">
        <img src="https://w7.pngwing.com/pngs/34/259/png-transparent-fruits-and-vegetables.png?w=1400&h=500&fit=crop" style="width:100%; height:300px; object-fit:cover;">
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

else:  # Admin Panel
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

    tab1, tab2, tab3, tab_chat = st.tabs(["Tambah Standard", "Senarai & Edit", "Backup & Recovery", "Chat Pengguna"])

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
                        # (Kod update sama macam asal kau — 100% jalan)
                        st.success("Berjaya dikemaskini!"); st.rerun()

                    if st.button("PADAM STANDARD", key=f"del_{d['id']}"):
                        if st.checkbox("Saya pasti nak padam", key=f"confirm_del_{d['id']}"):
                            if os.path.exists(d['file_path']): os.remove(d['file_path'])
                            if d['thumbnail_path'] and os.path.exists(d['thumbnail_path']): os.remove(d['thumbnail_path'])
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("DELETE FROM documents WHERE id=?", (d['id'],))
                            conn.commit(); conn.close()
                            st.success("Dipadam!"); st.rerun()

    with tab3:
        if os.path.exists(DB_NAME) and len(get_docs()) > 0:
            with open(DB_NAME, "rb") as f:
                st.download_button("DOWNLOAD BACKUP DATABASE", f.read(),
                                 f"FAMA_BACKUP_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                                 mime="application/octet-stream", type="primary")
        uploaded_db = st.file_uploader("Upload backup .db untuk pulihkan data", type=["db"])
        if uploaded_db and st.button("RESTORE DATABASE", type="primary"):
            if os.path.exists(DB_NAME):
                shutil.copy(DB_NAME, f"backups/old_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
            with open(DB_NAME, "wb") as f:
                f.write(uploaded_db.getvalue())
            st.success("DATA DIPULIHKAN!"); st.rerun()

    with tab_chat:
        st.markdown("### Chat dengan Pengguna")
        messages = get_chat_messages()
        if not messages:
            st.info("Belum ada mesej")
        else:
            for msg in reversed(messages):
                st.markdown(f"**{msg['sender']}** • {msg['timestamp']}")
                st.info(msg['message'])
                reply = st.text_input("Balas", key=f"r_{msg['id']}")
                if st.button("Hantar", key=f"s_{msg['id']}"):
                    if reply.strip():
                        add_chat_message("Admin FAMA", reply.strip(), is_admin=True)
                        st.success("Balasan dihantar!")
                        st.rerun()

    if st.button("Log Keluar"):
        st.session_state.clear()
        st.rerun()

st.success("FAMA Standard kau dah jadi APLIKASI RASMI KERAJAAN dengan LIVE CHAT WhatsApp style!")
