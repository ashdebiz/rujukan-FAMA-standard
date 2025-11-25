# ... (semua kod atas sampai Admin Panel kekal sama macam sebelum ni)

# =============================================
# ADMIN PANEL — DENGAN BUTANG CLEAR CHATBOX (BARU!)
# =============================================
else:  # Admin Panel
    if not st.session_state.get("logged_in"):
        st.markdown("<h1 style='text-align:center; color:#1B5E20;'>ADMIN PANEL</h1>", unsafe_allow_html=True)
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
                st.error("Salah!")
        st.stop()

    st.success(f"Selamat Datang, {st.session_state.user.upper()}")

    tab1, tab2, tab3, tab_chat = st.tabs(["Tambah Standard", "Senarai & Edit", "Backup & Recovery", "Chat Pengguna"])

    # ... (tab1, tab2, tab3 kekal sama)

    with tab_chat:
        st.markdown("### Chat dengan Pengguna")

        # BUTANG CLEAR CHATBOX — BARU!
        col_clear1, col_clear2 = st.columns([3, 1])
        with col_clear1:
            st.write("")  # spacer
        with col_clear2:
            if st.button("Padam Semua Chat", type="secondary"):
                if st.checkbox("Saya pasti nak padam SEMUA chat", key="confirm_clear_chat"):
                    conn = sqlite3.connect(DB_NAME)
                    conn.execute("DELETE FROM chat_messages")
                    conn.commit()
                    conn.close()
                    st.success("Semua chat telah dipadam!")
                    st.balloons()
                    st.rerun()

        st.markdown("---")

        msgs = get_chat_messages()
        if not msgs:
            st.info("Tiada mesej lagi")
        else:
            for m in reversed(msgs):
                st.markdown(f"**{m['sender']}** • {m['timestamp']}")
                st.info(m['message'])
                reply = st.text_input("Balas", key=f"rep_{m['id']}")
                if st.button("Hantar Balasan", key=f"send_{m['id']}"):
                    if reply.strip():
                        add_chat_message("Admin FAMA", reply.strip(), is_admin=True)
                        st.success("Balasan dihantar!")
                        st.rerun()

    if st.button("Log Keluar"):
        st.session_state.clear()
        st.rerun()
