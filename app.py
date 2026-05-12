import streamlit as st
import pandas as pd
import os
from streamlit_pdf_viewer import pdf_viewer

import database as db
import pdf_engine as engine

db.init_db()

st.set_page_config(page_title="RPA Care Label", page_icon="🤖", layout="wide")

# ==========================================
# 1. AUTHENTICATION SYSTEM (UPDATED)
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_role = None # Track if they are admin or user

def verify_login():
    """Checks credentials against the encrypted database."""
    # Using the new database function instead of hardcoded strings
    is_valid, role = db.verify_user(st.session_state.username, st.session_state.password)
    
    if is_valid:
        st.session_state.logged_in = True
        st.session_state.user_role = role
    else:
        st.session_state.logged_in = False
        st.error("Incorrect username or password.", icon=":material/error:")

def logout():
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.password = ""
    st.session_state.user_role = None

# ==========================================
# 2. THE LOGIN SCREEN
# ==========================================
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.title(":material/smart_toy: RPA Care Label")
        st.write("Please log in to access the automation system.")
        
        st.write("---")
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password")
        
        st.button("Login", on_click=verify_login, type="primary", use_container_width=True)

# ==========================================
# 3. THE MAIN APPLICATION
# ==========================================
else:
    st.sidebar.button("Logout", on_click=logout, icon=":material/logout:", use_container_width=True)
    st.sidebar.write("---")

    st.sidebar.title(":material/smart_toy: RPA Menu")
    
    # dynamically build the menu based on their role
    menu_options = ["Care Label Extractor", "Processing History"]
    if st.session_state.user_role == "admin":
        menu_options.append("Admin Settings") # Only admins see this!
        
    app_mode = st.sidebar.radio("Select a module:", menu_options)

    st.sidebar.write("---")
    st.sidebar.write("### :material/settings: System Settings")
    custom_target_dir = st.sidebar.text_input(
        "Local Output Directory:",
        value=r"D:\var\www\pdf_injector"
    )

    # ------------------------------------------
    # MODULE: RPA Care Label Extractor
    # ------------------------------------------
    if app_mode == "Care Label Extractor":
        st.title(":material/smart_toy: RPA Care Label")
        st.write("Automated extraction of Care Label specifications from Tech Pack PDFs.")

        uploaded_files = st.file_uploader("Upload Tech Pack PDFs", type=["pdf"], accept_multiple_files=True)

        if uploaded_files:
            if "saved_files" not in st.session_state:
                st.session_state.saved_files = set()
                
            for uploaded_file in uploaded_files:
                if uploaded_file.name not in st.session_state.saved_files:
                    try:
                        os.makedirs(custom_target_dir, exist_ok=True)
                        save_path = os.path.join(custom_target_dir, uploaded_file.name)
                        with open(save_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                            
                        db.log_upload(uploaded_file.name, save_path)
                        st.session_state.saved_files.add(uploaded_file.name)
                        st.toast(f"Archived: {uploaded_file.name}", icon=":material/save:")
                    except Exception as e:
                        st.error(f"Failed to archive '{uploaded_file.name}'. Error: {e}", icon=":material/error:")

            st.write("### :material/visibility: Source Document Preview")
            for uploaded_file in uploaded_files:
                with st.expander(f":material/visibility: Inspect: {uploaded_file.name}"):
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
                        try:
                            result = engine.process_pdf(uploaded_file, phrases_to_find)
                            if result["kept"] > 0:
                                st.session_state.extracted_pdfs.append(result)
                            else:
                                st.warning(f"No matching care label data found in {uploaded_file.name}", icon=":material/warning:")
                        except Exception as e:
                            st.error(f"RPA Error processing {uploaded_file.name}: {e}", icon=":material/error:")

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
                    st.download_button(
                        label=f"Download {len(selected_for_download)} Extracted Labels (ZIP Archive)",
                        icon=":material/archive:",
                        data=zip_data,
                        file_name="RPA_Care_Labels.zip",
                        mime="application/zip",
                        type="primary",
                        use_container_width=True 
                    )

    # ------------------------------------------
    # MODULE: Processing History
    # ------------------------------------------
    elif app_mode == "Processing History":
        st.title(":material/history: RPA Processing History")
        st.write("Audit log of all Tech Packs processed by the system.")
        
        try:
            history_df = db.get_upload_history()
            if history_df.empty:
                st.info("No documents have been processed by the RPA yet.", icon=":material/info:")
            else:
                st.metric("Total Tech Packs Processed", len(history_df))
                st.dataframe(history_df, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Could not load system database: {e}", icon=":material/error:")

    # ------------------------------------------
    # MODULE: Admin Settings (NEW!)
    # ------------------------------------------
    elif app_mode == "Admin Settings":
        st.title(":material/admin_panel_settings: System Administration")
        st.write("Manage access to the RPA Care Label system.")

        st.write("### Create New User")
        
        # User creation form
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