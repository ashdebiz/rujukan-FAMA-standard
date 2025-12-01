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
# CONFIG & DESIGN CANTIK + BACKGROUND BUAH-SAYUR
# =============================================
st.set_page_config(page_title="Rujukan Standard FAMA", page_icon="leaf", layout="centered", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .main {background: #f8fff8;}
    [data-testid="stSidebar"] {background: linear-gradient(#1B5E20, #2E7D32);}
    .card {background: white; border-radius: 20px; padding: 25px; box-shadow: 0 12px 35px rgba(0,0,0,0.12); border: 1px solid #c8e6c9; margin: 20px 0;}
    .qr-container {background: white; border-radius: 30px; padding: 50px; text-align: center; box-shadow: 0 25px 60px rgba(27,94,32,0.25); border: 6px solid #4CAF50; margin: 50px 0;}
    .stButton>button {background: #4CAF50; color: white; font-weight: bold; border-radius: 15px; height: 60px; border: none; font-size:1.1rem;}
    h1,h2,h3 {color: #1B5E20;}
    .sidebar-title {color: #ffffff; font-size: 2.3rem; font-weight: 900; text-align: center; text-shadow: 4px 4px 12px rgba(0,0,0,0.7);}
    .header-bg {
        background: linear-gradient(rgba(0,0,0,0.58), rgba(0,0,0,0.58)), 
                    url('https://imagine-public.x.ai/imagine-public/images/f0a77a24-6d97-4af7-919f-7a43a07ddff1.png?cache=1?q=80&w=2070&auto=format&fit=crop');
        background-size: cover; background-position: center; border-radius: 35px;
        padding: 90px 20px; text-align: center; margin: 20px 0 50px 0;
        box-shadow: 0 30px 70px rgba(0,0,0,0.45);
    }
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
# INIT DB & FUNGSI ASAS (sama macam sebelum ni)
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

def save_thumbnail(file_obj):
    if not file_obj: return None
    try:
        img = Image.open(file_obj).convert("RGB")
        img.thumbnail((400, 600))
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

def get_doc_by_id(doc_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

# =============================================
# TANGKAP QUERY PARAMS — INI YANG BUAT QR CODE SPESIFIK!
# =============================================
query_params = st.experimental_get_query_params()
direct_doc_id = query_params.get("doc", [None])[0]

# =============================================
# SIDEBAR
# =============================================
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding:25px 0;">
        <img src="https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png" width="120">
        <h3 class="sidebar-title">FAMA STANDARD</h3>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")
    page = st.selectbox("Menu", ["Halaman Utama", "Papar QR Code", "Admin Panel"], label_visibility="collapsed")
    st.markdown("---")
    st.markdown("### Hubungi Admin FAMA")
    # chat code sama macam sebelum ni...

# =============================================
# DIRECT OPEN DARI QR CODE — SPESIFIK KOMODITI!
# =============================================
if direct_doc_id and page != "Admin Panel":
    doc = get_doc_by_id(int(direct_doc_id))
    if doc:
        st.markdown(f"""
        <div style="background:#E8F5E8; padding:30px; border-radius:25px; text-align:center; margin:30px 0; border:4px solid #4CAF50;">
            <h1 style="color:#1B5E20; margin:0;">QR CODE BERJAYA!</h1>
            <p style="font-size:1.4rem; color:#2E7D32;">Standard komoditi berikut telah dibuka:</p>
        </div>
        """, unsafe_allow_html=True)

        with st.container():
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            c1, c2 = st.columns([1,2])
            with c1:
                img = doc['thumbnail_path'] if doc['thumbnail_path'] and os.path.exists(doc['thumbnail_path']) else "https://via.placeholder.com/400x600/4CAF50/white?text=FAMA"
                st.image(img, use_container_width=True)
            with c2:
                st.markdown(f"<h2 style='color:#1B5E20;'>{doc['title']}</h2>", unsafe_allow_html=True)
                st.markdown(f"**Kategori:** {doc['category']} | **ID:** {doc['id']} | **Upload:** {doc['upload_date'][:10]}")
                if os.path.exists(doc['file_path']):
                    with open(doc['file_path'], "rb") as f:
                        st.download_button("MUAT TURUN PDF SEKARANG", f.read(), doc['file_name'], 
                                         use_container_width=True, type="primary")
            st.markdown("</div>", unsafe_allow_html=True)
        st.stop()  # stop execution supaya tak tunjuk benda lain

# =============================================
# HALAMAN UTAMA (kalau takde QR)
# =============================================
if page == "Halaman Utama":
    st.markdown(f"""
    <div class="header-bg">
        <h1 style="color:white; font-size:5rem; font-weight:900; margin:0; text-shadow: 6px 6px 18px rgba(0,0,0,0.9);">RUJUKAN STANDARD FAMA</h1>
        <p style="color:white; font-size:2rem; margin:20px 0 0 0; text-shadow: 4px 4px 12px rgba(0,0,0,0.9);">Keluaran Hasil Pertanian Tempatan Malaysia</p>
    </div>
    """, unsafe_allow_html=True)

    # statistik + senarai standard (sama macam sebelum ni)

# =============================================
# PAPAR QR CODE — LINK DAH BETUL + SPESIFIK!
# =============================================
elif page == "Papar QR Code":
    st.markdown("<h1 style='text-align:center;color:#1B5E20;'>PAPAR QR CODE STANDARD FAMA</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;font-size:1.5rem;color:#2E7D32;margin:30px 0;'>Taip ID atau nama komoditi</p>", unsafe_allow_html=True)

    search = st.text_input("Cari ID / Tajuk", key="qr_search", placeholder="Contoh: 25 atau Durian")

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
                
                # LINK YANG BETUL — SPESIFIK KE KOMODITI
                current_url = "https://rujukan-fama-standard.streamlit.app"  # tukar kalau nama app lain
                qr_link = f"{current_url}?doc={d['id']}"

                qr = qrcode.QRCode(version=1, box_size=16, border=6)
                qr.add_data(qr_link)
                qr.make(fit=True)
                img = qr.make_image(fill_color="#1B5E20", back_color="white")
                buf = BytesIO()
                img.save(buf, format="PNG")

                col1, col2 = st.columns([1,2])
                with col1:
                    st.image(buf.getvalue(), width=350)
                    st.download_button("Download QR Code", buf.getvalue(), 
                                     f"QR_FAMA_{d['id']}_{d['title'][:15].replace(' ', '_')}.png", "image/png")
                with col2:
                    st.markdown(f"<h2 style='color:#1B5E20;margin-top:50px;'>{d['title']}</h2>", unsafe_allow_html=True)
                    st.write(f"**ID:** {d['id']} | **Kategori:** {d['category']}")
                    st.code(qr_link, language=None)
                    st.markdown(f"<p><strong>Bila di-scan → terus tunjuk standard ini sahaja!</strong></p>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.error("Tiada komoditi dijumpai!")

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
