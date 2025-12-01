import streamlit as st
import sqlite3
import os
import zipfile
from datetime import datetime, timedelta
import hashlib
import qrcode
from PIL import Image
import base64
import io

# =============================================
# CONFIG & DESIGN
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
    .search-box {background: white; padding: 20px; border-radius: 20px; box-shadow: 0 8px 25px rgba(0,0,0,0.1); margin: 20px 0; border: 3px solid #4CAF50;}
    .sidebar-title {color: #ffffff; font-size: 2rem; font-weight: 900; text-align: center; text-shadow: 3px 3px 10px rgba(0,0,0,0.6);}
</style>
""", unsafe_allow_html=True)

# Buat folder
for folder in ["uploads", "thumbnails"]:
    os.makedirs(folder, exist_ok=True)

DB_NAME = "fama_standards.db"
CATEGORIES = ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"]

# Password admin (fama2025 & fama123)
ADMIN_CREDENTIALS = {
    "admin": hashlib.sha256("fama2025".encode()).hexdigest(),
    "pengarah": hashlib.sha256("fama123".encode()).hexdigest()
}

# =============================================
# INIT DATABASE
# =============================================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        title TEXT, category TEXT,
        file_name TEXT, file_path TEXT, thumbnail_path TEXT, 
        upload_date TEXT, uploaded_by TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        sender TEXT, message TEXT, timestamp TEXT, is_admin INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

init_db()

# =============================================
# FUNGSI ASAS
# =============================================
def save_thumbnail(file_obj):
    if not file_obj:
        return None
    try:
        img = Image.open(file_obj).convert("RGB")
        img.thumbnail((350, 500))
        path = f"thumbnails/thumb_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
        img.save(path, "JPEG", quality=95)
        return path
    except:
        return None

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
# SIDEBAR & NAVIGATION
# =============================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png", width=110)
    st.markdown("<h3 class='sidebar-title'>FAMA STANDARD</h3>", unsafe_allow_html=True)
    st.markdown("---")
    page = st.selectbox("Pilih Halaman", ["Halaman Utama", "Papar QR Code", "Admin Panel"], label_visibility="collapsed")
    st.markdown("---")
    st.markdown("### Hubungi Admin FAMA")
    
    for msg in get_chat_messages()[-10:]:
        if msg['is_admin']:
            st.markdown(f'<div style="background:#E8F5E8;padding:10px;border-radius:12px;margin:5px 0;text-align:right;border-left:5px solid #4CAF50;"><small><b>Admin</b><br>{msg["message"]}</small></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="background:#4CAF50;color:white;padding:10px;border-radius:12px;margin:5px 0;"><small><b>{msg["sender"]}</b><br>{msg["message"]}</small></div>', unsafe_allow_html=True)
    
    with st.form("chat_form", clear_on_submit=True):
        nama = st.text_input("Nama")
        pesan = st.text_input("Mesej")
        if st.form_submit_button("Hantar"):
            if nama and pesan:
                add_chat_message(nama, pesan)
                st.success("Dihantar!")
                st.rerun()

# =============================================
# HALAMAN UTAMA
# =============================================
if page == "Halaman Utama":
    st.markdown("""
    <div style="text-align:center; padding:30px 0;">
        <h1 style="color:#1B5E20; font-size:3.5rem; font-weight:900;">RUJUKAN STANDARD FAMA</h1>
        <p style="font-size:1.4rem; color:#2E7D32;">Keluaran Hasil Pertanian Tempatan Malaysia</p>
    </div>
    """, unsafe_allow_html=True)

    docs = get_docs()
    total = len(docs)
    st.markdown(f"<h2 style='text-align:center; color:#1B5E20;'>Jumlah Standard: {total}</h2>", unsafe_allow_html=True)

    col1, col2 = st.columns([3,1])
    with col1: cari = st.text_input("", placeholder="Cari tajuk standard...")
    with col2: kat = st.selectbox("", ["Semua"] + CATEGORIES)

    hasil = [d for d in docs if (kat == "Semua" or d['category'] == kat) and (not cari or cari.lower() in d['title'].lower())]

    for d in hasil:
        with st.container():
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            c1, c2 = st.columns([1,3])
            with c1:
                img = d['thumbnail_path'] if d['thumbnail_path'] and os.path.exists(d['thumbnail_path']) else "https://via.placeholder.com/350x500/4CAF50/white?text=FAMA"
                st.image(img, use_container_width=True)
            with c2:
                st.markdown(f"<h3>{d['title']}</h3>", unsafe_allow_html=True)
                st.caption(f"{d['category']} • {d['upload_date'][:10]}")
                if os.path.exists(d['file_path']):
                    with open(d['file_path'], "rb") as f:
                        st.download_button("MUAT TURUN PDF", f.read(), d['file_name'], use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

# =============================================
# PAPAR QR CODE
# =============================================
elif page == "Papar QR Code":
    st.markdown("<h1 style='text-align:center;color:#1B5E20;'>PAPAR QR CODE</h1>", unsafe_allow_html=True)
    search = st.text_input("Cari tajuk standard")
    if search:
        matches = [d for d in get_docs() if search.lower() in d['title'].lower()]
        for d in matches:
            qr = qrcode.QRCode(box_size=12, border=6)
            qr.add_data(f"https://your-app-url.streamlit.app/?id={d['id']}")
            qr.make(fit=True)
            img = qr.make_image(fill_color="#1B5E20", back_color="white")
            buf = io.BytesIO()
            img.save(buf, "PNG")
            st.image(buf.getvalue(), width=300)
            st.write(f"**{d['title']}** • {d['category']}")

# =============================================
# ADMIN PANEL — FULL POWER!
# =============================================
else:  # Admin Panel
    if not st.session_state.get("logged_in"):
        st.title("ADMIN PANEL FAMA")
        c1, c2 = st.columns(2)
        with c1: user = st.text_input("Username")
        with c2: pwd = st.text_input("Password", type="password")
        if st.button("LOG MASUK"):
            if user in ADMIN_CREDENTIALS and hashlib.sha256(pwd.encode()).hexdigest() == ADMIN_CREDENTIALS[user]:
                st.session_state.logged_in = True
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Salah username/password")
        st.stop()

    st.success(f"Selamat Datang, {st.session_state.user.upper()}!")

    t1, t2, t3, t4 = st.tabs(["Tambah Standard", "Edit & Padam", "Backup", "Chat"])

    with t1:  # Tambah
        file = st.file_uploader("Upload PDF/DOCX", type=["pdf","docx"])
        title = st.text_input("Tajuk")
        cat = st.selectbox("Kategori", CATEGORIES)
        thumb = st.file_uploader("Thumbnail", type=["jpg","jpeg","png"])
        if file and title and st.button("SIMPAN", type="primary"):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fpath = f"uploads/{ts}_{file.name}"
            with open(fpath, "wb") as f: f.write(file.getvalue())
            tpath = save_thumbnail(thumb) if thumb else None
            conn = sqlite3.connect(DB_NAME)
            conn.execute("INSERT INTO documents (title, category, file_name, file_path, thumbnail_path, upload_date, uploaded_by) VALUES (?,?,?,?,?,?,?)",
                         (title, cat, file.name, fpath, tpath, datetime.now().strftime("%Y-%m-%d %H:%M"), st.session_state.user))
            conn.commit()
            conn.close()
            st.success("Berjaya ditambah!")
            st.balloons()
            st.rerun()

    with t2:  # Edit & Padam + Carian
        st.markdown("<div class='search-box'><h3>Cari Standard Untuk Edit</h3>", unsafe_allow_html=True)
        search = st.text_input("Cari tajuk / ID / kategori", key="search_admin")
        st.markdown("</div>", unsafe_allow_html=True)

        docs = get_docs()
        if search:
            s = search.lower()
            docs = [d for d in docs if s in d['title'].lower() or s in str(d['id']) or s in d['category'].lower()]

        for d in docs:
            with st.expander(f"ID {d['id']} • {d['title']} • {d['category']}"):
                col1, col2 = st.columns([1,3])
                with col1:
                    img = d['thumbnail_path'] if d['thumbnail_path'] and os.path.exists(d['thumbnail_path']) else "https://via.placeholder.com/300/4CAF50/white?text=FAMA"
                    st.image(img, use_container_width=True)
                with col2:
                    if f"t{d['id']}" not in st.session_state: st.session_state[f"t{d['id']}"] = d['title']
                    if f"c{d['id']}" not in st.session_state: st.session_state[f"c{d['id']}"] = CATEGORIES.index(d['category'])

                    nt = st.text_input("Tajuk", st.session_state[f"t{d['id']}"], key=f"tt{d['id']}")
                    nc = st.selectbox("Kategori", CATEGORIES, st.session_state[f"c{d['id']}"], key=f"cc{d['id']}")
                    ntmb = st.file_uploader("Tukar Thumbnail", type=["jpg","jpeg","png"], key=f"tm{d['id']}")
                    nfile = st.file_uploader("TUKAR FAIL PDF", type=["pdf","docx"], key=f"ff{d['id']}")

                    st.session_state[f"t{d['id']}"] = nt
                    st.session_state[f"c{d['id']}"] = CATEGORIES.index(nc)

                    c1, c2 = st.columns(2)
                    if c1.button("KEMASKINI", key=f"up{d['id']}"):
                        # Tukar fail
                        fp = d['file_path']
                        fn = d['file_name']
                        if nfile:
                            os.remove(d['file_path'])
                            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                            fp = f"uploads/{ts}_{nfile.name}"
                            fn = nfile.name
                            with open(fp, "wb") as f: f.write(nfile.getvalue())
                        # Tukar thumb
                        tp = d['thumbnail_path']
                        if ntmb and os.path.exists(d['thumbnail_path']) and os.remove(d['thumbnail_path'])
                        if ntmb: tp = save_thumbnail(ntmb)

                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("UPDATE documents SET title=?, category=?, file_name=?, file_path=?, thumbnail_path=? WHERE id=?", 
                                     (nt, nc, fn, fp, tp, d['id']))
                        conn.commit()
                        conn.close()
                        st.success("Kemaskini berjaya!")
                        st.rerun()

                    if c2.button("PADAM", key=f"dl{d['id']}"):
                        if st.session_state.get(f"del{d['id']}", False):
                            os.path.exists(d['file_path']) and os.remove(d['file_path'])
                            d['thumbnail_path'] and os.path.exists(d['thumbnail_path']) and os.remove(d['thumbnail_path'])
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("DELETE FROM documents WHERE id=?", (d['id'],))
                            conn.commit()
                            conn.close()
                            st.success("Dipadam!")
                            st.rerun()
                        else:
                            st.session_state[f"del{d['id']}"] = True
                            st.warning("Tekan sekali lagi untuk confirm")

    with t3:  # Backup
        if st.button("Download Backup ZIP"):
            zipname = f"backup_fama_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
            with zipfile.ZipFile(zipname, "w") as z:
                z.write(DB_NAME)
                for folder in ["uploads", "thumbnails"]:
                    for root, _, files in os.walk(folder):
                        for file in files:
                            z.write(os.path.join(root, file))
            with open(zipname, "rb") as f:
                st.download_button("Download Backup", f.read(), zipname)
            st.success("Backup siap!")

    with t4:  # Chat
        for m in reversed(get_chat_messages()):
            if m['is_admin']:
                st.success(f"Admin: {m['message']}")
            else:
                st.info(f"{m['sender']}: {m['message']}")
            r = st.text_input("Balas", key=f"r{m['id']}")
            if st.button("Hantar", key=f"s{m['id']}"):
                add_chat_message("Admin", r, True)
                st.rerun()

    if st.button("Log Keluar"):
        st.session_state.clear()
        st.rerun()

