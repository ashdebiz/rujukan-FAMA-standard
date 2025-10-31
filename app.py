import streamlit as st
import sqlite3
import os
from datetime import datetime
import PyPDF2
from docx import Document
import io
import shutil
from pathlib import Path

# Konfigurasi
DB_NAME = "standards_db.sqlite"
ADMIN_PASSWORD = "admin123"  # Ubah ini untuk keselamatan; gunakan st.secrets di production
UPLOADS_DIR = "uploads"
THUMBNAILS_DIR = "thumbnails"
CATEGORIES = ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"]  # Tukar 'Padi' kepada 'Keratan Bunga'
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(THUMBNAILS_DIR, exist_ok=True)

# Inisialisasi skema DB sekali pada permulaan (hanya jika belum wujud)
@st.cache_resource
def init_db():
    conn = sqlite3.connect(DB_NAME)
    # Cipta jadual jika tiada
    conn.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'Lain-lain',
            file_name TEXT,
            file_path TEXT,
            thumbnail_path TEXT,
            upload_date TEXT NOT NULL
        )
    ''')
    # Tambah kolum jika tiada (migrasi untuk DB sedia ada)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(documents)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'category' not in columns:
        conn.execute("ALTER TABLE documents ADD COLUMN category TEXT DEFAULT 'Lain-lain'")
    if 'file_name' not in columns:
        conn.execute("ALTER TABLE documents ADD COLUMN file_name TEXT")
    if 'file_path' not in columns:
        conn.execute("ALTER TABLE documents ADD COLUMN file_path TEXT")
    if 'thumbnail_path' not in columns:
        conn.execute("ALTER TABLE documents ADD COLUMN thumbnail_path TEXT")
    conn.commit()
    conn.close()

init_db()  # Panggil sekali

# Fungsi untuk mendapatkan dokumen penuh berdasarkan ID
def get_document_by_id(doc_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, content, category, file_name, file_path, thumbnail_path, upload_date 
        FROM documents WHERE id = ?
    """, (doc_id,))
    result = cursor.fetchone()
    conn.close()
    return result

# Fungsi ekstrak teks dari PDF (dengan try-except)
def extract_pdf_text(file):
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        st.error(f"Ralat ekstrak PDF: {e}")
        return ""

# Fungsi ekstrak teks dari DOCX (dengan try-except)
def extract_docx_text(file):
    try:
        doc = Document(io.BytesIO(file.read()))
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    except Exception as e:
        st.error(f"Ralat ekstrak DOCX: {e}")
        return ""

# Fungsi simpan dokumen ke DB (sambungan baru setiap kali) - kini simpan fail asal juga
def save_document(title, content, category, uploaded_file, original_filename, thumbnail_path=None):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_ext = Path(original_filename).suffix
    safe_filename = f"{timestamp}_{Path(original_filename).stem}{file_ext}"
    file_path = os.path.join(UPLOADS_DIR, safe_filename)
    
    # Simpan fail asal ke disk
    with open(file_path, "wb") as f:
        shutil.copyfileobj(uploaded_file, f)
    
    # Simpan ke DB
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO documents (title, content, category, file_name, file_path, thumbnail_path, upload_date) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (title, content, category, original_filename, file_path, thumbnail_path, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    st.success(f"Dokumen '{title}' (Kategori: {category}) berjaya disimpan! Fail asal disimpan sebagai '{safe_filename}'.")

# Fungsi edit dokumen
def edit_document(doc_id, title, content, category):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE documents 
        SET title = ?, content = ?, category = ? 
        WHERE id = ?
    """, (title, content, category, doc_id))
    conn.commit()
    conn.close()
    st.success(f"Dokumen dengan ID {doc_id} berjaya dikemaskini!")

# Fungsi simpan thumbnail untuk dokumen sedia ada
def save_thumbnail(doc_id, thumbnail_file):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_ext = Path(thumbnail_file.name).suffix
    safe_filename = f"{timestamp}_thumb{file_ext}"
    thumbnail_path = os.path.join(THUMBNAILS_DIR, safe_filename)
    
    # Simpan thumbnail ke disk
    with open(thumbnail_path, "wb") as f:
        shutil.copyfileobj(thumbnail_file, f)
    
    # Update DB
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE documents SET thumbnail_path = ? WHERE id = ?", (thumbnail_path, doc_id))
    conn.commit()
    conn.close()
    st.success(f"Thumbnail berjaya disimpan untuk dokumen ID {doc_id}!")

# Fungsi padam dokumen (sambungan baru setiap kali)
def delete_document(doc_id, file_path, thumbnail_path):
    # Padam rekod dari DB
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()
    
    # Padam fail fizikal jika wujud
    if file_path and os.path.exists(file_path):
        os.remove(file_path)
    if thumbnail_path and os.path.exists(thumbnail_path):
        os.remove(thumbnail_path)
    
    st.success(f"Dokumen dengan ID {doc_id} berjaya dipadam!")

# Fungsi carian (sambungan baru setiap kali, case-insensitive, dengan filter kategori)
def search_documents(query, category_filter=""):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    sql = """
        SELECT title, content, file_name, file_path, thumbnail_path, upload_date, category
        FROM documents
    """
    params = []
    conditions = []
    if query:
        conditions.append("LOWER(title) LIKE ? OR LOWER(content) LIKE ?")
        params.extend([f"%{query.lower()}%", f"%{query.lower()}%"])
    if category_filter and category_filter != "Semua":
        conditions.append("category = ?")
        params.append(category_filter)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY upload_date DESC"
    cursor.execute(sql, params)
    results = cursor.fetchall()
    conn.close()
    return results

# Fungsi carian untuk admin (sama seperti user, tapi boleh dipanggil untuk filter senarai, dengan kategori)
def search_documents_admin(query="", category_filter=""):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    sql = """
        SELECT id, title, upload_date, file_name, file_path, thumbnail_path, category, content
        FROM documents
    """
    params = []
    conditions = []
    if query:
        conditions.append("LOWER(title) LIKE ? OR LOWER(content) LIKE ?")
        params.extend([f"%{query.lower()}%", f"%{query.lower()}%"])
    if category_filter and category_filter != "Semua":
        conditions.append("category = ?")
        params.append(category_filter)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY upload_date DESC"
    cursor.execute(sql, params)
    results = cursor.fetchall()
    conn.close()
    return results

# Fungsi untuk download fail
@st.cache_data
def get_file_data(file_path):
    with open(file_path, "rb") as f:
        return f.read()

# Fungsi untuk mendapatkan senarai dokumen (untuk admin)
def get_all_documents(category_filter=""):
    return search_documents_admin(category_filter=category_filter)

# Antara muka Streamlit - Diubah suai untuk mobile-friendly dengan layout centered
st.set_page_config(
    page_title="Rujukan FAMA Standard", 
    page_icon="🌾", 
    layout="centered",  # Layout centered untuk skrin kecil seperti smartphone
    initial_sidebar_state="collapsed"  # Sidebar collapsed secara default untuk mobile
)

# CSS custom untuk tema hijau pertanian (menarik)
st.markdown("""
    <style>
    .main-header {color: #2E7D32; font-size: 2.5em; text-align: center; margin-bottom: 0.5em;}
    .search-box {background-color: #E8F5E8; padding: 1em; border-radius: 10px; border-left: 5px solid #4CAF50;}
    .result-card {background-color: #F1F8E9; padding: 1em; border-radius: 10px; margin: 0.5em 0; border-left: 4px solid #66BB6A;}
    .category-filter {background-color: #E3F2FD; padding: 0.5em; border-radius: 5px; margin: 0.5em 0;}
    </style>
""", unsafe_allow_html=True)

# Sidebar untuk navigasi - Gunakan expander untuk mobile
with st.sidebar:
    st.markdown("## Navigasi")
    page = st.selectbox("Pilih Halaman", ["Halaman Pengguna (Carian)", "Halaman Admin (Upload)"])

if page == "Halaman Pengguna (Carian)":
    # Hero section yang menarik
    st.markdown('<h1 class="main-header">🌾 Rujukan FAMA Standard Keluaran Hasil Pertanian</h1>', unsafe_allow_html=True)
    st.markdown("""
        <p style="text-align: center; color: #4CAF50; font-size: 1.1em;">
        Temui panduan standard pertanian terkini dengan mudah. Klik butang di bawah untuk papar senarai standard mengikut kategori!
        </p>
    """, unsafe_allow_html=True)
    
    # Kotak carian yang friendly dengan contoh clickable (diubah untuk papar senarai kategori)
    st.markdown('<div class="search-box">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🌸 Senarai Standard Keratan Bunga", key="suggest1"):
            st.session_state.query = ""
            st.session_state.user_category = "Keratan Bunga"
            st.rerun()
    with col2:
        if st.button("🥬 Senarai Standard Sayur-sayuran", key="suggest2"):
            st.session_state.query = ""
            st.session_state.user_category = "Sayur-sayuran"
            st.rerun()
    with col3:
        if st.button("🍎 Senarai Standard Buah-buahan", key="suggest3"):
            st.session_state.query = ""
            st.session_state.user_category = "Buah-buahan"
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Input carian dan filter kategori (autofill dari session_state jika ada)
    if "query" not in st.session_state:
        st.session_state.query = ""
    if "user_category" not in st.session_state:
        st.session_state.user_category = "Semua"
    
    col_search, col_cat = st.columns([3, 1])
    with col_search:
        query = st.text_input(
            "🔍 Masukkan kata kunci carian (opsional):", 
            value=st.session_state.query, 
            placeholder="Contoh: standard keratan bunga",
            key="search_input",
            help="Tekan Enter untuk cari automatik!"
        )
    with col_cat:
        category_filter = st.selectbox(
            "Filter Kategori:",
            options=["Semua"] + CATEGORIES,
            index=0 if st.session_state.user_category == "Semua" else CATEGORIES.index(st.session_state.user_category) + 1 if st.session_state.user_category in CATEGORIES else 0,
            key="category_filter_user"
        )
    
    # Carian automatik pada change (lebih friendly, tiada butang)
    if query != st.session_state.query or category_filter != st.session_state.user_category:
        st.session_state.query = query
        st.session_state.user_category = category_filter
        st.rerun()
    
    # Jalankan carian jika query berubah atau bukan kosong
    if query or st.session_state.query or category_filter != "Semua":
        with st.spinner(f'Mencari dokumen berkaitan "{query}" di kategori "{category_filter}"...'):
            results = search_documents(query, category_filter)
            
            # Metric untuk menarik
            col_left, col_mid, col_right = st.columns(3)
            with col_mid:
                st.metric("Dokumen Ditemui", len(results))
            
            if results:
                st.subheader(f"📋 Hasil Carian ({len(results)} Dokumen)")
                for i, (title, content, file_name, file_path, thumbnail_path, date, doc_category) in enumerate(results, 1):
                    # Gunakan expander untuk card-like friendly design
                    with st.expander(f"📄 {title} ({doc_category}) (Diupload: {date})", expanded=False):
                        st.markdown(f'<div class="result-card">', unsafe_allow_html=True)
                        
                        # Layout: Thumbnail kiri, content kanan
                        col_thumb, col_content = st.columns([1, 3])
                        with col_thumb:
                            if thumbnail_path and os.path.exists(thumbnail_path):
                                st.image(thumbnail_path, caption="Thumbnail", width=150, use_container_width=True)
                            else:
                                st.markdown("🖼️ Tiada thumbnail")
                        
                        with col_content:
                            st.write(f"**Ringkasan:** {content[:300]}..." if len(content) > 300 else content)
                            st.caption(f"Fail: {file_name or 'Tiada'} | Kategori: **{doc_category}**")
                        
                        # Download button di bawah
                        if file_path and os.path.exists(file_path):
                            file_data = get_file_data(file_path)
                            mime_type = "application/pdf" if file_name and file_name.endswith('.pdf') else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                            st.download_button(
                                label=f"📥 Muat Turun Dokumen Asal ({file_name or 'Fail'})",
                                data=file_data,
                                file_name=file_name or "dokumen.pdf",
                                mime=mime_type,
                                key=f"download_{i}",
                                use_container_width=True,
                                type="secondary"
                            )
                        else:
                            st.warning("Fail asal tidak ditemui.")
                        
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        st.markdown("---")  # Pemisah halus
            else:
                st.warning("❌ Tiada hasil ditemui. Cuba kata kunci lain atau upload dokumen baru di halaman admin.")
                st.info("💡 Cuba butang di atas untuk papar senarai kategori!")
    else:
        st.info("🌱 Klik butang di atas untuk papar senarai standard mengikut kategori, atau gunakan carian dan filter!")

elif page == "Halaman Admin (Upload)":
    st.title("🔐 Halaman Admin - Upload Dokumen Standard")
    
    # Pengesahan kata laluan
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        password = st.text_input("Masukkan kata laluan admin:", type="password")
        if st.button("Log Masuk", key="admin_login", use_container_width=True):
            if password == ADMIN_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Kata laluan salah!")
        st.stop()
    
    # Antara muka upload selepas log masuk
    st.success("Log masuk berjaya! Anda boleh upload dokumen sekarang.")
    if st.button("Log Keluar", key="admin_logout", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()
    
    # Upload fail utama (dengan kategori)
    st.subheader("Upload Dokumen Utama")
    uploaded_file = st.file_uploader("Pilih fail PDF atau DOCX untuk diupload:", type=["pdf", "docx"], key="main_file")
    title = st.text_input("Tajuk Dokumen (contoh: Standard Keluaran Keratan Bunga):", key="doc_title")
    category = st.selectbox("Pilih Kategori:", options=CATEGORIES, index=0, key="doc_category", help="Kategori untuk memudahkan carian")
    
    if uploaded_file is not None and title:
        # Reset pointer fail untuk baca dua kali (sekali untuk ekstrak, sekali untuk simpan)
        uploaded_file.seek(0)
        
        # Ekstrak teks berdasarkan jenis fail
        if uploaded_file.name.endswith('.pdf'):
            content = extract_pdf_text(uploaded_file)
        elif uploaded_file.name.endswith('.docx'):
            content = extract_docx_text(uploaded_file)
        else:
            st.error("Format fail tidak disokong! Hanya PDF atau DOCX.")
            st.stop()
        
        # Reset pointer semula untuk simpan fail
        uploaded_file.seek(0)
        
        st.write("**Pratonton Kandungan (1000 aksara pertama):**")
        st.text_area("", value=content[:1000], height=200, disabled=True)
        
        if st.button("Simpan Dokumen Utama", key="save_main_doc", use_container_width=True):
            save_document(title, content, category, uploaded_file, uploaded_file.name)
            st.rerun()
    
    # Upload thumbnail untuk dokumen sedia ada
    st.subheader("Upload Thumbnail untuk Dokumen Sedia Ada")
    existing_docs = get_all_documents()  # Sentiasa papar semua untuk pilihan thumbnail
    if existing_docs:
        doc_options = {f"{doc[1]} (ID: {doc[0]}, Kategori: {doc[6]})": doc[0] for doc in existing_docs}
        selected_doc = st.selectbox("Pilih Dokumen untuk Tambah Thumbnail:", options=list(doc_options.keys()))
        if selected_doc:
            selected_id = doc_options[selected_doc]
            thumbnail_file = st.file_uploader("Pilih fail thumbnail (PNG/JPG):", type=["png", "jpg", "jpeg"], key="thumbnail_file")
            if thumbnail_file is not None:
                if st.button("Simpan Thumbnail", key="save_thumbnail", use_container_width=True):
                    save_thumbnail(selected_id, thumbnail_file)
                    st.rerun()
    else:
        st.info("Tiada dokumen sedia ada. Upload dokumen utama dahulu.")
    
    # Senarai dokumen sedia ada dengan ciri carian dan filter kategori
    st.subheader("Dokumen Sedia Ada")
    col_admin_search, col_admin_cat = st.columns([3, 1])
    with col_admin_search:
        admin_query = st.text_input("Cari dokumen (masukkan kata kunci):", placeholder="Contoh: keratan bunga atau standard", key="admin_query")
    with col_admin_cat:
        admin_category_filter = st.selectbox("Filter Kategori:", options=["Semua"] + CATEGORIES, index=0, key="admin_category_filter")
    
    # Carian automatik (tiada butang)
    existing_docs = search_documents_admin(admin_query, admin_category_filter)
    if admin_query or admin_category_filter != "Semua":
        filter_info = f" (Carian: '{admin_query}', Kategori: '{admin_category_filter}') " if admin_query or admin_category_filter != "Semua" else ""
        st.info(f"Memaparkan {len(existing_docs)} dokumen{filter_info}.")
    else:
        st.info("Memaparkan semua dokumen.")
    
    # Inisialisasi session_state untuk edit dan padam jika tiada
    if "to_delete" not in st.session_state:
        st.session_state.to_delete = None
    if "editing_id" not in st.session_state:
        st.session_state.editing_id = None
    
    # Form Edit jika ada dokumen yang sedang diedit
    if st.session_state.editing_id is not None:
        st.subheader("Edit Dokumen")
        doc_data = get_document_by_id(st.session_state.editing_id)
        if doc_data:
            doc_id, current_title, current_content, current_category, file_name, file_path, thumbnail_path, upload_date = doc_data
            
            # Form edit
            new_title = st.text_input("Tajuk Dokumen:", value=current_title, key="edit_title")
            new_category = st.selectbox("Kategori:", options=CATEGORIES, index=CATEGORIES.index(current_category) if current_category in CATEGORIES else 0, key="edit_category")
            new_content = st.text_area("Kandungan (Teks Diekstrak):", value=current_content, height=200, key="edit_content")
            
            col_save, col_cancel = st.columns(2)
            with col_save:
                if st.button("💾 Simpan Perubahan", key="save_edit", use_container_width=True):
                    edit_document(doc_id, new_title, new_content, new_category)
                    st.session_state.editing_id = None
                    st.rerun()
            with col_cancel:
                if st.button("❌ Batal Edit", key="cancel_edit", use_container_width=True):
                    st.session_state.editing_id = None
                    st.rerun()
            
            st.markdown("---")
    
    if existing_docs:
        for doc_id, title, date, file_name, file_path, thumbnail_path, doc_category, content in existing_docs:
            # Gunakan container untuk mobile
            with st.container():
                # Columns disesuaikan untuk mobile: thumbnail dan info bertindan jika perlu
                col1, col2, col3 = st.columns([2, 1, 1])  # Tambah kolum untuk edit
                with col1:
                    st.write(f"- **{title}** (Diupload: {date}) | Fail: {file_name or 'Tiada'} | Kategori: **{doc_category}**")
                with col2:
                    # Papar thumbnail jika ada
                    if thumbnail_path and os.path.exists(thumbnail_path):
                        st.image(thumbnail_path, width=80, caption="")  # Saiz kecil untuk mobile
                    else:
                        st.write("Tiada thumb")
                with col3:
                    col_edit, col_del = st.columns(2)
                    with col_edit:
                        if st.button("✏️ Edit", key=f"edit_btn_{doc_id}", use_container_width=True):
                            st.session_state.editing_id = doc_id
                            st.rerun()
                    with col_del:
                        if st.button("🗑️ Padam", key=f"del_btn_{doc_id}", use_container_width=True):
                            st.session_state.to_delete = doc_id
                            st.rerun()
        
        # Modal konfirmasi padam (hanya jika ada yang dipilih)
        if st.session_state.to_delete is not None:
            st.warning(f"Adakah anda pasti mahu padam dokumen dengan ID {st.session_state.to_delete}? Tindakan ini tidak boleh dibatalkan!")
            
            col_confirm, col_cancel = st.columns(2)
            with col_confirm:
                if st.button("Ya, Padam!", key="confirm_delete", use_container_width=True):
                    # Dapatkan file_path dan thumbnail_path untuk padam
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("SELECT file_path, thumbnail_path FROM documents WHERE id = ?", (st.session_state.to_delete,))
                    result = cursor.fetchone()
                    file_path = result[0] if result else None
                    thumbnail_path = result[1] if result else None
                    conn.close()
                    
                    delete_document(st.session_state.to_delete, file_path, thumbnail_path)
                    st.session_state.to_delete = None
                    st.rerun()
            with col_cancel:
                if st.button("Batal", key="cancel_delete", use_container_width=True):
                    st.session_state.to_delete = None
                    st.rerun()
            
            # Garis pemisah untuk modal
            st.markdown("---")
    else:
        st.info("Tiada dokumen ditemui. Upload yang pertama!")