import streamlit as st
import pandas as pd
import tempfile
import os

def search_keyword_in_uploaded_files(uploaded_files, keyword):
    results = []

    for file in uploaded_files:
        if file.name.endswith((".xml", ".html", ".edge")):
            try:
                content = file.read().decode('utf-8', errors='ignore')
                lines = content.splitlines()
                for i, line in enumerate(lines, start=1):
                    if keyword.lower() in line.lower():
                        results.append({
                            "File Name": file.name,
                            "Line Number": i,
                            "Line Text": line.strip()
                        })
            except Exception as e:
                st.warning(f"⚠️ Could not read file: {file.name} — {e}")
    
    return pd.DataFrame(results)


def main():
    st.set_page_config(page_title="Folder XML Search", layout="wide")
    st.title("📂 Keyword Finder in Uploaded Folder Files")

    uploaded_files = st.file_uploader("📁 Upload all XML/HTML files from a folder", type=["xml", "html", "edge"], accept_multiple_files=True)
    keyword = st.text_input("🔑 Enter keyword to search")
    search_button = st.button("🔍 Search")

    if search_button:
        if not uploaded_files or not keyword.strip():
            st.warning("⚠️ Please upload files and enter a keyword.")
            return

        st.info("🔎 Searching...")
        df_results = search_keyword_in_uploaded_files(uploaded_files, keyword.strip())

        if not df_results.empty:
            st.success(f"✅ Found {len(df_results)} matching lines!")
            st.dataframe(df_results, use_container_width=True)

            # Download as CSV
            csv = df_results.to_csv(index=False).encode('utf-8')
            st.download_button("⬇️ Download CSV", csv, file_name="keyword_results.csv", mime="text/csv")

            # Download as Excel
            excel_path = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
            df_results.to_excel(excel_path.name, index=False)
            with open(excel_path.name, "rb") as f:
                st.download_button("⬇️ Download Excel", f.read(), file_name="keyword_results.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.warning("❌ No matches found in the uploaded files.")

if __name__ == "__main__":
    main()
