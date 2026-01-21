import streamlit as st
import requests
import base64
import xml.etree.ElementTree as ET
import pandas as pd
from io import StringIO
import json
import secrets
import string

st.set_page_config(page_title="HCM Bulk Password Reset", layout="wide")
st.title("🔐 HCM Bulk Password Reset Tool")

# Sidebar for Credentials
with st.sidebar:
    st.header("⚙️ Connection Settings")
    env_url = st.text_input("🌐 Environment URL", "https://iavnqy-dev2.fa.ocs.oraclecloud.com")
    username = st.text_input("👤 Admin Username")
    password = st.text_input("🔑 Admin Password", type="password")

# Main Input Area
st.subheader("👥 Target Users")
user_input = st.text_area("Enter Usernames (separated by commas)", 
                         placeholder="user1@example.com, user2@example.com",
                         help="Ensure you use the SQL string splitting logic in your BIP Data Model.")

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
    """Calls BIP SOAP service using the parameter items"""
    full_url = env_url.rstrip("/") + "/xmlpserver/services/ExternalReportWSSService"
    # Ensure this path matches exactly where you saved the report
    report_path = "/Custom/Human Capital Management/PASSWORD/User_GUID_Report.xdo"
    
    # Cleaning the input string to remove spaces after commas
    clean_user_list = ",".join([u.strip() for u in user_list_str.split(",")])

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
    
    auth_header = base64.b64encode(f"{username}:{password}".encode()).decode()
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
    except Exception as e:
        st.error(f"SOAP Connection Error: {e}")
        return None

def call_scim_bulk_api(env_url, username, password, guid_df):
    """Sends the Bulk SCIM PATCH request."""
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
    response = requests.post(scim_url, json=payload, auth=(username, password))
    return response, new_password

if st.button("🚀 Execute Bulk Password Reset"):
    if not (username and password and user_input):
        st.warning("⚠️ Please provide admin credentials and target usernames.")
    else:
        with st.spinner("Step 1: Fetching User GUIDs..."):
            csv_data = fetch_guids_soap(env_url, username, password, user_input)
            
            if csv_data:
                df = pd.read_csv(StringIO(csv_data))
                df.columns = [c.strip().upper() for c in df.columns] #
                
                # Filter out any rows where GUID is missing
                if 'USER_GUID' in df.columns and not df.empty:
                    st.info(f"✅ Found {len(df)} matching users in Oracle.")
                    
                    with st.spinner("Step 2: Resetting Passwords via SCIM Bulk API..."):
                        res, common_pwd = call_scim_bulk_api(env_url, username, password, df)
                        
                        if res.status_code in [200, 201]:
                            st.success(f"🎊 Process Complete! All users reset to: `{common_pwd}`")
                            
                            # Detailed Status Table
                            results = res.json().get("Operations", [])
                            status_list = []
                            for op in results:
                                status_list.append({
                                    "Username": op.get("bulkId"),
                                    "Status": "Success" if str(op.get("status", {}).get("code")).startswith("2") else "Failed",
                                    "Details": op.get("status", {}).get("code")
                                })
                            st.table(pd.DataFrame(status_list))
                        else:
                            st.error(f"SCIM Bulk Error: {res.status_code}")
                            st.json(res.json())
                else:
                    st.error("❌ No matching users found. Check if usernames are correct and update your BIP SQL logic.")
            else:
                st.error("❌ Failed to communicate with BIP Report.")

st.markdown('<div style="text-align: center; color: gray; margin-top: 50px;">© 2025 Raktim Pal | HCM Automation</div>', unsafe_allow_html=True)
