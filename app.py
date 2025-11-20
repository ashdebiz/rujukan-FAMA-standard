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
import json
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import io as io_lib

# =============================================
# GOOGLE DRIVE SETUP (PAKAI SERVICE ACCOUNT)
# =============================================
st.set_page_config(page_title="RUJUKAN FAMA STANDARD", page_icon="leaves", layout="centered")

# Pastikan service-account.json ada di repo kau
SERVICE_ACCOUNT_FILE = "service-account.json"
SCOPES = ['https://www.googleapis.com/auth/drive']

if not os.path.exists(SERVICE_ACCOUNT_FILE):
    st.error("service-account.json tak jumpa! Letak di repo kau.")
    st.stop()

credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=credentials)

# Folder ID dari link Drive kau
DRIVE_FOLDER_ID = "1RHHcCLR-n7k2rcwZr-QBFBD0KKpcAYTy"

# Subfolder di dalam Drive
DB_FILE_ID = None  # Auto detect nanti
UPLOADS_FOLDER_ID = None
THUMBNAILS_FOLDER_ID = None

# Cari atau buat subfolder
def get_or_create_folder(name, parent_id):
    query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false"
    response = drive_service.files().list(q=query, fields="files(id, name)").execute()
    folders = response.get('files', [])
    if folders:
        return folders[0]['id']
    else:
        file_metadata = {'name': name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent_id]}
        folder = drive_service.files().create(body=file_metadata, fields='id').execute()
        return folder['id']

# Inisialisasi folder
with st.spinner("Menyambung ke Google Drive..."):
    UPLOADS_FOLDER_ID = get_or_create_folder("uploads", DRIVE_FOLDER_ID)
    THUMBNAILS_FOLDER_ID = get_or_create_folder("thumbnails", DRIVE_FOLDER_ID)
    DB_FOLDER_ID = get_or_create_folder("db", DRIVE_FOLDER_ID)

st.success("Google Drive berjaya disambung!")

# Local temp paths
LOCAL_DB = "fama_standards.db"
LOCAL_UPLOADS = "temp_uploads"
LOCAL_THUMBNAILS = "temp_thumbnails"
os.makedirs(LOCAL_UPLOADS, exist_ok=True)
os.makedirs(LOCAL_THUMBNAILS, exist_ok=True)

# Download DB kalau ada
def download_db():
    global DB_FILE_ID
    query = f"name='fama_standards.db' and '{DB_FOLDER_ID}' in parents and trashed=false"
    response = drive_service.files().list(q=query, fields="files(id)").execute()
    files = response.get('files', [])
    if files:
        DB_FILE_ID = files[0]['id']
        request = drive_service.files().get_media(fileId=DB_FILE_ID)
        fh = io_lib.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        with open(LOCAL_DB, "wb") as f:
            f.write(fh.getbuffer())
        st.info("Database dimuat turun dari Drive.")
    else:
        st.info("Tiada database lama. Buat baru.")

download_db()

# Upload DB balik ke Drive
def upload_db():
    global DB_FILE_ID
    media = MediaFileUpload(LOCAL_DB, mimetype='application/x-sqlite3')
    if DB_FILE_ID:
        drive_service.files().update(fileId=DB_FILE_ID, media_body=media).execute()
    else:
        file_metadata = {'name': 'fama_standards.db', 'parents': [DB_FOLDER_ID]}
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        DB_FILE_ID = file['id']

# Upload fail biasa
def upload_file(local_path, folder_id):
    file_metadata = {'name': os.path.basename(local_path), 'parents': [folder_id]}
    media = MediaFileUpload(local_path)
    file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file['id']

# =============================================
# DATABASE
# =============================================
def get_db():
    return sqlite3.connect(LOCAL_DB, timeout=30)

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
            drive_file_id TEXT,
            thumbnail_drive_id TEXT,
            upload_date TEXT NOT NULL
        );
    ''')
    conn.commit()
    conn.close()
init_db()

# =============================================
# TAJUK FAMA
# =============================================
st.markdown("""
<div style="text-align:center; padding:20px;">
    <img src="https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png" width="80">
    <h1 style="color:#2E7D32; margin:15px 0; font-size:3em;">RUJUKAN FAMA STANDARD</h1>
    <p style="color:#388E3C; font-size:1.8em;">KELUARAN HASIL PERTANIAN</p>
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
today_count = cur.fetchone()[0] if cur.fetchone() else 0
conn.close()

c1, c2 = st.columns(2)
c1.metric("JUMLAH STANDARD", total)
c2.metric("BARU HARI INI", today_count)

# =============================================
# CARIAN & KATEGORI
# =============================================
query = st.text_input("Cari standard:", placeholder="Contoh: tomato, durian, ros")
category = st.selectbox("Kategori:", ["Semua", "Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"])

# =============================================
# SENARAI DOKUMEN
# =============================================
conn = get_db()
cur = conn.cursor()
sql = "SELECT id, title, content, file_name, drive_file_id, thumbnail_drive_id, upload_date, category FROM documents WHERE 1=1"
params = []
if query:
    sql += " AND (title LIKE ? OR content LIKE ?)"
    params.extend([f"%{query}%", f"%{query}%"])
if category != "Semua":
    sql += " AND category = ?"
    params.append(category)
sql += " ORDER BY upload_date DESC"
cur.execute(sql, params)
results = cur.fetchall()
conn.close()

st.write(f"**Ditemui {len(results)} standard**")

for doc in results:
    doc_id, title, content, fname, drive_id, thumb_id, date, cat = doc
    with st.expander(f"{title} • {cat} • {date[:10]}"):
        col1, col2 = st.columns([1, 3])
        with col1:
            if thumb_id:
                thumb_url = f"https://drive.google.com/uc?id={thumb_id}"
                st.image(thumb_url, use_column_width=True)
            else:
                st.image("https://via.placeholder.com/150x200/4CAF50/white?text=No+Image")
        with col2:
            st.write(content[:600] + ("..." if len(content) > 600 else ""))

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Lihat PDF", key=f"view_{doc_id}"):
                    st.session_state.view_pdf = f"https://drive.google.com/uc?id={drive_id}"
                    st.session_state.pdf_title = title
                    st.rerun()
            with col_b:
                dl_url = f"https://drive.google.com/uc?id={drive_id}"
                st.markdown(f"[Muat Turun]({dl_url})", unsafe_allow_html=True)

# =============================================
# PDF PREVIEW
# =============================================
if "view_pdf" in st.session_state:
    url = st.session_state.view_pdf
    title = st.session_state.pdf_title
    st.markdown(f"### {title}")
    st.markdown(f'<iframe src="{url}" width="100%" height="800px" style="border:3px solid #2E7D32; border-radius:12px;"></iframe>', unsafe_allow_html=True)
    if st.button("Tutup", type="primary"):
        del st.session_state.view_pdf
        del st.session_state.pdf_title
        st.rerun()

# =============================================
# ADMIN PANEL
# =============================================
with st.sidebar:
    st.markdown("## Admin")
    pw = st.text_input("Password", type="password")
    if pw == "admin123":
        st.success("Login Berjaya!")

        file = st.file_uploader("PDF/DOCX", type=["pdf","docx"])
        thumb = st.file_uploader("Thumbnail", type=["png","jpg","jpeg"])
        title = st.text_input("Tajuk")
        cat = st.selectbox("Kategori", ["Keratan Bunga","Sayur-sayuran","Buah-buahan","Lain-lain"])

        if st.button("SIMPAN", type="primary"):
            if file and title:
                # Simpan PDF
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                local_pdf = os.path.join(LOCAL_UPLOADS, f"{ts}_{file.name}")
                with open(local_pdf, "wb") as f:
                    shutil.copyfileobj(file, f)
                drive_id = upload_file(local_pdf, UPLOADS_FOLDER_ID)

                # Simpan thumbnail
                thumb_id = None
                if thumb:
                    local_thumb = os.path.join(LOCAL_THUMBNAILS, f"{ts}_thumb{Path(thumb.name).suffix}")
                    with open(local_thumb, "wb") as f:
                        shutil.copyfileobj(thumb, f)
                    thumb_id = upload_file(local_thumb, THUMBNAILS_FOLDER_ID)

                # Extract text
                file.seek(0)
                text = ""
                if file.name.endswith(".pdf"):
                    reader = PyPDF2.PdfReader(file)
                    text = "\n".join(p.extract_text() or "" for p in reader.pages)
                else:
                    text = "\n".join(p.text for p in Document(file).paragraphs)

                # Simpan ke DB
                conn = get_db()
                conn.execute("INSERT INTO documents(title,content,category,file_name,drive_file_id,thumbnail_drive_id,upload_date) VALUES(?,?,?,?,?,?,?)",
                             (title, text, cat, file.name, drive_id, thumb_id, datetime.now().strftime("%Y-%m-%d %H:%M")))
                conn.commit()
                conn.close()

                upload_db()
                st.success("Berjaya disimpan!")
                st.rerun()
