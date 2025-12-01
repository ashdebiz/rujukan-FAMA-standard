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
    .sidebar-logo-container {text-align: center; padding: 30px 0;}
    .sidebar-logo-container img {width: 100px; margin-bottom: 15px;}
    .sidebar-title {color: #ffffff; font-size: 1.8rem; font-weight: 900; margin: 0; text-shadow: 2px 2px 8px rgba(0,0,0,0.5);}
</style>
""", unsafe_allow_html=True)

# Buat folder
for f in ["uploads", "thumbnails", "backups"]:
    os.makedirs(f, exist_ok=True)

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
    cur.execute('''CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, category TEXT,
        file_name TEXT, file_path TEXT, thumbnail_path TEXT, upload_date TEXT, uploaded_by TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, sender TEXT, message TEXT, timestamp TEXT, is_admin INTEGER DEFAULT 0)''')
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
        img.save(path, "JPEG", quality=90)
        return path
    except Exception as e:
        st.error(f"Error simpan thumbnail: {e}")
        return None

def get_docs():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM documents ORDER BY upload_date DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@st.cache_data(ttl=1)
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

def clear_all_chat():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM chat_messages")
    conn.commit()
    conn.close()
    st.cache_data.clear()
    st.rerun()

# =============================================
# STATISTIK BIRU CANTIK
# =============================================
def show_stats():
    docs = get_docs()
    total = len(docs)
    baru = len([d for d in docs if d['upload_date'][:10] >= (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")]) if docs else 0
    latest = max((d['upload_date'][:10] for d in docs), default="Belum ada") if docs else "Belum ada"
    cat_count = {c: sum(1 for d in docs if d['category'] == c) for c in CATEGORIES}
    st.markdown(f"""
    <div style="background:linear-gradient(to bottom, #0066ff 0%, #0099ff 100%); border-radius:25px; padding:25px; color:white; margin:20px 0;">
        <h2 style="text-align:center;">STATISTIK RUJUKAN FAMA STANDARD</h2>
        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:20px; text-align:center;">
            <div style="background:rgba(255,255,255,0.15); border-radius:18px; padding:18px;">
                <h1 style="margin:0; font-size:2rem;">{total}</h1><p>JUMLAH</p>
            </div>
            <div style="background:rgba(255,255,255,0.15); border-radius:18px; padding:18px;">
                <h1 style="margin:0; font-size:2rem;">{baru}</h1><p>BARU (30 HARI)</p>
            </div>
            <div style="background:rgba(255,255,255,0.15); border-radius:18px; padding:18px;">
                <h1 style="margin:0; font-size:1.5rem;">{latest}</h1><p>TERKINI</p>
            </div>
        </div>
        <div style="margin-top:25px; display:grid; grid-template-columns: repeat(4,1fr); gap:15px;">
            {''.join(f'<div style="background:rgba(255,255,255,0.1); border-radius:12px; padding:12px;"><strong>{c}</strong><br>{cat_count.get(c,0)}</div>' for c in CATEGORIES)}
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
    page = st.selectbox("Menu", ["Halaman Utama", "Papar QR Code", "Admin Panel"], label_visibility="collapsed")
    st.markdown("---")
    st.markdown("#### Hubungi Admin FAMA")

    for msg in get_chat_messages()[-12:]:
        if msg['is_admin']:
            st.markdown(f'<div style="background:#E8F5E8; border-radius:12px; padding:10px 14px; margin:8px 0; max-width:88%; margin-left:auto; border-left:4px solid #4CAF50;"><small><strong>Admin FAMA</strong> • {msg["timestamp"][-5:]}</small><br>{msg["message"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="background:#4CAF50; color:white; border-radius:12px; padding:10px 14px; margin:8px 0; max-width:88%;"><small><strong>{msg["sender"]}</strong> • {msg["timestamp"][-5:]}</small><br>{msg["message"]}</div>', unsafe_allow_html=True)

    with st.form("chat_form", clear_on_submit=True):
        nama = st.text_input("Nama")
        pesan = st.text_input("Mesej")
        if st.form_submit_button("Hantar"):
            if nama.strip() and pesan.strip():
                add_chat_message(nama.strip(), pesan.strip())
                st.success("Dihantar!")
                st.rerun()

# =============================================
# HALAMAN UTAMA
# =============================================
if page == "Halaman Utama":
    st.markdown('<div style="position:relative; border-radius:25px; overflow:hidden; box-shadow:0 15px 40px rgba(27,94,32,0.5); margin:20px 0;"><img src="https://w7.pngwing.com/pngs/34/259/png-transparent-fruits-and-vegetables.png" style="width:100%; height:300px; object-fit:cover;"><div style="position:absolute; top:0; left:0; width:100%; height:100%; background: linear-gradient(135deg, rgba(27,94,32,0.85), rgba(76,175,80,0.75));"></div><div style="position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); text-align:center;"><h1 style="color:white; font-size:3.3rem; font-weight:900;">RUJUKAN FAMA STANDARD</h1><p style="color:#e8f5e8; font-size:1.5rem;">Keluaran Hasil Pertanian Tempatan</p></div></div>', unsafe_allow_html=True)
    
    show_stats()
    
    col1, col2 = st.columns([3,1])
    with col1: cari = st.text_input("", placeholder="Cari tajuk standard...")
    with col2: kat = st.selectbox("", ["Semua"] + CATEGORIES)
    
    docs = get_docs()
    hasil = [d for d in docs if (kat == "Semua" or d['category'] == kat) and (not cari or cari.lower() in d['title'].lower())]
    
    st.markdown(f"<h3>Ditemui {len(hasil)} Standard</h3>", unsafe_allow_html=True)
    
    for d in hasil:
        with st.container():
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            c1, c2 = st.columns([1,3])
            with c1:
                img = d['thumbnail_path'] if d['thumbnail_path'] and os.path.exists(d['thumbnail_path']) else "https://via.placeholder.com/350x500/4CAF50/white?text=FAMA"
                st.image(img, use_container_width=True)
            with c2:
                st.markdown(f"<h2 style='margin:0; color:#1B5E20;'>{d['title']}</h2>", unsafe_allow_html=True)
                st.caption(f"**{d['category']}** • {d['upload_date'][:10]} • {d['uploaded_by']}")
                if d['file_path'] and os.path.exists(d['file_path']):
                    with open(d['file_path'], "rb") as f:
                        st.download_button("MUAT TURUN PDF", f.read(), d['file_name'], use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

# =============================================
# PAPAR QR CODE
# =============================================
elif page == "Papar QR Code":
    st.markdown("<h1 style='text-align:center; color:#1B5E20;'>CARI & PAPAR QR CODE</h1>", unsafe_allow_html=True)
    show_stats()
    search = st.text_input("", placeholder="Taip nama standard...").strip()
    if not search:
        st.info("Taip nama standard untuk papar QR Code")
    else:
        matches = [d for d in get_docs() if search.lower() in d['title'].lower()]
        if not matches:
            st.warning("Tiada padanan")
        for d in matches:
            qr = qrcode.QRCode(box_size=15, border=8)
            qr.add_data(f"https://rujukan-fama-standard.streamlit.app/?doc={d['id']}")
            qr.make(fit=True)
            img = qr.make_image(fill_color="#1B5E20", back_color="white")
            buf = io.BytesIO()
            img.save(buf, "PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            st.markdown(f'<div class="qr-container"><h2 style="color:#1B5E20;">{d["title"]}</h2><p style="color:#4CAF50;"><strong>{d["category"]}</strong></p><img src="data:image/png;base64,{b64}" width="400"></div>', unsafe_allow_html=True)

# =============================================
# ADMIN PANEL — BOLEH EDIT FAIL PDF + THUMBNAIL + TAJUK + KATEGORI
# =============================================
else:  # Admin Panel
    if not st.session_state.get("logged_in"):
        st.title("ADMIN PANEL FAMA")
        col1, col2 = st.columns(2)
        with col1: username = st.text_input("Username")
        with col2: password = st.text_input("Kata Laluan", type="password")
        if st.button("Log Masuk"):
            h = hashlib.sha256(password.encode()).hexdigest()
            if username in ADMIN_CREDENTIALS and ADMIN_CREDENTIALS[username] == h:
                st.session_state.logged_in = True
                st.session_state.user = username
                st.rerun()
            else:
                st.error("Salah username/password")
        st.stop()

    st.success(f"Selamat Datang, {st.session_state.user.upper()}!")

    tab1, tab2, tab3, tab4 = st.tabs(["Tambah Standard", "Edit & Padam", "Backup & Restore", "Chat Pengguna"])

    # TAMBAH STANDARD
    with tab1:
        uploaded_file = st.file_uploader("Upload PDF/DOCX", type=["pdf","docx"])
        title = st.text_input("Tajuk Standard")
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
                conn.execute("INSERT INTO documents (title, category, file_name, file_path, thumbnail_path, upload_date, uploaded_by) VALUES (?,?,?,?,?,?,?)",
                             (title, category, uploaded_file.name, file_path, thumb_path, datetime.now().strftime("%Y-%m-%d %H:%M"), st.session_state.user))
                conn.commit()
                conn.close()
                st.success("Berjaya disimpan!")
                st.balloons()
                st.rerun()

    # EDIT & PADAM — BOLEH TUKAR FAIL PDF SEKALI!
    with tab2:
        docs = get_docs()
        if not docs:
            st.info("Tiada standard lagi")
        for doc in docs:
            with st.expander(f"ID {doc['id']} • {doc['title']} • {doc['category']}"):
                col1, col2 = st.columns([1, 3])
                with col1:
                    img_path = doc['thumbnail_path'] if doc['thumbnail_path'] and os.path.exists(doc['thumbnail_path']) else "https://via.placeholder.com/300x420/4CAF50/white?text=FAMA"
                    st.image(img_path, use_container_width=True)

                with col2:
                    # Simpan nilai dalam session_state
                    if f"title_{doc['id']}" not in st.session_state:
                        st.session_state[f"title_{doc['id']}"] = doc['title']
                    if f"cat_{doc['id']}" not in st.session_state:
                        try:
                            st.session_state[f"cat_{doc['id']}"] = CATEGORIES.index(doc['category'])
                        except:
                            st.session_state[f"cat_{doc['id']}"] = 0

                    new_title = st.text_input("Tajuk", value=st.session_state[f"title_{doc['id']}"], key=f"t_{doc['id']}")
                    new_category = st.selectbox("Kategori", CATEGORIES, index=st.session_state[f"cat_{doc['id']}"],
                                               key=f"c_{doc['id']}")
                    new_thumb = st.file_uploader("Tukar Thumbnail", type=["jpg","jpeg","png"], key=f"thumb_{doc['id']}")
                    new_file = st.file_uploader("TUKAR FAIL STANDARD (PDF/DOCX)", type=["pdf","docx"], key=f"file_{doc['id']}")

                    # Update session_state
                    st.session_state[f"title_{doc['id']}"] = new_title
                    st.session_state[f"cat_{doc['id']}"] = CATEGORIES.index(new_category)

                    col_upd, col_del = st.columns(2)
                    if col_upd.button("KEMASKINI SEMUA", key=f"upd_{doc['id']}", type="primary"):
                        # Proses fail baru
                        final_file_path = doc['file_path']
                        final_file_name = doc['file_name']
                        if new_file:
                            if os.path.exists(doc['file_path']):
                                os.remove(doc['file_path'])
                            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                            final_file_path = f"uploads/{ts}_{new_file.name}"
                            final_file_name = new_file.name
                            with open(final_file_path, "wb") as f:
                                f.write(new_file.getvalue())

                        # Proses thumbnail baru
                        final_thumb_path = doc['thumbnail_path']
                        if new_thumb:
                            if doc['thumbnail_path'] and os.path.exists(doc['thumbnail_path']):
                                os.remove(doc['thumbnail_path'])
                            final_thumb_path = save_thumbnail(new_thumb)

                        # Update database
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("""
                            UPDATE documents SET title=?, category=?, file_name=?, file_path=?, thumbnail_path=? WHERE id=?
                        """, (new_title, new_category, final_file_name, final_file_path, final_thumb_path, doc['id']))
                        conn.commit()
                        conn.close()

                        st.success(f"Standard ID {doc['id']} berjaya dikemaskini (termasuk fail PDF & thumbnail)!")
                        st.balloons()
                        st.rerun()

                    if col_del.button("PADAM", key=f"del_{doc['id']}", type="secondary"):
                        if st.session_state.get(f"confirm_{doc['id']}", False):
                            if os.path.exists(doc['file_path']): os.remove(doc['file_path'])
                            if doc['thumbnail_path'] and os.path.exists(doc['thumbnail_path']): os.remove(doc['thumbnail_path'])
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("DELETE FROM documents WHERE id=?", (doc['id'],))
                            conn.commit()
                            conn.close()
                            st.success("Standard telah dipadam selamanya!")
                            st.balloons()
                            st.rerun()
                        else:
                            st.session_state[f"confirm_{doc['id']}"] = True
                            st.warning("Tekan PADAM sekali lagi untuk confirm")

    # BACKUP & RESTORE
    with tab3:
        if st.button("Download Backup Lengkap", type="primary"):
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
            st.success("Semua data & fail berjaya dipulihkan!")
            st.balloons()
            st.rerun()

    # CHAT PENGGUNA
    with tab4:
        if st.button("Padam Semua Chat"):
            if st.button("Confirm Padam Semua"):
                clear_all_chat()
        st.markdown("---")
        for m in reversed(get_chat_messages()):
            sender = "Admin FAMA" if m['is_admin'] else m['sender']
            st.markdown(f"**{sender}** • {m['timestamp']}")
            st.info(m['message'])
            reply = st.text_input("Balas", key=f"r_{m['id']}")
            if st.button("Hantar Balasan", key=f"s_{m['id']}"):
                if reply.strip():
                    add_chat_message("Admin FAMA", reply.strip(), is_admin=True)
                    st.success("Balasan dihantar!")
                    st.rerun()

    if st.button("Log Keluar"):
        st.session_state.clear()
        st.rerun()

