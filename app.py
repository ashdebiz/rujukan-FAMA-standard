import streamlit as st
import sqlite3
import os
import zipfile
from datetime import datetime, timedelta
import hashlib
from PIL import Image

# =============================================
# CONFIG & DESIGN ASAL YANG KAU RINDU TU BRO!
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
    .search-box {background: white; padding: 20px; border-radius: 20px; box-shadow: 0 8px 25px rgba(0,0,0,0.1); margin: 20px 0; border: 2px solid #4CAF50;}
    .sidebar-logo-container {text-align: center; padding: 30px 0;}
    .sidebar-logo-container img {width: 110px; margin-bottom: 10px;}
    .sidebar-title {color: #ffffff; font-size: 2rem; font-weight: 900; margin: 0; text-shadow: 3px 3px 10px rgba(0,0,0,0.6);}
</style>
""", unsafe_allow_html=True)

# Buat folder
for folder in ["uploads", "thumbnails"]:
    os.makedirs(folder, exist_ok=True)

DB_NAME = "fama_standards.db"
CATEGORIES = ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"]

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
# SIDEBAR — SAMA MACAM ASAL
# =============================================
with st.sidebar:
    st.markdown("""
    <div class="sidebar-logo-container">
        <img src="https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png">
        <h3 class="sidebar-title">FAMA STANDARD</h3>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")
    page = st.selectbox("Menu Utama", ["Halaman Utama", "Papar QR Code", "Admin Panel"], label_visibility="collapsed")
    st.markdown("---")
    st.markdown("### Hubungi Admin FAMA")

    for msg in get_chat_messages()[-10:]:
        if msg['is_admin']:
            st.markdown(f'<div style="background:#E8F5E8; border-radius:12px; padding:10px; margin:8px 0; max-width:85%; margin-left:auto; border-left:5px solid #4CAF50;"><small><b>Admin</b> • {msg["timestamp"][-5:]}</small><br>{msg["message"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="background:#4CAF50; color:white; border-radius:12px; padding:10px; margin:8px 0; max-width:85%;"><small><b>{msg["sender"]}</b> • {msg["timestamp"][-5:]}</small><br>{msg["message"]}</div>', unsafe_allow_html=True)

    with st.form("chat_form", clear_on_submit=True):
        nama = st.text_input("Nama")
        pesan = st.text_area("Mesej", height=100)
        if st.form_submit_button("Hantar"):
            if nama and pesan:
                add_chat_message(nama, pesan)
                st.success("Mesej dihantar!")
                st.rerun()

# =============================================
# HALAMAN UTAMA — 100% SAMA MACAM ASAL BRO!!!
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
    baru = len([d for d in docs if (datetime.now() - datetime.strptime(d['upload_date'][:10], "%Y-%m-%d")).days <= 30])
    latest = max((d['upload_date'][:10] for d in docs), default="Tiada") if docs else "Tiada"
    cat_count = {c: sum(1 for d in docs if d['category'] == c) for c in CATEGORIES}

    st.markdown(f"""
    <div style="background:linear-gradient(135deg, #00695c, #009688); border-radius:25px; padding:30px; color:white; margin:25px 0; box-shadow:0 10px 30px rgba(0,0,0,0.2);">
        <h2 style="text-align:center; margin:0;">STATISTIK RUJUKAN FAMA STANDARD</h2>
        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:20px; margin-top:25px;">
            <div style="background:rgba(255,255,255,0.2); padding:20px; border-radius:15px; text-align:center;">
                <h1 style="margin:5px 0; font-size:2.8rem;">{total}</h1><p style="margin:0; font-size:1.1rem;">JUMLAH STANDARD</p>
            </div>
            <div style="background:rgba(255,255,255,0.2); padding:20px; border-radius:15px; text-align:center;">
                <h1 style="margin:5px 0; font-size:2.8rem;">{baru}</h1><p style="margin:0; font-size:1.1rem;">BARU (30 HARI)</p>
            </div>
            <div style="background:rgba(255,255,255,0.2); padding:20px; border-radius:15px; text-align:center;">
                <h1 style="margin:5px 0; font-size:1.8rem;">{latest}</h1><p style="margin:0;">TERKINI</p>
            </div>
        </div>
        <div style="margin-top:30px; display:grid; grid-template-columns: repeat(4,1fr); gap:12px;">
            {''.join(f'<div style="background:rgba(255,255,255,0.15); padding:12px; border-radius:12px; text-align:center;"><strong>{c}</strong><br><h3 style="margin:5px 0;">{cat_count.get(c,0)}</h3></div>' for c in CATEGORIES)}
        </div>
    </div>
    """, unsafe_allow_html=True)

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
# PAPAR QR CODE (kalau nak pakai nanti)
# =============================================
elif page == "Papar QR Code":
    st.markdown("<h1 style='text-align:center;color:#1B5E20;'>PAPAR QR CODE STANDARD</h1>", unsafe_allow_html=True)
    search = st.text_input("Cari tajuk untuk papar QR")
    if search:
        matches = [d for d in get_docs() if search.lower() in d['title'].lower()]
        for d in matches:
            import qrcode
            from io import BytesIO
            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(f"https://your-app-url.streamlit.app/?doc={d['id']}")
            qr.make(fit=True)
            img = qr.make_image(fill_color="#1B5E20", back_color="white")
            buf = BytesIO()
            img.save(buf, format="PNG")
            st.image(buf.getvalue(), width=250)
            st.write(f"**{d['title']}**")

# =============================================
# ADMIN PANEL — SAMA MACAM ASAL TAPI LEBIH POWER
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

    t1, t2, t3 = st.tabs(["Tambah Standard", "Edit & Padam", "Backup"])

    with t1:
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
            st.balloons()
            st.rerun()

    with t2:
        search = st.text_input("Cari tajuk/ID")
        docs = get_docs()
        if search:
            s = search.lower()
            docs = [d for d in docs if s in d['title'].lower() or s in str(d['id'])]

        for d in docs:
            with st.expander(f"ID {d['id']} • {d['title']}"):
                col1,col2 = st.columns([1,3])
                with col1:
                    img = d['thumbnail_path'] or "https://via.placeholder.com/300"
                    st.image(img, use_container_width=True)
                with col2:
                    nt = st.text_input("Tajuk", d['title'], key=f"t{d['id']}")
                    nc = st.selectbox("Kategori", CATEGORIES, CATEGORIES.index(d['category']), key=f"c{d['id']}")
                    new_file = st.file_uploader("Tukar PDF", type=["pdf"], key=f"f{d['id']}")
                    new_thumb = st.file_uploader("Tukar Thumbnail", type=["jpg","png"], key=f"th{d['id']}")
                    if st.button("KEMASKINI", key=f"u{d['id']}"):
                        fp = d['file_path']
                        if new_file:
                            os.remove(fp)
                            fp = f"uploads/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{new_file.name}"
                            with open(fp,"wb") as f: f.write(new_file.getvalue())
                        tp = d['thumbnail_path']
                        if new_thumb:
                            if tp: os.remove(tp)
                            tp = save_thumbnail(new_thumb)
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("UPDATE documents SET title=?,category=?,file_path=?,thumbnail_path=? WHERE id=?", (nt,nc,fp,tp,d['id']))
                        conn.commit()
                        conn.close()
                        st.success("Kemaskini!")
                        st.rerun()
                    if st.button("PADAM", key=f"d{d['id']}"):
                        st.warning("Confirm padam?")
                        if st.button("YA PADAM!", key=f"dy{d['id']}"):
                            os.remove(d['file_path'])
                            if d['thumbnail_path']: os.remove(d['thumbnail_path'])
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("DELETE FROM documents WHERE id=?", (d['id'],))
                            conn.commit()
                            conn.close()
                            st.success("Dipadam!")
                            st.rerun()

    with t3:
        if st.button("Download Backup ZIP"):
            zipname = f"backup_{datetime.now().strftime('%Y%m%d')}.zip"
            with zipfile.ZipFile(zipname,"w") as z:
                z.write(DB_NAME)
                for root,_,files in os.walk("uploads"): 
                    for f in files: z.write(os.path.join(root,f))
                for root,_,files in os.walk("thumbnails"): 
                    for f in files: z.write(os.path.join(root,f))
            with open(zipname,"rb") as f:
                st.download_button("Download Backup", f.read(), zipname)
            os.remove(zipname)

    if st.button("Log Keluar"):
        st.session_state.clear()
        st.rerun()

