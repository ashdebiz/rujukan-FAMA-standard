import streamlit as st
import sqlite3
import os
import shutil
from datetime import datetime
import PyPDF2
from docx import Document
from pathlib import Path

# =============================================
# AUTO MOUNT GOOGLE DRIVE (PAKAI gdown + manual folder)
# =============================================
st.set_page_config(page_title="RUJUKAN FAMA STANDARD", page_icon="leaves", layout="centered")

# Folder di Drive kau (ubah kalau nak letak folder lain)
DRIVE_ROOT = "/content/drive/MyDrive/FAMA_STANDARD_APP"
DB_PATH = f"{DRIVE_ROOT}/fama.db"
UPLOADS_DIR = f"{DRIVE_ROOT}/uploads"
THUMBS_DIR = f"{DRIVE_ROOT}/thumbnails"

# Mount Drive (cara paling senang & 100% jalan)
if not os.path.exists("/content/drive"):
    from google.colab import drive
    drive.mount('/content/drive')
    st.success("Google Drive berjaya disambung! Data kekal selamanya!")
else:
    st.sidebar.success("Drive dah sambung")

# Buat folder kalau tak wujud
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(THUMBS_DIR, exist_ok=True)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# =============================================
# DATABASE
# =============================================
conn = sqlite3.connect(DB_PATH)
conn.execute('''
CREATE TABLE IF NOT EXISTS docs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    content TEXT,
    cat TEXT,
    fname TEXT,
    fpath TEXT,
    tpath TEXT,
    date TEXT
)
''')
conn.commit()
conn.close()

# =============================================
# TAJUK
# =============================================
st.markdown("""
<div style="text-align:center; padding:30px;">
    <img src="https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png" width="80">
    <h1 style="color:#2E7D32;">RUJUKAN FAMA STANDARD</h1>
    <p style="color:#388E3C; font-size:1.6em;">KELUARAN HASIL PERTANIAN</p>
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
        title = st.text_input("Tajuk")
        cat = st.selectbox("Kategori", ["Keratan Bunga","Sayur-sayuran","Buah-buahan","Lain-lain"])
        
        if st.button("SIMPAN", type="primary"):
            if f and title:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                fpath = f"{UPLOADS_DIR}/{ts}_{f.name}"
                with open(fpath, "wb") as x:
                    x.write(f.getbuffer())
                
                tpath = None
                if t:
                    tpath = f"{THUMBS_DIR}/{ts}_{t.name}"
                    with open(tpath, "wb") as x:
                        x.write(t.getbuffer())
                
                # Extract text
                f.seek(0)
                text = ""
                if f.name.endswith(".pdf"):
                    text = "\n".join(p.extract_text() or "" for p in PyPDF2.PdfReader(f).pages)
                elif f.name.endswith(".docx"):
                    text = "\n".join(p.text for p in Document(f).paragraphs)
                
                conn = sqlite3.connect(DB_PATH)
                conn.execute("INSERT INTO docs(title,content,cat,fname,fpath,tpath,date) VALUES(?,?,?,?,?,?,?)",
                            (title, text, cat, f.name, fpath, tpath, datetime.now().strftime("%Y-%m-%d %H:%M")))
                conn.commit()
                conn.close()
                
                st.success("BERJAYA DISIMPAN!")
                st.balloons()
                st.rerun()

# =============================================
# CARIAN
# =============================================
q = st.text_input("Cari standard:")
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
sql = "SELECT title,content,cat,fname,fpath,tpath,date FROM docs WHERE 1=1"
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
    title, content, cat, fname, fpath, tpath, date = r
    with st.expander(f"{title} • {cat} • {date[:10]}"):
        c1, c2 = st.columns([1,3])
        with c1:
            img = tpath if tpath and os.path.exists(tpath) else "https://via.placeholder.com/150"
            st.image(img, use_column_width=True)
        with c2:
            st.write(content[:600] + ("..." if len(content)>600 else ""))
            if os.path.exists(fpath):
                with open(fpath, "rb") as x:
                    st.download_button("Muat Turun", x.read(), file_name=fname)
