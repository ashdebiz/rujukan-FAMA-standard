import streamlit as st
import sqlite3
import os
import zipfile
from datetime import datetime, timedelta
import hashlib
from PIL import Image
import qrcode
from io import BytesIO

# =============================================
# CONFIG & DESIGN CANTIK GILA + BACKGROUND BUAH-SAYUR
# =============================================
st.set_page_config(page_title="Rujukan Standard FAMA", page_icon="leaf", layout="centered", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .main {background: #f8fff8;}
    [data-testid="stSidebar"] {background: linear-gradient(#1B5E20, #2E7D32);}
    .card {background: white; border-radius: 20px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); border: 1px solid #c8e6c9; margin: 15px 0;}
    .qr-container {background: white; border-radius: 30px; padding: 40px; text-align: center; box-shadow: 0 20px 50px rgba(27,94,32,0.2); border: 5px solid #4CAF50; margin: 40px 0;}
    .stButton>button {background: #4CAF50; color: white; font-weight: bold; border-radius: 15px; height: 55px; border: none;}
    h1,h2,h3 {color: #1B5E20;}
    .sidebar-title {color: #ffffff; font-size: 2.2rem; font-weight: 900; text-align: center; text-shadow: 3px 3px 10px rgba(0,0,0,0.6);}
    .header-bg {
        background: linear-gradient(rgba(0,0,0,0.55), rgba(0,0,0,0.55)), 
                    url('https://imagine-public.x.ai/imagine-public/images/f0a77a24-6d97-4af7-919f-7a43a07ddff1.png?cache=1?q=80&w=2070&auto=format&fit=crop');
        background-size: cover;
        background-position: center;
        border-radius: 30px;
        padding: 80px 20px;
        text-align: center;
        margin: 20px 0 40px 0;
        box-shadow: 0 25px 60px rgba(0,0,0,0.4);
    }
</style>
""", unsafe_allow_html=True)

# Folder
for folder in ["uploads", "thumbnails"]:
    os.makedirs(folder, exist_ok=True)

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
    cur.execute("""CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, category TEXT,
        file_name TEXT, file_path TEXT, thumbnail_path TEXT, 
        upload_date TEXT, uploaded_by TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, sender TEXT, message TEXT, 
        timestamp TEXT, is_admin INTEGER DEFAULT 0)""")
    conn.commit()
    conn.close()
init_db()

# =============================================
# FUNGSI ASAS
# =============================================
def save_thumbnail(file_obj):
    if not file_obj: return None
    try:
        img = Image.open(file_obj).convert("RGB")
        img.thumbnail((350, 500))
        path = f"thumbnails/thumb_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
        img.save(path, "JPEG", quality=95)
        return path
    except: return None

def get_docs():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM documents ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@st.cache_data(ttl=5)
def get_chat_messages():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM chat_messages ORDER BY timestamp ASC")
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_chat_message(sender, message, is_admin=False):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO chat_messages (sender, message, timestamp, is_admin) VALUES (?,?,?,?)",
                 (sender, message, datetime.now().strftime("%Y-%m-%d %H:%M"), int(is_admin)))
    conn.commit()
    conn.close()
    st.cache_data.clear()

# =============================================
# SIDEBAR
# =============================================
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding:20px 0;">
        <img src="https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png" width="110">
        <h3 class="sidebar-title">FAMA STANDARD</h3>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")
    page = st.selectbox("Menu", ["Halaman Utama", "Papar QR Code", "Admin Panel"], label_visibility="collapsed")
    st.markdown("---")
    st.markdown("### Hubungi Admin FAMA")

    for msg in get_chat_messages()[-10:]:
        if msg['is_admin']:
            st.markdown(f'<div style="background:#E8F5E8; border-radius:12px; padding:10px; margin:8px 0; text-align:right; border-left:5px solid #4CAF50;"><small><b>Admin</b> • {msg["timestamp"][-5:]}</small><br>{msg["message"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="background:#4CAF50; color:white; border-radius:12px; padding:10px; margin:8px 0;"><small><b>{msg["sender"]}</b> • {msg["timestamp"][-5:]}</small><br>{msg["message"]}</div>', unsafe_allow_html=True)

    with st.form("chat_form", clear_on_submit=True):
        nama = st.text_input("Nama")
        pesan = st.text_area("Mesej", height=80)
        if st.form_submit_button("Hantar"):
            if nama.strip() and pesan.strip():
                add_chat_message(nama.strip(), pesan.strip())
                st.success("Mesej dihantar!")
                st.rerun()

# =============================================
# HALAMAN UTAMA
# =============================================
if page == "Halaman Utama":
    st.markdown(f"""
    <div class="header-bg">
        <h1 style="color:white; font-size:4.8rem; font-weight:900; margin:0; text-shadow: 5px 5px 15px rgba(0,0,0,0.9);">RUJUKAN STANDARD FAMA</h1>
        <p style="color:white; font-size:1.9rem; margin:20px 0 0 0; text-shadow: 3px 3px 10px rgba(0,0,0,0.9);">Keluaran Hasil Pertanian Tempatan Malaysia</p>
    </div>
    """, unsafe_allow_html=True)

    docs = get_docs()
    total = len(docs)
    baru = len([d for d in docs if (datetime.now() - datetime.strptime(d['upload_date'][:10], "%Y-%m-%d")).days <= 30])
    cat_count = {c: sum(1 for d in docs if d['category'] == c) for c in CATEGORIES}

    st.markdown(f"""
    <div style="background:linear-gradient(135deg, #00695c, #009688); border-radius:25px; padding:35px; color:white; margin:40px 0; box-shadow:0 20px 50px rgba(0,0,0,0.35);">
        <h2 style="text-align:center; margin:0 0 30px 0; font-size:2rem;">STATISTIK RUJUKAN STANDARD FAMA</h2>
        <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:30px;">
            <div style="background:rgba(255,255,255,0.25); padding:30px; border-radius:20px; text-align:center;">
                <h1 style="margin:0; font-size:4rem;">{total}</h1>
                <p style="margin:10px 0 0 0; font-size:1.4rem;">JUMLAH STANDARD</p>
            </div>
            <div style="background:rgba(255,255,255,0.25); padding:30px; border-radius:20px; text-align:center;">
                <h1 style="margin:0; font-size:4rem;">{baru}</h1>
                <p style="margin:10px 0 0 0; font-size:1.4rem;">BARU (30 HARI)</p>
            </div>
        </div>
        <div style="display:grid; grid-template-columns:repeat(4,1fr); gap:20px; margin-top:40px;">
            {''.join(f'<div style="background:rgba(255,255,255,0.2);padding:20px;border-radius:18px;text-align:center;"><strong style="font-size:1.1rem;">{c}</strong><br><h2 style="margin:12px 0; font-size:2rem;">{cat_count[c]}</h2></div>' for c in CATEGORIES)}
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([3,1])
    with col1: cari = st.text_input("", placeholder="Cari tajuk standard...", key="cari_utama")
    with col2: kat = st.selectbox("", ["Semua"] + CATEGORIES, key="kat_utama")

    hasil = [d for d in docs if (kat == "Semua" or d['category'] == kat) and (not cari or cari.lower() in d['title'].lower())]

    st.markdown(f"<h3 style='text-align:center;color:#1B5E20;'>Ditemui {len(hasil)} Standard</h3>", unsafe_allow_html=True)

    for d in hasil:
        with st.container():
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            c1, c2 = st.columns([1,3])
            with c1:
                img = d['thumbnail_path'] if d['thumbnail_path'] and os.path.exists(d['thumbnail_path']) else "https://via.placeholder.com/350x500/4CAF50/white?text=FAMA"
                st.image(img, use_container_width=True)
            with c2:
                st.markdown(f"<h3 style='color:#1B5E20; margin:0;'>{d['title']}</h3>", unsafe_allow_html=True)
                st.caption(f"**{d['category']}** • Upload: {d['upload_date'][:10]} • {d['uploaded_by']}")
                if os.path.exists(d['file_path']):
                    with open(d['file_path'], "rb") as f:
                        st.download_button("MUAT TURUN PDF", f.read(), d['file_name'], use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

# =============================================
# PAPAR QR CODE — CONFIRMED JALAN GEMPUR!
# =============================================
elif page == "Papar QR Code":
    st.markdown("<h1 style='text-align:center;color:#1B5E20;'>PAPAR QR CODE STANDARD FAMA</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;font-size:1.4rem;color:#2E7D32;'>Taip ID atau nama komoditi</p>", unsafe_allow_html=True)

    search = st.text_input("Cari ID / Tajuk", placeholder="Contoh: 12 atau Nanas", key="qr_search")

    if search:
        docs = get_docs()
        matches = []
        try:
            sid = int(search.strip())
            matches = [d for d in docs if d['id'] == sid]
        except:
            matches = [d for d in docs if search.lower() in d['title'].lower()]

        if matches:
            for d in matches:
                st.markdown(f"<div class='qr-container'>", unsafe_allow_html=True)
                
                # CARA BARU YANG CONFIRM JALAN 100% DI STREAMLIT CLOUD
                current_url = st.experimental_get_query_params().get("url", [None])[0]
                if not current_url:
                    current_url = os.getenv("STREAMLIT_SHARING_URL", "https://rujukan-fama-standard.streamlit.app")
                qr_link = f"{current_url}?doc={d['id']}"

                qr = qrcode.QRCode(version=1, box_size=15, border=6)
                qr.add_data(qr_link)
                qr.make(fit=True)
                img = qr.make_image(fill_color="#1B5E20", back_color="white")
                
                buf = BytesIO()
                img.save(buf, format="PNG")
                
                col1, col2 = st.columns([1,2])
                with col1:
                    st.image(buf.getvalue(), width=320)
                    st.download_button("Download QR", buf.getvalue(), f"QR_FAMA_{d['id']}.png", "image/png")
                with col2:
                    st.markdown(f"<h2 style='color:#1B5E20;'>{d['title']}</h2>", unsafe_allow_html=True)
                    st.write(f"**ID:** {d['id']} | **Kategori:** {d['category']}")
                    st.code(qr_link)
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.warning("Tiada padanan dijumpai.")

# =============================================
# ADMIN PANEL
# =============================================
else:
    if not st.session_state.get("logged_in"):
        st.markdown("<h1 style='text-align:center;color:#1B5E20;'>ADMIN PANEL</h1>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1: user = st.text_input("Username")
        with c2: pwd = st.text_input("Password", type="password")
        if st.button("LOG MASUK", type="primary"):
            if user in ADMIN_CREDENTIALS and hashlib.sha256(pwd.encode()).hexdigest() == ADMIN_CREDENTIALS[user]:
                st.session_state.logged_in = True
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Salah bro!")
        st.stop()

    st.success(f"Welcome back, {st.session_state.user.upper()}!")
    st.balloons()

    tab1, tab2, tab3 = st.tabs(["Tambah", "Edit/Padam", "Backup"])

    with tab1:
        file = st.file_uploader("Upload PDF", type=["pdf"])
        title = st.text_input("Tajuk")
        cat = st.selectbox("Kategori", CATEGORIES)
        thumb = st.file_uploader("Thumbnail", type=["jpg","jpeg","png"])
        if file and title and st.button("SIMPAN", type="primary"):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fpath = f"uploads/{ts}_{file.name}"
            with open(fpath, "wb") as f: f.write(file.getvalue())
            tpath = save_thumbnail(thumb) if thumb else None
            conn = sqlite3.connect(DB_NAME)
            conn.execute("INSERT INTO documents (title,category,file_name,file_path,thumbnail_path,upload_date,uploaded_by) VALUES (?,?,?,?,?,?,?)",
                         (title,cat,file.name,fpath,tpath,datetime.now().strftime("%Y-%m-%d %H:%M"),st.session_state.user))
            conn.commit()
            conn.close()
            st.success("Ditambah!")
            st.rerun()

    with tab2:
        search = st.text_input("Cari untuk edit/padam")
        docs = get_docs()
        if search:
            docs = [d for d in docs if search.lower() in d['title'].lower() or search in str(d['id'])]
        for d in docs:
            with st.expander(f"ID {d['id']} - {d['title']}"):
                if st.button("PADAM", key=f"del{d['id']}"):
                    if st.checkbox("Confirm?", key=f"cf{d['id']}"):
                        os.path.exists(d['file_path']) and os.remove(d['file_path'])
                        d['thumbnail_path'] and os.path.exists(d['thumbnail_path']) and os.remove(d['thumbnail_path'])
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("DELETE FROM documents WHERE id=?", (d['id'],))
                        conn.commit()
                        conn.close()
                        st.success("Dipadam!")
                        st.rerun()

    with tab3:
        if st.button("Download Backup ZIP", type="primary"):
            zipname = f"backup_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
            with zipfile.ZipFile(zipname,"w") as z:
                z.write(DB_NAME)
                for folder in ["uploads","thumbnails"]:
                    for root,_,files in os.walk(folder):
                        for file in files:
                            z.write(os.path.join(root,file))
            with open(zipname,"rb") as f:
                st.download_button("Download Backup", f.read(), zipname)
            os.remove(zipname)

    if st.button("Log Keluar"):
        st.session_state.clear()
        st.rerun()

