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
# AUTO MOUNT GOOGLE DRIVE (CARA PALING SENANG 2025)
# =============================================
st.set_page_config(page_title="RUJUKAN FAMA STANDARD", page_icon="leaves", layout="centered")

# Mount Drive (pertama kali je kena allow)
if not os.path.exists("/content/drive"):
    from google.colab import drive
    drive.mount('/content/drive')
    st.success("Google Drive berjaya disambung! Data kekal selamanya!")
else:
    st.sidebar.success("Drive dah sambung")

# Folder utama di Drive kau (ubah kalau nak folder lain)
DRIVE_ROOT = "/content/drive/MyDrive/FAMA_STANDARD_APP"
DB_PATH = f"{DRIVE_ROOT}/fama_standards.db"
UPLOADS_DIR = f"{DRIVE_ROOT}/uploads"
THUMBNAILS_DIR = f"{DRIVE_ROOT}/thumbnails"

# Buat folder kalau tak wujud
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(THUMBNAILS_DIR, exist_ok=True)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# =============================================
# DATABASE
# =============================================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

# Buat table kalau tak ada
conn = get_db()
conn.execute('''
    CREATE TABLE IF NOT EXISTS docs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT,
        category TEXT DEFAULT 'Lain-lain',
        file_name TEXT,
        file_path TEXT,
        thumb_path TEXT,
        upload_date TEXT
    )
''')
conn.commit()
conn.close()

# =============================================
# TAJUK FAMA CANTIK
# =============================================
st.markdown("""
<div style="text-align:center; padding:30px 0;">
    <img src="https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png" width="80">
    <h1 style="color:#2E7D32; margin:10px 0;">RUJUKAN FAMA STANDARD</h1>
    <p style="color:#388E3C; font-size:1.6em;">KELUARAN HASIL PERTANIAN</p>
</div>
""", unsafe_allow_html=True)

# =============================================
# STATISTIK
# =============================================
conn = get_db()
total = conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
today = conn.execute("SELECT COUNT(*) FROM docs WHERE date(upload_date) = date('now')").fetchone()[0]
conn.close()

c1, c2 = st.columns(2)
c1.metric("JUMLAH STANDARD", total)
c2.metric("BARU HARI INI", today)

# =============================================
# ADMIN PANEL
# =============================================
with st.sidebar:
    st.header("Admin Panel")
    pw = st.text_input("Password", type="password")
    
    if pw == "admin123":
        st.success("Login Berjaya!")

        uploaded_file = st.file_uploader("Upload PDF/DOCX", type=["pdf","docx"])
        thumbnail = st.file_uploader("Thumbnail (gambar)", type=["png","jpg","jpeg"])
        title = st.text_input("Tajuk Standard")
        category = st.selectbox("Kategori", ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"])

        if st.button("SIMPAN STANDARD", type="primary"):
            if uploaded_file and title:
                # Simpan file
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_ext = Path(uploaded_file.name).suffix
                new_path = os.path.join(UPLOADS_DIR, f"{ts}_{uploaded_file.name}")
                with open(new_path, "wb") as f:
                    shutil.copyfileobj(uploaded_file, f)

                # Simpan thumbnail
                thumb_path = None
                if thumbnail:
                    thumb_path = os.path.join(THUMBNAILS_DIR, f"{ts}_thumb{Path(thumbnail.name).suffix}")
                    with open(thumb_path, "wb") as f:
                        shutil.copyfileobj(thumbnail, f)

                # Extract text
                uploaded_file.seek(0)
                text = ""
                if uploaded_file.name.endswith(".pdf"):
                    reader = PyPDF2.PdfReader(uploaded_file)
                    text = "\n".join(page.extract_text() or "" for page in reader.pages)
                elif uploaded_file.name.endswith(".docx"):
                    doc = Document(uploaded_file)
                    text = "\n".join(p.text for p in doc.paragraphs)

                # Simpan ke DB
                conn = get_db()
                conn.execute("""INSERT INTO docs 
                    (title, content, category, file_name, file_path, thumb_path, upload_date)
                    VALUES (?,?,?, ?,?,?,?)""",
                    (title, text, category, uploaded_file.name, new_path, thumb_path, datetime.now().strftime("%Y-%m-%d %H:%M")))
                conn.commit()
                conn.close()

                st.success(f"Berjaya simpan: {title}")
                st.balloons()
                st.rerun()

# =============================================
# CARIAN & SENARAI
# =============================================
search = st.text_input("Cari standard:")
conn = get_db()
cur = conn.cursor()

sql = "SELECT title, content, category, file_name, file_path, thumb_path, upload_date FROM docs WHERE 1=1"
params = []

if search:
    sql += " AND (title LIKE ? OR content LIKE ?)"
    params.extend([f"%{search}%", f"%{search}%"])

sql += " ORDER BY upload_date DESC"
cur.execute(sql, params)
results = cur.fetchall()
conn.close()

st.write(f"**Ditemui {len(results)} standard**")

for row in results:
    title, content, cat, fname, fpath, tpath, date = row
    with st.expander(f"{title} • {cat} • {date[:10]}"):
        col1, col2 = st.columns([1, 3])
        with col1:
            img = tpath if tpath and os.path.exists(tpath) else "https://via.placeholder.com/150x200/4CAF50/white?text=FAMA"
            st.image(img, use_column_width=True)
        with col2:
            st.write(content[:700] + ("..." if len(content) > 700 else ""))
            if os.path.exists(fpath):
                with open(fpath, "rb") as f:
                    st.download_button("Muat Turun PDF", f.read(), file_name=fname, key=f"dl_{title}")

# =============================================
# FOOTER
# =============================================
st.markdown("---")
st.markdown("<p style='text-align:center; color:#666;'>App ini menggunakan Google Drive anda • Data kekal selamanya</p>", unsafe_allow_html=True)
