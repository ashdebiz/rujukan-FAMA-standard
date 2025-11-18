# app.py — VERSI FINAL + BUTANG "LIHAT PDF" + THUMBNAIL + ADMIN LENGKAP
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
# DATA KEKAL DI /tmp (Streamlit Cloud)
# =============================================
DB_NAME = "/tmp/standards_db.sqlite"
UPLOADS_DIR = "/tmp/uploads"
THUMBNAILS_DIR = "/tmp/thumbnails"

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(THUMBNAILS_DIR, exist_ok=True)

def get_db():
    conn = sqlite3.connect(DB_NAME, timeout=30.0, check_same_thread=False)
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
        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
            title, content, category, content='documents', content_rowid='id'
        );
        CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
            INSERT INTO documents_fts(rowid, title, content, category) VALUES (new.id, new.title, new.content, new.category);
        END;
        CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, title, content, category) VALUES ('delete', old.id, old.title, old.content, old.category);
        END;
        CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, title, content, category) VALUES ('delete', old.id, old.title, old.content, old.category);
            INSERT INTO documents_fts(rowid, title, content, category) VALUES (new.id, new.title, new.content, new.category);
        END;
    ''')
    conn.commit()
    conn.close()
init_db()

# =============================================
# BACKUP PENUH
# =============================================
def create_full_backup():
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(DB_NAME):
            zf.write(DB_NAME, "standards_db.sqlite")
        for root, _, files in os.walk(UPLOADS_DIR):
            for f in files:
                fp = os.path.join(root, f)
                zf.write(fp, os.path.join("uploads", os.path.relpath(fp, UPLOADS_DIR)))
        for root, _, files in os.walk(THUMBNAILS_DIR):
            for f in files:
                fp = os.path.join(root, f)
                zf.write(fp, os.path.join("thumbnails", os.path.relpath(fp, THUMBNAILS_DIR)))
    mem.seek(0)
    return mem

# =============================================
# TAJUK + LOGO FAMA
# =============================================
st.set_page_config(page_title="Rujukan FAMA Standard", page_icon="rice", layout="centered")

st.markdown("""
<div style="text-align:center; padding:20px 0;">
    <img src="https://www.fama.gov.my/wp-content/uploads/2023/06/Logo-FAMA-Baru-2023.png" width="140">
    <h1 style="color:#2E7D32; font-size:3em; margin:15px 0 5px 0;">RUJUKAN FAMA STANDARD</h1>
    <p style="color:#388E3C; font-size:1.8em; margin:0; font-weight:600;">KELUARAN HASIL PERTANIAN</p>
    <p style="color:#4CAF50; font-size:1.2em; margin-top:12px;">Temui panduan standard pertanian terkini dengan mudah</p>
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
row = cur.fetchone()
today_count = row[0] if row else 0
conn.close()

col1, col2 = st.columns(2)
col1.metric("Jumlah Standard Keseluruhan", total)
col2.metric("Standard Baru Hari Ini", today_count)

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

query = st.text_input("Masukkan kata kunci carian (opsional):", placeholder="Contoh: standard keratan bunga")
category_filter = st.selectbox("Filter Kategori:", 
    ["Semua", "Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"],
    index=0 if st.session_state.cat == "Semua" else ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"].index(st.session_state.cat) + 1)

# =============================================
# PAPAR HASIL CARIAN + BUTANG LIHAT PDF + MUAT TURUN
# =============================================
conn = get_db()
cur = conn.cursor()
sql = "SELECT d.id, d.title, d.content, d.file_name, d.file_path, d.thumbnail_path, d.upload_date, d.category FROM documents d JOIN documents_fts f ON d.id = f.rowid WHERE 1=1"
params = []
if query:
    sql += " AND documents_fts MATCH ?"
    params.append(query)
if category_filter != "Semua":
    sql += " AND d.category = ?"
    params.append(category_filter)
sql += " ORDER BY d.upload_date DESC"
cur.execute(sql, params)
results = cur.fetchall()
conn.close()

st.markdown(f"**Ditemui {len(results)} dokumen**")

for doc_id, title, content, fname, fpath, thumb_path, date, cat in results:
    with st.expander(f"{title} • {cat} • {date[:10]}"):
        col_img, col_content = st.columns([1, 4])
        with col_img:
            if thumb_path and os.path.exists(thumb_path):
                st.image(thumb_path, width=130)
            else:
                st.image("https://via.placeholder.com/130x180/4CAF50/white?text=No+Image", width=130)
        with col_content:
            st.write(content[:700] + ("..." if len(content) > 700 else ""))

            if fpath and os.path.exists(fpath):
                with open(fpath, "rb") as f:
                    pdf_data = f.read()

                col_view, col_download = st.columns(2)
                with col_view:
                    st.download_button(
                        label="Lihat PDF",
                        data=pdf_data,
                        file_name=fname,
                        mime="application/pdf",
                        key=f"view_{doc_id}"
                    )
                with col_download:
                    st.download_button(
                        label="Muat Turun",
                        data=pdf_data,
                        file_name=fname,
                        mime="application/pdf",
                        key=f"dl_{doc_id}"
                    )
            else:
                st.warning("Fail tidak dijumpai.")

# =============================================
# ADMIN PANEL (Upload + Edit + Padam + Thumbnail + Backup)
# =============================================
with st.sidebar:
    st.markdown("## Admin Panel")
    pw = st.text_input("Kata laluan", type="password", key="admin_pw")
    if pw == "admin123":
        st.success("Log masuk admin")

        st.download_button("Download Backup Penuh", data=create_full_backup(),
                           file_name=f"fama_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.zip", mime="application/zip")

        st.markdown("---")
        tab1, tab2 = st.tabs(["Upload Baru", "Edit & Padam"])

        with tab1:
            st.subheader("Upload Dokumen + Thumbnail")
            uploaded_file = st.file_uploader("Fail PDF/DOCX", type=["pdf", "docx"], key="file1")
            thumbnail = st.file_uploader("Thumbnail (gambar)", type=["png", "jpg", "jpeg"], key="thumb1")
            title = st.text_input("Nama Komoditi / Tajuk", key="title1")
            category = st.selectbox("Kategori", ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"], key="cat1")

            if st.button("Simpan Dokumen", type="primary"):
                if not uploaded_file or not title:
                    st.error("Sila isi semua medan!")
                else:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    ext = Path(uploaded_file.name).suffix
                    safe_name = f"{ts}_{Path(uploaded_file.name).stem}{ext}"
                    file_path = os.path.join(UPLOADS_DIR, safe_name)
                    with open(file_path, "wb") as f:
                        shutil.copyfileobj(uploaded_file, f)

                    thumb_path = None
                    if thumbnail:
                        thumb_name = f"{ts}_thumb{Path(thumbnail.name).suffix}"
                        thumb_path = os.path.join(THUMBNAILS_DIR, thumb_name)
                        with open(thumb_path, "wb") as f:
                            shutil.copyfileobj(thumbnail, f)

                    uploaded_file.seek(0)
                    if ext.lower() == ".pdf":
                        reader = PyPDF2.PdfReader(uploaded_file)
                        text = "\n".join(p.extract_text() or "" for p in reader.pages)
                    else:
                        doc = Document(uploaded_file)
                        text = "\n".join(p.text for p in doc.paragraphs)

                    conn = get_db()
                    conn.execute("""
                        INSERT INTO documents (title, content, category, file_name, file_path, thumbnail_path, upload_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (title, text, category, uploaded_file.name, file_path, thumb_path, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    conn.close()
                    st.success("Dokumen berjaya disimpan!")
                    st.rerun()

        with tab2:
            st.subheader("Edit / Padam Dokumen")
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT id, title FROM documents ORDER BY upload_date DESC")
            docs = cur.fetchall()
            conn.close()

            selected = st.selectbox("Pilih dokumen", [f"{t} (ID: {i})" for i, t in docs])
            doc_id = int(selected.split("ID: ")[-1].strip(")"))

            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
            doc = cur.fetchone()
            conn.close()

            if doc:
                col1, col2 = st.columns(2)
                with col1:
                    new_title = st.text_input("Tajuk", value=doc[1])
                    new_cat = st.selectbox("Kategori", ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"], 
                                          index=["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"].index(doc[3]))
                    new_file = st.file_uploader("Ganti fail", type=["pdf", "docx"])
                    new_thumb = st.file_uploader("Ganti thumbnail", type=["png", "jpg", "jpeg"])
                with col2:
                    if doc[6]: st.image(doc[6], caption="Thumbnail semasa", width=150)
                    st.write(f"Fail semasa: {doc[4]}")

                if st.button("Kemaskini", type="primary"):
                    conn = get_db()
                    updates = ["title = ?", "category = ?"]
                    params = [new_title, new_cat]

                    if new_file:
                        if doc[5] and os.path.exists(doc[5]): os.remove(doc[5])
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        ext = Path(new_file.name).suffix
                        new_path = os.path.join(UPLOADS_DIR, f"{ts}_{Path(new_file.name).stem}{ext}")
                        with open(new_path, "wb") as f: shutil.copyfileobj(new_file, f)
                        new_file.seek(0)
                        text = "\n".join(p.extract_text() or "" for p in PyPDF2.PdfReader(new_file).pages) if ext == ".pdf" else "\n".join(p.text for p in Document(new_file).paragraphs)
                        updates += ["file_path = ?", "file_name = ?", "content = ?"]
                        params += [new_path, new_file.name, text]

                    if new_thumb:
                        if doc[6] and os.path.exists(doc[6]): os.remove(doc[6])
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        new_tpath = os.path.join(THUMBNAILS_DIR, f"{ts}_thumb{Path(new_thumb.name).suffix}")
                        with open(new_tpath, "wb") as f: shutil.copyfileobj(new_thumb, f)
                        updates.append("thumbnail_path = ?")
                        params.append(new_tpath)

                    sql = f"UPDATE documents SET {', '.join(updates)} WHERE id = ?"
                    params.append(doc_id)
                    conn.execute(sql, params)
                    conn.commit()
                    conn.close()
                    st.success("Berjaya dikemaskini!")
                    st.rerun()

                if st.button("Padam Dokumen Ini", type="secondary"):
                    if st.checkbox("Saya pasti nak padam"):
                        if doc[5] and os.path.exists(doc[5]): os.remove(doc[5])
                        if doc[6] and os.path.exists(doc[6]): os.remove(doc[6])
                        conn = get_db()
                        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
                        conn.commit()
                        conn.close()
                        st.success("Dokumen dipadam!")
                        st.rerun()