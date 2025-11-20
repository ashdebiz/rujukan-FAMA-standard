import streamlit as st
import sqlite3
import os
import shutil
from datetime import datetime
import PyPDF2
from docx import Document
import io
from pathlib import Path

# =============================================
# GOOGLE DRIVE — PAKAI SERVICE ACCOUNT (100% JALAN!)
# =============================================
st.set_page_config(page_title="RUJUKAN FAMA STANDARD", page_icon="leaves", layout="centered")

# Pastikan service-account.json ada di repo
if not osraf.exists("service-account.json"):
    st.error("service-account.json tak jumpa! Letak di repo kau.")
    st.stop()

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import io as io_lib

# Setup Drive
SCOPES = ['https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_file("service-account.json", scopes=SCOPES)
drive = build('drive', 'v3', credentials=creds)

# Folder ID kau
ROOT_FOLDER_ID = "1RHHcCLR-n7k2rcwZr-QBFBD0KKpcAYTy"

# Auto buat subfolder
def folder_id(name, parent):
    q = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and '{parent}' in parents and trashed=false"
    r = drive.files().list(q=q, fields="files(id)").execute().get('files', [])
    if r:
        return r[0]['id']
    else:
        f = drive.files().create(body={'name': name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent]}, fields='id').execute()
        return f['id']

UPLOADS_ID = folder_id("uploads", ROOT_FOLDER_ID)
THUMBS_ID = folder_id("thumbnails", ROOT_FOLDER_ID)
DB_ID = folder_id("db", ROOT_FOLDER_ID)

st.success("Google Drive berjaya disambung!")

# Local
os.makedirs("tmp", exist_ok=True)
DB_PATH = "tmp/fama.db"

# Download DB
def pull_db():
    q = f"name='fama.db' and '{DB_ID}' in parents"
    r = drive.files().list(q=q, fields="files(id)").execute().get('files', [])
    if r:
        fid = r[0]['id']
        req = drive.files().get_media(fileId=fid)
        fh = io_lib.BytesIO()
        down = MediaIoBaseDownload(fh, req)
        done = False
        while not done:
            _, done = down.next_chunk()
        with open(DB_PATH, "wb") as f:
            f.write(fh.getbuffer())
        return True
    return False

# Upload DB
def push_db():
    media = MediaFileUpload(DB_PATH)
    q = f"name='fama.db' and '{DB_ID}' in parents"
    r = drive.files().list(q=q).execute().get('files', [])
    if r:
        drive.files().update(fileId=r[0]['id'], media_body=media).execute()
    else:
        drive.files().create(body={'name': 'fama.db', 'parents': [DB_ID]}, media_body=media).execute()

# Upload fail
def upload(path, parent):
    name = Path(path).name
    media = MediaFileUpload(path)
    f = drive.files().create(body={'name': name, 'parents': [parent]}, media_body=media, fields='id').execute()
    return f['id']

# Init DB
pull_db() or st.info("Database baru dibuat.")
conn = sqlite3.connect(DB_PATH)
conn.execute('''CREATE TABLE IF NOT EXISTS docs (
    id INTEGER PRIMARY KEY,
    title TEXT, content TEXT, cat TEXT,
    fname TEXT, fid TEXT, tid TEXT, date TEXT
)''')
conn.commit()
conn.close()

# =============================================
# TAJUK FAMA
# =============================================
st.markdown("""
<div style="text-align:center; padding:20px;">
    <img src="https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png" width="80">
    <h1 style="color:#2E7D32;">RUJUKAN FAMA STANDARD</h1>
    <p style="color:#388E3C; font-size:1.5em;">KELUARAN HASIL PERTANIAN</p>
</div>
""", unsafe_allow_html=True)

# =============================================
# ADMIN
# =============================================
with st.sidebar:
    st.header("Admin")
    if st.text_input("Password", type="password") == "admin123":
        st.success("Login OK!")
        
        f = st.file_uploader("PDF/DOCX", type=["pdf","docx"])
        t = st.file_uploader("Thumbnail", type=["png","jpg","jpeg"])
        title = st.text_input("Tajuk Standard")
        cat = st.selectbox("Kategori", ["Keratan Bunga","Sayur-sayuran","Buah-buahan","Lain-lain"])
        
        if st.button("SIMPAN STANDARD", type="primary"):
            if f and title:
                # Upload PDF
                p1 = f"tmp/{f.name}"
                with open(p1, "wb") as x:
                    x.write(f.getbuffer())
                fid = upload(p1, UPLOADS_ID)
                
                # Upload thumb
                tid = None
                if t:
                    p2 = f"tmp/thumb_{t.name}"
                    with open(p2, "wb") as x:
                        x.write(t.getbuffer())
                    tid = upload(p2, THUMBS_ID)
                
                # Extract text
                f.seek(0)
                text = ""
                if f.name.endswith(".pdf"):
                    text = "\n".join(p.extract_text() or "" for p in PyPDF2.PdfReader(f).pages)
                else:
                    text = "\n".join(p.text for p in Document(f).paragraphs)
                
                # Simpan DB
                conn = sqlite3.connect(DB_PATH)
                conn.execute("INSERT INTO docs(title,content,cat,fname,fid,tid,date) VALUES(?,?,?,?,?,?,?)",
                            (title, text, cat, f.name, fid, tid, datetime.now().strftime("%Y-%m-%d %H:%M")))
                conn.commit()
                conn.close()
                push_db()
                
                st.success("BERJAYA DISIMPAN!")
                st.balloons()
                st.rerun()

# =============================================
# CARIAN
# =============================================
q = st.text_input("Cari standard:")
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
sql = "SELECT title, content, cat, fname, fid, tid, date FROM docs WHERE 1=1"
p = []
if q:
    sql += " AND (title LIKE ? OR content LIKE ?)"
    p += [f"%{q}%", f"%{q}%"]
sql += " ORDER BY date DESC"
cur.execute(sql, p)
rows = cur.fetchall()
conn.close()

st.write(f"**Ditemui {len(rows)} standard**")

for r in rows:
    title, content, cat, fname, fid, tid, date = r
    with st.expander(f"{title} • {cat} • {date[:10]}"):
        c1, c2 = st.columns([1,3])
        with c1:
            if tid:
                st.image(f"https://drive.google.com/uc?id={tid}", use_column_width=True)
            else:
                st.image("https://via.placeholder.com/150x200/4CAF50/white?text=No+Image")
        with c2:
            st.write(content[:600] + ("..." if len(content)>600 else ""))
            st.markdown(f"[Muat Turun PDF](https://drive.google.com/uc?id={fid})")
