import streamlit as st
import sqlite3
import os
import zipfile
import shutil
from datetime import datetime
import hashlib
from PIL import Image
import qrcode
from io import BytesIO

# =============================================
# CONFIG + AUTO RESPONSIVE
# =============================================
st.set_page_config(
    page_title="Rujukan Standard FAMA",
    page_icon="leaf",
    layout="centered",
    initial_sidebar_state="auto"
)

# Detect device
try:
    width = st.get_option("client.width") or 1200
    device = "mobile" if width < 768 else "tablet" if width < 1200 else "desktop"
except:
    device = "desktop"

# Dynamic styling
if device == "mobile":
    header_size = "3.2rem"
    padding = "15px"
    qr_size = 260
else:
    header_size = "5rem"
    padding = "25px"
    qr_size = 350

st.markdown(f"""
<style>
    .main {{background: #f8fff8; padding: 10px;}}
    [data-testid="stSidebar"] {{background: linear-gradient(#1B5E20, #2E7D32);}}
    .card {{background: white; border-radius: 18px; padding: {padding}; box-shadow: 0 10px 30px rgba(0,0,0,0.1); border: 1px solid #c8e6c9; margin: 20px 0;}}
    .info-box {{background: linear-gradient(135deg, #E8F5E8, #C8E6C9); border-left: 10px solid #4CAF50; border-radius: 15px; padding: 25px; margin: 30px 0; font-size: 1.15rem; line-height: 1.8;}}
    .error-box {{background: #FFEBEE; border-left: 8px solid #D32F2F; padding: 15px; border-radius: 10px; margin: 10px 0;}}
    .stButton>button {{background: #4CAF50; color: white; font-weight: bold; border-radius: 15px; height: 55px; width: 100%;}}
    .stButton>button[kind="secondary"] {{background: #d32f2f !important;}}
    h1 {{color: #1B5E20; font-size: {header_size}; text-align: center;}}
    .header-bg {{
        background: linear-gradient(rgba(0,0,0.65), rgba(0,0,0,0.65)),
                    url('https://imagine-public.x.ai/imagine-public/images/f0a77a24-6d97-4af7-919f-7a43a07ddff1.png?cache=1');
        background-size: cover; background-position: center; border-radius: 30px;
        padding: 70px 20px; margin: 15px 0 35px 0;
        box-shadow: 0 25px 60px rgba(0,0,0,0.5);
    }}
    .restore-box {{background: #FFEBEE; border: 4px dashed #D32F2F; border-radius: 20px; padding: 30px; margin: 30px 0;}}
</style>
""", unsafe_allow_html=True)

# =============================================
# FOLDER + DATABASE + ERROR LOG TABLE
# =============================================
for folder in ["uploads", "thumbnails", "backup_temp"]:
    os.makedirs(folder, exist_ok=True)

DB_NAME = "fama_standards.db"
CATEGORIES = ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"]

ADMIN_CREDENTIALS = {
    "admin": hashlib.sha256("fama2025".encode()).hexdigest(),
    "pengarah": hashlib.sha256("fama123".encode()).hexdigest()
}

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, category TEXT,
        file_name TEXT, file_path TEXT, thumbnail_path TEXT,
        upload_date TEXT, uploaded_by TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, sender TEXT, message TEXT,
        timestamp TEXT, is_admin INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS site_info (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        welcome_text TEXT DEFAULT 'Selamat Datang ke Sistem Rujukan Standard FAMA',
        update_info TEXT DEFAULT 'Semua standard komoditi telah dikemaskini sehingga Disember 2025')""")
    # TABLE ERROR LOG BARU
    c.execute("""CREATE TABLE IF NOT EXISTS error_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        error_type TEXT,
        error_message TEXT,
        location TEXT,
        user_info TEXT
    )""")
    c.execute("INSERT OR IGNORE INTO site_info (id) VALUES (1)")
    conn.commit()
    conn.close()
init_db()

# =============================================
# FUNGSI ERROR LOGGING
# =============================================
def log_error(error_type, error_message, location="", user_info="Unknown"):
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.execute("""INSERT INTO error_logs 
                        (timestamp, error_type, error_message, location, user_info) 
                        VALUES (?,?,?,?,?)""",
                     (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                      error_type, str(error_message)[:500], location, str(user_info)[:100]))
        conn.commit()
        conn.close()
    except:
        pass

def get_error_logs():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM error_logs ORDER BY id DESC LIMIT 200")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def clear_error_logs():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM error_logs")
    conn.commit()
    conn.close()

# =============================================
# FUNGSI ASAS LAIN
# =============================================
def save_thumbnail(file_obj):
    if not file_obj: return None
    try:
        img = Image.open(file_obj).convert("RGB")
        img.thumbnail((400, 600))
        path = f"thumbnails/thumb_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
        img.save(path, "JPEG", quality=95)
        return path
    except Exception as e:
        log_error("THUMBNAIL_FAILED", str(e), "save_thumbnail()")
        return None

def get_docs():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM documents ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_doc_by_id(doc_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

@st.cache_data(ttl=10)
def get_chat_messages():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM chat_messages ORDER BY timestamp ASC")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_chat_message(sender, message, is_admin=False):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO chat_messages (sender, message, timestamp, is_admin) VALUES (?,?,?,?)",
                 (sender, message, datetime.now().strftime("%Y-%m-%d %H:%M"), int(is_admin)))
    conn.commit()
    conn.close()
    st.cache_data.clear()

def clear_all_chat():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM chat_messages")
    conn.commit()
    conn.close()
    st.cache_data.clear()

def get_site_info():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT welcome_text, update_info FROM site_info WHERE id = 1")
    row = c.fetchone()
    conn.close()
    return {"welcome": row[0] if row else "Selamat Datang", "update": row[1] if row else "Tiada maklumat"}

def update_site_info(welcome, update):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE site_info SET welcome_text = ?, update_info = ? WHERE id = 1", (welcome, update))
    conn.commit()
    conn.close()

# =============================================
# SIDEBAR + QR DIRECT
# =============================================
query_params = st.experimental_get_query_params()
direct_doc_id = query_params.get("doc", [None])[0]

with st.sidebar:
    st.markdown("<div style='text-align:center;padding:20px 0;'><img src='https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png' width=110><h3 style='color:white;margin:10px 0;font-weight:900;'>FAMA STANDARD</h3></div>", unsafe_allow_html=True)
    st.markdown("---")
    page = st.selectbox("Menu", ["Halaman Utama", "Papar QR Code", "Admin Panel"], label_visibility="collapsed")
    st.markdown("---")
    st.markdown("### Hubungi Admin FAMA")
    for msg in get_chat_messages()[-8:]:
        if msg['is_admin']:
            st.markdown(f'<div style="background:#E8F5E8;border-radius:12px;padding:10px;margin:6px 0;text-align:right;border-left:5px solid #4CAF50;"><small><b>Admin</b> • {msg["timestamp"][-5:]}</small><br>{msg["message"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="background:#4CAF50;color:white;border-radius:12px;padding:10px;margin:6px 0;"><small><b>{msg["sender"]}</b> • {msg["timestamp"][-5:]}</small><br>{msg["message"]}</div>', unsafe_allow_html=True)
    with st.form("chat_form", clear_on_submit=True):
        nama = st.text_input("Nama Anda")
        pesan = st.text_area("Mesej", height=80)
        if st.form_submit_button("Hantar"):
            if nama.strip() and pesan.strip():
                add_chat_message(nama.strip(), pesan.strip())
                st.success("Dihantar!")
                st.rerun()

# =============================================
# DIRECT QR ACCESS
# =============================================
if direct_doc_id and page != "Admin Panel":
    try:
        doc = get_doc_by_id(int(direct_doc_id))
        if doc:
            st.markdown("<div class='direct-card'><h1>QR CODE BERJAYA!</h1><p>Standard dibuka secara langsung</p></div>", unsafe_allow_html=True)
            c1, c2 = st.columns([1, 2] if device != "mobile" else [1, 1])
            with c1:
                img = doc['thumbnail_path'] if doc['thumbnail_path'] and os.path.exists(doc['thumbnail_path']) else "https://via.placeholder.com/400x600/4CAF50/white?text=FAMA"
                st.image(img, use_container_width=True)
            with c2:
                st.markdown(f"<h2 style='color:#1B5E20;margin-top:0;'>{doc['title']}</h2>", unsafe_allow_html=True)
                st.write(f"**Kategori:** {doc['category']} • **ID:** {doc['id']}")
                if os.path.exists(doc['file_path']):
                    with open(doc['file_path'], "rb") as f:
                        st.download_button("MUAT TURUN PDF", f.read(), doc['file_name'], type="primary", use_container_width=True)
            st.stop()
        else:
            log_error("QR_DOC_NOT_FOUND", f"ID: {direct_doc_id}", "QR Direct", "Pengguna Luar")
            st.error("Standard tidak dijumpai atau telah dipadam.")
    except Exception as e:
        log_error("QR_DIRECT_CRASH", str(e), "QR Direct Access", "Pengguna Luar")
        st.error("Ralat akses QR. Admin telah dimaklumkan.")

# =============================================
# HALAMAN UTAMA
# =============================================
if page == "Halaman Utama":
    info = get_site_info()
    st.markdown("<div class='header-bg'><h1 style='color:white;margin:0;'>RUJUKAN STANDARD FAMA</h1><p style='color:white;font-size:1.8rem;margin:15px 0 0 0;'>Keluaran Hasil Pertanian Malaysia</p></div>", unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class='info-box'>
        <h2 style='text-align:center;margin:0 0 15px 0;color:#1B5E20;'>Maklumat Terkini</h2>
        <p style='text-align:center;font-size:1.3rem;font-weight:bold;color:#1B5E20;'>{{info['welcome']}}</p>
        <p style='text-align:center;color:#2E7D32;font-style:italic;margin-top:15px;'>{{info['update']}}</p>
    </div>
    """, unsafe_allow_html=True)

    # statistik + senarai standard (sama seperti sebelum ni)
    # ... [kod statistik & senarai — tak ubah, jimat space]

# =============================================
# ADMIN PANEL — DENGAN TAB LOG ERROR!
# =============================================
else:
    if not st.session_state.get("logged_in"):
        st.markdown("<h1>ADMIN PANEL FAMA</h1>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1: user = st.text_input("Username")
        with c2: pwd = st.text_input("Password", type="password")
        if st.button("LOG MASUK", type="primary"):
            if user in ADMIN_CREDENTIALS and hashlib.sha256(pwd.encode()).hexdigest() == ADMIN_CREDENTIALS[user]:
                st.session_state.logged_in = True
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Salah!")
        st.stop()

    st.success(f"Selamat Datang, {st.session_state.user.upper()}!")
    st.balloons()

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Tambah Standard",
        "Edit & Padam",
        "Chat + Backup",
        "Edit Info Halaman Utama",
        "LOG ERROR & MONITORING"
    ])

    # TAB 1-4 SAMA MACAM SEBELUM NI (aku pendekkan)

    with tab5:
        st.markdown("### LOG ERROR & MONITORING SISTEM")
        st.markdown("*Semua ralat automatik direkod. Anda adalah Tuhan di sini.*", unsafe_allow_html=True)
        
        logs = get_error_logs()
        
        if not logs:
            st.success("TIADA ERROR! Sistem FAMA berjalan dengan sempurna!")
            st.balloons()
        else:
            st.error(f"Dikesan **{len(logs)}** ralat dalam sistem")
            for log in logs:
                with st.expander(f"{log['timestamp']} — {log['error_type']}"):
                    st.markdown(f"<div class='error-box'><strong>Ralat:</strong> {log['error_message']}</div>", unsafe_allow_html=True)
                    st.caption(f"Lokasi: {log['location'] or 'Tiada'} | Dilaporkan oleh: {log['user_info']}")
                    st.code(f"ID: {log['id']} | Jenis: {log['error_type']}")

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("PADAM SEMUA LOG", type="secondary"):
                if st.session_state.get("confirm_clear_log"):
                    clear_error_logs()
                    st.success("Log dipadam!")
                    st.rerun()
                else:
                    st.session_state.confirm_clear_log = True
                    st.warning("Tekan sekali lagi untuk sah")
        with col2:
            log_txt = "\n".join([f"{l['timestamp']} | {l['error_type']} | {l['location']} | {l['error_message']}" for l in logs])
            st.download_button("Download Log TXT", log_txt, "FAMA_ERROR_LOG.txt", "text/plain")
        with col3:
            st.write(f"**Jumlah Log:** {len(logs)}")

        if st.session_state.get("confirm_clear_log"):
            if st.button("BATAL PADAM"):
                del st.session_state.confirm_clear_log
                st.rerun()

    if st.button("Log Keluar"):
        st.session_state.clear()
        st.rerun()

st.caption("© Rujukan Standard FAMA • Created on 2025 by Santana Techno")
