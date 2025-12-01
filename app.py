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
# CONFIG & DESIGN PREMIUM FAMA
# =============================================
st.set_page_config(page_title="Rujukan Standard FAMA", page_icon="leaf", layout="centered", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .main {background: #f8fff8;}
    [data-testid="stSidebar"] {background: linear-gradient(#1B5E20, #2E7D32);}
    .card {background: white; border-radius: 20px; padding: 25px; box-shadow: 0 12px 35px rgba(0,0,0,0.12); border: 1px solid #c8e6c9; margin: 20px 0;}
    .qr-container {background: white; border-radius: 30px; padding: 50px; text-align: center; box-shadow: 0 25px 60px rgba(27,94,32,0.25); border: 6px solid #4CAF50; margin: 50px 0;}
    .direct-card {background: linear-gradient(135deg, #E8F5E8, #C8E6C9); border-radius: 25px; padding: 30px; border: 4px solid #4CAF50; margin: 30px 0;}
    .stButton>button {background: #4CAF50; color: white; font-weight: bold; border-radius: 15px; height: 60px; border: none; font-size:1.1rem;}
    .stButton>button[kind="secondary"] {background: #d32f2f !important;}
    h1,h2,h3 {color: #1B5E20;}
    .header-bg {
        background: linear-gradient(rgba(0,0,0,0.58), rgba(0,0,0,0.58)), 
                    url('https://imagine-public.x.ai/imagine-public/images/f0a77a24-6d97-4af7-919f-7a43a07ddff1.png?cache=1?q=80&w=2070&auto=format&fit=crop');
        background-size: cover; background-position: center; border-radius: 35px;
        padding: 90px 20px; text-align: center; margin: 20px 0 50px 0;
        box-shadow: 0 30px 70px rgba(0,0,0,0.45);
    }
    .stat-box {background: rgba(255,255,255,0.25); padding: 30px; border-radius: 20px; text-align: center; backdrop-filter: blur(5px);}
    .search-admin {background: linear-gradient(135deg, #E8F5E8, #C8E6C9); padding: 25px; border-radius: 20px; border: 4px solid #4CAF50; margin-bottom: 30px;}
    .restore-box {background: #FFEBEE; border: 4px dashed #D32F2F; border-radius: 20px; padding: 30px; text-align: center; margin: 30px 0;}
</style>
""", unsafe_allow_html=True)

# Buat folder
for folder in ["uploads", "thumbnails", "backup_temp"]:
    os.makedirs(folder, exist_ok=True)

DB_NAME = "fama_standards.db"
CATEGORIES = ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"]

ADMIN_CREDENTIALS = {
    "admin": hashlib.sha256("fama2025".encode()).hexdigest(),
    "pengarah": hashlib.sha256("fama123".encode()).hexdigest()
}

# =============================================
# DATABASE & FUNGSI ASAS
# =============================================
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
    conn.execute("INSERT INTO chat_messages (sender, message, timestamp, is_admin) VALUES (?,?,?,?)",
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

# =============================================
# QR DIRECT + SIDEBAR
# =============================================
query_params = st.experimental_get_query_params()
direct_doc_id = query_params.get("doc", [None])[0]

with st.sidebar:
    st.markdown("<div style='text-align:center;padding:25px 0;'><img src='https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png' width=120><h3 style='color:white;margin:10px 0;font-weight:900;'>REGULASI PASARAN</h3></div>", unsafe_allow_html=True)
    st.markdown("---")
    page = st.selectbox("Menu", ["Halaman Utama", "Papar QR Code", "Admin Panel"], label_visibility="collapsed")
    st.markdown("---")
    st.markdown("### Hubungi Admin FAMA")
    for msg in get_chat_messages()[-10:]:
        if msg['is_admin']:
            st.markdown(f'<div style="background:#E8F5E8;border-radius:12px;padding:12px;margin:8px 0;text-align:right;border-left:5px solid #4CAF50;"><small><b>Admin</b> • {msg["timestamp"][-5:]}</small><br>{msg["message"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="background:#4CAF50;color:white;border-radius:12px;padding:12px;margin:8px 0;"><small><b>{msg["sender"]}</b> • {msg["timestamp"][-5:]}</small><br>{msg["message"]}</div>', unsafe_allow_html=True)
    with st.form("chat_form", clear_on_submit=True):
        nama = st.text_input("Nama Anda")
        pesan = st.text_area("Mesej", height=80)
        if st.form_submit_button("Hantar"):
            if nama.strip() and pesan.strip():
                add_chat_message(nama.strip(), pesan.strip())
                st.success("Dihantar!")
                st.rerun()

# =============================================
# DIRECT QR OPEN
# =============================================
if direct_doc_id and page != "Admin Panel":
    try:
        doc = get_doc_by_id(int(direct_doc_id))
        if doc:
            st.markdown("<div class='direct-card'><h1 style='text-align:center;color:#1B5E20;'>QR CODE BERJAYA!</h1></div>", unsafe_allow_html=True)
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            c1,c2 = st.columns([1,2])
            with c1:
                img = doc['thumbnail_path'] if doc['thumbnail_path'] and os.path.exists(doc['thumbnail_path']) else "https://via.placeholder.com/400x600/4CAF50/white?text=FAMA"
                st.image(img, use_container_width=True)
            with c2:
                st.markdown(f"<h2 style='color:#1B5E20;margin-top:0;'>{doc['title']}</h2>", unsafe_allow_html=True)
                st.write(f"**Kategori:** {doc['category']} • **ID:** {doc['id']}")
                if os.path.exists(doc['file_path']):
                    with open(doc['file_path'],"rb") as f:
                        st.download_button("MUAT TURUN PDF", f.read(), doc['file_name'], use_container_width=True, type="primary")
            st.markdown("</div>", unsafe_allow_html=True)
            st.stop()
    except:
        st.error("Standard tidak dijumpai.")

# =============================================
# HALAMAN UTAMA + STATISTIK
# =============================================
if page == "Halaman Utama":
    st.markdown("<div class='header-bg'><h1 style='color:white;font-size:5rem;text-align:center;'>RUJUKAN STANDARD FAMA</h1></div>", unsafe_allow_html=True)
    docs = get_docs()
    total = len(docs)
    baru = len([d for d in docs if (datetime.now() - datetime.strptime(d['upload_date'][:10], "%Y-%m-%d")).days <= 30])
    cat_count = {c: sum(1 for d in docs if d['category'] == c) for c in CATEGORIES}

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#00695c,#009688);border-radius:25px;padding:35px;color:white;margin:40px 0;box-shadow:0 20px 50px rgba(0,0,0,0.35);">
        <h2 style="text-align:center;margin:0 0 30px 0;font-size:2.5rem;">STATISTIK RUJUKAN STANDARD FAMA</h2>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:30px;">
            <div class="stat-box"><h1 style="margin:0;font-size:5rem;">{total}</h1><p style="margin:10px 0 0 0;font-size:1.6rem;">JUMLAH STANDARD</p></div>
            <div class="stat-box"><h1 style="margin:0;font-size:5rem;">{baru}</h1><p style="margin:10px 0 0 0;font-size:1.6rem;">BARU (30 HARI)</p></div>
        </div>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:25px;margin-top:40px;">
            {''.join(f'<div class="stat-box"><strong style="font-size:1.4rem;">{c}</strong><br><h2 style="margin:15px 0;font-size:3.2rem;">{cat_count.get(c,0)}</h2></div>' for c in CATEGORIES)}
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([3,1])
    with col1: cari = st.text_input("", placeholder="Cari tajuk standard...", key="cari_main")
    with col2: kat = st.selectbox("", ["Semua"] + CATEGORIES, key="kat_main")

    hasil = [d for d in docs if (kat == "Semua" or d['category'] == kat) and (not cari or cari.lower() in d['title'].lower())]
    for d in hasil:
        with st.container():
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            c1,c2 = st.columns([1,3])
            with c1:
                img = d['thumbnail_path'] if d['thumbnail_path'] and os.path.exists(d['thumbnail_path']) else "https://via.placeholder.com/400x600/4CAF50/white?text=FAMA"
                st.image(img, use_container_width=True)
            with c2:
                st.markdown(f"<h3 style='color:#1B5E20;margin:0;'>{d['title']}</h3>", unsafe_allow_html=True)
                st.caption(f"**{d['category']}** • Upload: {d['upload_date'][:10]} • {d['uploaded_by']}")
                if os.path.exists(d['file_path']):
                    with open(d['file_path'],"rb") as f:
                        st.download_button("MUAT TURUN PDF", f.read(), d['file_name'], use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

# =============================================
# PAPAR QR CODE
# =============================================
elif page == "Papar QR Code":
    st.markdown("<h1 style='text-align:center;color:#1B5E20;'>PAPAR QR CODE STANDARD FAMA</h1>", unsafe_allow_html=True)
    search = st.text_input("Cari ID / Tajuk", key="qr_search")
    if search:
        docs = get_docs()
        try:
            sid = int(search.strip())
            matches = [d for d in docs if d['id'] == sid]
        except:
            matches = [d for d in docs if search.lower() in d['title'].lower()]
        if matches:
            for d in matches:
                link = f"https://rujukan-fama-standard.streamlit.app?doc={d['id']}"
                qr = qrcode.QRCode(box_size=16, border=6)
                qr.add_data(link); qr.make(fit=True)
                img = qr.make_image(fill_color="#1B5E20", back_color="white")
                buf = BytesIO(); img.save(buf, format="PNG")
                c1,c2 = st.columns([1,2])
                with c1:
                    st.image(buf.getvalue(), width=350)
                    st.download_button("Download QR", buf.getvalue(), f"QR_FAMA_{d['id']}.png", "image/png")
                with c2:
                    st.markdown(f"<h2 style='color:#1B5E20;margin-top:60px;'>{d['title']}</h2>", unsafe_allow_html=True)
                    st.code(link)
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.error("Tiada dijumpai!")

# =============================================
# ADMIN PANEL — ADA UPLOAD & RESTORE BACKUP!
# =============================================
else:
    if not st.session_state.get("logged_in"):
        st.markdown("<h1 style='text-align:center;color:#1B5E20;'>ADMIN PANEL FAMA</h1>", unsafe_allow_html=True)
        c1,c2 = st.columns(2)
        with c1: user = st.text_input("Username")
        with c2: pwd = st.text_input("Password", type="password")
        if st.button("LOG MASUK", type="primary"):
            if user in ADMIN_CREDENTIALS and hashlib.sha256(pwd.encode()).hexdigest() == ADMIN_CREDENTIALS[user]:
                st.session_state.logged_in = True
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Salah!")
        st.stop()

    st.success(f"Selamat Datang, {st.session_state.user.upper()}!")
    st.balloons()

    tab1, tab2, tab3 = st.tabs(["Tambah Standard", "Edit & Padam", "Chat + Backup + Restore"])

    with tab1:
        file = st.file_uploader("Upload PDF", type="pdf")
        title = st.text_input("Tajuk Standard")
        cat = st.selectbox("Kategori", CATEGORIES)
        thumb = st.file_uploader("Thumbnail (pilihan)", type=["jpg","jpeg","png"])
        if file and title and st.button("SIMPAN STANDARD", type="primary"):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fpath = f"uploads/{ts}_{file.name}"
            with open(fpath,"wb") as f: f.write(file.getvalue())
            tpath = save_thumbnail(thumb) if thumb else None
            conn = sqlite3.connect(DB_NAME)
            conn.execute("INSERT INTO documents (title,category,file_name,file_path,thumbnail_path,upload_date,uploaded_by) VALUES (?,?,?,?,?,?,?)",
                         (title,cat,file.name,fpath,tpath,datetime.now().strftime("%Y-%m-%d %H:%M"),st.session_state.user))
            conn.commit(); conn.close()
            st.success("Ditambah!"); st.rerun()

    with tab2:
        st.markdown("<div class='search-admin'><h3 style='text-align:center;color:#1B5E20;margin:0;'>CARI STANDARD UNTUK EDIT / PADAM</h3>", unsafe_allow_html=True)
        admin_search = st.text_input("ID atau tajuk", key="admin_cari", label_visibility="collapsed")
        st.markdown("</div>", unsafe_allow_html=True)

        all_docs = get_docs()
        if admin_search.strip():
            try:
                sid = int(admin_search.strip())
                docs_show = [d for d in all_docs if d['id'] == sid]
            except:
                docs_show = [d for d in all_docs if admin_search.lower() in d['title'].lower()]
        else:
            docs_show = all_docs

        for idx, d in enumerate(docs_show):
            with st.expander(f"ID {d['id']} • {d['title']}"):
                c1,c2 = st.columns([1,3])
                with c1:
                    st.image(d['thumbnail_path'] or "https://via.placeholder.com/300", use_container_width=True)
                with c2:
                    nt = st.text_input("Tajuk", d['title'], key=f"t_{d['id']}_{idx}")
                    nc = st.selectbox("Kategori", CATEGORIES, CATEGORIES.index(d['category']), key=f"c_{d['id']}_{idx}")
                    np = st.file_uploader("Ganti PDF", type="pdf", key=f"p_{d['id']}_{idx}")
                    nth = st.file_uploader("Ganti Thumbnail", type=["jpg","jpeg","png"], key=f"th_{d['id']}_{idx}")

                    if st.button("KEMASKINI", key=f"upd_{d['id']}_{idx}", type="primary"):
                        updates = []; params = []
                        if nt != d['title']: updates.append("title=?"); params.append(nt)
                        if nc != d['category']: updates.append("category=?"); params.append(nc)
                        if np:
                            new_fp = f"uploads/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{np.name}"
                            with open(new_fp,"wb") as f: f.write(np.getvalue())
                            updates.append("file_name=?,file_path=?"); params.extend([np.name, new_fp])
                            if os.path.exists(d['file_path']): os.remove(d['file_path'])
                        if nth:
                            new_tp = save_thumbnail(nth)
                            if new_tp:
                                updates.append("thumbnail_path=?"); params.append(new_tp)
                                if d['thumbnail_path'] and os.path.exists(d['thumbnail_path']): os.remove(d['thumbnail_path'])
                        if updates:
                            params.append(d['id'])
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute(f"UPDATE documents SET {', '.join(updates)} WHERE id=?", params)
                            conn.commit(); conn.close()
                            st.success("Dikemaskini!"); st.rerun()

                    if st.button("PADAM", key=f"del_{d['id']}_{idx}", type="secondary"):
                        if st.session_state.get(f"confirm_{d['id']}_{idx}", False):
                            if os.path.exists(d['file_path']): os.remove(d['file_path'])
                            if d['thumbnail_path'] and os.path.exists(d['thumbnail_path']): os.remove(d['thumbnail_path'])
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("DELETE FROM documents WHERE id=?", (d['id'],))
                            conn.commit(); conn.close()
                            st.success("Dipadam!"); st.rerun()
                        else:
                            st.session_state[f"confirm_{d['id']}_{idx}"] = True
                            st.warning("Tekan sekali lagi untuk confirm padam!")

    with tab3:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### Download Backup ZIP")
            if st.button("Download Backup Sekarang", type="primary"):
                zipname = f"FAMA_BACKUP_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
                with zipfile.ZipFile(zipname,"w") as z:
                    z.write(DB_NAME)
                    for folder in ["uploads","thumbnails"]:
                        for root,_,files in os.walk(folder):
                            for file in files:
                                z.write(os.path.join(root,file))
                with open(zipname,"rb") as f:
                    st.download_button("Download ZIP", f.read(), zipname, "application/zip")
                os.remove(zipname)
                st.success("Backup siap!")

        with col2:
            st.markdown("### Upload & Restore Backup")
            st.markdown("<div class='restore-box'>", unsafe_allow_html=True)
            st.markdown("<h3 style='color:#D32F2F;'>PERINGATAN: SEMUA DATA AKAN DIGANTI!</h3>", unsafe_allow_html=True)
            backup_file = st.file_uploader("Pilih fail backup .zip", type=["zip"], key="restore_file")
            if backup_file and st.button("RESTORE BACKUP SEKARANG", type="secondary"):
                if st.session_state.get("confirm_restore", False):
                    with st.spinner("Sedang restore backup..."):
                        temp_zip = "backup_temp/restore.zip"
                        with open(temp_zip, "wb") as f:
                            f.write(backup_file.getvalue())
                        # Padam semua
                        if os.path.exists(DB_NAME): os.remove(DB_NAME)
                        for folder in ["uploads", "thumbnails"]:
                            if os.path.exists(folder):
                                shutil.rmtree(folder)
                                os.makedirs(folder)
                        # Extract
                        with zipfile.ZipFile(temp_zip, 'r') as z:
                            z.extractall(".")
                        st.cache_data.clear()
                        st.success("BACKUP BERJAYA DIRESTORE!")
                        st.balloons()
                        st.experimental_rerun()
                else:
                    st.session_state.confirm_restore = True
                    st.warning("TEKAN SEKALI LAGI UNTUK SAH RESTORE!")

            if st.session_state.get("confirm_restore"):
                if st.button("BATAL RESTORE"):
                    st.session_state.confirm_restore = False
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("### Mesej Pengguna")
        for m in reversed(get_chat_messages()):
            if m['is_admin']:
                st.success(f"Admin: {m['message']}")
            else:
                st.info(f"{m['sender']}: {m['message']}")
                balas = st.text_input("Balas", key=f"b{m['id']}")
                if st.button("Hantar", key=f"s{m['id']}"):
                    add_chat_message("Admin FAMA", balas, True)
                    st.rerun()

        if st.button("PADAM SEMUA CHAT", type="primary"):
            if st.session_state.get("confirm_clear", False):
                clear_all_chat()
                st.success("Semua chat dipadam!")
                del st.session_state["confirm_clear"]
                st.rerun()
            else:
                st.session_state["confirm_clear"] = True
                st.warning("Tekan sekali lagi untuk padam semua chat!")

    if st.button("Log Keluar"):
        st.session_state.clear()
        st.rerun()

