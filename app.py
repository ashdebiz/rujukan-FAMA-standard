# app.py
import streamlit as st
import psycopg2
import os
import shutil
from datetime import datetime
import PyPDF2
from docx import Document
import io
import zipfile
from pathlib import Path
import mimetypes

# =============================================
# KONEKSI SUPABASE (DATA KEKAL SELAMANYA)
# =============================================
@st.cache_resource
def get_db():
    return psycopg2.connect(
        host=st.secrets["SUPABASE_URL"],
        database="postgres",
        user="postgres",
        password=st.secrets["SUPABASE_KEY"],
        port="5432"
    )

# Init sekali je
conn = get_db()
cur = conn.cursor()
cur.execute("SELECT 1 FROM pg_tables WHERE tablename = 'documents'")
if not cur.fetchone():
    st.error("Jadual belum dibuat! Sila jalankan SQL di Supabase dulu.")
    st.stop()
conn.close()

# =============================================
# SEMUA FUNGSI ASAL KAMU (cuma tukar sqlite → postgres)
# =============================================
def save_document(title, content, category, uploaded_file, original_filename):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = Path(original_filename).suffix
    safe_name = f"{timestamp}_{Path(original_filename).stem}{ext}"
    file_path = os.path.join("uploads", safe_name)
    os.makedirs("uploads", exist_ok=True)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(uploaded_file, f)

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO documents (title, content, category, file_name, file_path, upload_date)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (title, content, category, original_filename, file_path, datetime.now()))
    conn.commit()
    conn.close()
    st.success("Berjaya disimpan!")

def search_documents(query="", category_filter="Semua"):
    conn = get_db()
    cur = conn.cursor()
    sql = "SELECT title, content, file_name, file_path, thumbnail_path, upload_date, category FROM documents"
    params = []
    conditions = []
    if query:
        conditions.append("(title ILIKE %s OR content ILIKE %s)")
        params.extend([f"%{query}%", f"%{query}%"])
    if category_filter != "Semua":
        conditions.append("category = %s")
        params.append(category_filter)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY upload_date DESC"
    cur.execute(sql, params)
    results = cur.fetchall()
    conn.close()
    return results

# =============================================
# UI 100% SAMA DENGAN GAMBAR KAMU
# =============================================
st.set_page_config(page_title="Rujukan FAMA Standard", page_icon="rice", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<div style="text-align:center; margin-bottom:20px;">
    <h1 style="color:#2E7D32; font-size:2.8em;">RUJUKAN FAMA STANDARD<br>KELUARAN HASIL PERTANIAN</h1>
    <p style="color:#4CAF50; font-size:1.2em;">Temui panduan standard pertanian terkini dengan mudah. Klik butang di bawah untuk papar senarai standard mengikut kategori!</p>
</div>
""", unsafe_allow_html=True)

# Statistik
conn = get_db()
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM documents")
total = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM documents WHERE DATE(upload_date) = CURRENT_DATE")
today = cur.fetchone()[0]
conn.close()

c1, c2 = st.columns(2)
c1.metric("Jumlah Standard Keseluruhan", total)
c2.metric("Standard Baru Hari Ini", today)

# 4 Butang Kategori Hijau Bulat (sama persis gambar)
col1, col2, col3, col4 = st.columns(4)
with col1:
    if st.button("Keratan Bunga", type="primary", use_container_width=True):
        st.session_state.cat = "Keratan Bunga"
        st.rerun()
with col2:
    if st.button("Sayur-sayuran", type="primary", use_container_width=True):
        st.session_state.cat = "Sayur-sayuran"
        st.rerun()
with col3:
    if st.button("Buah-buahan", type="primary", use_container_width=True):
        st.session_state.cat = "Buah-buahan"
        st.rerun()
with col4:
    if st.button("Lain-lain", type="primary", use_container_width=True):
        st.session_state.cat = "Lain-lain"
        st.rerun()

if "cat" not in st.session_state:
    st.session_state.cat = "Semua"

query = st.text_input("Masukkan kata kunci carian (opsional):", placeholder="Contoh: standard keratan bunga")
category = st.selectbox("Filter Kategori:", ["Semua"] + ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"],
                        index=0 if st.session_state.cat=="Semua" else ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"].index(st.session_state.cat)+1)

results = search_documents(query, category if category != "Semua" else "")

st.write(f"**Ditemui {len(results)} dokumen**")
for title, content, fname, fpath, thumb, date, cat in results:
    with st.expander(f"{title} ({cat}) – {date.strftime('%d/%m/%Y')}"):
        st.write(content[:500] + ("..." if len(content)>500 else ""))
        if fpath and os.path.exists(fpath):
            with open(fpath, "rb") as f:
                st.download_button("Muat Turun PDF/DOCX", f.read(), file_name=fname)

# ADMIN: Backup satu klik
with st.sidebar:
    st.markdown("## Admin")
    if st.checkbox("Backup Database"):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM documents")
        rows = cur.fetchall()
        mem = io.BytesIO()
        with zipfile.ZipFile(mem, "w") as zf:
            for row in rows:
                if row[3] and os.path.exists(row[3]):
                    zf.write(row[3], f"uploads/{os.path.basename(row[3])}")
                if row[4] and os.path.exists(row[4]):
                    zf.write(row[4], f"thumbnails/{os.path.basename(row[4])}")
        mem.seek(0)
        st.download_button("Download Backup Penuh", mem, f"fama_backup_{datetime.now().strftime('%Y%m%d')}.zip", "application/zip")