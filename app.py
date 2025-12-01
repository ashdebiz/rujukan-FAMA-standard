import streamlit as st
import sqlite3
import os
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import qrcode
from PIL import Image
import base64
import io

# =============================================
# CONFIG & DESIGN GEMPUR
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
    = {
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
    if not file_obj: return None
    try:
        img = Image.open(file_obj).convert("RGB")
        img.thumbnail((350, 500))
        path = f"thumbnails/thumb_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
        img.save(path, "JPEG", quality=95)
        return path
    except Exception as e:
        st.error(f"Gagal simpan thumbnail: {e}")
        return None

def get_docs():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM documents ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@st.cache_data(ttl=3)
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
                 (sender, message, datetime.now().strftime("%Y-%m-%d %H:%M"), 1 if is_admin else 0))
    conn.commit()
    conn.close()
    st.cache_data.clear()

# =============================================
# STATISTIK CANTIK
# =============================================
def show_stats():
    docs = get_docs()
    total = len(docs)
    baru = len([d for d in docs if d['upload_date'][:10] >= (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")])
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

# =============================================
# SIDEBAR
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
            st.markdown(f'<div style="background:#4CAF50; color:white; border-radius:12px; padding:10px; margin:8px 0; max-width:85%;"><small><b>{msg["sender"]}</b> • {msg["timestamp"][-5:]}</small><br>{msg["message"]}</div>', unsafe_allow_html)

    with st.form("chat_form", clear_on_submit=True):
        nama = st.text_input("Nama Anda")
        pesan = st.text_input("Tanya soalan standard...")
        if st.form_submit_button("Hantar"):
            if nama.strip() and pesan.strip():
                add_chat_message(nama.strip(), pesan.strip())
                st.success("Mesej dihantar!")
                st.rerun()

# =============================================
# HALAMAN UTAMA
# =============================================
if page == "Halaman Utama":
    st.markdown("""
    <div style="position:relative; border-radius:30px; overflow:hidden; box-shadow:0 20px 50px rgba(27,94,32,0.4); margin:20px 0;">
        <img src="https://w7.pngwing.com/pngs/34/259/png-transparent-fruits-and-vegetables.png" style="width:100%; height:320px; object-fit:cover;">
        <div style="position:absolute; top:0; left:0; width:100%; height:100%; background: linear-gradient(135deg, rgba(27,94,32,0.9), rgba(76,175,80,0.8));"></div>
        <div style="position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); text-align:center; width:100%;">
            <h1 style="color:white; font-size:3.8rem; font-weight:900; margin:0;">RUJUKAN FAMA STANDARD</h1>
            <p style="color:#e8f5e8; font-size:1.6rem; margin:10px 0 0 0;">Keluaran Hasil Pertanian Tempatan Malaysia</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    show_stats()

    col1, col2 = st.columns([3,1])
    with col1: cari = st.text_input("", placeholder="Cari tajuk standard...", key="cari_utama")
    with col2: kat = st.selectbox("", ["Semua"] + CATEGORIES, key="kat_utama")

    docs = get_docs()
    hasil = [d for d in docs 
             if (kat == "Semua" or d['category'] == kat) 
             and (not cari or cari.lower() in d['title'].lower())]

    st.markdown(f"### Ditemui {len(hasil)} Standard")
    for d in hasil:
        with st.container():
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            c1, c2 = st.columns([1,3])
            with c1:
                img = d['thumbnail_path'] if d['thumbnail_path'] and os.path.exists(d['thumbnail_path']) else "https://via.placeholder.com/350x500/4CAF50/white?text=FAMA+STANDARD"
                st.image(img, use_container_width=True)
            with c2:
                st.markdown(f"<h2 style='margin:0; color:#1B5E20;'>{d['title']}</h2>", unsafe_allow_html=True)
                st.caption(f"**{d['category']}** • Upload: {d['upload_date'][:10]} • Oleh: {d['uploaded_by']}")
                if d['file_path'] and os.path.exists(d['file_path']):
                    with open(d['file_path'], "rb") as f:
                        st.download_button("MUAT TURUN PDF", f.read(), d['file_name'], use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

# =============================================
# PAPAR QR CODE
# =============================================
elif page == "Papar QR Code":
    st.markdown("<h1 style='text-align:center; color:#1B5E20;'>PAPAR QR CODE STANDARD</h1>", unsafe_allow_html=True)
    show_stats()
    search = st.text_input("Taip tajuk standard untuk cari QR Code", placeholder="Contoh: Standard Durian Musang King")
    if search:
        matches = [d for d in get_docs() if search.lower() in d['title'].lower()]
        if matches:
            for d in matches[:10]:
                qr = qrcode.QRCode(box_size=15, border=8)
                qr.add_data(f"https://rujukan-fama-standard.streamlit.app/?doc={d['id']}")
                qr.make(fit=True)
                img = qr.make_image(fill_color="#1B5E20", back_color="white")
                buf = io.BytesIO()
                img.save(buf, "PNG")
                b64 = base64.b64encode(buf.getvalue()).decode()
                st.markdown(f"""
                <div class="qr-container">
                    <h2 style="color:#1B5E20;">{d['title']}</h2>
                    <p style="color:#4CAF50; font-weight:bold;">{d['category']}</p>
                    <img src="data:image/png;base64,{b64}" width="380">
                    <p style="margin-top:15px; color:#666;">ID: {d['id']} • Upload: {d['upload_date'][:10]}</p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.warning("Tiada padanan ditemui")

# =============================================
# ADMIN PANEL — DENGAN CARIAN POWER + EDIT FAIL PDF
# =============================================
else:  # Admin Panel
    if not st.session_state.get("logged_in"):
        st.markdown("<h1 style='text-align:center; color:#1B5E20;'>ADMIN PANEL FAMA</h1>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1: username = st.text_input("Username")
        with col2: password = st.text_input("Kata Laluan", type="password")
        if st.button("LOG MASUK", type="primary"):
            h = hashlib.sha256(password.encode()).hexdigest()
            if username in ADMIN_CREDENTIALS and ADMIN_CREDENTIALS[username] == h:
                st.session_state.logged_in = True
                st.session_state.user = username
                st.rerun()
            else:
                st.error("Username atau kata laluan salah!")
        st.stop()

    st.success(f"Selamat Datang, {st.session_state.user.upper()}!")

    tab1, tab2, tab3, tab4 = st.tabs(["Tambah Standard", "Edit & Padam ← CARIAN!", "Backup & Restore", "Chat Pengguna"])

    # TAMBAH
    with tab1:
        st.markdown("### Tambah Standard Baru")
        uploaded_file = st.file_uploader("Upload Fail PDF/DOCX", type=["pdf","docx"])
        title = st.text_input("Tajuk Standard", placeholder="Contoh: Standard Pembungkusan Durian")
        category = st.selectbox("Kategori", CATEGORIES)
        thumbnail = st.file_uploader("Thumbnail (pilihan)", type=["jpg","jpeg","png"])

        if uploaded_file and title:
            if st.button("SIMPAN STANDARD", type="primary"):
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_path = f"uploads/{ts}_{uploaded_file.name}"
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getvalue())
                thumb_path = save_thumbnail(thumbnail) if thumbnail else None

                conn = sqlite3.connect(DB_NAME)
                conn.execute("""INSERT INTO documents 
                    (title, category, file_name, file_path, thumbnail_path, upload_date, uploaded_by) 
                    VALUES (?,?,?,?,?,?,?)""",
                    (title, category, uploaded_file.name, file_path, thumb_path, 
                     datetime.now().strftime("%Y-%m-%d %H:%M"), st.session_state.user))
                conn.commit()
                conn.close()
                st.success("Standard berjaya ditambah!")
                st.balloons()
                st.rerun()

    # EDIT & PADAM — DENGAN CARIAN GILA!
    with tab2:
        st.markdown("<div class='search-box'>", unsafe_allow_html=True)
        st.markdown("### Cari Standard Untuk Edit / Padam")
        col1, col2 = st.columns([3,1])
        with col1:
            search_term = st.text_input("Cari tajuk / ID / kategori", placeholder="Contoh: durian, 45, Buah", key="cari_admin")
        with col2:
            filter_cat = st.selectbox("Filter Kategori", ["Semua"] + CATEGORIES, key="filter_admin")
        st.markdown("</div>", unsafe_allow_html=True)

        all_docs = get_docs()
        filtered = all_docs

        if search_term:
            s = search_term.lower()
            filtered = [d for d in all_docs if s in d['title'].lower() or s in str(d['id']) or s in d['category'].lower()]
        if filter_cat != "Semua":
            filtered = [d for d in filtered if d['category'] == filter_cat]

        st.markdown(f"**Ditemui {len(filtered)} standard**")

        for doc in filtered:
            with st.expander(f"ID {doc['id']} • {doc['title']} • {doc['category']} • {doc['upload_date'][:10]}", expanded=False):
                col_img, col_form = st.columns([1, 3])

                with col_img:
                    img = doc['thumbnail_path'] if doc['thumbnail_path'] and os.path.exists(doc['thumbnail_path']) else "https://via.placeholder.com/300x420/4CAF50/white?text=FAMA"
                    st.image(img, use_container_width=True)

                with col_form:
                    # Session state simpan input
                    if f"title_{doc['id']}" not in st.session_state:
                        st.session_state[f"title_{doc['id']}"] = doc['title']
                    if f"cat_{doc['id']}" not in st.session_state:
                        st.session_state[f"cat_{doc['id']}"] = CATEGORIES.index(doc['category']) if doc['category'] in CATEGORIES else 0

                    new_title = st.text_input("Tajuk", value=st.session_state[f"title_{doc['id']}"], key=f"t{doc['id']}")
                    new_cat = st.selectbox("Kategori", CATEGORIES, index=st.session_state[f"cat_{doc['id']}"], key=f"c{doc['id']}")
                    new_thumb = st.file_uploader("Tukar Thumbnail", type=["jpg","jpeg","png"], key=f"th{doc['id']}")
                    new_file = st.file_uploader("TUKAR FAIL PDF/DOCX", type=["pdf","docx"], key=f"f{doc['id']}")

                    # Update session
                    st.session_state[f"title_{doc['id']}"] = new_title
                    st.session_state[f"cat_{doc['id']}"] = CATEGORIES.index(new_cat)

                    col_upd, col_del = st.columns(2)
                    if col_upd.button("KEMASKINI", key=f"u{doc['id']}", type="primary"):
                        # Tukar fail PDF
                        final_path = doc['file_path']
                        final_name = doc['file_name']
                        if new_file:
                            if os.path.exists(doc['file_path']):
                                os.remove(doc['file_path'])
                            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                            final_path = f"uploads/{ts}_{new_file.name}"
                            final_name = new_file.name
                            with open(final_path, "wb") as f:
                                f.write(new_file.getvalue())

                        # Tukar thumbnail
                        final_thumb = doc['thumbnail_path']
                        if new_thumb:
                            if doc['thumbnail_path'] and os.path.exists(doc['thumbnail_path']):
                                os.remove(doc['thumbnail_path'])
                            final_thumb = save_thumbnail(new_thumb)

                        # Update DB
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("""UPDATE documents 
                            SET title=?, category=?, file_name=?, file_path=?, thumbnail_path=? 
                            WHERE id=?""",
                            (new_title, new_cat, final_name, final_path, final_thumb, doc['id']))
                        conn.commit()
                        conn.close()
                        st.success(f"ID {doc['id']} berjaya dikemaskini!")
                        st.balloons()
                        st.rerun()

                    if col_del.button("PADAM", key=f"d{doc['id']}", type="secondary"):
                        if st.session_state.get(f"confirm{doc['id']}", False):
                            # Padam fail & thumbnail
                            if os.path.exists(doc['file_path']): os.remove(doc['file_path'])
                            if doc['thumbnail_path'] and os.path.exists(doc['thumbnail_path']): os.remove(doc['thumbnail_path'])
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("DELETE FROM documents WHERE id=?", (doc['id'],))
                            conn.commit()
                            conn.close()
                            st.success("Standard dipadam selamanya!")
                            st.balloons()
                            st.rerun()
                        else:
                            st.session_state[f"confirm{doc['id']}"] = True
                            st.warning("Tekan PADAM sekali lagi untuk confirm")

    # BACKUP
    with tab3:
        st.markdown("### Backup & Restore Database")
        if st.button("Download Backup Lengkap Sekarang", type="primary"):
            zipname = f"FAMA_BACKUP_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
            with zipfile.ZipFile(zipname, "w") as z:
                z.write(DB_NAME)
                for folder in ["uploads", "thumbnails"]:
                    if os.path.exists(folder):
                        for root, _, files in os.walk(folder):
                            for file in files:
                                z.write(os.path.join(root, file), arcname=os.path.join(folder, file))
            with open(zipname, "rb") as f:
                st.download_button("Download ZIP Backup", f.read(), zipname, "application/zip")
            st.success("Backup siap!")

        uploaded = st.file_uploader("Upload backup .zip untuk restore", type=["zip"])
        if uploaded and st.button("RESTORE BACKUP", type="primary"):
            with zipfile.ZipFile(uploaded) as z:
                z.extractall(".")
            st.success("Semua data berjaya dipulihkan!")
            st.balloons()
            st.rerun()

    # CHAT
    with tab4:
        st.markdown("### Chat Dengan Pengguna")
        for m in reversed(get_chat_messages()):
            if m['is_admin']:
                st.markdown(f"**Admin FAMA** • {m['timestamp']}")
                st.success(m['message'])
            else:
                st.markdown(f"**{m['sender']}** • {m['timestamp']}")
                st.info(m['message'])
            reply = st.text_input("Balas", key=f"r{m['id']}")
            if st.button("Hantar Balasan", key=f"s{m['id']}"):
                if reply.strip():
                    add_chat_message("Admin FAMA", reply.strip(), is_admin=True)
                    st.success("Balasan dihantar!")
                    st.rerun()

    if st.button("Log Keluar"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

