# clemson_report_automation.py

import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
from io import BytesIO

# Store processed report data
if 'report_data' not in st.session_state:
    st.session_state.report_data = []  # List of dicts, one per report

# --- STEP 1: Upload reports ---
st.title("Clemson Soil Sample Report Automation")
uploaded_files = st.file_uploader("Upload soil sample PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    # Placeholder for initial CSV summary table
    report_rows = []
    for uploaded_file in uploaded_files:
        file_bytes = uploaded_file.read()
        pdf_text = ""
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            for page in doc:
                pdf_text += page.get_text()
        except Exception as e:
            st.error(f"Could not read {uploaded_file.name}: {e}")
            continue

        # Initial report row (without crop type)
        row = {
            "Filename": uploaded_file.name,
            "Crop Type": "",
            "Lime Amount": "",  # Placeholder; populate this elsewhere as needed
            "PDF Text": pdf_text
        }
        report_rows.append(row)

    st.session_state.report_data = report_rows

# --- STEP 2: Show initial table ---
if st.session_state.report_data:
    df = pd.DataFrame([{
        "Filename": r["Filename"],
        "Crop Type": r["Crop Type"],
        "Lime Amount": r["Lime Amount"]
    } for r in st.session_state.report_data])

    st.write("### Soil Report Summary")
    st.dataframe(df, use_container_width=True)

    # --- STEP 3: Add Crop Screen Button ---
    if st.button("Run Crop Screen"):
        for row in st.session_state.report_data:
            text = row["PDF Text"]
            for crop in ["WarmSeasonGrsMaint(sq ft)", "CoolSeasonGrsMaint(sq ft)", "Centipedegrass(sq ft)"]:
                if crop in text:
                    row["Crop Type"] = crop
                    break  # Only take the first match

        # Update display table after crop match step
        df = pd.DataFrame([{
            "Filename": r["Filename"],
            "Crop Type": r["Crop Type"],
            "Lime Amount": r["Lime Amount"]
        } for r in st.session_state.report_data])

        st.success("Crop types added where detected.")
        st.dataframe(df, use_container_width=True)

        # --- STEP 4: Download Updated CSV ---
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Updated CSV",
            data=csv,
            file_name="updated_soil_report.csv",
            mime="text/csv"
        )
