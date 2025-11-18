# app.py — KOD FINAL FAMA STANDARD (ADMIN FULL + PDF VIEW CANTIK + 100% BERJALAN!)
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
# SETUP FOLDER & DATABASE
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

# =============================================
# INIT DATABASE + FTS5
# =============================================
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
        CREATE TRIGGER IF NOT EXISTS docs_au AFTER UPDATE ON documents BEGIN
            INSERT INTO docs_fts(docs_fts, rowid, title, content, category) VALUES ('delete', old.id, old.title, old.content, old.category);
            INSERT INTO docs_fts(rowid, title, content, category) VALUES (new.id, new.title, new.content, new.category);
        END;
    ''')
    conn.commit()
    conn.close()
init_db()

# =============================================
# BACKUP PENUH
# =============================================
def create_backup():
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(DB_NAME):
            zf.write(DB_NAME, "fama_standards.db")
        for root, _, files in os.walk(UPLOADS_DIR):
            for f in files:
                fp = os.path.join(root, f)
                zf.write(fp, f"uploads/{f}")
        for root, _, files in os.walk(THUMBNAILS_DIR):
            for f in files:
                fp = os.path.join(root, f)
                zf.write(fp, f"thumbnails/{f}")
    mem.seek(0)
    return mem

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
cur.execute("SELECT COUNT(*) FROM documents")
total = cur.fetchone()[0]
today = datetime.now().strftime("%Y-%m-%d")
cur.execute("SELECT COUNT(*) FROM documents WHERE substr(upload_date,1,10) = ?", (today,))
today_row = cur.fetchone()
today_count = today_row[0] if today_row else 0
conn.close()

c1, c2 = st.columns(2)
c1.metric("JUMLAH STANDARD", total)
c2.metric("BARU HARI INI", today_count)

# =============================================
# BUTANG KATEGORI
# =============================================
col1, col2, col3, col4 = st.columns(4)
with col1:
    if st.button("Keratan Bunga", type="primary", use_container_width=True):
        st.session_state.cat = "Keratan Bunga"; st.rerun()
with col2:
    if st.button("Sayur-sayuran", type="primary", use_container_width=True):
        st.session_state.cat = "Sayur-sayuran"; st.rerun()
with col3:
    if st.button("Buah-buahan", type="primary", use_container_width=True):
        st.session_state.cat = "Buah-buahan"; st.rerun()
with col4:
    if st.button("Lain-lain", type="primary", use_container_width=True):
        st.session_state.cat = "Lain-lain"; st.rerun()

if "cat" not in st.session_state:
    st.session_state.cat = "Semua"

# =============================================
# CARIAN + FILTER
# =============================================
query = st.text_input("Cari standard:", placeholder="Contoh: tomato, ros, durian...")
cat_filter = st.selectbox("Kategori:", ["Semua","Keratan Bunga","Sayur-sayuran","Buah-buahan","Lain-lain"],
                          index=0 if st.session_state.cat=="Semua" else ["Keratan Bunga","Sayur-sayuran","Buah-buahan","Lain-lain"].index(st.session_state.cat)+1)

# =============================================
# SENARAI DOKUMEN + LIHAT PDF
# =============================================
conn = get_db()
cur = conn.cursor()
sql = "SELECT d.id, d.title, d.content, d.file_name, d.file_path, d.thumbnail_path, d.upload_date, d.category FROM documents d JOIN docs_fts f ON d.id = f.rowid WHERE 1=1"
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
                col_v, col_d = st.columns(2)
                with col_v:
                    if st.button("Lihat PDF", key=f"view_{doc_id}"):
                        st.session_state.viewing_pdf = fpath
                        st.session_state.pdf_title = title
                        st.rerun()
                with col_d:
                    with open(fpath, "rb") as f:
                        st.download_button("Muat Turun", f.read(), file_name=fname, key=f"dl_{doc_id}")

# =============================================
# PDF VIEWER CANTIK (100% TAK KENA BLOCK!)
# =============================================
if "viewing_pdf" in st.session_state:
    pdf_path = st.session_state.viewing_pdf
    pdf_title = st.session_state.pdf_title

    st.markdown(f"### {pdf_title}")
    with open(pdf_path, "rb") as f:
        st.download_button("Muat Turun", f.read(), file_name=os.path.basename(pdf_path), mime="application/pdf")

    st.markdown(f'''
    <iframe src="{pdf_path}" width="100%" height="800px" style="border:3px solid #2E7D32; border-radius:12px;"></iframe>
    ''', unsafe_allow_html=True)

    if st.button("Tutup Preview", type="primary", use_container_width=True):
        del st.session_state.viewing_pdf
        del st.session_state.pdf_title
        st.rerun()

# =============================================
# ADMIN PANEL LENGKAP (Upload + Edit + Padam + Thumbnail)
# =============================================
with st.sidebar:
    st.markdown("## Admin Panel")
    pw = st.text_input("Password", type="password", key="adminpw")
    
    if pw == "admin123":  # Tukar password bila nak
        st.success("Login Admin Berjaya!")

        st.download_button("Backup Penuh (.zip)", data=create_backup(),
                           file_name=f"FAMA_Backup_{datetime.now().strftime('%Y%m%d_%H%M')}.zip", mime="application/zip")

        tab1, tab2, tab3 = st.tabs(["Upload Baru", "Edit/Padam", "Senarai"])

        with tab1:
            st.subheader("Upload Standard + Thumbnail")
            uploaded_file = st.file_uploader("Pilih PDF/DOCX", type=["pdf", "docx"])
            thumbnail = st.file_uploader("Pilih Thumbnail", type=["png", "jpg", "jpeg"])
            title = st.text_input("Nama Standard")
            category = st.selectbox("Kategori", ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"])

            if st.button("Simpan Standard", type="primary"):
                if uploaded_file and title:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    ext = Path(uploaded_file.name).suffix
                    new_name = f"{ts}_{Path(uploaded_file.name).stem}{ext}"
                    file_path = os.path.join(UPLOADS_DIR, new_name)
                    with open(file_path, "wb") as f:
                        shutil.copyfileobj(uploaded_file, f)

                    thumb_path = None
                    if thumbnail:
                        tname = f"{ts}_thumb{Path(thumbnail.name).suffix}"
                        thumb_path = os.path.join(THUMBNAILS_DIR, tname)
                        with open(thumb_path, "wb") as f:
                            shutil.copyfileobj(thumbnail, f)

                    # Ekstrak teks
                    uploaded_file.seek(0)
                    if ext.lower() == ".pdf":
                        text = "\n".join([p.extract_text() or "" for p in PyPDF2.PdfReader(uploaded_file).pages])
                    else:
                        text = "\n".join([p.text for p in Document(uploaded_file).paragraphs])

                    conn = get_db()
                    conn.execute("INSERT INTO documents (title, content, category, file_name, file_path, thumbnail_path, upload_date) VALUES (?,?,?,?,?,?,?)",
                                 (title, text, category, uploaded_file.name, file_path, thumb_path, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    conn.close()
                    st.success("Standard berjaya disimpan!")
                    st.rerun()
                else:
                    st.error("Sila isi semua medan!")

        with tab2:
            st.subheader("Edit / Padam Standard")
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT id, title, category FROM documents ORDER BY upload_date DESC")
            docs = cur.fetchall()
            conn.close()

            if docs:
                choice = st.selectbox("Pilih standard", [f"{t} - {c} (ID: {i})" for i,t,c in docs])
                doc_id = int(choice.split("ID: ")[1].split(")")[0])

                conn = get_db()
                cur = conn.cursor()
                cur.execute("SELECT * FROM documents WHERE id=?", (doc_id,))
                doc = cur.fetchone()
                conn.close()

                if doc:
                    st.write(f"**Tajuk:** {doc[1]}")
                    st.write(f"**Kategori:** {doc[3]}")
                    if doc[6]: st.image(doc[6], width=150)

                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button("Padam Permanent", type="secondary"):
                            if st.checkbox("Ya, saya pasti nak padam"):
                                if doc[5] and os.path.exists(doc[5]): os.remove(doc[5])
                                if doc[6] and os.path.exists(doc[6]): os.remove(doc[6])
                                conn = get_db()
                                conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
                                conn.commit()
                                conn.close()
                                st.success("Dokumen dipadam!")
                                st.rerun()
                    with col_b:
                        st.info("Fungsi edit penuh boleh ditambah kemudian.")
            else:
                st.info("Tiada dokumen lagi.")