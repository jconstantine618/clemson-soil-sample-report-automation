import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from urllib.parse import urljoin
import re

st.set_page_config(
    page_title="Clemson Soil Report Scraper + Lime Calculator",
    layout="wide"
)
st.title("🌱 Clemson Soil Report Scraper + Lime Calculator")
st.markdown(
    "Scrapes summary rows from Clemson’s soil‑test results and "
    "calculates lime (lbs / 1 000 ft²) using the embedded Adams‑Evans "
    "Target pH 6.5 table."
)

# -----------------------------------
#  Static—Clemson Adams‑Evans pH 6.5 table
#  Buffer pH → { soil pH → lbs CaCO₃ / acre }
#  Data pulled from Clemson’s PDF table (Adams & Evans method).
# -----------------------------------
LIME_TABLE_6_5 = {
    4.5: {4.5: 6440, 5.0: 5970, 5.5: 5410, 6.0: 4380, 6.5: 3650, 7.0: 2790, 7.5: 2150, 8.0: 1600},
    5.0: {4.5: 5850, 5.0: 5380, 5.5: 4810, 6.0: 3880, 6.5: 3190, 7.0: 2410, 7.5: 1840, 8.0: 1390},
    5.5: {4.5: 5330, 5.0: 4860, 5.5: 4280, 6.0: 3450, 6.5: 2800, 7.0: 2100, 7.5: 1600, 8.0: 1210},
    6.0: {4.5: 4970, 5.0: 4490, 5.5: 3920, 6.0: 3200, 6.5: 2600, 7.0: 1950, 7.5: 1500, 8.0: 1130},
    6.5: {4.5: 4760, 5.0: 4280, 5.5: 3720, 6.0: 3020, 6.5: 2460, 7.0: 1850, 7.5: 1420, 8.0: 1090},
    7.0: {4.5: 4690, 5.0: 4210, 5.5: 3650, 6.0: 2970, 6.5: 2410, 7.0: 1820, 7.5: 1400, 8.0: 1070},
    7.5: {4.5: 4740, 5.0: 4260, 5.5: 3710, 6.0: 3040, 6.5: 2500, 7.0: 1940, 7.5: 1530, 8.0: 1180},
    8.0: {4.5: 4880, 5.0: 4400, 5.5: 3860, 6.0: 3180, 6.5: 2630, 7.0: 2070, 7.5: 1690, 8.0: 1340},
}

def nearest(val, options):
    return min(options, key=lambda x: abs(x - val))

def lime_per_1000_sqft(buffer_pH: float, soil_pH: float) -> int:
    # 1 / 43.56 × (100 / 85) × (4 / 8) ≈ 0.588
    factor = 0.588
    buf_key = nearest(buffer_pH, LIME_TABLE_6_5.keys())
    soil_key = nearest(soil_pH, LIME_TABLE_6_5[buf_key].keys())
    lbs_per_acre = LIME_TABLE_6_5[buf_key][soil_key]
    return round(lbs_per_acre * factor)

# -----------------------------------
#  Scrape and compute
# -----------------------------------
base_url = "https://psaweb.clemson.edu"
results_url = urljoin(
    base_url,
    "/soils/aspx/results.aspx?qs=1&LabNumA=25050901&LabNumB=25050930"
    "&DateA=&DateB=&Name=&UserName=AGSRVLB&AdminAuth=0&submit=SEARCH"
)

if st.button("Start Scraping"):
    with st.spinner("Fetching summary and computing lime…"):
        try:
            page = requests.get(results_url, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(page.text, "html.parser")

            # find the table with our test results
            summary_tbl = next(
                (
                    t for t in soup.find_all("table")
                    if "Sample No" in t.get_text() and "Soil pH" in t.get_text()
                ),
                None
            )
            if summary_tbl is None:
                st.error("Could not find the soil‑results table. Check layout or access.")
                st.stop()

            records = []
            for tr in summary_tbl.find_all("tr")[1:]:
                td = tr.find_all("td")
                if len(td) < 20:
                    continue

                sample_no = td[2].get_text(strip=True)
                date_s = td[1].get_text(strip=True)
                labnum = td[3].get_text(strip=True)
                soil_pH = float(td[4].get_text(strip=True))
                buffer_pH = float(td[5].get_text(strip=True))
                acct = re.sub(r"\D", "", sample_no)

                records.append({
                    "Account": acct,
                    "Sample No": sample_no,
                    "Lab #": labnum,
                    "Date": date_s,
                    "Soil pH": soil_pH,
                    "Buffer pH": buffer_pH,
                    "P (lbs/A)": td[6].get_text(strip=True),
                    "K (lbs/A)": td[7].get_text(strip=True),
                    "Ca (lbs/A)": td[8].get_text(strip=True),
                    "Mg (lbs/A)": td[9].get_text(strip=True),
                    "Lime (lbs/1 000 ft²)": lime_per_1000_sqft(buffer_pH, soil_pH),
                })

            df = pd.DataFrame(records)
            st.success("✅ Done!")
            st.dataframe(df)
            st.download_button(
                "📥 Download CSV", df.to_csv(index=False), "clemson_soil_data.csv"
            )

        except Exception as e:
            st.error(f"Error: {e}")
