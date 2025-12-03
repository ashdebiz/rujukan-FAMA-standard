import streamlit as st
import sqlite3
import os
import os
import zipfile
import shutil
from datetime import datetime
import hashlib
from PIL import Image
import qrcode
from io import BytesIO
import time

# =============================================
# PAGE CONFIG + CSS MANTAP GILA
# =============================================
st.set_page_config(
    page_title="Rujukan FAMA Standard",
    page_icon="leaf",
    layout="centered",
    initial_sidebar_state="auto"
)

st.markdown("""
<style>
    .main {background: #f8fff8;}
    [data-testid="stSidebar"] {background: linear-gradient(#1B5E20, #2E7D32);}
    .card {background: white; border-radius: 18px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); border: 1px solid #c8e6c9; margin: 20px 0;}
    .card:hover {box-shadow: 0 20px 40px rgba(0,0,0,0.15);}
    .info-box {background: linear-gradient(135deg, #E8F5E8, #C8E6C9); border-left: 10px solid #4CAF50; border-radius: 15px; padding: 25px; margin: 30px 0;}
    .direct-card {background: linear-gradient(135deg, #E8F5E8, #C8E6C9); border-radius: 25px; padding: 30px; border: 6px solid #4CAF50; margin: 30px 0; text-align: center; box-shadow: 0 15px 40px rgba(0,0,0,0.2);}
    .stButton>button {background: #4CAF50; color: white; font-weight: bold; border-radius: 15px; height: 55px; width: 100%; font-size: 1.1rem;}
    .stButton>button[kind="secondary"] {background: #d32f2f !important;}
    .header-bg {background: linear-gradient(rgba(0,0,0,0.7), rgba(0,0,0,0.7)), url('https://imagine-public.x.ai/imagine-public/images/f0a77a24-6d97-4af7-919f-7a43a07ddff1.png?cache=1'); background-size: cover; background-position: center; border-radius: 30px; padding: 80px 20px; margin: 15px 0 40px 0; box-shadow: 0 30px 70px rgba(0,0,0,0.5);}
    .stat-box {background: rgba(255,255,255,0.3); padding: 20px; border-radius: 18px; text-align: center; backdrop-filter: blur(8px);}
    .restore-box {background: #FFEBEE; border: 4px dashed #D32F2F; border-radius: 20px; padding: 30px; margin: 30px 0;}
    .hubungi-admin-title h3 {color: white !important; font-weight: 900; font-size: 1.4rem; text-shadow: 2px 2px 10px rgba(0,0,0,0.8); text-align: center;}
</style>
""", unsafe_allow_html=True)

# =============================================
# SETUP FOLDER & DATABASE
# =============================================
for folder in ["uploads", "thumbnails"]:
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
        welcome_text TEXT, update_info TEXT)""")
    c.execute("INSERT OR IGNORE INTO site_info (id, welcome_text, update_info) VALUES (1, 'Selamat Datang ke Sistem Rujukan FAMA Standard', 'Semua standard komoditi telah dikemaskini sehingga Disember 2025')")
    conn.commit()
    conn.close()
init_db()

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
    except: return None

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
    return {"welcome": row[0] if row else "Selamat Datang", "update": row[1] if row else ""}

def update_site_info(welcome, update):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE site_info SET welcome_text=?, update_info=? WHERE id=1", (welcome, update))
    conn.commit()
    conn.close()

# =============================================
# SIDEBAR + DIRECT QR ACCESS
# =============================================
query_params = st.experimental_get_query_params()
direct_doc_id = query_params.get("doc", [None])[0]

with st.sidebar:
    st.markdown("<div style='text-align:center;padding:20px 0;'><img src='https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png' width=120><h3 style='color:white;margin:10px 0;font-weight:900;'>FAMA STANDARD</h3></div>", unsafe_allow_html=True)
    st.markdown("---")
    page = st.selectbox("Menu", ["Halaman Utama", "Papar QR Code", "Admin Panel"], label_visibility="collapsed")
    st.markdown("---")
    st.markdown("<div class='hubungi-admin-title'><h3>Hubungi Admin FAMA</h3></div>", unsafe_allow_html=True)
    
    for msg in get_chat_messages()[-8:]:
        if msg['is_admin']:
            st.markdown(f'<div style="background:#E8F5E8;border-radius:12px;padding:12px;margin:8px 0;text-align:right;border-left:6px solid #4CAF50;"><small><b>Admin</b> • {msg["timestamp"][-5:]}</small><br>{msg["message"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="background:#4CAF50;color:white;border-radius:12px;padding:12px;margin:8px 0;"><small><b>{msg["sender"]}</b> • {msg["timestamp"][-5:]}</small><br>{msg["message"]}</div>', unsafe_allow_html=True)
    
    with st.form("chat_form", clear_on_submit=True):
        nama = st.text_input("Nama Anda")
        pesan = st.text_area("Mesej", height=90)
        if st.form_submit_button("Hantar") and nama.strip() and pesan.strip():
            add_chat_message(nama.strip(), pesan.strip())
            st.success("Mesej dihantar!")
            st.rerun()

# =============================================
# DIRECT QR ACCESS (JALAN KALAU LINK ?doc=123)
# =============================================
if direct_doc_id and page != "Admin Panel":
    try:
        doc = get_doc_by_id(int(direct_doc_id))
        if doc:
            st.markdown("<div class='direct-card'><h1>QR CODE BERJAYA!</h1><h2>Standard Dibuka Secara Langsung</h2></div>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                img = doc['thumbnail_path'] if doc['thumbnail_path'] and os.path.exists(doc['thumbnail_path']) else "https://via.placeholder.com/400x600/4CAF50/white?text=FAMA"
                st.image(img, use_container_width=True)
            with c2:
                st.markdown(f"<h2 style='color:#1B5E20;'>{doc['title']}</h2>", unsafe_allow_html=True)
                st.write(f"**Kategori:** {doc['category']} • **ID:** {doc['id']}")
                if os.path.exists(doc['file_path']):
                    with open(doc['file_path'], "rb") as f:
                        st.download_button("MUAT TURUN PDF", f.read(), doc['file_name'], type="primary", use_container_width=True)
            st.stop()
    except:
        st.error("Standard tidak dijumpai.")
        st.stop()

# =============================================
# HALAMAN UTAMA — FULL FEATURES
# =============================================
if page == "Halaman Utama":
    info = get_site_info()
    
    st.markdown("<div class='header-bg'><h1 style='text-align:center;color:white;'>RUJUKAN FAMA STANDARD</h1><p style='text-align:center;color:white;font-size:2rem;'>Keluaran Hasil Pertanian Malaysia</p></div>", unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class='info-box'>
        <h2 style='text-align:center;color:#1B5E20;'>MAKLUMAT TERKINI</h2>
        <p style='text-align:center;font-weight:bold;font-size:1.3rem;color:#1B5E20;'>{info['welcome']}</p>
        <p style='text-align:center;color:#2E7D32;font-style:italic;'>{info['update']}</p>
    </div>
    """, unsafe_allow_html=True)

    docs = get_docs()
    total = len(docs)
    baru = len([d for d in docs if (datetime.now() - datetime.strptime(d['upload_date'][:10], "%Y-%m-%d")).days <= 30])
    cat_count = {cat: sum(1 for d in docs if d['category'] == cat) for cat in CATEGORIES}

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#00695c,#009688);border-radius:25px;padding:35px;color:white;margin:40px 0;">
        <h2 style="text-align:center;">STATISTIK STANDARD</h2>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:30px;">
            <div class="stat-box"><h1 style="margin:0;color:#E8F5E8;">{total}</h1><p>JUMLAH</p></div>
            <div class="stat-box"><h1 style="margin:0;color:#C8E6C9;">{baru}</h1><p>BARU (30 HARI)</p></div>
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:25px;margin-top:40px;">
            {''.join(f'<div class="stat-box"><strong>{cat}</strong><h2 style="margin:10px 0;color:#E8F5E8;">{cat_count[cat]}</h2></div>' for cat in CATEGORIES)}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Cari + Filter
    col1, col2 = st.columns([3,1])
    with col1: cari = st.text_input("", placeholder="Cari tajuk standard...", key="cari")
    with col2: kat = st.selectbox("", ["Semua"] + CATEGORIES, key="kat")

    filtered = [d for d in docs if (kat == "Semua" or d['category'] == kat) and (not cari or cari.lower() in d['title'].lower())]

    # Pagination
    per_page = 10
    total_page = max(1, (len(filtered) + per_page - 1) // per_page)
    if "page" not in st.session_state: st.session_state.page = 1

    c1, c2, c3 = st.columns([1.5,3,1.5])
    with c1:
        if st.button("Sebelumnya", disabled=st.session_state.page<=1):
            st.session_state.page -= 1; st.rerun()
    with c2:
        st.markdown(f"<div style='text-align:center;padding:15px;background:#4CAF50;color:white;border-radius:15px;font-weight:bold;'>Halaman {st.session_state.page} / {total_page} • {len(filtered)} standard</div>", unsafe_allow_html=True)
    with c3:
        if st.button("Seterusnya", disabled=st.session_state.page>=total_page):
            st.session_state.page += 1; st.rerun()

    start = (st.session_state.page-1) * per_page
    for d in filtered[start:start+per_page]:
        with st.container():
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            c1, c2 = st.columns([1,2])
            with c1:
                img = d['thumbnail_path'] if d['thumbnail_path'] and os.path.exists(d['thumbnail_path']) else "https://via.placeholder.com/400x600/4CAF50/white?text=FAMA"
                st.image(img, use_container_width=True)
            with c2:
                st.markdown(f"<h3 style='margin-top:0;color:#1B5E20;'>{d['title']}</h3>", unsafe_allow_html=True)
                st.caption(f"**{d['category']}** • {d['upload_date'][:10]} • {d['uploaded_by']}")
                if os.path.exists(d['file_path']):
                    with open(d['file_path'], "rb") as f:
                        st.download_button("MUAT TURUN PDF", f.read(), d['file_name'], use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.get("last_cari") != cari or st.session_state.get("last_kat") != kat:
        st.session_state.page = 1
        st.session_state.last_cari = cari
        st.session_state.last_kat = kat

# =============================================
# PAPAR QR CODE
# =============================================
elif page == "Papar QR Code":
    st.markdown("<h1 style='text-align:center;color:#1B5E20;'>PAPAR QR CODE FAMA STANDARD</h1>", unsafe_allow_html=True)
    search = st.text_input("Cari ID atau Tajuk")
    if search.strip():
        matches = [d for d in get_docs() if str(d['id']) == search.strip() or search.lower() in d['title'].lower()][:15]
        for d in matches:
            link = f"https://rujukan-fama-standard.streamlit.app/?doc={d['id']}"
            qr = qrcode.QRCode(box_size=18, border=6)
            qr.add_data(link); qr.make(fit=True)
            img = qr.make_image(fill_color="#1B5E20", back_color="white")
            buf = BytesIO(); img.save(buf, "PNG")
            c1, c2 = st.columns([1,2])
            with c1:
                st.image(buf.getvalue(), use_container_width=True)
                st.download_button("Download QR", buf.getvalue(), f"QR_FAMA_{d['id']}.png", "image/png")
            with c2:
                st.markdown(f"### {d['title']}")
                st.code(link)
            st.markdown("---")

# =============================================
# ADMIN PANEL — FULL POWER
# =============================================
else:
    if not st.session_state.get("logged_in"):
        st.markdown("<h1 style='text-align:center;color:#1B5E20;'>ADMIN PANEL FAMA</h1>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1: username = st.text_input("Username")
        with c2: password = st.text_input("Password", type="password")
        if st.button("LOG MASUK", type="primary", use_container_width=True):
            if username in ADMIN_CREDENTIALS and hashlib.sha256(password.encode()).hexdigest() == ADMIN_CREDENTIALS[username]:
                st.session_state.logged_in = True
                st.session_state.user = username
                st.success("Login berjaya!"); st.balloons(); st.rerun()
            else:
                st.error("Salah bro!")
        st.stop()

    st.success(f"ADMIN: {st.session_state.user.upper()}")
    t1, t2, t3, t4 = st.tabs(["Tambah Standard", "Edit & Padam", "Chat + Backup", "Edit Info"])

    with t1:
        file = st.file_uploader("Upload PDF", type="pdf")
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
                         (title, cat, file.name, fpath, tpath, datetime.now().strftime("%Y-%m-%d %H:%M"), st.session_state.user))
            conn.commit(); conn.close()
            st.success("Berjaya!"); st.balloons(); st.rerun()

    with t2:
        search = st.text_input("Cari ID atau tajuk")
        docs = get_docs()
        if search:
            docs = [d for d in docs if search in str(d['id']) or search.lower() in d['title'].lower()]
        for d in docs:
            with st.expander(f"ID {d['id']} • {d['title']}"):
                new_title = st.text_input("Tajuk", d['title'], key=f"title{d['id']}")
                new_cat = st.selectbox("Kategori", CATEGORIES, CATEGORIES.index(d['category']), key=f"cat{d['id']}")
                if st.button("KEMASKINI", key=f"up{d['id']}"):
                    conn = sqlite3.connect(DB_NAME)
                    conn.execute("UPDATE documents SET title=?, category=? WHERE id=?", (new_title, new_cat, d['id']))
                    conn.commit(); conn.close()
                    st.success("Dikemaskini!"); st.rerun()
                if st.button("PADAM", key=f"del{d['id']}", type="secondary"):
                    if st.button("SAH PADAM?", key=f"cf{d['id']}"):
                        if os.path.exists(d['file_path']): os.remove(d['file_path'])
                        if d['thumbnail_path'] and os.path.exists(d['thumbnail_path']): os.remove(d['thumbnail_path'])
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("DELETE FROM documents WHERE id=?", (d['id'],))
                        conn.commit(); conn.close()
                        st.success("Dipadam!"); st.rerun()

    with t3:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Download Backup ZIP"):
                zipname = f"FAMA_BACKUP_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
                with zipfile.ZipFile(zipname, "w", zipfile.ZIP_DEFLATED) as z:
                    z.write(DB_NAME)
                    for folder in ["uploads", "thumbnails"]:
                        for root, _, files in os.walk(folder):
                            for file in files:
                                z.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file)))
                with open(zipname, "rb") as f:
                    st.download_button("Download Backup", f.read(), zipname)
                os.remove(zipname)

            st.markdown("<div class='restore-box'>", unsafe_allow_html=True)
            uploaded = st.file_uploader("Upload backup .zip", type="zip")
            if uploaded and st.checkbox("Saya faham data akan diganti"):
                if st.button("RESTORE SEKARANG", type="secondary"):
                    with st.spinner("Restoring..."):
                        for f in ["uploads", "thumbnails"]:
                            if os.path.exists(f): shutil.rmtree(f); os.makedirs(f)
                        with zipfile.ZipFile(uploaded) as z:
                            z.extractall(".")
                        st.success("RESTORE 100% BERJAYA!")
                        st.balloons()
                        time.sleep(2)
                        st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        with c2:
            if st.button("PADAM SEMUA CHAT", type="secondary"):
                if st.session_state.get("confirm_clear"):
                    clear_all_chat()
                    st.success("Chat dipadam!"); del st.session_state.confirm_clear; st.rerun()
                else:
                    st.session_state.confirm_clear = True
                    st.warning("Tekan sekali lagi untuk sah!")

            for m in reversed(get_chat_messages()):
                if m['is_admin']:
                    st.success(f"Admin: {m['message']}")
                else:
                    st.info(f"{m['sender']}: {m['message']}")
                    r = st.text_input("Balas", key=f"r{m['id']}")
                    if st.button("Hantar", key=f"s{m['id']}"):
                        add_chat_message("Admin FAMA", r, True); st.rerun()

    with t4:
        info = get_site_info()
        with st.form("edit_info"):
            w = st.text_area("Teks Selamat Datang", info['welcome'], height=150)
            u = st.text_area("Maklumat Terkini", info['update'], height=150)
            if st.form_submit_button("SIMPAN"):
                update_site_info(w, u)
                st.success("Berjaya!"); st.rerun()

    if st.button("Log Keluar"):
        st.session_state.clear()
        st.rerun()

st.markdown("<p style='text-align:center;color:gray;font-size:0.9rem;'>© Rujukan Standard FAMA • 2025 • Powered By Santana Techno!</p>", unsafe_allow_html=True)
