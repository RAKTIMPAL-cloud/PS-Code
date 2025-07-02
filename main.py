import streamlit as st
import zipfile
import tempfile
import os
import pandas as pd

def search_keyword_in_files(folder_path, keyword):
    results = []

    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith((".xml", ".html")):
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, folder_path)
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for i, line in enumerate(f, start=1):
                            if keyword.lower() in line.lower():
                                results.append({
                                    'File Path': relative_path,
                                    'Line Number': i,
                                    'Line Text': line.strip()
                                })
                except Exception as e:
                    st.warning(f"Could not read file: {relative_path} — {e}")
    return pd.DataFrame(results)

def main():
    st.set_page_config(page_title="XML Keyword Finder", layout="wide")
    st.title("🔍 XML/HTML Keyword Search in Zipped Folder")

    uploaded_zip = st.file_uploader("📁 Upload a zipped folder containing .xml/.html files", type=["zip"])
    keyword = st.text_input("🔑 Enter keyword to search")

    search_button = st.button("🔍 Search")

    if search_button:
        if not uploaded_zip or not keyword.strip():
            st.warning("Please upload a ZIP file and enter a keyword.")
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "uploaded.zip")

            # Save uploaded ZIP
            with open(zip_path, "wb") as f:
                f.write(uploaded_zip.read())

            # Extract ZIP
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(tmpdir)

            st.info("Searching... Please wait ⏳")
            df_results = search_keyword_in_files(tmpdir, keyword.strip())

            if not df_results.empty:
                st.success(f"✅ Found {len(df_results)} matching lines!")
                st.dataframe(df_results, use_container_width=True)

                # CSV download
                csv = df_results.to_csv(index=False).encode('utf-8')
                st.download_button("⬇️ Download CSV", csv, file_name="search_results.csv", mime="text/csv")

                # Excel download
                excel_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
                df_results.to_excel(excel_file.name, index=False)
                with open(excel_file.name, 'rb') as f:
                    st.download_button("⬇️ Download Excel", f.read(), file_name="search_results.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else:
                st.warning("❌ No matching keyword found in any .xml or .html file.")

if __name__ == "__main__":
    main()
