import streamlit as st
import os
import shutil
import zipfile
import time
import hashlib
from datetime import datetime
from PIL import Image
from io import BytesIO
import qrcode

from sqlalchemy import create_engine, text

try:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    st.success("✅ Neon connected")
except Exception as e:
    st.error("❌ DB connection failed")
    st.exception(e)
    st.stop()

# ======================================================
# CONFIG
# ======================================================
st.set_page_config(
    page_title="Rujukan FAMA Standard",
    page_icon="leaf",
    layout="centered"
)

# ======================================================
# DATABASE (NEON POSTGRES)
# ======================================================
engine = create_engine(
    st.secrets["DATABASE_URL"],
    pool_pre_ping=True
)

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
        );
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id SERIAL PRIMARY KEY,
            sender TEXT,
            message TEXT,
            timestamp TEXT,
            is_admin BOOLEAN DEFAULT FALSE
        );
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS site_info (
            id INTEGER PRIMARY KEY,
            welcome_text TEXT,
            update_info TEXT
        );
        """))

        conn.execute(text("""
        INSERT INTO site_info (id, welcome_text, update_info)
        VALUES (1,'Selamat Datang ke Sistem Rujukan FAMA Standard',
                   'Semua standard telah dikemaskini')
        ON CONFLICT (id) DO NOTHING;
        """))

init_db()

# ======================================================
# CONSTANT
# ======================================================
CATEGORIES = ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"]

ADMIN_CREDENTIALS = {
    "admin": hashlib.sha256("fama2025".encode()).hexdigest(),
    "pengarah": hashlib.sha256("fama123".encode()).hexdigest()
}

for f in ["uploads", "thumbnails"]:
    os.makedirs(f, exist_ok=True)

# ======================================================
# DB FUNCTIONS
# ======================================================
def get_docs():
    with engine.connect() as conn:
        res = conn.execute(text("SELECT * FROM documents ORDER BY id DESC"))
        return [dict(r._mapping) for r in res]

def get_doc(doc_id):
    with engine.connect() as conn:
        res = conn.execute(
            text("SELECT * FROM documents WHERE id=:id"),
            {"id": doc_id}
        ).fetchone()
        return dict(res._mapping) if res else None

@st.cache_data(ttl=10)
def get_chat():
    with engine.connect() as conn:
        res = conn.execute(text("SELECT * FROM chat_messages ORDER BY id"))
        return [dict(r._mapping) for r in res]

def add_chat(sender, msg, is_admin=False):
    with engine.begin() as conn:
        conn.execute(
            text("""INSERT INTO chat_messages
            (sender,message,timestamp,is_admin)
            VALUES (:s,:m,:t,:a)"""),
            {
                "s": sender,
                "m": msg,
                "t": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "a": is_admin
            }
        )
    st.cache_data.clear()

def clear_chat():
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM chat_messages"))
    st.cache_data.clear()

def get_site():
    with engine.connect() as conn:
        r = conn.execute(
            text("SELECT welcome_text,update_info FROM site_info WHERE id=1")
        ).fetchone()
        return {"welcome": r[0], "update": r[1]}

def update_site(w,u):
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE site_info SET welcome_text=:w, update_info=:u WHERE id=1"),
            {"w": w, "u": u}
        )

# ======================================================
# SIDEBAR
# ======================================================
with st.sidebar:
    st.image("fama_icon.png", width=120)
    page = st.selectbox("Menu", ["Halaman Utama", "QR Code", "Admin Panel"])

    st.markdown("### Chat")
    for m in get_chat()[-6:]:
        st.write(f"**{m['sender']}**: {m['message']}")

    with st.form("chat"):
        n = st.text_input("Nama")
        t = st.text_area("Mesej")
        if st.form_submit_button("Hantar") and n and t:
            add_chat(n,t)
            st.rerun()

# ======================================================
# HALAMAN UTAMA
# ======================================================
if page == "Halaman Utama":
    info = get_site()
    st.title("RUJUKAN FAMA STANDARD")
    st.success(info["welcome"])
    st.caption(info["update"])

    docs = get_docs()
    for d in docs:
        with st.expander(f"{d['title']} ({d['category']})"):
            if d["thumbnail_path"] and os.path.exists(d["thumbnail_path"]):
                st.image(d["thumbnail_path"], width=200)
            if d["file_path"] and os.path.exists(d["file_path"]):
                with open(d["file_path"], "rb") as f:
                    st.download_button(
                        "Download PDF",
                        f.read(),
                        d["file_name"]
                    )

# ======================================================
# QR CODE
# ======================================================
elif page == "QR Code":
    q = st.text_input("Cari ID")
    if q.isdigit():
        d = get_doc(int(q))
        if d:
            link = f"{st.get_url()}?doc={d['id']}"
            qr = qrcode.make(link)
            buf = BytesIO()
            qr.save(buf)
            st.image(buf.getvalue())
            st.code(link)

# ======================================================
# ADMIN PANEL
# ======================================================
else:
    if not st.session_state.get("admin"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Login"):
            if u in ADMIN_CREDENTIALS and \
               hashlib.sha256(p.encode()).hexdigest() == ADMIN_CREDENTIALS[u]:
                st.session_state.admin = u
                st.success("Login OK")
                st.rerun()
            else:
                st.error("Login gagal")
        st.stop()

    st.success(f"ADMIN: {st.session_state.admin}")

    tab1, tab2, tab3 = st.tabs(["Tambah", "Edit/Padam", "Setting"])

    with tab1:
        f = st.file_uploader("PDF", type="pdf")
        t = st.text_input("Tajuk")
        c = st.selectbox("Kategori", CATEGORIES)
        img = st.file_uploader("Thumbnail", type=["jpg","png"])
        if st.button("Simpan") and f and t:
            ts = datetime.now().strftime("%Y%m%d%H%M%S")
            pdf_path = f"uploads/{ts}_{f.name}"
            with open(pdf_path,"wb") as x: x.write(f.getvalue())

            thumb_path = None
            if img:
                im = Image.open(img)
                im.thumbnail((400,600))
                thumb_path = f"thumbnails/{ts}.jpg"
                im.save(thumb_path)

            with engine.begin() as conn:
                conn.execute(text("""
                INSERT INTO documents
                (title,category,file_name,file_path,thumbnail_path,upload_date,uploaded_by)
                VALUES (:t,:c,:fn,:fp,:tp,:d,:u)
                """),{
                    "t": t, "c": c, "fn": f.name,
                    "fp": pdf_path, "tp": thumb_path,
                    "d": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "u": st.session_state.admin
                })
            st.success("Berjaya")
            st.rerun()

    with tab2:
        for d in get_docs():
            if st.button(f"Padam {d['id']}"):
                with engine.begin() as conn:
                    conn.execute(
                        text("DELETE FROM documents WHERE id=:id"),
                        {"id": d["id"]}
                    )
                st.warning("Dipadam")
                st.rerun()

    with tab3:
        i = get_site()
        w = st.text_area("Welcome", i["welcome"])
        u = st.text_area("Update", i["update"])
        if st.button("Simpan"):
            update_site(w,u)
            st.success("Updated")

    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

st.caption("© FAMA Standard 2025")
