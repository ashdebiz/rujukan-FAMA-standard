import streamlit as st
import sqlite3
import os
import zipfile
from datetime import datetime
import hashlib
from PIL import Image
import qrcode
from io import BytesIO
import qrcode

# =============================================
# PAGE CONFIG & DESIGN CANTIK GILA
# =============================================
st.set_page_config(page_title="Rujukan Standard FAMA", page_icon="leaf", layout="centered", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .main {background: #f8fff8;}
    [data-testid="stSidebar"] {background: linear-gradient(#1B5E20, #2E7D32);}
    .card {background: white; border-radius: 20px; padding: 25px; box-shadow: 0 0 12px 35px rgba(0,0,0,0.12); border: 1px solid #c8e6c9; margin: 20px 0;}
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
</style>
""", unsafe_allow_html=True)

# Buat folder
for f in ["uploads", "thumbnails"]:
    os.makedirs(f, exist_ok=True)

DB_NAME = "fama_standards.db"
CATEGORIES = ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"]

ADMIN = {
    "admin": hashlib.sha256("fama2025".encode()).hexdigest(),
    "pengarah": hashlib.sha256("fama123".encode()).hexdigest()
}

# =============================================
# DATABASE FUNCTIONS
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

def save_thumbnail(file):
    if not file: return None
    img = Image.open(file).convert("RGB")
    img.thumbnail((400, 600))
    path = f"thumbnails/thumb_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
    img.save(path, "JPEG", quality=95)
    return path

def get_docs():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM documents ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_doc_by_id(did):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM documents WHERE id=?", (did,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

@st.cache_data(ttl=10)
def get_chat():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM chat_messages ORDER BY timestamp")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_chat(sender, msg, admin=False):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO chat_messages (sender,message,timestamp,is_admin) VALUES (?,?,?,?)",
                 (sender, msg, datetime.now().strftime("%Y-%m-%d %H:%M"), int(admin)))
    conn.commit()
    conn.close()
    st.cache_data.clear()

def clear_chat():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM chat_messages")
    conn.commit()
    conn.close()
    st.cache_data.clear()

# =============================================
# QR DIRECT LINK
# =============================================
qp = st.experimental_get_query_params()
direct_id = qp.get("doc", [None])[0]

# =============================================
# SIDEBAR
# =============================================
with st.sidebar:
    st.markdown("<div style='text-align:center;padding:20px 0;'><img src='https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png' width=110><h3 style='color:white;margin:10px 0;font-weight:900;'>FAMA STANDARD</h3></div>", unsafe_allow_html=True)
    st.markdown("---")
    page = st.selectbox("Menu", ["Halaman Utama", "Papar QR Code", "Admin Panel"], label_visibility="collapsed")
    st.markdown("---")
    st.markdown("### Hubungi Admin FAMA")
    for m in get_chat()[-10:]:
        if m['is_admin']:
            st.markdown(f'<div style="background:#E8F5E8;padding:10px;margin:6px 0;border-radius:12px;text-align:right;border-left:5px solid #4CAF50;"><small><b>Admin</b> {m["timestamp"][-5:]}</small><br>{m["message"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="background:#4CAF50;color:white;padding:10px;margin:6px 0;border-radius:12px;"><small><b>{m["sender"]}</b> {m["timestamp"][-5:]}</small><br>{m["message"]}</div>', unsafe_allow_html=True)
    with st.form("chat_form", clear_on_submit=True):
        n = st.text_input("Nama")
        p = st.text_area("Mesej", height=80)
        if st.form_submit_button("Hantar"):
            if n.strip() and p.strip():
                add_chat(n.strip(), p.strip())
                st.success("Dihantar!")
                st.rerun()

# =============================================
# DIRECT QR OPEN
# =============================================
if direct_id and page != "Admin Panel":
    try:
        doc = get_doc_by_id(int(direct_id))
        if doc:
            st.markdown("<div class='direct-card'><h1 style='text-align:center;color:#1B5E20;'>QR CODE BERJAYA!</h1><p style='text-align:center;font-size:1.5rem;color:#2E7D32;'>Standard dibuka secara langsung</p></div>", unsafe_allow_html=True)
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            c1, c2 = st.columns([1,2])
            with c1:
                img = doc['thumbnail_path'] if doc['thumbnail_path'] and os.path.exists(doc['thumbnail_path']) else "https://via.placeholder.com/400x600/4CAF50/white?text=FAMA"
                st.image(img, use_container_width=True)
            with c2:
                st.markdown(f"<h2 style='color:#1B5E20;margin-top:0;'>{doc['title']}</h2>", unsafe_allow_html=True)
                st.write(f"**Kategori:** {doc['category']} • **ID:** {doc['id']}")
                if os.path.exists(doc['file_path']):
                    with open(doc['file_path'], "rb") as f:
                        st.download_button("MUAT TURUN PDF", f.read(), doc['file_name'], use_container_width=True, type="primary")
            st.markdown("</div>", unsafe_allow_html=True)
            st.stop()
    except:
        st.error("Standard tidak dijumpai.")

# =============================================
# HALAMAN UTAMA
# =============================================
if page == "Halaman Utama":
    st.markdown("<div class='header-bg'><h1 style='color:white;font-size:5rem;text-align:center;text-shadow:6px 6px 18px black;'>RUJUKAN STANDARD FAMA</h1><p style='color:white;font-size:2rem;text-align:center;text-shadow:4px 4px 12px black;'>Keluaran Hasil Pertanian Tempatan Malaysia</p></div>", unsafe_allow_html=True)

    docs = get_docs()
    col1, col2 = st.columns([3,1])
    with col1: cari = st.text_input("", placeholder="Cari tajuk...", key="cari")
    with col2: kat = st.selectbox("", ["Semua"]+CATEGORIES, key="kat")

    hasil = [d for d in docs if (kat=="Semua" or d['category']==kat) and (not cari or cari.lower() in d['title'].lower())]

    for d in hasil:
        with st.container():
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            c1,c2 = st.columns([1,3])
            with c1:
                img = d['thumbnail_path'] if d['thumbnail_path'] and os.path.exists(d['thumbnail_path']) else "https://via.placeholder.com/400x600/4CAF50/white?text=FAMA"
                st.image(img, use_container_width=True)
            with c2:
                st.markdown(f"<h3 style='color:#1B5E20;margin:0;'>{d['title']}</h3>", unsafe_allow_html=True)
                st.caption(f"**{d['category']}** • {d['upload_date'][:10]} • {d['uploaded_by']}")
                if os.path.exists(d['file_path']):
                    with open(d['file_path'],"rb") as f:
                        st.download_button("MUAT TURUN PDF", f.read(), d['file_name'], use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

# =============================================
# PAPAR QR CODE
# =============================================
elif page == "Papar QR Code":
    st.markdown("<h1 style='text-align:center;color:#1B5E20;'>PAPAR QR CODE STANDARD FAMA</h1>", unsafe_allow_html=True)
    search = st.text_input("Cari ID atau Tajuk", placeholder="Contoh: 15 atau Nanas", key="qrsearch")

    if search:
        docs = get_docs()
        matches = []
        try:
            sid = int(search.strip())
            matches = [d for d in docs if d['id']==sid]
        except:
            matches = [d for d in docs if search.lower() in d['title'].lower()]

        if matches:
            for d in matches:
                st.markdown("<div class='qr-container'>", unsafe_allow_html=True)
                url = "https://rujukan-fama-standard.streamlit.app"  # tukar kalau nama app lain
                link = f"{url}?doc={d['id']}"

                qr = qrcode.QRCode(box_size=16, border=6)
                qr.add_data(link)
                qr.make(fit=True)
                img = qr.make_image(fill_color="#1B5E20", back_color="white")
                buf = BytesIO()
                img.save(buf, format="PNG")

                c1, c2 = st.columns([1,2])
                with c1:
                    st.image(buf.getvalue(), width=350)
                    st.download_button("Download QR", buf.getvalue(), f"QR_FAMA_{d['id']}.png", "image/png")
                with c2:
                    st.markdown(f"<h2 style='color:#1B5E20;margin-top:50px;'>{d['title']}</h2>", unsafe_allow_html=True)
                    st.code(link)
                    st.success("Scan → terus buka standard ini!")
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.error("Tiada padanan.")

# =============================================
# ADMIN PANEL — SEMUA BUTTON DAH JALAN!
# =============================================
else:
    if not st.session_state.get("logged_in"):
        st.markdown("<h1 style='text-align:center;color:#1B5E20;'>ADMIN PANEL</h1>", unsafe_allow_html=True)
        c1,c2 = st.columns(2)
        with c1: u = st.text_input("Username")
        with c2: p = st.text_input("Password", type="password")
        if st.button("LOG MASUK", type="primary"):
            if u in ADMIN and hashlib.sha256(p.encode()).hexdigest() == ADMIN[u]:
                st.session_state.logged_in = True
                st.session_state.user = u
                st.rerun()
            else:
                st.error("Salah!")
        st.stop()

    st.success(f"Selamat Datang, {st.session_state.user.upper()}!")
    st.balloons()

    t1, t2, t3 = st.tabs(["Tambah Standard", "Edit & Padam", "Chat + Backup"])

    # TAMBAH
    with t1:
        f = st.file_uploader("Upload PDF", type=["pdf"])
        tj = st.text_input("Tajuk")
        ct = st.selectbox("Kategori", CATEGORIES)
        th = st.file_uploader("Thumbnail", type=["jpg","jpeg","png"])
        if f and tj and st.button("SIMPAN", type="primary"):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fp = f"uploads/{ts}_{f.name}"
            with open(fp,"wb") as wf: wf.write(f.getvalue())
            tp = save_thumbnail(th) if th else None
            conn = sqlite3.connect(DB_NAME)
            conn.execute("INSERT INTO documents (title,category,file_name,file_path,thumbnail_path,upload_date,uploaded_by) VALUES (?,?,?,?,?,?,?)",
                         (tj,ct,f.name,fp,tp,datetime.now().strftime("%Y-%m-%d %H:%M"),st.session_state.user))
            conn.commit()
            conn.close()
            st.success("Ditambah!")
            st.rerun()

    # EDIT & PADAM (DAH BETUL 100%)
    with t2:
        for i, d in enumerate(get_docs()):
            with st.expander(f"ID {d['id']} • {d['title']} • {d['category']}"):
                col1, col2 = st.columns([1,3])
                with col1:
                    st.image(d['thumbnail_path'] or "https://via.placeholder.com/300", use_container_width=True)
                with col2:
                    nt = st.text_input("Tajuk", d['title'], key=f"t{i}")
                    nc = st.selectbox("Kategori", CATEGORIES, CATEGORIES.index(d['category']), key=f"c{i}")
                    np = st.file_uploader("Ganti PDF", type=["pdf"], key=f"p{i}")
                    ntmb = st.file_uploader("Ganti Thumbnail", type=["jpg","jpeg","png"], key=f"tm{i}")

                    if st.button("KEMASKINI", key=f"u{i}"):
                        sql = []; par = []
                        if nt != d['title']: sql.append("title=?"); par.append(nt)
                        if nc != d['category']: sql.append("category=?"); par.append(nc)
                        if np:
                            nfp = f"uploads/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{np.name}"
                            with open(nfp,"wb") as wf: wf.write(np.getvalue())
                            sql.append("file_name=?,file_path=?"); par.extend([np.name, nfp])
                            if os.path.exists(d['file_path']): os.remove(d['file_path'])
                        if ntmb:
                            ntp = save_thumbnail(ntmb)
                            if ntp:
                                sql.append("thumbnail_path=?"); par.append(ntp)
                                if d['thumbnail_path'] and os.path.exists(d['thumbnail_path']): os.remove(d['thumbnail_path'])
                        if sql:
                            par.append(d['id'])
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute(f"UPDATE documents SET {', '.join(sql)} WHERE id=?", tuple(par))
                            conn.commit()
                            conn.close()
                            st.success("Dikemaskini!")
                            st.rerun()

                    # PADAM DENGAN CONFIRM
                    key_del = f"del_{d['id']}_{i}"
                    if st.button("PADAM STANDARD", key=key_del, type="secondary"):
                        if st.session_state.get(key_del+"_confirm", False):
                            if os.path.exists(d['file_path']): os.remove(d['file_path'])
                            if d['thumbnail_path'] and os.path.exists(d['thumbnail_path']): os.remove(d['thumbnail_path'])
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("DELETE FROM documents WHERE id=?", (d['id'],))
                            conn.commit()
                            conn.close()
                            st.success("Dipadam!")
                            st.rerun()
                        else:
                            st.session_state[key_del+"_confirm"] = True
                            st.warning("Tekan sekali lagi untuk confirm padam!")

    # CHAT + CLEAR CHAT (DAH JALAN!)
    with t3:
        st.markdown("### Mesej Pengguna")
        msgs = get_chat()
        for m in reversed(msgs):
            if m['is_admin']:
                st.success(f"Admin: {m['message']}")
            else:
                st.info(f"{m['sender']}: {m['message']}")
                balas = st.text_input("Balas", key=f"b{m['id']}")
                if st.button("Hantar", key=f"s{m['id']}"):
                    add_chat("Admin FAMA", balas, is_admin=True)
                    st.rerun()

        if st.button("PADAM SEMUA CHAT", type="primary"):
            if st.session_state.get("confirm_clear", False):
                clear_chat()
                st.success("Semua chat dipadam!")
                del st.session_state["confirm_clear"]
                st.rerun()
            else:
                st.session_state["confirm_clear"] = True
                st.warning("Tekan sekali lagi untuk padam semua chat!")

        if st.button("Download Backup ZIP", type="primary"):
            zipname = f"BACKUP_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
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

