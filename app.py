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
# AUTO RESPONSIVE + CONFIG
# =============================================
st.set_page_config(
    page_title="Rujukan Standard FAMA",
    page_icon="leaf",
    layout="centered",
    initial_sidebar_state="auto"  # "auto" = collapsed di phone, expanded di desktop
)

# Auto detect device & adjust design
def get_device_type():
    user_agent = st.get_option("deprecation.showPyplotGlobalUse")
    try:
        import streamlit as st
        ua = st.experimental_get_query_params().get("user_agent", [""])[0]
        if not ua:
            # Fallback: gunakan lebar screen
            if st.get_option("client.width") < 768:
                return "mobile"
            elif st.get_option("client.width") < 1200:
                return "tablet"
            else:
                return "desktop"
    except:
        pass
    return "desktop"

device = "mobile"  # default
try:
    width = st._config.get_option("client.width")
    device = "mobile" if width < 768 else "tablet" if width < 1200 else "desktop"
except:
    device = "desktop"

# Dynamic styling berdasarkan device
if device == "mobile":
    padding_top = "20px"
    header_font = "3.5rem"
    card_padding = "15px"
    qr_size = 280
else:
    padding_top = "50px"
    header_font = "5rem"
    card_padding = "25px"
    qr_size = 350

st.markdown(f"""
<style>
    .main {{background: #f8fff8; padding-top: {padding_top};}}
    [data-testid="stSidebar"] {{background: linear-gradient(#1B5E20, #2E7D32);}}
    .card {{background: white; border-radius: 20px; padding: {card_padding}; box-shadow: 0 12px 35px rgba(0,0,0,0.12); border: 1px solid #c8e6c9; margin: 20px 0;}}
    .info-box {{background: linear-gradient(135deg, #E8F5E8, #C8E6C9); border-left: 8px solid #4CAF50; border-radius: 15px; padding: 20px; margin: 30px 0; font-size: 1.1rem; line-height: 1.8;}}
    .qr-container {{background: white; border-radius: 30px; padding: 40px; text-align: center; box-shadow: 0 25px 60px rgba(27,94,32,0.25); border: 6px solid #4CAF50; margin: 40px 0;}}
    .direct-card {{background: linear-gradient(135deg, #E8F5E8, #C8E6C9); border-radius: 25px; padding: 25px; border: 4px solid #4CAF50; margin: 20px 0;}}
    .stButton>button {{background: #4CAF50; color: white; font-weight: bold; border-radius: 15px; height: 55px; border: none; font-size:1rem;}}
    .stButton>button[kind="secondary"] {{background: #d32f2f !important;}}
    h1 {{color: #1B5E20; font-size: {header_font};}}
    h2,h3 {{color: #1B5E20;}}
    .header-bg {{
        background: linear-gradient(rgba(0,0,0,0.6), rgba(0,0,0,0.6)),
                    url('https://imagine-public.x.ai/imagine-public/images/f0a77a24-6d97-4af7-919f-7a43a07ddff1.png?cache=1?q=80&w=2070&auto=format&fit=crop');
        background-size: cover; background-position: center; border-radius: 35px;
        padding: 80px 20px; text-align: center; margin: 20px 0 40px 0;
        box-shadow: 0 30px 70px rgba(0,0,0,0.45);
    }}
    .stat-box {{background: rgba(255,255,255,0.3); padding: 25px; border-radius: 20px; text-align: center; backdrop-filter: blur(5px);}}
    .restore-box {{background: #FFEBEE; border: 4px dashed #D32F2F; border-radius: 20px; padding: 30px; text-align: center; margin: 30px 0;}}
</style>
""", unsafe_allow_html=True)

# =============================================
# DATABASE + INFO TABLE BARU
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
    # TABLE BARU: INFO UNTUK HALAMAN UTAMA
    c.execute("""CREATE TABLE IF NOT EXISTS site_info (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        welcome_text TEXT DEFAULT 'Selamat Datang ke Sistem Rujukan Standard FAMA',
        update_info TEXT DEFAULT 'Semua standard komoditi telah dikemaskini sehingga Disember 2025')""")
    c.execute("INSERT OR IGNORE INTO site_info (id) VALUES (1)")
    conn.commit()
    conn.close()
init_db()

# Fungsi untuk ambil info
def get_site_info():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT welcome_text, update_info FROM site_info WHERE id = 1")
    row = c.fetchone()
    conn.close()
    return {"welcome": row[0] if row else "Selamat Datang", "update": row[1] if row else "Tiada maklumat kemaskini"}

# Fungsi untuk update info
def update_site_info(welcome, update):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE site_info SET welcome_text = ?, update_info = ? WHERE id = 1", (welcome, update))
    conn.commit()
    conn.close()

# (semua fungsi lain — save_thumbnail, get_docs, dll — sama macam sebelum ni)
# ... [sila letak semua fungsi dari code lama kau kat sini — aku pendekkan supaya nampak bersih]

# =============================================
# SIDEBAR + QR DIRECT
# =============================================
query_params = st.experimental_get_query_params()
direct_doc_id = query_params.get("doc", [None])[0]

with st.sidebar:
    st.markdown("<div style='text-align:center;padding:25px 0;'><img src='https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png' width=120><h3 style='color:white;margin:10px 0;font-weight:900;'>FAMA STANDARD</h3></div>", unsafe_allow_html=True)
    st.markdown("---")
    page = st.selectbox("Menu", ["Halaman Utama", "Papar QR Code", "Admin Panel"], label_visibility="collapsed")
    st.markdown("---")
    st.markdown("### Hubungi Admin FAMA")
    # ... [chat code sama]

# =============================================
# HALAMAN UTAMA — DENGAN RUANGAN INFO BOLEH EDIT
# =============================================
if page == "Halaman Utama":
    info = get_site_info()
    
    st.markdown("<div class='header-bg'><h1 style='color:white;text-align:center;'>RUJUKAN STANDARD FAMA</h1></div>", unsafe_allow_html=True)
    
    # RUANGAN INFO — CANTIK & BOLEH EDIT OLEH ADMIN SAHAJA
    st.markdown(f"""
    <div class='info-box'>
        <h2 style='color:#1B5E20;margin-top:0;text-align:center;'>Maklumat Terkini</h2>
        <p style='font-size:1.3rem;text-align:center;'><strong>{info['welcome']}</strong></p>
        <p style='font-style:italic;color:#2E7D32;'>{info['update']}</p>
    </div>
    """, unsafe_allow_html=True)

    # ... [statistik + senarai standard — sama macam sebelum ni]

# =============================================
# ADMIN PANEL — TAMBAH TAB "Edit Info Halaman Utama"
# =============================================
else:  # Admin Panel
    if not st.session_state.get("logged_in"):
        # login code sama
        st.stop()

    st.success(f"Selamat Datang, {st.session_state.user.upper()}!")
    st.balloons()

    tab1, tab2, tab3, tab4 = st.tabs(["Tambah Standard", "Edit & Padam", "Chat + Backup", "Edit Info Halaman Utama"])

    # ... tab1, tab2, tab3 — sama

    with tab4:
        st.markdown("### Edit Maklumat Halaman Utama")
        current = get_site_info()
        with st.form("edit_info_form"):
            welcome = st.text_area("Teks Selamat Datang", value=current['welcome'], height=100)
            update = st.text_area("Maklumat Kemaskini", value=current['update'], height=100)
            if st.form_submit_button("SIMPAN PERUBAHAN", type="primary"):
                update_site_info(welcome, update)
                st.success("Maklumat halaman utama berjaya dikemaskini!")
                st.balloons()
                st.rerun()

    if st.button("Log Keluar"):
        st.session_state.clear()
        st.rerun()

st.caption("© Rujukan Standard FAMA • Auto Responsive • Info Boleh Edit • Backup & Restore • 2025")
