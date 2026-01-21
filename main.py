import streamlit as st
import requests
import base64
import xml.etree.ElementTree as ET
import pandas as pd
from io import StringIO
import json
import secrets
import string

# Configuration and Page Setup
st.set_page_config(page_title="HCM Bulk Password Reset", layout="wide")
st.title("🔐 HCM Bulk Password Reset Tool")
st.markdown("---")

# 1. Inputs: Connection Details
col1, col2 = st.columns(2)
with col1:
    env_url = st.text_input("🌐 Environment URL", "https://iavnqy-dev2.fa.ocs.oraclecloud.com")
    username = st.text_input("👤 Admin Username")
with col2:
    password = st.text_input("🔑 Admin Password", type="password")
    user_input = st.text_area("👥 Target Usernames (Comma Separated)", placeholder="user1@example.com, user2@example.com")

# --- Helper Functions ---

def generate_secure_password(length=12):
    """Generates a policy-compliant password."""
    alphabet = string.ascii_letters + string.digits + "!#$%"
    pwd = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!#$%")
    ]
    pwd += [secrets.choice(alphabet) for _ in range(length - 4)]
    secrets.SystemRandom().shuffle(pwd)
    return "".join(pwd)

def fetch_guids_soap(env_url, username, password, user_list_str):
    """Calls BIP SOAP service to resolve Usernames to GUIDs."""
    full_url = env_url.rstrip("/") + "/xmlpserver/services/ExternalReportWSSService"
    report_path = "/Custom/Human Capital Management/PASSWORD/User_GUID_Report.xdo"
    
    # Standard SOAP Envelope with Parameter passing
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
                            <pub:item>{user_list_str}</pub:item>
                        </pub:values>
                    </pub:item>
                </pub:parameterNameValues>
                <pub:sizeOfDataChunkDownload>-1</pub:sizeOfDataChunkDownload>
             </pub:reportRequest>
          </pub:runReport>
       </soap:Body>
    </soap:Envelope>
    """
    
    headers = {
        "Content-Type": "application/soap+xml; charset=utf-8",
        "Authorization": f"Basic {base64.b64encode(f'{username}:{password}'.encode()).decode()}"
    }

    try:
        response = requests.post(full_url, data=soap_request, headers=headers)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            # Use namespace searching from original main.py
            ns = {'ns': 'http://xmlns.oracle.com/oxp/service/PublicReportService'}
            report_bytes = root.find('.//ns:reportBytes', ns)
            
            if report_bytes is not None and report_bytes.text:
                return base64.b64decode(report_bytes.text).decode("utf-8")
        st.error(f"SOAP Error: {response.status_code}")
        return None
    except Exception as e:
        st.error(f"Connection Error: {str(e)}")
        return None

def call_scim_bulk_api(env_url, username, password, guid_df):
    """Performs the Bulk PATCH operation via REST."""
    scim_url = env_url.rstrip("/") + "/hcmRestApi/scim/Bulk"
    new_password = generate_secure_password()
    
    operations = []
    for _, row in guid_df.iterrows():
        operations.append({
            "method": "PATCH",
            "path": f"/Users/{row['USER_GUID']}",
            "bulkId": row['USERNAME'],
            "data": {
                "schemas": ["urn:scim:schemas:core:2.0:User"],
                "password": new_password
            }
        })

    payload = {"Operations": operations}
    
    response = requests.post(
        scim_url, 
        json=payload, 
        auth=(username, password),
        headers={"Content-Type": "application/json"}
    )
    return response, new_password

# --- Main Execution Trigger ---

if st.button("🚀 Execute Bulk Password Reset"):
    if not (username and password and user_input):
        st.warning("⚠️ Please fill in credentials and usernames.")
    else:
        # Step 1: Get GUIDs
        with st.spinner("🔍 Fetching GUIDs from Oracle..."):
            csv_data = fetch_guids_soap(env_url, username, password, user_input)
            
            if csv_data:
                df = pd.read_csv(StringIO(csv_data))
                # Cleanup column names
                df.columns = [c.strip().upper() for c in df.columns]
                
                if 'USER_GUID' in df.columns and not df.empty:
                    st.write(f"✅ Found {len(df)} users. Starting reset...")
                    
                    # Step 2: Bulk Reset
                    with st.spinner("⚡ Resetting passwords via SCIM..."):
                        res, new_pwd = call_scim_bulk_api(env_url, username, password, df)
                        
                        if res.status_code in [200, 201]:
                            st.success(f"🎊 Success! All users reset to: `{new_pwd}`")
                            
                            # Step 3: Parse Results
                            results = res.json().get("Operations", [])
                            status_data = []
                            for op in results:
                                status_data.append({
                                    "Username": op.get("bulkId"),
                                    "Status Code": op.get("status", {}).get("code"),
                                    "Result": "Success" if str(op.get("status", {}).get("code")).startswith("2") else "Failed"
                                })
                            st.table(pd.DataFrame(status_data))
                        else:
                            st.error(f"Bulk API Error: {res.status_code}")
                            st.json(res.json())
                else:
                    st.error("❌ No matching users found in PER_USERS.")
            else:
                st.error("❌ Could not retrieve report data. Check your Report Path.")

# Footer
st.markdown("""
<hr style="margin-top: 50px;">
<div style='text-align: center; color: gray; font-size: 0.85em;'>
    <p>© 2025 Automation Tool • Powered by SCIM Bulk API</p>
</div>
""", unsafe_allow_html=True)
