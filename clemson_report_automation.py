import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from urllib.parse import urljoin
import re

st.set_page_config(page_title="Clemson Soil Report Scraper + Lime Calculator",
                   layout="wide")
st.title("🌱 Clemson Soil Report Scraper + Lime Calculator")
st.markdown(
    "Scrapes full soil‑test summary data and calculates **lime "
    "(lbs / 1 000 ft²)** using Clemson’s buffer‑pH tables."
)

# --------------------- URLs ---------------------
base_url = "https://psaweb.clemson.edu"
results_url = urljoin(
    base_url,
    "/soils/aspx/results.aspx?qs=1&LabNumA=25050901&LabNumB=25050930"
    "&DateA=&DateB=&Name=&UserName=AGSRVLB&AdminAuth=0&submit=SEARCH"
)
lime_table_url = (
    "https://www.clemson.edu/public/regulatory/ag-srvc-lab/"
    "soil-testing/lime-tables.html"
)

# ------------------- lime lookup ----------------
@st.cache_data(show_spinner=False)
def build_lime_lookup() -> dict:
    """Return nested dict {buffer_pH: {soil_pH: lbs CaCO3 / acre}}."""
    res = requests.get(lime_table_url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(res.text, "html.parser")

    hdr = soup.find(string=lambda t: t and "Target pH = 6.5" in t)
    table = hdr.find_next("table") if hdr else None
    if table is None:
        raise RuntimeError("6.5‑table not found on lime‑tables page")

    rows = table.find_all("tr")
    soil_headers = [
        float(td.text.strip())
        for td in rows[1].find_all("td")
    ]  # row of soil‑pH labels

    look = {}
    for tr in rows[2:]:
        tds = tr.find_all("td")
        buf_val = float(tds[0].text.strip())
        look[buf_val] = {
            soil_headers[i]: int(tds[i + 1].text.replace(",", "").strip())
            for i in range(len(soil_headers))
        }
    return look


lime_table = build_lime_lookup()


def nearest(val: float, options):
    """Return the option value closest to val."""
    return min(options, key=lambda x: abs(x - val))


def lime_per_1000_sqft(buffer_pH: float, soil_pH: float) -> int:
    """Clemson surface‑application factor 0.588."""
    buf_key = nearest(buffer_pH, lime_table.keys())
    soil_key = nearest(soil_pH, lime_table[buf_key].keys())
    lbs_acre = lime_table[buf_key][soil_key]
    return round(lbs_acre * 0.588)  # lbs / 1 000 ft²


# ------------------ main button -----------------
if st.button("Start Scraping"):
    with st.spinner("Collecting summary rows and computing lime…"):
        records = []

        try:
            page = requests.get(results_url, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(page.text, "html.parser")

            # pick the summary table (has Sample No & Soil pH headers)
            summary_table = None
            for tbl in soup.find_all("table"):
                txt = tbl.get_text()
                if "Sample No" in txt and "Soil pH" in txt:
                    summary_table = tbl
                    break

            if summary_table is None:
                st.error("❌  Soil‑results table not found. "
                         "Layout may have changed or access is blocked.")
                st.stop()

            rows = summary_table.find_all("tr")[1:]  # skip header
            st.write(f"🔍 Found {len(rows)} data rows.")
            if not rows:
                st.warning("No data rows present; nothing to process.")
                st.stop()

            for r in rows:
                td = r.find_all("td")
                if len(td) < 20:
                    continue

                sample_no = td[2].get_text(strip=True)
                soil_pH = float(td[4].get_text(strip=True))
                buffer_pH = float(td[5].get_text(strip=True))

                record = {
                    "Account": re.sub(r"\\D", "", sample_no),
                    "Sample No": sample_no,
                    "Lab #": td[3].get_text(strip=True),
                    "Date": td[1].get_text(strip=True),
                    "Soil pH": soil_pH,
                    "Buffer pH": buffer_pH,
                    "P (lbs/A)": td[6].get_text(strip=True),
                    "K (lbs/A)": td[7].get_text(strip=True),
                    "Ca (lbs/A)": td[8].get_text(strip=True),
                    "Mg (lbs/A)": td[9].get_text(strip=True),
                    "Lime (lbs/1 000 ft²)": lime_per_1000_sqft(buffer_pH, soil_pH),
                }

                records.append(record)
                time.sleep(0.15)

            df = pd.DataFrame(records)
            st.success("✅ Done!")
            st.dataframe(df)
            st.download_button(
                "📥 Download CSV",
                data=df.to_csv(index=False),
                file_name="clemson_soil_data.csv",
            )

        except Exception as exc:
            st.error(f"Unhandled error: {exc}")
