import streamlit as st
import os, zipfile, shutil, time, hashlib
from datetime import datetime
from io import BytesIO
from PIL import Image
import qrcode

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(
    page_title="Rujukan FAMA Standard",
    page_icon="leaf",
    layout="centered"
)

# =====================================================
# DATABASE (NEON)
# =====================================================
engine = create_engine(
    st.secrets["DATABASE_URL"],
    pool_pre_ping=True
)
Session = sessionmaker(bind=engine)

# =====================================================
# TEST CONNECTION (NO REDACT)
# =====================================================
try:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
except Exception as e:
    st.error("❌ Database connection failed")
    st.exception(e)
    st.stop()

# =====================================================
# SETUP FOLDER
# =====================================================
for folder in ["uploads", "thumbnails"]:
    os.makedirs(folder, exist_ok=True)

CATEGORIES = ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"]

ADMIN_CREDENTIALS = {
    "admin": hashlib.sha256("fama2025".encode()).hexdigest(),
    "pengarah": hashlib.sha256("fama123".encode()).hexdigest()
}

# =====================================================
# INIT DB
# =====================================================
def init_db():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS documents (
                id SERIAL PRIMARY KEY,
                title TEXT,
                category TEXT,
                file_name TEXT,
                file_path TEXT,
                thumbnail_path TEXT,
                upload_date TEXT,
                uploaded_by TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id SERIAL PRIMARY KEY,
                sender TEXT,
                message TEXT,
                timestamp TEXT,
                is_admin BOOLEAN DEFAULT FALSE
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS site_info (
                id INTEGER PRIMARY KEY,
                welcome_text TEXT,
                update_info TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO site_info (id, welcome_text, update_info)
            VALUES (1, 'Selamat Datang ke Sistem Rujukan FAMA Standard',
                    'Semua standard dikemaskini sehingga Disember 2025')
            ON CONFLICT (id) DO NOTHING
        """))

init_db()

# =====================================================
# HELPERS
# =====================================================
def save_thumbnail(file):
    if not file:
        return None
    try:
        img = Image.open(file).convert("RGB")
        img.thumbnail((400, 600))
        path = f"thumbnails/thumb_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
        img.save(path, "JPEG", quality=95)
        return path
    except:
        return None

def get_docs():
    with engine.connect() as conn:
        res = conn.execute(text("SELECT * FROM documents ORDER BY id DESC"))
        return [dict(r._mapping) for r in res]

def get_doc_by_id(doc_id):
    with engine.connect() as conn:
        res = conn.execute(
            text("SELECT * FROM documents WHERE id = :id"),
            {"id": doc_id}
        ).fetchone()
        return dict(res._mapping) if res else None

@st.cache_data(ttl=10)
def get_chat_messages():
    with engine.connect() as conn:
        res = conn.execute(
            text("SELECT * FROM chat_messages ORDER BY timestamp ASC")
        )
        return [dict(r._mapping) for r in res]

def add_chat_message(sender, message, is_admin=False):
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO chat_messages (sender, message, timestamp, is_admin)
                VALUES (:s, :m, :t, :a)
            """),
            {
                "s": sender,
                "m": message,
                "t": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "a": is_admin
            }
        )
    st.cache_data.clear()

def clear_all_chat():
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM chat_messages"))
    st.cache_data.clear()

def get_site_info():
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT welcome_text, update_info FROM site_info WHERE id=1")
        ).fetchone()
        return {
            "welcome": row[0] if row else "",
            "update": row[1] if row else ""
        }

def update_site_info(welcome, update):
    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE site_info
                SET welcome_text=:w, update_info=:u
                WHERE id=1
            """),
            {"w": welcome, "u": update}
        )

# =====================================================
# SIDEBAR
# =====================================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png", width=120)
    page = st.selectbox("Menu", ["Halaman Utama", "Papar QR Code", "Admin Panel"])

    st.markdown("### Hubungi Admin")
    for msg in get_chat_messages()[-6:]:
        st.write(f"**{msg['sender']}**: {msg['message']}")

    with st.form("chat"):
        nama = st.text_input("Nama")
        mesej = st.text_area("Mesej")
        if st.form_submit_button("Hantar") and nama and mesej:
            add_chat_message(nama, mesej)
            st.rerun()

# =====================================================
# HALAMAN UTAMA
# =====================================================
if page == "Halaman Utama":
    info = get_site_info()
    st.title("RUJUKAN FAMA STANDARD")
    st.success(info["welcome"])
    st.info(info["update"])

    docs = get_docs()
    for d in docs:
        with st.expander(d["title"]):
            st.caption(f"{d['category']} • {d['upload_date']}")
            if os.path.exists(d["thumbnail_path"] or ""):
                st.image(d["thumbnail_path"], width=200)
            if os.path.exists(d["file_path"] or ""):
                with open(d["file_path"], "rb") as f:
                    st.download_button(
                        "Muat Turun PDF",
                        f.read(),
                        d["file_name"]
                    )

# =====================================================
# QR PAGE
# =====================================================
elif page == "Papar QR Code":
    st.title("QR Code Standard")
    q = st.text_input("Cari ID atau Tajuk")
    if q:
        matches = [
            d for d in get_docs()
            if q.lower() in d["title"].lower() or q == str(d["id"])
        ]
        for d in matches[:10]:
            link = f"{st.secrets['APP_URL']}?doc={d['id']}"
            qr = qrcode.make(link)
            buf = BytesIO()
            qr.save(buf)
            st.image(buf.getvalue(), width=200)
            st.code(link)

# =====================================================
# ADMIN PANEL
# =====================================================
else:
    if not st.session_state.get("logged_in"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Login"):
            if u in ADMIN_CREDENTIALS and hashlib.sha256(p.encode()).hexdigest() == ADMIN_CREDENTIALS[u]:
                st.session_state.logged_in = True
                st.session_state.user = u
                st.rerun()
            else:
                st.error("Login gagal")
        st.stop()

    st.success(f"ADMIN: {st.session_state.user}")

    tab1, tab2, tab3 = st.tabs(["Tambah", "Edit/Padam", "Info"])

    with tab1:
        file = st.file_uploader("PDF", type="pdf")
        title = st.text_input("Tajuk")
        cat = st.selectbox("Kategori", CATEGORIES)
        thumb = st.file_uploader("Thumbnail", type=["jpg","png"])
        if st.button("Simpan") and file and title:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fpath = f"uploads/{ts}_{file.name}"
            with open(fpath, "wb") as f:
                f.write(file.getvalue())
            tpath = save_thumbnail(thumb)
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO documents
                        (title, category, file_name, file_path,
                         thumbnail_path, upload_date, uploaded_by)
                        VALUES (:t,:c,:fn,:fp,:tp,:ud,:u)
                    """),
                    {
                        "t": title,
                        "c": cat,
                        "fn": file.name,
                        "fp": fpath,
                        "tp": tpath,
                        "ud": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "u": st.session_state.user
                    }
                )
            st.success("Berjaya")
            st.rerun()

    with tab2:
        for d in get_docs():
            with st.expander(f"{d['id']} • {d['title']}"):
                if st.button("Padam", key=f"del{d['id']}"):
                    with engine.begin() as conn:
                        conn.execute(
                            text("DELETE FROM documents WHERE id=:i"),
                            {"i": d["id"]}
                        )
                    if os.path.exists(d["file_path"]):
                        os.remove(d["file_path"])
                    if d["thumbnail_path"] and os.path.exists(d["thumbnail_path"]):
                        os.remove(d["thumbnail_path"])
                    st.success("Dipadam")
                    st.rerun()

    with tab3:
        info = get_site_info()
        w = st.text_area("Welcome", info["welcome"])
        u = st.text_area("Update", info["update"])
        if st.button("Simpan Info"):
            update_site_info(w, u)
            st.success("Dikemaskini")

    if st.button("Log Keluar"):
        st.session_state.clear()
        st.rerun()

st.caption("© Rujukan Standard FAMA 2025")
