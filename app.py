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
# CONFIG & DESIGN CANTIK
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

# Password: admin → fama2025 | pengarah → fama123
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
# SIDEBAR
# =============================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png", width=110)
    st.markdown("<h3 class='sidebar-title'>FAMA STANDARD</h3>", unsafe_allow_html=True)
    st.markdown("---")
    page = st.selectbox("Menu", ["Halaman Utama", "Papar QR Code", "Admin Panel"], label_visibility="collapsed")
    st.markdown("---")
    st.markdown("### Hubungi Admin FAMA")

    for msg in get_chat_messages()[-10:]:
        if msg['is_admin']:
            st.markdown(f'<div style="background:#E8F5E8;padding:12px;border-radius:12px;margin:8px 0;text-align:right;border-left:5px solid #4CAF50;"><small><b>Admin</b> • {msg["timestamp"][-5:]}</small><br>{msg["message"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="background:#4CAF50;color:white;padding:10px;border-radius:12px;margin:8px 0;"><small><b>{msg["sender"]}</b> • {msg["timestamp"][-5:]}</small><br>{msg["message"]}</div>', unsafe_allow_html=True)

    with st.form("chat_form", clear_on_submit=True):
        nama = st.text_input("Nama")
        pesan = st.text_input("Mesej")
        if st.form_submit_button("Hantar"):
            if nama.strip() and pesan.strip():
                add_chat_message(nama.strip(), pesan.strip())
                st.success("Mesej dihantar!")
                st.rerun()

# =============================================
# HALAMAN UTAMA
# =============================================
if page == "Halaman Utama":
    st.markdown("<h1 style='text-align:center;color:#1B5E20;'>RUJUKAN STANDARD FAMA</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;font-size:1.4rem;color:#2E7D32;'>Keluaran Hasil Pertanian Tempatan Malaysia</p>", unsafe_allow_html=True)

    docs = get_docs()
    st.markdown(f"<h3 style='text-align:center;color:#1B5E20;'>Jumlah Standard: {len(docs)}</h3>", unsafe_allow_html=True)

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
                st.markdown(f"<h3 style='color:#1B5E20;'>{d['title']}</h3>", unsafe_allow_html=True)
                st.caption(f"**{d['category']}** • {d['upload_date'][:10]} • {d['uploaded_by']}")
                if os.path.exists(d['file_path']):
                    with open(d['file_path'], "rb") as f:
                        st.download_button("MUAT TURUN PDF", f.read(), d['file_name'], use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

# =============================================
# ADMIN PANEL — FULL POWER + CARIAN
# =============================================
else:
    if not st.session_state.get("logged_in"):
        st.markdown("<h1 style='text-align:center;color:#1B5E20;'>ADMIN PANEL FAMA</h1>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1: user = st.text_input("Username")
        with col2: pwd = st.text_input("Password", type="password")
        if st.button("LOG MASUK", type="primary"):
            if user in ADMIN_CREDENTIALS and hashlib.sha256(pwd.encode()).hexdigest() == ADMIN_CREDENTIALS[user]:
                st.session_state.logged_in = True
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Salah username atau kata laluan!")
        st.stop()

    st.success(f"Selamat Datang, {st.session_state.user.upper()}!")

    tab1, tab2, tab3 = st.tabs(["Tambah Standard", "Edit & Padam", "Backup & Chat"])

    # TAMBAH
    with tab1:
        uploaded_file = st.file_uploader("Upload PDF/DOCX", type=["pdf","docx"])
        title = st.text_input("Tajuk Standard")
        category = st.selectbox("Kategori", CATEGORIES)
        thumb = st.file_uploader("Thumbnail (pilihan)", type=["jpg","jpeg","png"])
        if uploaded_file and title:
            if st.button("SIMPAN STANDARD", type="primary"):
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                fpath = f"uploads/{ts}_{uploaded_file.name}"
                with open(fpath, "wb") as f:
                    f.write(uploaded_file.getvalue())
                tpath = save_thumbnail(thumb) if thumb else None
                conn = sqlite3.connect(DB_NAME)
                conn.execute("INSERT INTO documents (title, category, file_name, file_path, thumbnail_path, upload_date, uploaded_by) VALUES (?,?,?,?,?,?,?)",
                             (title, category, uploaded_file.name, fpath, tpath, datetime.now().strftime("%Y-%m-%d %H:%M"), st.session_state.user))
                conn.commit()
                conn.close()
                st.success("Standard berjaya ditambah!")
                st.balloons()
                st.rerun()

    # EDIT & PADAM + CARIAN
    with tab2:
        st.markdown("<div class='search-box'><h3>Cari Standard Untuk Edit</h3>", unsafe_allow_html=True)
        search = st.text_input("Cari tajuk / ID / kategori", placeholder="Taip di sini...", key="cari_admin")
        st.markdown("</div>", unsafe_allow_html=True)

        docs = get_docs()
        if search = search.strip().lower()
        if search:
            docs = [d for d in docs if search in d['title'].lower() or search in str(d['id']) or search in d['category'].lower()]

        for doc in docs:
            with st.expander(f"ID {doc['id']} • {doc['title']} • {doc['category']}"):
                col1, col2 = st.columns([1,3])
                with col1:
                    img = doc['thumbnail_path'] if doc['thumbnail_path'] and os.path.exists(doc['thumbnail_path']) else "https://via.placeholder.com/300x420/4CAF50/white?text=FAMA"
                    st.image(img, use_container_width=True)

                with col2:
                    # Simpan nilai sementara
                    key_t = f"t_{doc['id']}"
                    key_c = f"c_{doc['id']}"
                    if key_t not in st.session_state:
                        st.session_state[key_t] = doc['title']
                    if key_c not in st.session_state:
                        st.session_state[key_c] = CATEGORIES.index(doc['category']) if doc['category'] in CATEGORIES else 0

                    new_title = st.text_input("Tajuk", value=st.session_state[key_t], key=f"ti_{doc['id']}")
                    new_cat = st.selectbox("Kategori", CATEGORIES, index=st.session_state[key_c], key=f"ca_{doc['id']}")
                    new_thumb = st.file_uploader("Tukar Thumbnail", type=["jpg","jpeg","png"], key=f"th_{doc['id']}")
                    new_file = st.file_uploader("TUKAR FAIL PDF/DOCX", type=["pdf","docx"], key=f"fi_{doc['id']}")

                    # Update session state
                    st.session_state[key_t] = new_title
                    st.session_state[key_c] = CATEGORIES.index(new_cat)

                    c1, c2 = st.columns(2)
                    if c1.button("KEMASKINI", key=f"up_{doc['id']}", type="primary"):
                        # Tukar fail PDF
                        final_fpath = doc['file_path']
                        final_fname = doc['file_name']
                        if new_file:
                            if os.path.exists(doc['file_path']):
                                os.remove(doc['file_path'])
                            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                            final_fpath = f"uploads/{ts}_{new_file.name}"
                            final_fname = new_file.name
                            with open(final_fpath, "wb") as f:
                                f.write(new_file.getvalue())

                        # Tukar thumbnail
                        final_tpath = doc['thumbnail_path']
                        if new_thumb:
                            if doc['thumbnail_path'] and os.path.exists(doc['thumbnail_path']):
                                os.remove(doc['thumbnail_path'])
                            final_tpath = save_thumbnail(new_thumb)

                        # Update database
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("UPDATE documents SET title=?, category=?, file_name=?, file_path=?, thumbnail_path=? WHERE id=?",
                                     (new_title, new_cat, final_fname, final_fpath, final_tpath, doc['id']))
                        conn.commit()
                        conn.close()
                        st.success(f"ID {doc['id']} berjaya dikemaskini!")
                        st.balloons()
                        # Reset session state
                        del st.session_state[key_t]
                        del st.session_state[key_c]
                        st.rerun()

                    if c2.button("PADAM", key=f"del_{doc['id']}", type="secondary"):
                        if st.session_state.get(f"confirm_{doc['id']}", False):
                            # Padam fail
                            if os.path.exists(doc['file_path']): os.remove(doc['file_path'])
                            if doc['thumbnail_path'] and os.path.exists(doc['thumbnail_path']): os.remove(doc['thumbnail_path'])
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("DELETE FROM documents WHERE id=?", (doc['id'],))
                            conn.commit()
                            conn.close()
                            st.success("Standard telah dipadam!")
                            st.balloons()
                            st.rerun()
                        else:
                            st.session_state[f"confirm_{doc['id']}"] = True
                            st.warning("Tekan PADAM sekali lagi untuk confirm")

    # BACKUP & CHAT
    with tab3:
        if st.button("Download Backup ZIP Sekarang", type="primary"):
            zipname = f"FAMA_BACKUP_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
            with zipfile.ZipFile(zipname, "w") as z:
                z.write(DB_NAME)
                for folder in ["uploads", "thumbnails"]:
                    if os.path.exists(folder):
                        for root, _, files in os.walk(folder):
                            for file in files:
                                z.write(os.path.join(root, file), arcname=os.path.join(folder, file))
            with open(zipname, "rb") as f:
                st.download_button("Download Backup ZIP", f.read(), zipname, "application/zip")
            st.success("Backup siap!")

        st.markdown("### Chat Pengguna")
        for m in reversed(get_chat_messages()):
            if m['is_admin']:
                st.success(f"Admin: {m['message']}")
            else:
                st.info(f"{m['sender']}: {m['message']}")
            reply = st.text_input("Balas", key=f"r_{m['id']}")
            if st.button("Hantar Balasan", key=f"s_{m['id']}"):
                if reply.strip():
                    add_chat_message("Admin FAMA", reply.strip(), is_admin=True)
                    st.rerun()

    if st.button("Log Keluar"):
        st.session_state.clear()
        st.rerun()

