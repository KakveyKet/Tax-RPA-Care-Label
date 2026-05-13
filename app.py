import streamlit as st
import streamlit.components.v1 as components
from streamlit_javascript import st_javascript
import pandas as pd
import os
import re
from datetime import datetime
from pypdf import PdfReader
from streamlit_pdf_viewer import pdf_viewer

import database as db
import pdf_engine as engine

db.init_db()

st.set_page_config(page_title="RPA Care Label", page_icon="🤖", layout="wide")

# ==========================================
# SMART FILENAME EXTRACTOR
# ==========================================
def get_clean_filename(uploaded_file):
    """Reads the PDF to extract the season and formats the filename cleanly."""
    base_name, ext = os.path.splitext(uploaded_file.name)
    
    if " CET_" in base_name:
        base_name = base_name.replace(" CET_", " (") + ")"
        
    season = None
    try:
        reader = PdfReader(uploaded_file)
        first_page_text = reader.pages[0].extract_text()
        uploaded_file.seek(0) 
        
        match = re.search(r'Season\s*:\s*([A-Za-z0-9]+)', first_page_text)
        if match:
            season = match.group(1)
    except Exception:
        pass
        
    if season and f"_{season}" not in base_name:
        parts = base_name.split('_', 1) 
        if len(parts) == 2:
            base_name = f"{parts[0]}_{season}_{parts[1]}"
        else:
            base_name = f"{base_name}_{season}"
            
    return base_name + ext

# ==========================================
# 0. SECURE LOGOUT EXECUTOR
# ==========================================
if st.session_state.get("just_logged_out", False):
    components.html(
        """
        <script>
        window.parent.document.cookie = 'rpa_auth=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
        window.parent.document.cookie = 'rpa_role=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
        window.parent.location.reload();
        </script>
        """,
        height=0, width=0
    )
    st.session_state.just_logged_out = False
    st.stop() 

# ==========================================
# 1. AUTHENTICATION SYSTEM
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_role = None

if not st.session_state.logged_in:
    raw_cookies = st_javascript("document.cookie", key="read_cookies")
    
    if raw_cookies == 0:
        st.stop()
        
    def parse_cookie(cookie_string, cookie_name):
        if isinstance(cookie_string, str):
            for c in cookie_string.split(';'):
                if c.strip().startswith(f"{cookie_name}="):
                    return c.split('=')[1]
        return None

    auth_cookie = parse_cookie(raw_cookies, "rpa_auth")
    if auth_cookie == "true":
        st.session_state.logged_in = True
        st.session_state.user_role = parse_cookie(raw_cookies, "rpa_role")
        st.rerun() 

# ==========================================
# 2. THE LOGIN SCREEN
# ==========================================
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.title(":material/smart_toy: RPA Care Label")
        st.write("Please log in to access the automation system.")
        st.write("---")
        
        with st.form("login_form"):
            username_input = st.text_input("Username")
            password_input = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", type="primary", use_container_width=True)
            
            if submitted:
                is_valid, role = db.verify_user(username_input, password_input)
                
                if is_valid:
                    st.session_state.logged_in = True
                    st.session_state.user_role = role
                    st.session_state.just_logged_in = True
                    st.rerun()
                else:
                    st.error("Incorrect username or password.", icon=":material/error:")

# ==========================================
# 3. THE MAIN APPLICATION
# ==========================================
if st.session_state.logged_in:
    
    if st.session_state.get("just_logged_in", False):
        components.html(
            f"""
            <script>
            window.parent.document.cookie = 'rpa_auth=true; path=/; max-age=2592000';
            window.parent.document.cookie = 'rpa_role={st.session_state.user_role}; path=/; max-age=2592000';
            </script>
            """,
            height=0, width=0
        )
        st.session_state.just_logged_in = False
    
    if st.sidebar.button("Logout", icon=":material/logout:", use_container_width=True):
        st.session_state.just_logged_out = True
        st.rerun() 

    st.sidebar.write("---")
    st.sidebar.title(":material/smart_toy: RPA Menu")
    
    menu_options = ["Care Label Extractor", "Processing History"]
    if st.session_state.user_role == "admin":
        menu_options.append("Admin Settings") 
        
    app_mode = st.sidebar.radio("Select a module:", menu_options)

    custom_target_dir = r"D:\var\www\pdf_injector"

    # ------------------------------------------
    # MODULE: RPA Care Label Extractor
    # ------------------------------------------
    if app_mode == "Care Label Extractor":
        st.title(":material/smart_toy: RPA Care Label")

        uploaded_files = st.file_uploader("Upload Tech Pack PDFs", type=["pdf"], accept_multiple_files=True)

        if uploaded_files:
            if "saved_files" not in st.session_state:
                st.session_state.saved_files = set()
                
            for uploaded_file in uploaded_files:
                clean_filename = get_clean_filename(uploaded_file)
                
                if clean_filename not in st.session_state.saved_files:
                    try:
                        try:
                            os.makedirs(custom_target_dir, exist_ok=True)
                            final_dir = custom_target_dir
                        except OSError:
                            final_dir = os.path.join(os.getcwd(), "fallback_pdf_archive")
                            os.makedirs(final_dir, exist_ok=True)

                        save_path = os.path.join(final_dir, clean_filename)
                        with open(save_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                            
                        db.log_upload(clean_filename, save_path)
                        st.session_state.saved_files.add(clean_filename)
                        st.toast(f"Archived: {clean_filename}", icon=":material/save:")
                        
                    except Exception as e:
                        st.error(f"Failed to archive '{clean_filename}'. Error: {e}", icon=":material/error:")

            st.write("### :material/visibility: Source Document Preview")
            for uploaded_file in uploaded_files:
                clean_filename = get_clean_filename(uploaded_file)
                with st.expander(f":material/visibility: Inspect: {clean_filename}"):
                    pdf_viewer(uploaded_file.getvalue(), width=1000, height=600) 

            st.write("---")
            search_phrases_input = st.text_input(
                "Target Extraction Keywords (Comma-separated):", 
                value="General Info:, Extra Instructions Group, Fiber Text Position, Label Remarks, Gender" 
            )

            if "extracted_pdfs" not in st.session_state:
                st.session_state.extracted_pdfs = []

            if st.button("Run RPA Extraction", icon=":material/memory:", type="primary"):
                if search_phrases_input.strip() == "":
                    st.warning("Please define at least one keyword for the RPA to target.", icon=":material/warning:")
                else:
                    phrases_to_find = [p.strip().lower() for p in search_phrases_input.split(',') if p.strip() != ""]
                    st.session_state.extracted_pdfs = []

                    for uploaded_file in uploaded_files:
                        clean_filename = get_clean_filename(uploaded_file)
                        
                        try:
                            result = engine.process_pdf(uploaded_file, phrases_to_find)
                            if result["kept"] > 0:
                                result["filename"] = clean_filename
                                st.session_state.extracted_pdfs.append(result)
                            else:
                                st.warning(f"No matching care label data found in {clean_filename}", icon=":material/warning:")
                        except Exception as e:
                            st.error(f"RPA Error processing {clean_filename}: {e}", icon=":material/error:")

            if st.session_state.extracted_pdfs:
                st.write("---")
                st.write("## :material/checklist: Processed Care Labels")
                st.write("Select the successfully extracted files you wish to download.")
                
                selected_for_download = []

                for result in st.session_state.extracted_pdfs:
                    col1, col2, col3 = st.columns([4, 1, 1])
                    
                    with col1:
                        is_checked = st.checkbox(f":material/description: **{result['filename']}** (Extracted {result['kept']}/{result['total']} pages)", value=True, key=f"chk_{result['filename']}")
                        if is_checked:
                            selected_for_download.append((result["filename"], result["bytes"]))
                            
                        with st.expander(":material/analytics: View RPA Audit Log", expanded=False):
                            st.dataframe(pd.DataFrame(result["log"]), use_container_width=True)

                    with col3:
                        st.download_button(
                            label="Download PDF",
                            icon=":material/download:",
                            data=result["bytes"],
                            file_name=result["filename"],
                            mime="application/pdf",
                            key=f"dl_{result['filename']}"
                        )
                    st.divider()

                if len(selected_for_download) > 1:
                    st.write("### :material/folder_zip: Batch Download")
                    zip_data = engine.create_zip_archive(selected_for_download)
                    
                    current_date = datetime.now().strftime("%d_%m_%Y")
                    dynamic_zip_name = f"RPA_Care_Labels_{current_date}.zip"
                    
                    st.download_button(
                        label=f"Download {len(selected_for_download)} Extracted Labels (ZIP Archive)",
                        icon=":material/archive:",
                        data=zip_data,
                        file_name=dynamic_zip_name,
                        mime="application/zip",
                        type="primary",
                        use_container_width=True 
                    )

    # ------------------------------------------
    # MODULE: Processing History
    # ------------------------------------------
    elif app_mode == "Processing History":
        st.title(":material/history: RPA Processing History")
        
        try:
            history_df = db.get_upload_history()
            if history_df.empty:
                st.info("No documents have been processed by the RPA yet.", icon=":material/info:")
            else:
                st.metric("Upload Report", len(history_df))
                
                # ADMIN VIEW (Can Delete)
                if st.session_state.user_role == "admin":
                    st.write("### :material/delete: Manage Records")
                    
                    history_df.insert(0, "Select", False)
                    
                    edited_df = st.data_editor(
                        history_df,
                        column_config={
                            "Select": st.column_config.CheckboxColumn("Delete?", default=False)
                        },
                        disabled=history_df.columns.drop("Select"), 
                        hide_index=True,
                        width="stretch", 
                        key="admin_history_editor"
                    )
                    
                    selected_rows = edited_df[edited_df["Select"] == True]
                    
                    if st.button(f"Delete {len(selected_rows)} Selected Records", type="primary", icon=":material/delete:"):
                        col_name = "filename"  
                        files_to_delete = selected_rows[col_name].tolist()
                        
                        success_count = 0
                        for f in files_to_delete:
                            if db.delete_upload_log(f):
                                success_count += 1
                        
                        if success_count > 0:
                            st.success(f"Successfully permanently deleted {success_count} records!")
                            st.cache_data.clear() 
                            st.rerun()
                        else:
                            st.error(f"Failed to delete. The system looked for column '{col_name}' but couldn't find those files in the database.", icon=":material/error:")
                
                # STANDARD USER VIEW (Read-Only)
                else:
                    st.dataframe(history_df, width="stretch", hide_index=True)
                    
        except Exception as e:
            st.error(f"Could not load system database: {e}", icon=":material/error:")

    # ------------------------------------------
    # MODULE: Admin Settings
    # ------------------------------------------
    elif app_mode == "Admin Settings":
        st.title(":material/admin_panel_settings: System Administration")
        st.write("Manage access to the RPA Care Label system.")

        st.write("### Create New User")
        
        with st.form("new_user_form"):
            new_user = st.text_input("New Username")
            new_pass = st.text_input("New Password", type="password")
            new_role = st.selectbox("Role", ["user", "admin"])
            
            submitted = st.form_submit_button("Create Account", type="primary")
            
            if submitted:
                if new_user and new_pass:
                    success = db.create_user(new_user, new_pass, new_role)
                    if success:
                        st.success(f"User '{new_user}' successfully created!", icon=":material/check_circle:")
                    else:
                        st.error(f"Username '{new_user}' already exists.", icon=":material/error:")
                else:
                    st.warning("Please fill out both username and password.", icon=":material/warning:")
                    
        st.write("---")
        st.write("### Registered Users")
        users_df = db.get_all_users()
        st.dataframe(users_df, use_container_width=True, hide_index=True)