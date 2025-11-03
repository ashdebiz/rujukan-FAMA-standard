import streamlit as st
import sqlite3
import os
from datetime import datetime, date
import PyPDF2
from docx import Document
import io
import shutil
from pathlib import Path
import mimetypes  # Tambahan untuk mime detection

# Konfigurasi Streamlit - HARUS DI BAWAH SEBELUM SEBARANG ST CALL LAIN
st.set_page_config(
    page_title="Rujukan FAMA Standard", 
    page_icon="🌾", 
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Konfigurasi
DB_NAME = "standards_db.sqlite"
ADMIN_PASSWORD = "admin123"  # Hardcoded untuk local dev; gunakan st.secrets di production
UPLOADS_DIR = "uploads"
THUMBNAILS_DIR = "thumbnails"
CATEGORIES = ["Keratan Bunga", "Sayur-sayuran", "Buah-buahan", "Lain-lain"]
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(THUMBNAILS_DIR, exist_ok=True)

# Inisialisasi skema DB dengan FTS5 untuk carian cepat
@st.cache_resource
def init_db():
    conn = sqlite3.connect(DB_NAME)
    # Jadual utama
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
    # Virtual table untuk FTS (full-text search)
    conn.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
            title, content, category, content='documents', content_rowid='id'
        )
    ''')
    # Trigger untuk sync FTS (auto-update)
    conn.execute('''
        CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
            INSERT INTO documents_fts(rowid, title, content, category) VALUES (new.id, new.title, new.content, new.category);
        END;
    ''')
    conn.execute('''
        CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, title, content, category) VALUES ('delete', old.id, old.title, old.content, old.category);
        END;
    ''')
    conn.execute('''
        CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, title, content, category) VALUES ('delete', old.id, old.title, old.content, old.category);
            INSERT INTO documents_fts(rowid, title, content, category) VALUES (new.id, new.title, new.content, new.category);
        END;
    ''')
    # Migrasi kolum lama
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
    # Sync FTS jika DB lama
    conn.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
    conn.commit()
    conn.close()

init_db()

# Fungsi untuk sync FTS selepas operasi (optional, trigger handle most)
def sync_fts():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
    conn.commit()
    conn.close()

# Fungsi untuk mendapatkan statistik
@st.cache_data(ttl=300)  # Cache 5 minit
def get_stats():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Jumlah keseluruhan
    total_docs = cursor.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    # Jumlah hari ini
    today = date.today().strftime("%Y-%m-%d")
    today_docs = cursor.execute("SELECT COUNT(*) FROM documents WHERE upload_date LIKE ?", (f"{today}%",)).fetchone()[0]
    conn.close()
    return total_docs, today_docs

# Fungsi mendapatkan dokumen penuh berdasarkan ID
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

# Fungsi ekstrak teks dari PDF
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

# Fungsi ekstrak teks dari DOCX
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

# Fungsi simpan dokumen (dengan validasi)
def save_document(title, content, category, uploaded_file, original_filename, thumbnail_path=None):
    if not title.strip():
        st.error("Nama komoditi / tajuk dokumen tidak boleh kosong!")
        return
    uploaded_file.seek(0)  # Reset untuk saiz check
    if len(uploaded_file.read()) > MAX_FILE_SIZE:
        st.error("Fail terlalu besar! Maksimum 10MB.")
        return
    uploaded_file.seek(0)  # Reset untuk simpan
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_ext = Path(original_filename).suffix
    safe_filename = f"{timestamp}_{Path(original_filename).stem}{file_ext}"
    file_path = os.path.join(UPLOADS_DIR, safe_filename)
    
    with open(file_path, "wb") as f:
        shutil.copyfileobj(uploaded_file, f)
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO documents (title, content, category, file_name, file_path, thumbnail_path, upload_date) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (title, content, category, original_filename, file_path, thumbnail_path, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    sync_fts()  # Sync FTS
    st.success(f"Dokumen '{title}' (Kategori: {category}) berjaya disimpan!")

# Fungsi edit dokumen, attachment, dan thumbnail
def edit_document(doc_id, title, content, category, new_attachment_file=None, current_file_path=None, current_file_name=None, new_thumbnail_file=None, current_thumbnail_path=None):
    if not title.strip():
        st.error("Nama komoditi / tajuk tidak boleh kosong!")
        return
    
    new_file_path = current_file_path
    new_file_name = current_file_name
    new_content = content  # Gunakan content yang diedit atau ekstrak baru
    
    # Edit attachment jika ada fail baru
    if new_attachment_file is not None:
        new_attachment_file.seek(0)
        if len(new_attachment_file.read()) > MAX_FILE_SIZE:
            st.error("Fail attachment terlalu besar! Maksimum 10MB.")
            return
        new_attachment_file.seek(0)
        
        # Ekstrak content baru
        if new_attachment_file.name.endswith('.pdf'):
            new_content = extract_pdf_text(new_attachment_file)
        elif new_attachment_file.name.endswith('.docx'):
            new_content = extract_docx_text(new_attachment_file)
        else:
            st.error("Format fail attachment tidak disokong! Hanya PDF atau DOCX.")
            return
        
        new_attachment_file.seek(0)
        
        # Simpan fail baru
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_ext = Path(new_attachment_file.name).suffix
        safe_filename = f"{timestamp}_{Path(new_attachment_file.name).stem}{file_ext}"
        new_file_path = os.path.join(UPLOADS_DIR, safe_filename)
        new_file_name = new_attachment_file.name
        
        with open(new_file_path, "wb") as f:
            shutil.copyfileobj(new_attachment_file, f)
        
        # Padam fail lama jika wujud
        if current_file_path and os.path.exists(current_file_path):
            os.remove(current_file_path)
    
    # Edit thumbnail jika ada
    new_thumbnail_path = current_thumbnail_path
    if new_thumbnail_file is not None:
        new_thumbnail_file.seek(0)
        if len(new_thumbnail_file.read()) > MAX_FILE_SIZE / 10:  # Thumbnail kecil
            st.error("Thumbnail terlalu besar!")
            return
        new_thumbnail_file.seek(0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_ext = Path(new_thumbnail_file.name).suffix
        safe_filename = f"{timestamp}_thumb{file_ext}"
        new_thumbnail_path = os.path.join(THUMBNAILS_DIR, safe_filename)
        
        with open(new_thumbnail_path, "wb") as f:
            shutil.copyfileobj(new_thumbnail_file, f)
        
        # Padam thumbnail lama jika wujud
        if current_thumbnail_path and os.path.exists(current_thumbnail_path):
            os.remove(current_thumbnail_path)
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE documents 
        SET title = ?, content = ?, category = ?, file_name = ?, file_path = ?, thumbnail_path = ? 
        WHERE id = ?
    """, (title, new_content, category, new_file_name, new_file_path, new_thumbnail_path, doc_id))
    conn.commit()
    conn.close()
    sync_fts()
    st.success(f"Dokumen dengan ID {doc_id} berjaya dikemaskini! Nama komoditi, kategori, attachment dan thumbnail dikemaskini jika diubah.")

# Fungsi simpan thumbnail untuk dokumen sedia ada (terpisah)
def save_thumbnail(doc_id, thumbnail_file):
    thumbnail_file.seek(0)
    if len(thumbnail_file.read()) > MAX_FILE_SIZE / 10:  # Thumbnail kecil
        st.error("Thumbnail terlalu besar!")
        return
    thumbnail_file.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_ext = Path(thumbnail_file.name).suffix
    safe_filename = f"{timestamp}_thumb{file_ext}"
    thumbnail_path = os.path.join(THUMBNAILS_DIR, safe_filename)
    
    with open(thumbnail_path, "wb") as f:
        shutil.copyfileobj(thumbnail_file, f)
    
    # Dapatkan thumbnail lama dan padam
    doc_data = get_document_by_id(doc_id)
    if doc_data:
        current_thumbnail = doc_data[6]
        if current_thumbnail and os.path.exists(current_thumbnail):
            os.remove(current_thumbnail)
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE documents SET thumbnail_path = ? WHERE id = ?", (thumbnail_path, doc_id))
    conn.commit()
    conn.close()
    sync_fts()
    st.success(f"Thumbnail berjaya dikemaskini untuk dokumen ID {doc_id}!")

# Fungsi padam dokumen
def delete_document(doc_id, file_path, thumbnail_path):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()
    
    if file_path and os.path.exists(file_path):
        os.remove(file_path)
    if thumbnail_path and os.path.exists(thumbnail_path):
        os.remove(thumbnail_path)
    
    sync_fts()
    st.success(f"Dokumen dengan ID {doc_id} berjaya dipadam!")

# Fungsi carian dengan FTS (lebih cepat) - DIPERBAIKI UNTUK FTS5 EXTERNAL CONTENT
def search_documents(query, category_filter=""):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    sql = "SELECT d.title, d.content, d.file_name, d.file_path, d.thumbnail_path, d.upload_date, d.category FROM documents d JOIN documents_fts f ON d.id = f.rowid WHERE "
    params = []
    conditions = []
    if query:
        conditions.append("documents_fts MATCH ?")
        params.append(query)
    if category_filter and category_filter != "Semua":
        conditions.append("d.category = ?")
        params.append(category_filter)
    if conditions:
        sql += " AND ".join(conditions)
    else:
        sql = sql.replace("WHERE ", "")  # Jika tiada filter
    sql += " ORDER BY d.upload_date DESC"
    cursor.execute(sql, params)
    results = cursor.fetchall()
    conn.close()
    return results

# Fungsi carian admin (sama, dengan ID) - DIPERBAIKI UNTUK FTS5 EXTERNAL CONTENT
def search_documents_admin(query="", category_filter=""):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    sql = """
        SELECT d.id, d.title, d.upload_date, d.file_name, d.file_path, d.thumbnail_path, d.category, d.content
        FROM documents d JOIN documents_fts f ON d.id = f.rowid
    """
    params = []
    conditions = []
    if query:
        conditions.append("documents_fts MATCH ?")
        params.append(query)
    if category_filter and category_filter != "Semua":
        conditions.append("d.category = ?")
        params.append(category_filter)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY d.upload_date DESC"
    cursor.execute(sql, params)
    results = cursor.fetchall()
    conn.close()
    return results

# Fungsi download dengan mime detection
@st.cache_data
def get_file_data(file_path):
    with open(file_path, "rb") as f:
        return f.read(), mimetypes.guess_type(file_path)[0] or "application/octet-stream"

# Fungsi dapatkan semua dokumen
def get_all_documents(category_filter=""):
    return search_documents_admin(category_filter=category_filter)

# CSS custom (tambah responsive button dan layout untuk mobile/desktop)
st.markdown("""
    <style>
    .main-header {color: #2E7D32; font-size: 2.5em; text-align: center; margin-bottom: 0.5em;}
    .search-box {background-color: #E8F5E8; padding: 1em; border-radius: 10px; border-left: 5px solid #4CAF50;}
    .result-card {background-color: #F1F8E9; padding: 1em; border-radius: 10px; margin: 0.5em 0; border-left: 4px solid #66BB6A;}
    .category-filter {background-color: #E3F2FD; padding: 0.5em; border-radius: 5px; margin: 0.5em 0;}
    .stButton > button {width: 100%; margin: 0.2em 0; padding: 0.5em;}
    .header-container { text-align: center; margin-bottom: 1em; }
    .header-logo { display: block; margin: 0 auto 0.5em; }
    
    /* Responsive untuk mobile (lebar skrin kurang daripada 768px) */
    @media (max-width: 768px) {
        .main-header { font-size: 1.8em; margin-bottom: 0.3em; }
        .stButton > button { font-size: 1em; padding: 0.8em; margin: 0.3em 0; }
        .search-box { padding: 0.8em; border-radius: 8px; }
        .result-card { padding: 0.8em; border-radius: 8px; margin: 0.3em 0; }
        /* Stack columns untuk 4 butang kategori pada mobile */
        [data-testid="column"] { width: 100% !important; }
        [data-testid="column"]:nth-child(1) { margin-bottom: 0.5em; }
        [data-testid="column"]:nth-child(2) { margin-bottom: 0.5em; }
        [data-testid="column"]:nth-child(3) { margin-bottom: 0.5em; }
        [data-testid="column"]:nth-child(4) { margin-bottom: 0.5em; }
        /* Adjust untuk search dan filter columns */
        [data-testid="column"] > div > div { flex-direction: column !important; }
        [data-testid="column"] > div { width: 100% !important; }
    }
    
    /* Untuk skrin sangat kecil (kurang daripada 480px) */
    @media (max-width: 480px) {
        .main-header { font-size: 1.5em; }
        .stButton > button { font-size: 0.9em; padding: 0.6em; }
        .header-logo { width: 120px !important; }
    }
    
    /* Desktop adjustments (min-width 769px) */
    @media (min-width: 769px) {
        .stButton > button { padding: 0.6em; font-size: 1.1em; }
        .main-header { font-size: 2.8em; }
    }
    </style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("## Navigasi")
    page = st.selectbox("Pilih Halaman", ["Halaman Pengguna (Carian)", "Halaman Admin (Upload)"])

if page == "Halaman Pengguna (Carian)":
    # Logo FAMA dan tajuk header di tengah betul-betul
    st.markdown("""
        <div class="header-container">
            <img src="https://upload.wikimedia.org/wikipedia/commons/4/4b/FAMA_logo.png" alt="Logo FAMA" class="header-logo" width="80">
            <h1 class="main-header">🌾 Rujukan FAMA Standard Keluaran Hasil Pertanian</h1>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
        <p style="text-align: center; color: #4CAF50; font-size: 1.1em;">
        Temui panduan standard pertanian terkini dengan mudah. Klik butang di bawah untuk papar senarai standard mengikut kategori!
        </p>
    """, unsafe_allow_html=True)
    
    # Statistik
    st.subheader("📊 Statistik Standard Terkini")
    total_docs, today_docs = get_stats()
    col_total, col_today = st.columns(2)
    with col_total:
        st.metric("Jumlah Standard Keseluruhan", total_docs)
    with col_today:
        st.metric("Standard Baru Hari Ini", today_docs)
    
    st.markdown('<div class="search-box">', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
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
    with col4:
        if st.button("🌿 Senarai Standard Lain-lain", key="suggest4"):
            st.session_state.query = ""
            st.session_state.user_category = "Lain-lain"
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Inisialisasi session
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
            key="search_input"
        )
    with col_cat:
        category_filter = st.selectbox(
            "Filter Kategori:",
            options=["Semua"] + CATEGORIES,
            index=0 if st.session_state.user_category == "Semua" else CATEGORIES.index(st.session_state.user_category) + 1 if st.session_state.user_category in CATEGORIES else 0,
            key="category_filter_user"
        )
    
    # Auto carian tanpa rerun berlebihan
    if 'last_query' not in st.session_state:
        st.session_state.last_query = ""
        st.session_state.last_category = ""
    if query != st.session_state.last_query or category_filter != st.session_state.last_category:
        st.session_state.query = query
        st.session_state.user_category = category_filter
        st.session_state.last_query = query
        st.session_state.last_category = category_filter
        st.rerun()
    
    if query or category_filter != "Semua":
        with st.spinner(f'Mencari dokumen berkaitan "{query}" di kategori "{category_filter}"...'):
            results = search_documents(query, category_filter)
            
            col_left, col_mid, col_right = st.columns(3)
            with col_mid:
                st.metric("Dokumen Ditemui", len(results))
            
            if results:
                st.subheader(f"📋 Hasil Carian ({len(results)} Dokumen)")
                for i, (title, content, file_name, file_path, thumbnail_path, date, doc_category) in enumerate(results, 1):
                    with st.expander(f"📄 {title} ({doc_category}) (Diupload: {date})", expanded=False):
                        st.markdown(f'<div class="result-card">', unsafe_allow_html=True)
                        
                        col_thumb, col_content = st.columns([1, 3])
                        with col_thumb:
                            if thumbnail_path and os.path.exists(thumbnail_path):
                                st.image(thumbnail_path, caption="Thumbnail", width=150, use_container_width=True, clamp=True)
                            else:
                                st.markdown("🖼️ Tiada thumbnail")
                        
                        with col_content:
                            st.write(f"**Ringkasan:** {content[:300]}..." if len(content) > 300 else content)
                            st.caption(f"Fail: {file_name or 'Tiada'} | Kategori: **{doc_category}**")
                        
                        if file_path and os.path.exists(file_path):
                            file_data, mime_type = get_file_data(file_path)
                            st.download_button(
                                label=f"📥 Muat Turun Dokumen Asal ({file_name or 'Fail'})",
                                data=file_data,
                                file_name=file_name or "dokumen",
                                mime=mime_type,
                                key=f"download_{i}",
                                use_container_width=True,
                                type="secondary"
                            )
                        else:
                            st.warning("Fail asal tidak ditemui.")
                        
                        st.markdown('</div>', unsafe_allow_html=True)
                        st.markdown("---")
            else:
                st.warning("❌ Tiada hasil ditemui. Cuba kata kunci lain atau upload dokumen baru di halaman admin.")
                st.info("💡 Cuba butang di atas untuk papar senarai kategori!")
    else:
        st.info("🌱 Klik butang di atas untuk papar senarai standard mengikut kategori, atau gunakan carian dan filter!")

elif page == "Halaman Admin (Upload)":
    st.title("🔐 Halaman Admin - Upload Dokumen Standard")
    
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
    
    st.success("Log masuk berjaya! Anda boleh upload dokumen sekarang.")
    if st.button("Log Keluar", key="admin_logout", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()
    
    # Info DB
    conn = sqlite3.connect(DB_NAME)
    total_docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    db_size = os.path.getsize(DB_NAME) / (1024 * 1024)  # MB
    conn.close()
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Jumlah Dokumen", total_docs)
    with col2:
        st.metric("Saiz DB", f"{db_size:.1f} MB")
    
    # Upload utama
    st.subheader("Upload Dokumen Utama")
    uploaded_file = st.file_uploader("Pilih fail PDF atau DOCX untuk diupload:", type=["pdf", "docx"], key="main_file")
    title = st.text_input("Nama Komoditi / Tajuk Dokumen (contoh: Standard Keluaran Keratan Bunga):", key="doc_title")
    category = st.selectbox("Pilih Kategori:", options=CATEGORIES, index=0, key="doc_category")
    
    if uploaded_file is not None and title:
        # Validasi saiz
        uploaded_file.seek(0)
        if len(uploaded_file.read()) > MAX_FILE_SIZE:
            st.error("Fail terlalu besar! Maksimum 10MB.")
            st.stop()
        uploaded_file.seek(0)
        
        # Ekstrak
        if uploaded_file.name.endswith('.pdf'):
            content = extract_pdf_text(uploaded_file)
        elif uploaded_file.name.endswith('.docx'):
            content = extract_docx_text(uploaded_file)
        else:
            st.error("Format fail tidak disokong! Hanya PDF atau DOCX.")
            st.stop()
        
        uploaded_file.seek(0)
        
        st.write("**Pratonton Kandungan (1000 aksara pertama):**")
        st.text_area("", value=content[:1000], height=200, disabled=True)
        
        if st.button("Simpan Dokumen Utama", key="save_main_doc", use_container_width=True):
            save_document(title, content, category, uploaded_file, uploaded_file.name)
            st.rerun()
    
    # Upload thumbnail untuk dokumen sedia ada (terpisah, untuk kemudahan)
    st.subheader("Upload Thumbnail untuk Dokumen Sedia Ada")
    existing_docs = get_all_documents()
    if existing_docs:
        doc_options = {f"{doc[1]} (ID: {doc[0]}, Kategori: {doc[6]})": doc[0] for doc in existing_docs}
        selected_doc = st.selectbox("Pilih Dokumen untuk Tambah/Ubah Thumbnail:", options=list(doc_options.keys()))
        if selected_doc:
            selected_id = doc_options[selected_doc]
            thumbnail_file = st.file_uploader("Pilih fail thumbnail (PNG/JPG):", type=["png", "jpg", "jpeg"], key="thumbnail_file")
            if thumbnail_file is not None:
                if st.button("Simpan/Ubah Thumbnail", key="save_thumbnail", use_container_width=True):
                    save_thumbnail(selected_id, thumbnail_file)
                    st.rerun()
    else:
        st.info("Tiada dokumen sedia ada. Upload dokumen utama dahulu.")
    
    # Senarai sedia ada
    st.subheader("Dokumen Sedia Ada")
    col_admin_search, col_admin_cat = st.columns([3, 1])
    with col_admin_search:
        admin_query = st.text_input("Cari dokumen (masukkan kata kunci):", placeholder="Contoh: keratan bunga", key="admin_query")
    with col_admin_cat:
        admin_category_filter = st.selectbox("Filter Kategori:", options=["Semua"] + CATEGORIES, index=0, key="admin_category_filter")
    
    existing_docs = search_documents_admin(admin_query, admin_category_filter)
    filter_info = f" (Carian: '{admin_query}', Kategori: '{admin_category_filter}') " if admin_query or admin_category_filter != "Semua" else ""
    st.info(f"Memaparkan {len(existing_docs)} dokumen{filter_info}.")
    
    if "to_delete" not in st.session_state:
        st.session_state.to_delete = None
    if "editing_id" not in st.session_state:
        st.session_state.editing_id = None
    
    # Form edit (kini termasuk attachment dan thumbnail)
    if st.session_state.editing_id is not None:
        st.subheader("Edit Dokumen")
        doc_data = get_document_by_id(st.session_state.editing_id)
        if doc_data:
            doc_id, current_title, current_content, current_category, current_file_name, current_file_path, current_thumbnail_path, _ = doc_data
            
            new_title = st.text_input("Nama Komoditi / Tajuk Dokumen:", value=current_title, key="edit_title")
            new_category = st.selectbox("Kategori:", options=CATEGORIES, index=CATEGORIES.index(current_category) if current_category in CATEGORIES else 0, key="edit_category")
            new_content = st.text_area("Kandungan (Teks Diekstrak):", value=current_content, height=200, key="edit_content")
            
            # Edit attachment
            st.subheader("Edit Attachment Standard (Opsional)")
            col_attach_show, col_attach_upload = st.columns(2)
            with col_attach_show:
                if current_file_name:
                    st.caption(f"Attachment semasa: {current_file_name}")
                    if current_file_path and os.path.exists(current_file_path):
                        file_data, mime_type = get_file_data(current_file_path)
                        st.download_button(
                            label="Muat Turun Attachment Semasa",
                            data=file_data,
                            file_name=current_file_name,
                            mime=mime_type,
                            key="current_attach_download"
                        )
                    st.caption("Attachment semasa akan diganti jika fail baru diupload.")
                else:
                    st.markdown("📎 Tiada attachment semasa")
            with col_attach_upload:
                new_attachment_file = st.file_uploader("Upload attachment baru (PDF/DOCX):", type=["pdf", "docx"], key="edit_attachment_file")
            
            # Edit thumbnail
            st.subheader("Edit Thumbnail (Opsional)")
            col_thumb_show, col_thumb_upload = st.columns(2)
            with col_thumb_show:
                if current_thumbnail_path and os.path.exists(current_thumbnail_path):
                    st.image(current_thumbnail_path, caption="Thumbnail Semasa", width=150)
                    st.caption("Thumbnail semasa akan diganti jika fail baru diupload.")
                else:
                    st.markdown("🖼️ Tiada thumbnail semasa")
            with col_thumb_upload:
                new_thumbnail_file = st.file_uploader("Upload thumbnail baru (PNG/JPG):", type=["png", "jpg", "jpeg"], key="edit_thumbnail_file")
            
            col_save, col_cancel = st.columns(2)
            with col_save:
                if st.button("💾 Simpan Perubahan", key="save_edit", use_container_width=True):
                    edit_document(doc_id, new_title, new_content, new_category, new_attachment_file, current_file_path, current_file_name, new_thumbnail_file, current_thumbnail_path)
                    st.session_state.editing_id = None
                    st.rerun()
            with col_cancel:
                if st.button("❌ Batal Edit", key="cancel_edit", use_container_width=True):
                    st.session_state.editing_id = None
                    st.rerun()
        
        st.markdown("---")
    
    if existing_docs:
        for doc_id, title, date, file_name, file_path, thumbnail_path, doc_category, content in existing_docs:
            with st.container():
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    st.write(f"- **{title}** (Diupload: {date}) | Fail: {file_name or 'Tiada'} | Kategori: **{doc_category}**")
                with col2:
                    if thumbnail_path and os.path.exists(thumbnail_path):
                        st.image(thumbnail_path, width=80, caption="", clamp=True)
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
        
        if st.session_state.to_delete is not None:
            st.warning(f"Adakah anda pasti mahu padam dokumen dengan ID {st.session_state.to_delete}? Tindakan ini tidak boleh dibatalkan!")
            
            col_confirm, col_cancel = st.columns(2)
            with col_confirm:
                if st.button("Ya, Padam!", key="confirm_delete", use_container_width=True):
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
            
            st.markdown("---")
    else:
        st.info("Tiada dokumen ditemui. Upload yang pertama!")
