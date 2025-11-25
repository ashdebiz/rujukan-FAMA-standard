import streamlit as st
import sqlite3
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import PyPDF2
from docx import Document
import io
import hashlib
import qrcode
from PIL import Image
import base64

# =============================================
# FORCE CLEAR CACHE SETIAP KALI PAGE LOAD
# =============================================
if "chat_cleared" not in st.session_state:
    st.session_state.chat_cleared = False

# Kosongkan cache bila perlu
@st.cache_data(ttl=1)  # ttl 1 saat je — force refresh setiap kali
def get_chat_messages():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM chat_messages ORDER BY timestamp ASC")
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# Tambah cache buster untuk padam chat
def clear_chat_completely():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.execute("DELETE FROM chat_messages")
    conn.commit()
    conn.close()
    st.session_state.chat_cleared = True
    st.cache_data.clear()  # INI YANG PALING PENTING — HAPUS SEMUA CACHE
    st.rerun()

# =============================================
# (Semua kod lain kekal sama sampai Admin Panel)
# =============================================

# ... [letak semua kod sebelum ni sampai sidebar & halaman utama macam biasa]

# ADMIN PANEL — BAHAGIAN CHAT DENGAN CLEAR 100% BERJAYA
else:
    if not st.session_state.get("logged_in"):
        st.markdown("<h1 style='text-align:center; color:#1B5E20;'>ADMIN PANEL</h1>")
        c1, c2 = st.columns(2)
        with c1: username = st.text_input("Username")
        with c2: password = st.text_input("Kata Laluan", type="password")
        if st.button("LOG MASUK"):
            h = hashlib.sha256(password.encode()).hexdigest()
            if username in ADMIN_CREDENTIALS and ADMIN_CREDENTIALS[username] == h:
                st.session_state.logged_in = True
                st.session_state.user = username
                st.rerun()
            else:
                st.error("Salah username/kata laluan!")
        st.stop()

    st.success(f"Selamat Datang, {st.session_state.user.upper()}")

    tab1, tab2, tab3, tab_chat = st.tabs(["Tambah Standard", "Senarai & Edit", "Backup & Recovery", "Chat Pengguna"])

    # ... [tab1, tab2, tab3 kekal sama]

    with tab_chat:
        st.markdown("### Chat dengan Pengguna")

        # BUTANG PADAM CHAT YANG BENAR-BENAR BERJALAN 100%
        col1, col2 = st.columns([5, 2])
        with col2:
            if st.button("Padam Semua Chat", type="secondary", use_container_width=True):
                st.session_state.confirm_delete = True

        if st.session_state.get("confirm_delete", False):
            st.error("⚠️ ANDA PASTI NAK PADAM SEMUA CHAT?")
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("YA, PADAM SEMUA!", type="primary"):
                    clear_chat_completely()  # Fungsi yg betul-betul clear
            with col_b:
                if st.button("BATAL"):
                    st.session_state.confirm_delete = False
                    st.rerun()

        st.markdown("---")

        # Papar chat — dengan force refresh
        messages = get_chat_messages()
        if not messages:
            st.info("Tiada mesej lagi")
        else:
            for m in reversed(messages):
                sender = "Admin FAMA" if m['is_admin'] else m['sender']
                st.markdown(f"**{sender}** • {m['timestamp']}")
                st.info(m['message'])
                reply = st.text_input("Balas mesej ini", key=f"rep_{m['id']}_{datetime.now().microsecond}")
                if st.button("Hantar Balasan", key=f"send_{m['id']}_{datetime.now().microsecond}"):
                    if reply.strip():
                        add_chat_message("Admin FAMA", reply.strip(), is_admin=True)
                        st.success("Balasan dihantar!")
                        st.rerun()

    if st.button("Log Keluar"):
        st.session_state.clear()
        st.rerun()
