import streamlit as st
import pandas as pd
import tempfile

def search_keyword_in_files(files, keyword):
    results = []

    for file in files:
        try:
            # Read the file content with utf-8 and ignore errors
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
            st.warning(f"⚠️ Could not read file {file.name}: {e}")

    return pd.DataFrame(results)

def main():
    st.set_page_config(page_title="XML Keyword Search", layout="wide")
    st.title("🔍 Keyword Finder in XML/HTML Files (Case-Insensitive)")

    files = st.file_uploader(
        "📁 Upload multiple .xml or .html files (select all inside folder)",
        type=["xml", "html"],
        accept_multiple_files=True
    )
    keyword = st.text_input("🔑 Enter keyword (case-insensitive search)")
    if st.button("🔍 Search"):
        if not files or not keyword.strip():
            st.warning("Please upload files and enter a keyword.")
            return

        df = search_keyword_in_files(files, keyword.strip())

        if not df.empty:
            st.success(f"✅ Found {len(df)} matching lines.")
            st.dataframe(df, use_container_width=True)

            # Download CSV
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("⬇️ Download CSV", csv, file_name="search_results.csv", mime="text/csv")

            # Download Excel
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_excel:
                df.to_excel(tmp_excel.name, index=False)
                tmp_excel.seek(0)
                st.download_button("⬇️ Download Excel", tmp_excel.read(), file_name="search_results.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.warning("❌ No keyword found in uploaded files.")

if __name__ == "__main__":
    main()
