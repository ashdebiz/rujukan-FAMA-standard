import streamlit as st
import sqlite3
import os
import zipfile
from datetime import datetime, timedelta
import hashlib
from PIL import Image

# =============================================
# CONFIG & DESIGN FAMA GEMPUR
# =============================================
st.set_page_config(page_title="Rujukan Standard FAMA", page_icon="leaf", layout="centered", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .main {background: #f8fff8;}
    [data-testid="stSidebar"] {background: linear-gradient(#1B5E20, #2E7D32);}
    .card {background: white; border-radius: 20px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); border: 1px solid #c8e6c9; margin: 15px 0;}
    .stButton>button {background: #4CAF50; color: white; font-weight: bold; border-radius: 15px; height: 55px; border: none;}
    h1,h2,h3 {color: #1B5E20;}
    .search-box {background: white; padding: 20px; border-radius: 20px; box-shadow: 0 8px 25px rgba(0,0,0,0.1); margin: 20px 0; border: 3px solid #4CAF50;}
    .stats-box {background: linear-gradient(135deg, #00695c, #009688); border-radius: 25px; padding: 30px; color: white; margin: 30px 0; box-shadow: 0 15px 35px rgba(0,0,0,0.3);}
    .sidebar-title {color: #ffffff; font-size: 2.3rem; font-weight: 900; text-align: center; text-shadow: 4px 4px 12px rgba(0,0,0,0.7);}
</style>
""", unsafe_allow_html=True)

# Folder
for f in ["uploads", "thumbnails"]:
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
    cur.execute("""CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        title TEXT, category TEXT, file_name TEXT, file_path TEXT, 
        thumbnail_path TEXT, upload_date TEXT, uploaded_by TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        sender TEXT, message TEXT, timestamp TEXT, is_admin INTEGER DEFAULT 0)""")
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
    st.image("https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png", width=120)
    st.markdown("<h3 class='sidebar-title'>FAMA STANDARD</h3>", unsafe_allow_html=True)
    st.markdown("---")
    page = st.selectbox("Menu", ["Halaman Utama", "Admin Panel"], label_visibility="collapsed")
    st.markdown("---")
    st.markdown("### Hubungi Admin FAMA")
    
    for msg in get_chat_messages()[-8:]:
        if msg['is_admin']:
            st.markdown(f'<div style="background:#E8F5E8;padding:10px;border-radius:12px;margin:6px 0;text-align:right;border-left:5px solid #4CAF50;"><small><b>Admin</b><br>{msg["message"]}</small></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="background:#4CAF50;color:white;padding:10px;border-radius:12px;margin:6px 0;"><small><b>{msg["sender"]}</b><br>{msg["message"]}</small></div>', unsafe_allow_html=True)
    
    with st.form("chat_form", clear_on_submit=True):
        nama = st.text_input("Nama Anda")
        pesan = st.text_input("Tanya soalan standard...")
        if st.form_submit_button("Hantar"):
            if nama.strip() and pesan.strip():
                add_chat_message(nama.strip(), pesan.strip())
                st.success("Mesej dihantar!")
                st.rerun()

# =============================================
# HALAMAN UTAMA — CANTIK GILA BALIK!
# =============================================
if page == "Halaman Utama":
    st.markdown("""
    <div style="text-align:center; padding:50px 0; background:linear-gradient(135deg,#E8F5E8,#C8E6C9); border-radius:30px; margin:20px 0;">
        <h1 style="font-size:4.5rem; font-weight:900; color:#1B5E20; margin:0; text-shadow: 3px 3px 10px rgba(0,0,0,0.3);">RUJUKAN STANDARD FAMA</h1>
        <p style="font-size:1.8rem; color:#2E7D32; margin:15px 0 0 0;">Keluaran Hasil Pertanian Tempatan Malaysia</p>
    </div>
    <img src="https://w7.pngwing.com/pngs/34/259/png-transparent-fruits-and-vegetables.png" style="width:100%; max-width:900px; display:block; margin:0 auto; border-radius:25px; box-shadow:0 20px 50px rgba(0,0,0,0.3);">
    """, unsafe_allow_html=True)

    # STATISTIK POWER
    docs = get_docs()
    total = len(docs)
    baru = len([d for d in docs if (datetime.now() - datetime.strptime(d['upload_date'][:10], "%Y-%m-%d")).days <= 30])
    cat_count = {c: sum(1 for d in docs if d['category'] == c) for c in CATEGORIES}

    st.markdown(f"""
    <div class="stats-box">
        <h2 style="text-align:center;">STATISTIK RUJUKAN FAMA</h2>
        <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:25px; margin:30px 0;">
            <div style="background:rgba(255,255,255,0.3); padding:25px; border-radius:18px; text-align:center;">
                <h1 style="margin:0; font-size:3.5rem;">{total}</h1>
                <p style="margin:8px 0 0 0; font-size:1.3rem;">JUMLAH STANDARD</p>
            </div>
            <div style="background:rgba(255,255,255,0.3); padding:25px; border-radius:18px; text-align:center;">
                <h1 style="margin:0; font-size:3.5rem;">{baru}</h1>
                <p style="margin:8px 0 0 0; font-size:1.3rem;">BARU (30 HARI)</p>
            </div>
        </div>
        <div style="display:grid; grid-template-columns:repeat(4,1fr); gap:15px;">
            {''.join(f'<div style="background:rgba(255,255,255,0.25);padding:18px;border-radius:15px;text-align:center;"><strong>{c}</strong><br><h2 style="margin:10px 0;">{cat_count[c]}</h2></div>' for c in CATEGORIES)}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Carian
    col1, col2 = st.columns([3,1])
    with col1: cari = st.text_input("", placeholder="Cari tajuk standard...", key="cari_utama")
    with col2: kat = st.selectbox("", ["Semua"] + CATEGORIES, key="kat_utama")

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
                st.markdown(f"<h3 style='color:#1B5E20; margin:0;'>{d['title']}</h3>", unsafe_allow_html=True)
                st.caption(f"**{d['category']}** • Upload: {d['upload_date'][:10]} • {d['uploaded_by']}")
                if os.path.exists(d['file_path']):
                    with open(d['file_path'], "rb") as f:
                        st.download_button("MUAT TURUN PDF", f.read(), d['file_name'], use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

# =============================================
# ADMIN PANEL — FULL POWER
# =============================================
else:
    if not st.session_state.get("logged_in"):
        st.markdown("<h1 style='text-align:center;color:#1B5E20;'>ADMIN PANEL FAMA</h1>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1: user = st.text_input("Username")
        with c2: pwd = st.text_input("Password", type="password")
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

    with tab1:
        file = st.file_uploader("Upload PDF/DOCX", type=["pdf","docx"])
        title = st.text_input("Tajuk Standard")
        cat = st.selectbox("Kategori", CATEGORIES)
        thumb = st.file_uploader("Thumbnail (pilihan)", type=["jpg","jpeg","png"])
        if file and title and st.button("SIMPAN STANDARD", type="primary"):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fpath = f"uploads/{ts}_{file.name}"
            with open(fpath, "wb") as f: f.write(file.getvalue())
            tpath = save_thumbnail(thumb) if thumb else None
            conn = sqlite3.connect(DB_NAME)
            conn.execute("INSERT INTO documents (title,category,file_name,file_path,thumbnail_path,upload_date,uploaded_by) VALUES (?,?,?,?,?,?,?)",
                         (title, cat, file.name, fpath, tpath, datetime.now().strftime("%Y-%m-%d %H:%M"), st.session_state.user))
            conn.commit()
            conn.close()
            st.success("Berjaya ditambah!")
            st.balloons()
            st.rerun()

    with tab2:
        st.markdown("<div class='search-box'><h3>Cari & Edit Standard</h3>", unsafe_allow_html=True)
        search = st.text_input("Cari tajuk / ID / kategori", key="admin_search")
        st.markdown("</div>", unsafe_allow_html=True)

        docs = get_docs()
        if search:
            s = search.strip().lower()
            docs = [d for d in docs if s in d['title'].lower() or s in str(d['id']) or s in d['category'].lower()]

        st.write(f"**Ditemui {len(docs)} standard**")

        for d in docs:
            with st.expander(f"ID {d['id']} • {d['title']} • {d['category']}"):
                col1, col2 = st.columns([1,3])
                with col1:
                    img = d['thumbnail_path'] if d['thumbnail_path'] and os.path.exists(d['thumbnail_path']) else "https://via.placeholder.com/300/4CAF50/white?text=FAMA"
                    st.image(img, use_container_width=True)
                with col2:
                    key_t = f"title_{d['id']}"
                    key_c = f"cat_{d['id']}"
                    if key_t not in st.session_state: st.session_state[key_t] = d['title']
                    if key_c not in st.session_state: st.session_state[key_c] = CATEGORIES.index(d['category'])

                    new_title = st.text_input("Tajuk", st.session_state[key_t], key=f"t{d['id']}")
                    new_cat = st.selectbox("Kategori", CATEGORIES, st.session_state[key_c], key=f"c{d['id']}")
                    new_thumb = st.file_uploader("Tukar Thumbnail", type=["jpg","jpeg","png"], key=f"th{d['id']}")
                    new_file = st.file_uploader("TUKAR FAIL PDF", type=["pdf","docx"], key=f"f{d['id']}")

                    st.session_state[key_t] = new_title
                    st.session_state[key_c] = CATEGORIES.index(new_cat)

                    c1, c2 = st.columns(2)
                    if c1.button("KEMASKINI", key=f"up{d['id']}", type="primary"):
                        fp = d['file_path']
                        fn = d['file_name']
                        if new_file:
                            if os.path.exists(fp): os.remove(fp)
                            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                            fp = f"uploads/{ts}_{new_file.name}"
                            fn = new_file.name
                            with open(fp, "wb") as f: f.write(new_file.getvalue())
                        tp = d['thumbnail_path']
                        if new_thumb:
                            if tp and os.path.exists(tp): os.remove(tp)
                            tp = save_thumbnail(new_thumb)
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("UPDATE documents SET title=?,category=?,file_name=?,file_path=?,thumbnail_path=? WHERE id=?", 
                                     (new_title, new_cat, fn, fp, tp, d['id']))
                        conn.commit()
                        conn.close()
                        st.success("Kemaskini berjaya!")
                        st.balloons()
                        st.rerun()

                    if c2.button("PADAM", key=f"del{d['id']}"):
                        if st.session_state.get(f"cf{d['id']}", False):
                            if os.path.exists(d['file_path']): os.remove(d['file_path'])
                            if d['thumbnail_path'] and os.path.exists(d['thumbnail_path']): os.remove(d['thumbnail_path'])
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("DELETE FROM documents WHERE id=?", (d['id'],))
                            conn.commit()
                            conn.close()
                            st.success("Dipadam selamanya!")
                            st.rerun()
                        else:
                            st.session_state[f"cf{d['id']}"] = True
                            st.warning("Tekan sekali lagi untuk confirm")

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
                st.download_button("Download ZIP Backup", f.read(), zipname)
            st.success("Backup siap!")

        st.markdown("### Chat Pengguna")
        for m in reversed(get_chat_messages()):
            if m['is_admin']:
                st.success(f"Admin: {m['message']}")
            else:
                st.info(f"{m['sender']}: {m['message']}")
            reply = st.text_input("Balas", key=f"r{m['id']}")
            if st.button("Hantar", key=f"s{m['id']}"):
                if reply:
                    add_chat_message("Admin FAMA", reply, True)
                    st.rerun()

    if st.button("Log Keluar"):
        st.session_state.clear()
        st.rerun()

