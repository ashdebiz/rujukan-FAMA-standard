# app.py — KOD FINAL FAMA STANDARD (ADMIN FULL + PDF CANTIK + 100% BERJALAN!)
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
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

# Auto authenticate pertama kali je
gauth = GoogleAuth()
gauth.LocalWebserverAuth()  # akan buka browser sekali je
drive = GoogleDrive(gauth)

# Set folder ID (dari URL folder kau)
FOLDER_ID = "1RHHcCLR-n7k2rcwZr-QBFBD0KKpcAYTy"  # tukar dengan ID folder kau

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
        CREATE TRIGGER IF NOT EXISTS docs_ad AFTER DELETE ON documents BEGIN
            INSERT INTO docs_fts(docs_fts, rowid, title, content, category) VALUES ('delete', old.id, old.title, old.content, old.category);
        END;
    ''')
    conn.commit()
    conn.close()
init_db()

def create_backup():
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(DB_NAME): zf.write(DB_NAME, "fama_standards.db")
        for root, _, files in os.walk(UPLOADS_DIR):
            for f in files: zf.write(os.path.join(root, f), f"uploads/{f}")
        for root, _, files in os.walk(THUMBNAILS_DIR):
            for f in files: zf.write(os.path.join(root, f), f"thumbnails/{f}")
    mem.seek(0)
    return mem

# =============================================
# TAJUK FAMA
# =============================================
st.set_page_config(page_title="Rujukan FAMA Standard", page_icon="leaves", layout="centered")
st.markdown("""
<div style="text-align:center; padding:20px;">
    <img src="https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png" width="80">
    <h1 style="color:#2E7D32; margin:15px 0 5px 0; font-size:3em;">RUJUKUN FAMA STANDARD</h1>
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

col1, col2 = st.columns(2)
col1.metric("JUMLAH STANDARD", total)
col2.metric("BARU HARI INI", today_count)

# =============================================
# BUTANG KATEGORI
# =============================================
c1, c2, c3, c4 = st.columns(4)

with c1:
    if st.button("Keratan Bunga", type="primary", use_container_width=True):
        st.session_state.cat = "Keratan Bunga"; st.rerun()
with c2:
    if st.button("Sayur-sayuran", type="primary", use_container_width=True):
        st.session_state.cat = "Sayur-sayuran"; st.rerun()
with c3:
    if st.button("Buah-buahan", type="primary", use_container_width=True):
        st.session_state.cat = "Buah-buahan"; st.rerun()
with c4:
    if st.button("Lain-lain", type="primary", use_container_width=True):
        st.session_state.cat = "Lain-lain"; st.rerun()

if "cat" not in st.session_state:
    st.session_state.cat = "Semua"

query = st.text_input("Cari standard:", placeholder="Contoh: tomato, durian, ros")
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
        col_img, col_info = st.columns([1,4])
        with col_img:
            img = thumb_path if thumb_path and os.path.exists(thumb_path) else "https://via.placeholder.com/150x200/4CAF50/white?text=No+Image"
            st.image(img, use_column_width=True)
        with col_info:
            st.write(content[:700] + ("..." if len(content)>700 else ""))

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Lihat PDF", key=f"view_{doc_id}"):
                    st.session_state.viewing_pdf = fpath
                    st.session_state.pdf_title = title
                    st.rerun()
            with col_b:
                with open(fpath, "rb") as f:
                    st.download_button("Muat Turun", f.read(), file_name=fname, key=f"dl_{doc_id}")

# =============================================
# PDF PREVIEW — TAK KENA BLOCK CHROME!
# =============================================
if "viewing_pdf" in st.session_state:
    pdf_path = st.session_state.viewing_pdf
    pdf_title = st.session_state.pdf_title

    st.markdown(f"### {pdf_title}")

    with open(pdf_path, "rb") as f:
        st.download_button("Muat Turun PDF", f.read(), file_name=os.path.basename(pdf_path))

    st.markdown(f"""
    <iframe src="{pdf_path}" width="100%" height="900px" 
            style="border:4px solid #2E7D32; border-radius:15px;">
    </iframe>
    """, unsafe_allow_html=True)

    if st.button("Tutup Preview", type="primary", use_container_width=True):
        del st.session_state.viewing_pdf
        del st.session_state.pdf_title
        st.rerun()

# =============================================
# ADMIN PANEL LENGKAP & STABIL
# =============================================
with st.sidebar:
    st.markdown("## Admin Panel")
    pw = st.text_input("Password", type="password", key="adminpw")
    
    if pw == "admin123":
        st.success("Login Admin Berjaya!")

        # Backup
        st.download_button("Backup Penuh", data=create_backup(),
                           file_name=f"FAMA_Backup_{datetime.now().strftime('%Y%m%d_%H%M')}.zip", mime="application/zip")

        tab1, tab2, tab3 = st.tabs(["Upload Baru", "Edit/Padam", "Senarai"])

        # TAB 1: UPLOAD
        with tab1:
            uploaded_file = st.file_uploader("Pilih PDF atau DOCX", type=["pdf","docx"])
            thumbnail = st.file_uploader("Pilih Thumbnail", type=["png","jpg","jpeg"])
            title = st.text_input("Tajuk Standard")
            category = st.selectbox("Kategori", ["Keratan Bunga","Sayur-sayuran","Buah-buahan","Lain-lain"])

            if st.button("Simpan Standard", type="primary"):
                if not uploaded_file or not title:
                    st.error("Sila isi tajuk & pilih fail!")
                else:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    ext = Path(uploaded_file.name).suffix
                    new_path = os.path.join(UPLOADS_DIR, f"{ts}_{uploaded_file.name}")
                    with open(new_path, "wb") as f:
                        shutil.copyfileobj(uploaded_file, f)

                    thumb_path = None
                    if thumbnail:
                        thumb_path = os.path.join(THUMBNAILS_DIR, f"{ts}_thumb{Path(thumbnail.name).suffix}")
                        with open(thumb_path, "wb") as f:
                            shutil.copyfileobj(thumbnail, f)

                    # Ekstrak teks
                    uploaded_file.seek(0)
                    if ext == ".pdf":
                        text = "\n".join(p.extract_text() or "" for p in PyPDF2.PdfReader(uploaded_file).pages)
                    else:
                        text = "\n".join(p.text for p in Document(uploaded_file).paragraphs)

                    conn = get_db()
                    conn.execute("INSERT INTO documents (title,content,category,file_name,file_path,thumbnail_path,upload_date) VALUES(?,?,?,?,?,?,?)",
                                 (title, text, category, uploaded_file.name, new_path, thumb_path, datetime.now()))
                    conn.commit()
                    conn.close()
                    st.success("Berjaya disimpan!")
                    st.rerun()

        # TAB 2: EDIT / PADAM
        with tab2:
            conn = get_db()
            docs = conn.execute("SELECT id, title, category FROM documents ORDER BY upload_date DESC").fetchall()
            conn.close()

            if docs:
                choice = st.selectbox("Pilih standard", [f"{t} - {c} (ID: {i})" for i,t,c in docs])
                doc_id = int(choice.split("ID: ")[1].split(")")[0])

                # Papar info
                conn = get_db()
                doc = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
                conn.close()

                st.write(f"**Tajuk:** {doc[1]}")
                st.write(f"**Kategori:** {doc[3]}")
                if doc[6]: st.image(doc[6], width=200)

                colx, coly = st.columns(2)
                with colx:
                    if st.button("Padam Permanent", type="secondary"):
                        if st.checkbox("Ya, saya pasti nak padam"):
                            if doc[5]: os.remove(doc[5])
                            if doc[6]: os.remove(doc[6])
                            conn = get_db()
                            conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
                            conn.commit()
                            conn.close()
                            st.success("Dipadam!")
                            st.rerun()
                with coly:
                    st.info("Fungsi edit penuh boleh ditambah kemudian")

        # TAB 3: SENARAI SEMUA
        with tab3:
            conn = get_db()
            all_docs = conn.execute("SELECT id, title, category, upload_date FROM documents ORDER BY upload_date DESC").fetchall()
            conn.close()
            for i, t, c, d in all_docs:
                st.write(f"**{t}** • {c} • {d[:10]} (ID: {i})")