import streamlit as st
import requests
import base64
import xml.etree.ElementTree as ET
import pandas as pd
from io import StringIO
import json
import secrets
import string

# --- App Configuration ---
st.set_page_config(page_title="Oracle HCM SecureReset Pro", layout="wide")

# --- Logo Header Section ---
log_col1, log_col2, log_col3 = st.columns([1, 4, 1])
with log_col1:
    st.image("https://upload.wikimedia.org/wikipedia/commons/5/50/Oracle_logo.svg", width=150)
with log_col3:
    st.image("https://upload.wikimedia.org/wikipedia/commons/5/51/IBM_logo.svg", width=120)

st.title("🔐 Oracle HCM SecureReset Pro")

# --- UI Layout: Connection & Inputs ---
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("🌐 Connection Details")
    env_url = st.text_input("Environment URL", "https://iavnqy-dev2.fa.ocs.oraclecloud.com")
    username = st.text_input("Admin Username")
    password = st.text_input("Admin Password", type="password")

with col2:
    st.subheader("👥 Password Configuration")
    # NEW FIELD: Admin manual password choice
    custom_common_pwd = st.text_input("Set Common Password for All Users", placeholder="Enter desired temporary password")
    
    user_input = st.text_area(
        "Enter Usernames (comma separated)", 
        placeholder="user1@example.com, user2@example.com",
        height=100
    )

# --- Logic Functions ---

def fetch_guids_soap(env_url, admin_user, admin_pwd, user_list_str):
    """Calls BIP SOAP service to resolve Usernames to GUIDs."""
    full_url = env_url.rstrip("/") + "/xmlpserver/services/ExternalReportWSSService"
    report_path = "/Custom/Human Capital Management/PASSWORD/User_GUID_Report.xdo"
    
    clean_user_list = ",".join([u.strip() for u in user_list_str.split(",") if u.strip()])

    soap_request = f"""
    <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:pub="http://xmlns.oracle.com/oxp/service/PublicReportService">
       <soap:Header/>
       <soap:Body>
          <pub:runReport>
             <pub:reportRequest>
                <pub:attributeFormat>csv</pub:attributeFormat>
                <pub:reportAbsolutePath>{report_path}</pub:reportAbsolutePath>
                <pub:parameterNameValues>
                    <pub:item>
                        <pub:name>p_usernames</pub:name>
                        <pub:values>
                            <pub:item>{clean_user_list}</pub:item>
                        </pub:values>
                    </pub:item>
                </pub:parameterNameValues>
                <pub:sizeOfDataChunkDownload>-1</pub:sizeOfDataChunkDownload>
             </pub:reportRequest>
          </pub:runReport>
       </soap:Body>
    </soap:Envelope>
    """
    
    auth_header = base64.b64encode(f"{admin_user}:{admin_pwd}".encode()).decode()
    headers = {
        "Content-Type": "application/soap+xml; charset=utf-8",
        "Authorization": f"Basic {auth_header}"
    }

    try:
        response = requests.post(full_url, data=soap_request, headers=headers)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            ns = {'ns': 'http://xmlns.oracle.com/oxp/service/PublicReportService'}
            report_bytes = root.find('.//ns:reportBytes', ns)
            if report_bytes is not None and report_bytes.text:
                return base64.b64decode(report_bytes.text).decode("utf-8")
        return None
    except Exception:
        return None

def call_scim_bulk_api_manual(env_url, admin_user, admin_pwd, guid_df, manual_pwd):
    """Executes Bulk PATCH via SCIM REST API with the ADMIN CHOSEN password."""
    scim_url = env_url.rstrip("/") + "/hcmRestApi/scim/Bulk"
    
    operations = []
    for _, row in guid_df.iterrows():
        operations.append({
            "method": "PATCH",
            "path": f"/Users/{row['USER_GUID']}",
            "bulkId": str(row['USERNAME']),
            "data": {
                "schemas": ["urn:scim:schemas:core:2.0:User"],
                "password": manual_pwd  # Passing the chosen password variable
            }
        })

    payload = {"Operations": operations}
    response = requests.post(
        scim_url, 
        json=payload, 
        auth=(admin_user, admin_pwd),
        headers={"Content-Type": "application/json"}
    )
    return response

# --- Main Logic ---

if st.button("🚀 Execute Bulk Password Reset"):
    if not (username and password and user_input and custom_common_pwd):
        st.warning("⚠️ Please provide all credentials, target usernames, and the new common password.")
    else:
        with st.spinner("🔍 Step 1: Querying Oracle for User GUIDs..."):
            csv_data = fetch_guids_soap(env_url, username, password, user_input)
            
            if csv_data:
                df = pd.read_csv(StringIO(csv_data))
                df.columns = [c.strip().upper() for c in df.columns]
                
                if 'USER_GUID' in df.columns and not df.empty:
                    st.info(f"✅ Found {len(df)} users in Fusion.")
                    
                    with st.spinner("⚡ Step 2: Resetting Passwords via SCIM Bulk API..."):
                        res = call_scim_bulk_api_manual(env_url, username, password, df, custom_common_pwd)
                        
                        if res.status_code in [200, 201]:
                            st.success("🎊 Bulk Reset Process Completed Successfully!")
                            
                            # Build Results Table
                            results = res.json().get("Operations", [])
                            status_rows = []
                            for op in results:
                                u_name = op.get("bulkId")
                                status_code = str(op.get("status", {}).get("code"))
                                success = status_code.startswith("2")
                                
                                status_rows.append({
                                    "Username": u_name,
                                    "Outcome": "✅ Password reset successful" if success else "❌ Reset failed",
                                    "Assigned Password": custom_common_pwd if success else "N/A"
                                })
                            
                            result_df = pd.DataFrame(status_rows)
                            st.table(result_df)
                            
                            # --- Download Section ---
                            st.subheader("📥 Export Credentials")
                            csv_download = result_df.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                label="💾 Download Results as CSV",
                                data=csv_download,
                                file_name="HCM_Custom_Password_Reset.csv",
                                mime="text/csv",
                            )
                        
                        else:
                            error_messages = {
                                401: "🚫 **Unauthorized**: Invalid Admin Username or Password.",
                                403: "🛑 **Forbidden**: You do not have the required roles.",
                                500: "⚙️ **Internal Server Error**: Fusion API Error."
                            }
                            friendly_err = error_messages.get(res.status_code, f"⚠️ **Request Failed (Status: {res.status_code})**")
                            st.error(friendly_err)
                else:
                    st.error("❌ No matching users found in Fusion.")
            else:
                st.error("❌ Could not connect to the BIP report. Verify credentials/path.")

# Footer
st.markdown("""
<hr style="margin-top: 50px;">
<div style='text-align: center; color: yellow; font-size: 0.85em;'>
    <p>App has been developed by <strong>Raktim Pal</strong></p>
    <p>© 2026 Raktim Pal. All rights reserved.</p>
</div>
""", unsafe_allow_html=True)
