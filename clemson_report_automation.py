import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
from urllib.parse import urljoin

st.set_page_config(
    page_title="Clemson Soil Full Data + Crop Type Extractor",
    layout="wide"
)
st.title("🌱 Clemson Soil Report Scraper – Full Data + Crop Type")
st.markdown(
    "Enter a Clemson **results.aspx** URL and extract each sample’s full soil data "
    "plus the crop type (Cool‑Season, Warm‑Season, or Centipede) from the Recommendations section."
)

# User input for the results page URL
results_url = st.text_input(
    "Results page URL",
    value=(
        "https://psaweb.clemson.edu/soils/aspx/results.aspx?"
        "qs=1&LabNumA=25050901&LabNumB=25050930"
        "&DateA=&DateB=&Name=&UserName=AGSRVLB"
        "&AdminAuth=0&submit=SEARCH"
    ),
    help="Paste the full URL that lists your LabNum range or date range."
)

def extract_crop_type(html: str) -> str | None:
    """Extracts the crop type ('COOL‑SEASON', 'WARM‑SEASON', 'CENTIPEDE', etc.)"""
    soup = BeautifulSoup(html, "html.parser")
    # Look for the cell that starts with 'Crop'
    for td in soup.find_all("td"):
        text = td.get_text(strip=True)
        if text.startswith("Crop"):
            parts = text.split(":", 1)
            if len(parts) == 2:
                return parts[1].strip()
    return None

if st.button("Start Scraping"):
    if not results_url.strip():
        st.error("Please enter a valid results.aspx URL above.")
    else:
        with st.spinner("Scraping summary and extracting full data…"):
            records = []
            try:
                # Fetch summary page
                resp = requests.get(results_url, headers={"User-Agent":"Mozilla/5.0"})
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")

                # Locate the main results table by headers
                summary_tbl = next(
                    (
                        tbl for tbl in soup.find_all("table")
                        if "Sample No" in tbl.get_text() and "Soil pH" in tbl.get_text()
                    ),
                    None
                )
                if not summary_tbl:
                    st.error("Could not find the main results table.")
                    st.stop()

                # Iterate each data row
                for row in summary_tbl.find_all("tr")[1:]:
                    cols = row.find_all("td")
                    if len(cols) < 20:
                        continue

                    name           = cols[0].get_text(strip=True)
                    date_sampled   = cols[1].get_text(strip=True)
                    sample_no      = cols[2].get_text(strip=True)
                    account_number = re.sub(r"\D", "", sample_no)
                    lab_num        = cols[3].get_text(strip=True)
                    href           = cols[3].find("a")["href"] if cols[3].find("a") else ""
                    detail_url     = urljoin(results_url, href)
                    soil_pH        = cols[4].get_text(strip=True)
                    buffer_pH      = cols[5].get_text(strip=True)
                    p_lbs          = cols[6].get_text(strip=True)
                    k_lbs          = cols[7].get_text(strip=True)
                    ca_lbs         = cols[8].get_text(strip=True)
                    mg_lbs         = cols[9].get_text(strip=True)
                    zn_lbs         = cols[10].get_text(strip=True)
                    mn_lbs         = cols[11].get_text(strip=True)
                    cu_lbs         = cols[12].get_text(strip=True)
                    b_lbs          = cols[13].get_text(strip=True)
                    na_lbs         = cols[14].get_text(strip=True)
                    s_lbs          = cols[15].get_text(strip=True)
                    ec             = cols[16].get_text(strip=True)
                    no3_n          = cols[17].get_text(strip=True)
                    om_pct         = cols[18].get_text(strip=True)
                    bulk_density   = cols[19].get_text(strip=True)

                    # Fetch detail page to extract crop type
                    crop_type = None
                    if detail_url:
                        dresp = requests.get(detail_url, headers={"User-Agent":"Mozilla/5.0"})
                        if dresp.ok:
                            crop_type = extract_crop_type(dresp.text)

                    records.append({
                        "Account Number": account_number,
                        "Name": name,
                        "Date Sampled": date_sampled,
                        "Sample No": sample_no,
                        "Lab Number": lab_num,
                        "Soil pH": soil_pH,
                        "Buffer pH": buffer_pH,
                        "P (lbs/A)": p_lbs,
                        "K (lbs/A)": k_lbs,
                        "Ca (lbs/A)": ca_lbs,
                        "Mg (lbs/A)": mg_lbs,
                        "Zn (lbs/A)": zn_lbs,
                        "Mn (lbs/A)": mn_lbs,
                        "Cu (lbs/A)": cu_lbs,
                        "B (lbs/A)": b_lbs,
                        "Na (lbs/A)": na_lbs,
                        "S (lbs/A)": s_lbs,
                        "EC (mmhos/cm)": ec,
                        "NO3-N (ppm)": no3_n,
                        "OM (%)": om_pct,
                        "Bulk Density (lbs/A)": bulk_density,
                        "Crop Type": crop_type,
                    })

                df = pd.DataFrame(records)
                st.success("✅ Extraction complete!")
                st.dataframe(df)
                st.download_button(
                    "📥 Download CSV",
                    data=df.to_csv(index=False),
                    file_name="soil_full_data.csv",
                    mime="text/csv"
                )

            except Exception as e:
                st.error(f"Error: {e}")
