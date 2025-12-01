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
# PAGE CONFIG + RESPONSIVE CSS (NO ERROR!)
# =============================================
st.set_page_config(
    page_title="Rujukan Standard FAMA",
    page_icon="leaf",
    layout="centered",
    initial_sidebar_state="auto"
)

st.markdown("""
<style>
    .main {background: #f8fff8; padding: 10px;}
    [data-testid="stSidebar"] {background: linear-gradient(#1B5E20, #2E7D32);}
    .card {background: white; border-radius: 18px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); border: 1px solid #c8e6c9; margin: 20px 0;}
    .info-box {background: linear-gradient(135deg, #E8F5E8, #C8E6C9); border-left: 10px solid #4CAF50; border-radius: 15px; padding: 25px; margin: 30px 0; font-size: 1.15rem; line-height: 1.8;}
    .error-box {background: #FFEBEE; border-left: 8px solid #D32F2F; padding: 15px; border-radius: 10px; margin: 10px 0;}
    .direct-card {background: linear-gradient(135deg, #E8F5E8, #C8E6C9); border-radius: 25px; padding: 25px; border: 5px solid #4CAF50; margin: 20px 0; text-align: center;}
    .stButton>button {background: #4CAF50; color: white; font-weight: bold; border-radius: 15px; height: 55px; width: 100%; font-size:1rem;}
    .stButton>button[kind="secondary"] {background: #d32f2f !important;}
    h1 {color: #1B5E20; text-align: center; font-size: clamp(2.8rem, 8vw, 5rem); margin: 0;}
    h2, h3 {color: #1B5E20;}
    .header-bg {
        background: linear-gradient(rgba(0,0,0,0.65), rgba(0,0,0,0.65)),
                    url('https://imagine-public.x.ai/imagine-public/images/f0a77a24-6d97-4af7-919f-7a43a07ddff1.png?cache=1');
        background-size: cover; background-position: center; border-radius: 30px;
        padding: 70px 20px; margin: 15px 0 40px 0;
        box-shadow: 0 25px 60px rgba(0,0,0,0.5);
    }
    .stat-box {background: rgba(255,255,255,0.3); padding: 20px; border-radius: 18px; text-align: center; backdrop-filter: blur(8px);}
    .restore-box {background: #FFEBEE; border: 4px dashed #D32F2F; border-radius: 20px; padding: 30px; margin: 30px 0;}
    @media (max-width: 768px) {
        .card {padding: 15px;}
        .direct-card {padding: 20px;}
    }
</style>
""", unsafe_allow_html=True)

# =============================================
# SETUP FOLDER & DATABASE
# =============================================
for folder in ["uploads", "thumbnails", "backup_temp"]:
    os.makedirs(folder, exist_ok=True)

DB_NAME = "fama_standards.db"
CATEGORIES = ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"]

# GANTI PASSWORD NI KALAU NAK LEBIH SELAMAT
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
        welcome_text TEXT, update_info TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS error_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT, error_type TEXT, error_message TEXT,
        location TEXT, user_info TEXT)""")
    c.execute("INSERT OR IGNORE INTO site_info (id, welcome_text, update_info) VALUES (1, 'Selamat Datang ke Sistem Rujukan Standard FAMA', 'Semua standard telah dikemaskini sehingga Disember 2025')")
    conn.commit()
    conn.close()
init_db()

# =============================================
# ERROR LOGGING SYSTEM
# =============================================
def log_error(error_type, message, location="", user="Unknown"):
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.execute("INSERT INTO error_logs (timestamp,error_type,error_message,location,user_info) VALUES (?,?,?,?,?)",
                     (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), error_type, str(message)[:500], location, str(user)[:100]))
        conn.commit()
        conn.close()
    except:
        pass

def get_error_logs():
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM error_logs ORDER BY id DESC LIMIT 200")
        rows = c.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except:
        return []

def clear_error_logs():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM error_logs")
    conn.commit()
    conn.close()

# =============================================
# HELPER FUNCTIONS
# =============================================
def save_thumbnail(file):
    if not file: return None
    try:
        img = Image.open(file).convert("RGB")
        img.thumbnail((400, 600))
        path = f"thumbnails/thumb_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
        img.save(path, "JPEG", quality=95)
        return path
    except Exception as e:
        log_error("THUMBNAIL_FAIL", str(e))
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
    conn.execute("INSERT INTO chat_messages (sender,message,timestamp,is_admin) VALUES (?,?,?,?)",
                 (sender, message, datetime.now().strftime("%Y-%m-%d %H:%M"), int(is_admin)))
    conn.commit()
    conn.close()
    st.cache_data.clear()

def get_site_info():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT welcome_text, update_info FROM site_info WHERE id = 1")
    row = c.fetchone()
    conn.close()
    return {"welcome": row[0], "update": row[1]} if row else {"welcome": "Selamat Datang", "update": ""}

def update_site_info(welcome, update):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE site_info SET welcome_text=?, update_info=? WHERE id=1", (welcome, update))
    conn.commit()
    conn.close()

# =============================================
# SIDEBAR & DIRECT QR
# =============================================
query_params = st.experimental_get_query_params()
direct_doc_id = query_params.get("doc", [None])[0]

with st.sidebar:
    st.markdown("<div style='text-align:center;padding:20px 0;'><img src='https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png' width=110><h3 style='color:white;margin:10px 0;font-weight:900;'>FAMA STANDARD</h3></div>", unsafe_allow_html=True)
    st.markdown("---")
    page = st.selectbox("Menu", ["Halaman Utama", "Papar QR Code", "Admin Panel"], label_visibility="collapsed")
    st.markdown("---")
    st.markdown("### Hubungi Admin")
    for msg in get_chat_messages()[-8:]:
        if msg['is_admin']:
            st.markdown(f'<div style="background:#E8F5E8;border-radius:12px;padding:10px;margin:6px 0;text-align:right;"><small><b>Admin</b> • {msg["timestamp"][-5:]}</small><br>{msg["message"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="background:#4CAF50;color:white;border-radius:12px;padding:10px;margin:6px 0;"><small><b>{msg["sender"]}</b> • {msg["timestamp"][-5:]}</small><br>{msg["message"]}</div>', unsafe_allow_html=True)
    with st.form("chat_form", clear_on_submit=True):
        nama = st.text_input("Nama Anda")
        pesan = st.text_area("Mesej", height=80)
        if st.form_submit_button("Hantar") and nama.strip() and pesan.strip():
            add_chat_message(nama.strip(), pesan.strip())
            st.success("Berjaya dihantar!")

# =============================================
# DIRECT QR ACCESS
# =============================================
if direct_doc_id and page != "Admin Panel":
    try:
        doc = get_doc_by_id(int(direct_doc_id))
        if doc:
            st.markdown("<div class='direct-card'><h1>QR CODE BERJAYA DIBUKA!</h1><p>Standard komoditi dimuat secara langsung</p></div>", unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            with col1:
                img = doc['thumbnail_path'] if doc['thumbnail_path'] and os.path.exists(doc['thumbnail_path']) else "https://via.placeholder.com/400x600/4CAF50/white?text=FAMA"
                st.image(img, use_container_width=True)
            with col2:
                st.markdown(f"<h2>{doc['title']}</h2>", unsafe_allow_html=True)
                st.write(f"**Kategori:** {doc['category']} • **ID:** {doc['id']}")
                if os.path.exists(doc['file_path']):
                    with open(doc['file_path'], "rb") as f:
                        st.download_button("MUAT TURUN PDF", f.read(), doc['file_name'], "application/pdf", use_container_width=True)
            st.stop()
    except:
        st.error("Standard tidak dijumpai atau QR tidak sah.")
        log_error("QR_ACCESS_FAIL", f"ID: {direct_doc_id}")

# =============================================
# HALAMAN UTAMA
# =============================================
if page == "Halaman Utama":
    info = get_site_info()
    
    st.markdown("<div class='header-bg'><h1 style='color:white;'>RUJUKAN STANDARD FAMA</h1><p style='color:white;font-size:1.8rem;margin-top:10px;'>Keluaran Hasil Pertanian Malaysia</p></div>", unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class='info-box'>
        <h2 style='text-align:center;color:#1B5E20;'>Maklumat Terkini</h2>
        <p style='text-align:center;font-weight:bold;font-size:1.3rem;color:#1B5E20;'>{info['welcome']}</p>
        <p style='text-align:center;font-style:italic;color:#2E7D32;'>{info['update']}</p>
    </div>
    """, unsafe_allow_html=True)

    docs = get_docs()
    total = len(docs)
    baru = len([d for d in docs if (datetime.now() - datetime.strptime(d['upload_date'][:10], "%Y-%m-%d")).days <= 30])

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#00695c,#009688);border-radius:25px;padding:30px;color:white;margin:35px 0;">
        <h2 style="text-align:center;margin-bottom:30px;">STATISTIK STANDARD</h2>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:20px;">
            <div class="stat-box"><h1 style="margin:0;color:#E8F5E8;">{total}</h1><p>JUMLAH STANDARD</p></div>
            <div class="stat-box"><h1 style="margin:0;color:#C8E6C9;">{baru}</h1><p>BARU (30 HARI)</p></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([3,1])
    with col1: cari = st.text_input("", placeholder="Cari tajuk...", key="cari")
    with col2: kat = st.selectbox("", ["Semua"] + CATEGORIES, key="kat")

    hasil = [d for d in docs if (kat == "Semua" or d['category'] == kat) and (not cari or cari.lower() in d['title'].lower())]

    for d in hasil:
        with st.container():
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                img = d['thumbnail_path'] if d['thumbnail_path'] and os.path.exists(d['thumbnail_path']) else "https://via.placeholder.com/400x600/4CAF50/white?text=FAMA"
                st.image(img, use_container_width=True)
            with c2:
                st.markdown(f"<h3>{d['title']}</h3>", unsafe_allow_html=True)
                st.caption(f"**{d['category']}** • {d['upload_date'][:10]} • {d['uploaded_by']}")
                if os.path.exists(d['file_path']):
                    with open(d['file_path'], "rb") as f:
                        st.download_button("MUAT TURUN PDF", f.read(), d['file_name'], use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

# =============================================
# PAPAR QR CODE
# =============================================
elif page == "Papar QR Code":
    st.markdown("<h1>PAPAR QR CODE STANDARD</h1>", unsafe_allow_html=True)
    search = st.text_input("Cari ID atau Tajuk")
    if search.strip():
        docs = get_docs()
        matches = []
        try:
            if search.strip().isdigit():
                matches = [d for d in docs if d['id'] == int(search.strip())]
        except:
            pass
        if not matches:
            matches = [d for d in docs if search.lower() in d['title'].lower()][:10]

        for d in matches:
            link = f"https://{st.secrets.get('app_url', 'rujukan-fama-standard.streamlit.app')}?doc={d['id']}"
            qr = qrcode.QRCode(box_size=15, border=5)
            qr.add_data(link); qr.make(fit=True)
            img = qr.make_image(fill_color="#1B5E20", back_color="white")
            buf = BytesIO(); img.save(buf, "PNG")
            col1, col2 = st.columns(2)
            with col1:
                st.image(buf.getvalue(), use_container_width=True)
                st.download_button("Download QR", buf.getvalue(), f"QR_FAMA_{d['id']}.png")
            with col2:
                st.markdown(f"**{d['title']}**")
                st.code(link, language=None)

# =============================================
# ADMIN PANEL
# =============================================
else:  # Admin Panel
    if not st.session_state.get("logged_in"):
        st.markdown("<h1>ADMIN PANEL FAMA</h1>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1: username = st.text_input("Username")
        with c2: password = st.text_input("Password", type="password")
        if st.button("LOG MASUK", type="primary"):
            if username in ADMIN_CREDENTIALS and hashlib.sha256(password.encode()).hexdigest() == ADMIN_CREDENTIALS[username]:
                st.session_state.logged_in = True
                st.session_state.user = username
                st.rerun()
            else:
                st.error("Username atau password salah!")
        st.stop()

    st.success(f"Selamat Datang, {st.session_state.user.upper()}!")
    st.balloons()

    t1, t2, t3, t4, t5 = st.tabs(["Tambah", "Edit/Padam", "Chat+Backup", "Edit Info", "Log Error"])

    with t1:
        uploaded_file = st.file_uploader("Upload PDF Standard", type="pdf")
        title = st.text_input("Tajuk Standard")
        category = st.selectbox("Kategori", CATEGORIES)
        thumbnail = st.file_uploader("Thumbnail (pilihan)", type=["jpg","jpeg","png"])
        if uploaded_file and title and st.button("SIMPAN STANDARD", type="primary"):
            try:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                filepath = f"uploads/{ts}_{uploaded_file.name}"
                with open(filepath, "wb") as f:
                    f.write(uploaded_file.getvalue())
                thumb_path = save_thumbnail(thumbnail) if thumbnail else None
                conn = sqlite3.connect(DB_NAME)
                conn.execute("INSERT INTO documents (title,category,file_name,file_path,thumbnail_path,upload_date,uploaded_by) VALUES (?,?,?,?,?,?,?)",
                             (title, category, uploaded_file.name, filepath, thumb_path, datetime.now().strftime("%Y-%m-%d %H:%M"), st.session_state.user))
                conn.commit()
                conn.close()
                st.success("Standard berjaya ditambah!")
                st.rerun()
            except Exception as e:
                log_error("UPLOAD_FAIL", str(e), user=st.session_state.user)
                st.error("Gagal upload!")

    with t5:  # LOG ERROR TAB
        st.markdown("### LOG ERROR & MONITORING")
        logs = get_error_logs()
        if not logs:
            st.success("TIADA ERROR! Sistem berjalan sempurna!")
            st.balloons()
        else:
            st.error(f"Terdapat {len(logs)} error direkod")
            for log in logs:
                with st.expander(f"{log['timestamp']} — {log['error_type']}"):
                    st.markdown(f"<div class='error-box'>{log['error_message']}</div>", unsafe_allow_html=True)
                    st.caption(f"Lokasi: {log['location']} | User: {log['user_info']}")
            if st.button("PADAM SEMUA LOG", type="secondary"):
                clear_error_logs()
                st.success("Log dipadam!")
                st.rerun()

    if st.button("Log Keluar"):
        st.session_state.clear()
        st.rerun()

st.caption("© Rujukan Standard FAMA • 2025 • Powered by Santana Techno")
