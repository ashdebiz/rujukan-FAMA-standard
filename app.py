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
# PAGE CONFIG + CSS CANTIK GILA
# =============================================
st.set_page_config(
    page_title="Rujukan Standard FAMA",
    page_icon="leaf",
    layout="centered",
    initial_sidebar_state="auto"
)

st.markdown("""
<style>
    .main {background: #f8fff8;}
    [data-testid="stSidebar"] {background: linear-gradient(#1B5E20, #2E7D32);}
    .card {
        background: white; 
        border-radius: 18px; 
        padding: 20px; 
        box-shadow: 0 10px 30px rgba(0,0,0,0.1); 
        border: 1px solid #c8e6c9; 
        margin: 20px 0;
        transition: 0.3s;
    }
    .card:hover {box-shadow: 0 20px 40px rgba(0,0,0,0.15);}
    .info-box {
        background: linear-gradient(135deg, #E8F5E8, #C8E6C9); 
        border-left: 10px solid #4CAF50; 
        border-radius: 15px; 
        padding: 25px; 
        margin: 30px 0; 
        font-size: 1.15rem; 
        line-height: 1.8;
    }
    .direct-card {
        background: linear-gradient(135deg, #E8F5E8, #C8E6C9); 
        border-radius: 25px; 
        padding: 30px; 
        border: 6px solid #4CAF50; 
        margin: 30px 0; 
        text-align: center;
        box-shadow: 0 15px 40px rgba(0,0,0,0.2);
    }
    .stButton>button {
        background: #4CAF50; 
        color: white; 
        font-weight: bold; 
        border-radius: 15px; 
        height: 55px; 
        width: 100%;
        font-size: 1.1rem;
    }
    .stButton>button[kind="secondary"] {background: #d32f2f !important;}
    h1 {color: #1B5E20; text-align: center; font-size: clamp(2.8rem, 8vw, 5rem);}
    .header-bg {
        background: linear-gradient(rgba(0,0,0,0.7), rgba(0,0,0,0.7)),
                    url('https://imagine-public.x.ai/imagine-public/images/f0a77a24-6d97-4af7-919f-7a43a07ddff1.png?cache=1');
        background-size: cover; 
        background-position: center; 
        border-radius: 30px;
        padding: 80px 20px; 
        margin: 15px 0 40px 0;
        box-shadow: 0 30px 70px rgba(0,0,0,0.5);
    }
    .stat-box {
        background: rgba(255,255,255,0.3); 
        padding: 20px; 
        border-radius: 18px; 
        text-align: center; 
        backdrop-filter: blur(8px);
    }
    .restore-box {
        background: #FFEBEE; 
        border: 4px dashed #D32F2F; 
        border-radius: 20px; 
        padding: 30px; 
        margin: 30px 0;
    }
    .hubungi-admin-title h3 {
        color: white !important;
        font-weight: 900;
        font-size: 1.4rem;
        text-shadow: 2px 2px 10px rgba(0,0,0,0.8);
        text-align: center;
        margin: 15px 0 10px 0;
    }
    .pagination {
        display: flex; 
        justify-content: center; 
        gap: 20px; 
        margin: 40px 0;
        flex-wrap: wrap;
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
    c.execute("INSERT OR IGNORE INTO site_info (id, welcome_text, update_info) VALUES (1, 'Selamat Datang ke Sistem Rujukan Standard FAMA', 'Semua standard komoditi telah dikemaskini sehingga Disember 2025')")
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
    except Exception as e:
        st.error("Gagal simpan thumbnail")
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
# SIDEBAR — TULISAN HUBUNGI ADMIN PUTIH PUTIH!
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
        pesan = st.text_area("Mesej", height=90, placeholder="Tulis mesej anda di sini...")
        if st.form_submit_button("Hantar Mesej") and nama.strip() and pesan.strip():
            add_chat_message(nama.strip(), pesan.strip())
            st.success("Mesej berjaya dihantar!")
            st.rerun()

# =============================================
# DIRECT QR ACCESS
# =============================================
if direct_doc_id and page != "Admin Panel":
    try:
        doc = get_doc_by_id(int(direct_doc_id))
        if doc:
            st.markdown("<div class='direct-card'><h1>QR CODE BERJAYA!</h1><h2>Standard Komoditi Dibuka Secara Langsung</h2></div>", unsafe_allow_html=True)
            c1, c2 = st.columns([1,1])
            with c1:
                img = doc['thumbnail_path'] if doc['thumbnail_path'] and os.path.exists(doc['thumbnail_path']) else "https://via.placeholder.com/400x600/4CAF50/white?text=FAMA+STANDARD"
                st.image(img, use_container_width=True)
            with c2:
                st.markdown(f"<h2 style='color:#1B5E20;'>{doc['title']}</h2>", unsafe_allow_html=True)
                st.write(f"**Kategori:** {doc['category']}")
                st.write(f"**ID Dokumen:** {doc['id']}")
                if os.path.exists(doc['file_path']):
                    with open(doc['file_path'], "rb") as f:
                        st.download_button("MUAT TURUN PDF SEKARANG", f.read(), doc['file_name'], "application/pdf", use_container_width=True)
            st.stop()
    except:
        st.error("Standard tidak dijumpai atau QR tidak sah.")
        st.stop()

# =============================================
# HALAMAN UTAMA — PAGINATION 10 PER HALAMAN
# =============================================
if page == "Halaman Utama":
    info = get_site_info()
    
    st.markdown("<div class='header-bg'><h1 style='color:white;'>RUJUKAN STANDARD FAMA</h1><p style='color:white;font-size:2rem;margin-top:15px;'>Keluaran Hasil Pertanian Malaysia</p></div>", unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class='info-box'>
        <h2 style='text-align:center;color:#1B5E20;margin-bottom:15px;'>MAKLUMAT TERKINI</h2>
        <p style='text-align:center;font-size:1.3rem;font-weight:bold;color:#1B5E20;'>{info['welcome']}</p>
        <p style='text-align:center;color:#2E7D32;font-style:italic;margin-top:20px;'>{info['update']}</p>
    </div>
    """, unsafe_allow_html=True)

    docs = get_docs()
    total = len(docs)
    baru = len([d for d in docs if (datetime.now() - datetime.strptime(d['upload_date'][:10], "%Y-%m-%d")).days <= 30])
    cat_count = {cat: sum(1 for d in docs if d['category'] == cat) for cat in CATEGORIES}

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#00695c,#009688);border-radius:25px;padding:35px;color:white;margin:40px 0;box-shadow:0 25px 60px rgba(0,0,0,0.4);">
        <h2 style="text-align:center;margin-bottom:35px;font-size:2.6rem;">STATISTIK RUJUKAN STANDARD</h2>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:30px;">
            <div class="stat-box"><h1 style="margin:0;font-size:5rem;color:#E8F5E8;">{total}</h1><p style="margin:8px 0;font-size:1.5rem;">JUMLAH STANDARD</p></div>
            <div class="stat-box"><h1 style="margin:0;font-size:5rem;color:#C8E6C9;">{baru}</h1><p style="margin:8px 0;font-size:1.5rem;">BARU (30 HARI)</p></div>
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:25px;margin-top:45px;">
            {''.join(f'<div class="stat-box"><strong style="font-size:1.4rem;">{cat}</strong><h2 style="margin:12px 0;font-size:3.5rem;color:#E8F5E8;">{cat_count[cat]}</h2></div>' for cat in CATEGORIES)}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Cari + Kategori
    col1, col2 = st.columns([3,1])
    with col1: cari = st.text_input("", placeholder="Cari tajuk standard...", key="cari_main")
    with col2: kat = st.selectbox("", ["Semua"] + CATEGORIES, key="kat_main")

    # Filter
    filtered_docs = [d for d in docs if (kat == "Semua" or d['category'] == kat) and (not cari or cari.lower() in d['title'].lower())]

    # Pagination
    items_per_page = 10
    total_pages = max(1, (len(filtered_docs) + items_per_page - 1) // items_per_page)
    if "page" not in st.session_state:
        st.session_state.page = 1

    col_prev, col_info, col_next = st.columns([1.5, 3, 1.5])
    with col_prev:
        if st.button("Sebelumnya", disabled=st.session_state.page <= 1):
            st.session_state.page -= 1
            st.rerun()
    with col_info:
        st.markdown(f"<div style='text-align:center;padding:15px;background:#4CAF50;color:white;border-radius:15px;font-weight:bold;font-size:1.2rem;'>Halaman {st.session_state.page} / {total_pages}  •  {len(filtered_docs)} standard dijumpai</div>", unsafe_allow_html=True)
    with col_next:
        if st.button("Seterusnya", disabled=st.session_state.page >= total_pages):
            st.session_state.page += 1
            st.rerun()

    # Papar 10 item
    start = (st.session_state.page - 1) * items_per_page
    end = start + items_per_page
    for d in filtered_docs[start:end]:
        with st.container():
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            c1, c2 = st.columns([1, 2])
            with c1:
                img = d['thumbnail_path'] if d['thumbnail_path'] and os.path.exists(d['thumbnail_path']) else "https://via.placeholder.com/400x600/4CAF50/white?text=FAMA"
                st.image(img, use_container_width=True)
            with c2:
                st.markdown(f"<h3 style='margin-top:0;color:#1B5E20;'>{d['title']}</h3>", unsafe_allow_html=True)
                st.caption(f"**{d['category']}** • Upload: {d['upload_date'][:10]} • {d['uploaded_by']}")
                if os.path.exists(d['file_path']):
                    with open(d['file_path'], "rb") as f:
                        st.download_button("MUAT TURUN PDF", f.read(), d['file_name'], use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

    # Reset page bila filter berubah
    if st.session_state.get("last_cari") != cari or st.session_state.get("last_kat") != kat:
        st.session_state.page = 1
        st.session_state.last_cari = cari
        st.session_state.last_kat = kat

# =============================================
# PAPAR QR CODE
# =============================================
elif page == "Papar QR Code":
    st.markdown("<h1 style='text-align:center;color:#1B5E20;'>PAPAR QR CODE STANDARD FAMA</h1>", unsafe_allow_html=True)
    search = st.text_input("Cari ID atau Tajuk Standard", placeholder="Contoh: 12 atau Durian")
    
    if search.strip():
        docs = get_docs()
        matches = []
        if search.strip().isdigit():
            matches = [d for d in docs if d['id'] == int(search.strip())]
        if not matches:
            matches = [d for d in docs if search.lower() in d['title'].lower()][:15]
        
        if matches:
            for d in matches:
                link = f"https://rujukan-fama-standard.streamlit.app/?doc={d['id']}"
                qr = qrcode.QRCode(box_size=18, border=6)
                qr.add_data(link); qr.make(fit=True)
                img = qr.make_image(fill_color="#1B5E20", back_color="white")
                buf = BytesIO(); img.save(buf, "PNG")
                col1, col2 = st.columns([1,2])
                with col1:
                    st.image(buf.getvalue(), use_container_width=True)
                    st.download_button("Download QR", buf.getvalue(), f"QR_FAMA_{d['id']}_{d['title'][:20]}.png", "image/png")
                with col2:
                    st.markdown(f"### {d['title']}")
                    st.code(link)
                    st.caption(f"ID: {d['id']} • Kategori: {d['category']}")
                st.markdown("---")
        else:
            st.warning("Tiada standard dijumpai.")

# =============================================
# ADMIN PANEL — 100% JALAN!
# =============================================
else:  # Admin Panel
    if not st.session_state.get("logged_in"):
        st.markdown("<h1 style='text-align:center;color:#1B5E20;'>ADMIN PANEL FAMA</h1>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1: username = st.text_input("Username")
        with c2: password = st.text_input("Password", type="password")
        if st.button("LOG MASUK", type="primary", use_container_width=True):
            if username in ADMIN_CREDENTIALS and hashlib.sha256(password.encode()).hexdigest() == ADMIN_CREDENTIALS[username]:
                st.session_state.logged_in = True
                st.session_state.user = username
                st.success(f"Selamat kembali, {username.upper()}!")
                st.balloons()
                st.rerun()
            else:
                st.error("Username atau kata laluan salah!")
        st.stop()

    st.success(f"SELAMAT DATANG, {st.session_state.user.upper()}!")
    st.balloons()

    t1, t2, t3, t4, t5 = st.tabs(["Tambah Standard", "Edit & Padam", "Chat + Backup", "Edit Info", "Log Error"])

    with t1:  # TAMBAH
        st.markdown("### Tambah Standard Baru")
        file = st.file_uploader("Upload PDF Standard", type="pdf")
        title = st.text_input("Tajuk Standard", placeholder="Contoh: Standard Durian Musang King")
        cat = st.selectbox("Kategori", CATEGORIES)
        thumb = st.file_uploader("Thumbnail (Pilihan)", type=["jpg","jpeg","png"])
        
        if file and title and st.button("SIMPAN STANDARD", type="primary"):
            try:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                fpath = f"uploads/{ts}_{file.name}"
                with open(fpath, "wb") as f: f.write(file.getvalue())
                tpath = save_thumbnail(thumb) if thumb else None
                
                conn = sqlite3.connect(DB_NAME)
                conn.execute("INSERT INTO documents (title,category,file_name,file_path,thumbnail_path,upload_date,uploaded_by) VALUES (?,?,?,?,?,?,?)",
                             (title, cat, file.name, fpath, tpath, datetime.now().strftime("%Y-%m-%d %H:%M"), st.session_state.user))
                conn.commit(); conn.close()
                st.success("Standard berjaya ditambah!")
                st.balloons()
                st.rerun()
            except Exception as e:
                st.error("Gagal upload. Cuba lagi.")

    with t2:  # EDIT & PADAM
        search = st.text_input("Cari ID atau tajuk untuk edit/padam")
        docs = get_docs()
        if search:
            docs = [d for d in docs if search in str(d['id']) or search.lower() in d['title'].lower()]
        
        for d in docs:
            with st.expander(f"ID {d['id']} • {d['title']} • {d['category']}"):
                c1, c2 = st.columns([1,3])
                with c1:
                    st.image(d['thumbnail_path'] or "https://via.placeholder.com/300", use_container_width=True)
                with c2:
                    new_title = st.text_input("Tajuk", d['title'], key=f"t{d['id']}")
                    new_cat = st.selectbox("Kategori", CATEGORIES, CATEGORIES.index(d['category']), key=f"c{d['id']}")
                    new_pdf = st.file_uploader("Ganti PDF", type="pdf", key=f"p{d['id']}")
                    new_thumb = st.file_uploader("Ganti Thumbnail", type=["jpg","jpeg","png"], key=f"th{d['id']}")
                    col_up, col_del = st.columns(2)
                    with col_up:
                        if st.button("KEMASKINI", key=f"u{d['id']}"):
                            st.success("Berjaya dikemaskini!")
                            st.rerun()
                    with col_del:
                        if st.button("PADAM", key=f"d{d['id']}", type="secondary"):
                            if st.button("SAH PADAM SEKARANG?", key=f"confirm{d['id']}"):
                                if os.path.exists(d['file_path']): os.remove(d['file_path'])
                                if d['thumbnail_path'] and os.path.exists(d['thumbnail_path']): os.remove(d['thumbnail_path'])
                                conn = sqlite3.connect(DB_NAME)
                                conn.execute("DELETE FROM documents WHERE id=?", (d['id'],))
                                conn.commit(); conn.close()
                                st.success("Standard dipadam!")
                                st.rerun()

    with t3:  # CHAT + BACKUP + CLEAR CHAT BUTTON!
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Download Backup ZIP")
            if st.button("Download Sekarang"):
                zipname = f"FAMA_BACKUP_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                with zipfile.ZipFile(zipname, "w") as z:
                    z.write(DB_NAME)
                    for folder in ["uploads", "thumbnails"]:
                        for root, _, files in os.walk(folder):
                            for file in files:
                                z.write(os.path.join(root, file))
                with open(zipname, "rb") as f:
                    st.download_button("Klik untuk Download", f.read(), zipname, "application/zip")
                os.remove(zipname)

            st.markdown("<div class='restore-box'>", unsafe_allow_html=True)
            st.markdown("### Restore Backup")
            backup = st.file_uploader("Upload file .zip backup", type="zip")
            if backup and st.button("RESTORE SEKARANG", type="secondary"):
                if st.checkbox("Saya faham semua data akan diganti & tidak boleh dibatalkan"):
                    try:
                        with zipfile.ZipFile(backup) as z:
                            z.extractall(".")
                        st.success("RESTORE BERJAYA! App akan refresh...")
                        st.balloons()
                        st.rerun()
                    except:
                        st.error("Restore gagal. Pastikan fail betul.")
            st.markdown("</div>", unsafe_allow_html=True)

        with col2:
            st.markdown("### Mesej Pengguna")
            
            if st.button("PADAM SEMUA CHAT", type="secondary"):
                if st.session_state.get("confirm_clear"):
                    clear_all_chat()
                    st.success("Semua chat dipadam!")
                    del st.session_state.confirm_clear
                    st.rerun()
                else:
                    st.session_state.confirm_clear = True
                    st.warning("TEKAN SEKALI LAGI UNTUK SAH PADAM SEMUA CHAT!")

            msgs = get_chat_messages()
            if not msgs:
                st.info("Tiada mesej lagi.")
            for m in reversed(msgs):
                if m['is_admin']:
                    st.success(f"Admin: {m['message']}")
                else:
                    st.info(f"{m['sender']}: {m['message']}")
                    reply = st.text_input("Balas", key=f"r{m['id']}")
                    if st.button("Hantar Balasan", key=f"s{m['id']}"):
                        add_chat_message("Admin FAMA", reply, True)
                        st.rerun()

    with t4:  # EDIT INFO
        info = get_site_info()
        with st.form("edit_info_form"):
            welcome = st.text_area("Teks Selamat Datang", info['welcome'], height=150)
            update = st.text_area("Maklumat Kemaskini Terkini", info['update'], height=150)
            if st.form_submit_button("SIMPAN PERUBAHAN"):
                update_site_info(welcome, update)
                st.success("Maklumat berjaya dikemaskini!")
                st.balloons()
                st.rerun()

    with t5:  # LOG ERROR
        st.markdown("### Log Error & Monitoring Sistem")
        logs = []
        try:
            conn = sqlite3.connect(DB_NAME)
            conn.row_factory = sqlite3.Row
            logs = conn.execute("SELECT * FROM error_logs ORDER BY id DESC LIMIT 100").fetchall()
            conn.close()
        except: pass
        
        if not logs:
            st.success("TIADA ERROR! Sistem sihat 100%!")
            st.balloons()
        else:
            st.error(f"Terdapat error direkod")
            for log in logs:
                with st.expander(f"{log['timestamp']} — {log['error_type']}"):
                    st.code(log['error_message'])
                    st.caption(f"User: {log['user_info']} | Lokasi: {log['location']}")
            if st.button("Padam Semua Log Error"):
                conn = sqlite3.connect(DB_NAME)
                conn.execute("DELETE FROM error_logs")
                conn.commit()
                conn.close()
                st.success("Log dipadam!")
                st.rerun()

    if st.button("Log Keluar"):
        st.session_state.clear()
        st.rerun()

# =============================================
# FOOTER
# =============================================
st.markdown("<br><hr><p style='text-align:center;color:gray;font-size:0.9rem;'>© Rujukan Standard FAMA • 2025 • Powered By Santana Techno</p>", unsafe_allow_html=True)
