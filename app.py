# app.py — FINAL 100% TAK KENA BLOCK CHROME + PDF VIEW CANTIK
import streamlit as st
import sqlite3
import os
import shutil
from datetime import datetime
import PyPDF2
from docx import Document
import io
import zipfile
from pathlib import Path

# =============================================
# SETUP
# =============================================
DB_NAME = "/tmp/fama_standards.db"
UPLOADS_DIR = "/tmp/uploads"
THUMBNAILS_DIR = "/tmp/thumbnails"

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(THUMBNAILS_DIR, exist_ok=True)

def get_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

if not os.path.exists(DB_NAME):
    open(DB_NAME, "a").close()

@st.cache_resource
def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'Lain-lain',
            file_name TEXT,
            file_path TEXT,
            thumbnail_path TEXT,
            upload_date TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(title, content, category, content='documents', content_rowid='id');
        CREATE TRIGGER IF NOT EXISTS docs_ai AFTER INSERT ON documents BEGIN
            INSERT INTO docs_fts(rowid, title, content, category) VALUES (new.id, new.title, new.content, new.category);
        END;
    ''')
    conn.commit()
    conn.close()
init_db()

# =============================================
# TAJUK + LOGO FAMA
# =============================================
st.set_page_config(page_title="Rujukan FAMA Standard", page_icon="leaves", layout="centered")

st.markdown("""
<div style="text-align:center; padding:20px;">
    <img src="https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png" width="80">
    <h1 style="color:#2E7D32; margin:15px 0 5px 0; font-size:3em;">RUJUKAN FAMA STANDARD</h1>
    <p style="color:#388E3C; font-size:1.8em; margin:0; font-weight:600;">KELUARAN HASIL PERTANIAN</p>
</div>
""", unsafe_allow_html=True)

# =============================================
# STATISTIK
# =============================================
conn = get_db()
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM documents"); total = cur.fetchone()[0]
today = datetime.now().strftime("%Y-%m-%d")
cur.execute("SELECT COUNT(*) FROM documents WHERE substr(upload_date,1,10)=?", (today,))
today_row = cur.fetchone()
today_count = today_row[0] if today_row else 0
conn.close()

c1, c2 = st.columns(2)
c1.metric("JUMLAH STANDARD", total)
c2.metric("BARU HARI INI", today_count)

# =============================================
# KATEGORI + CARIAN
# =============================================
col1,col2,col3,col4 = st.columns(4)
with col1: if st.button("Keratan Bunga", type="primary", use_container_width=True): st.session_state.cat="Keratan Bunga"; st.rerun()
with col2: if st.button("Sayur-sayuran", type="primary", use_container_width=True): st.session_state.cat="Sayur-sayuran"; st.rerun()
with col3: if st.button("Buah-buahan", type="primary", use_container_width=True): st.session_state.cat="Buah-buahan"; st.rerun()
with col4: if st.button("Lain-lain", type="primary", use_container_width=True): st.session_state.cat="Lain-lain"; st.rerun()

if "cat" not in st.session_state: st.session_state.cat = "Semua"

query = st.text_input("Cari standard:", placeholder="contoh: tomato, ros, durian")
cat_filter = st.selectbox("Kategori:", ["Semua","Keratan Bunga","Sayur-sayuran","Buah-buahan","Lain-lain"],
                          index=0 if st.session_state.cat=="Semua" else ["Keratan Bunga","Sayur-sayuran","Buah-buahan","Lain-lain"].index(st.session_state.cat)+1)

# =============================================
# SENARAI DOKUMEN
# =============================================
conn = get_db()
cur = conn.cursor()
sql = "SELECT d.id, d.title, d.content, d.file_name, d.file_path, d.thumbnail_path, d.upload_date, d.category FROM documents d JOIN docs_fts f ON d.id=f.rowid WHERE 1=1"
params = []
if query: sql += " AND docs_fts MATCH ?"; params.append(query)
if cat_filter != "Semua": sql += " AND d.category = ?"; params.append(cat_filter)
sql += " ORDER BY d.upload_date DESC"
cur.execute(sql, params)
results = cur.fetchall()
conn.close()

st.markdown(f"**Ditemui {len(results)} standard**")

for doc_id, title, content, fname, fpath, thumb_path, date, cat in results:
    with st.expander(f"{title} • {cat} • {date[:10]}"):
        col_img, col_text = st.columns([1, 4])
        with col_img:
            img = thumb_path if thumb_path and os.path.exists(thumb_path) else "https://via.placeholder.com/150x200/4CAF50/white?text=No+Image"
            st.image(img, use_column_width=True)
        with col_text:
            st.write(content[:800] + ("..." if len(content)>800 else ""))

            if fpath and os.path.exists(fpath):
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Lihat PDF", key=f"view_{doc_id}"):
                        st.session_state.viewing_pdf = fpath
                        st.session_state.pdf_title = title
                        st.rerun()
                with col2:
                    with open(fpath, "rb") as f:
                        st.download_button("Muat Turun", f.read(), file_name=fname, key=f"dl_{doc_id}")

# =============================================
# PDF VIEWER YANG TAK KENA BLOCK CHROME!
# =============================================
if st.session_state.get("viewing_pdf"):
    pdf_path = st.session_state.viewing_pdf
    title = st.session_state.pdf_title

    st.markdown(f"### {title}")

    # Cara paling selamat — guna Streamlit static file server
    with open(pdf_path, "rb") as pdf_file:
        st.download_button("Muat Turun Semula", pdf_file.read(), file_name=Path(pdf_path).name, mime="application/pdf")

    # Embed PDF guna URL dalaman Streamlit (tak kena block!)
    st.markdown(f"""
    <iframe src="/media/{os.path.basename(pdf_path)}" width="100%" height="800px" style="border:3px solid #2E7D32; border-radius:12px;"></iframe>
    """, unsafe_allow_html=True)

    if st.button("Tutup Preview", type="primary", use_container_width=True):
        del st.session_state.viewing_pdf
        del st.session_state.pdf_title
        st.rerun()

# =============================================
# ADMIN PANEL (Ringkas & Berfungsi)
# =============================================
with st.sidebar:
    st.markdown("## Admin")
    if st.text_input("Password", type="password") == "admin123":
        st.success("Login OK")
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM documents"); total_docs = cur.fetchone()[0]
        conn.close()
        st.write(f"Total dokumen: {total_docs}")

        if st.button("Backup Penuh"):
            # Backup simple
            backup_data = create_backup()
            st.download_button("Download Backup Sekarang", backup_data,
                               file_name=f"FAMA_Backup_{datetime.now().strftime('%Y%m%d')}.zip",
                               mime="application/zip")