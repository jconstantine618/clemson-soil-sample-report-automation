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
    "Scrapes summary rows from Clemson’s soil‑test results and **calculates lime "
    "(lbs / 1 000 ft²)** using the official buffer‑pH tables (target pH 6.5, turf‑maintenance)."
)

# ------------------------------------------------------------------ #
#  URLs
# ------------------------------------------------------------------ #
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

# ------------------------------------------------------------------ #
#  Build lime‑rate lookup from Clemson Target‑pH 6.5 table
# ------------------------------------------------------------------ #
@st.cache_data(show_spinner=False)
def build_lime_lookup() -> dict:
    """
    Return nested dict  {buffer_pH: {soil_pH: lbs CaCO3 / acre}}
    parsed from Clemson's Target‑pH 6.5 Adams‑Evans table.
    """
    resp = requests.get(lime_table_url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(resp.text, "html.parser")

    # Find the table that contains the heading "Target pH = 6.5"
    target_tbl = next(
        (t for t in soup.find_all("table") if "Target pH = 6.5" in t.get_text()),
        None,
    )
    if target_tbl is None:
        raise RuntimeError("Target‑pH 6.5 lime table not found.")

    rows = target_tbl.find_all("tr")

    # Locate the row whose cells (except first) are all numeric → soil‑pH header row
    soil_headers, start_idx = None, None
    for idx, tr in enumerate(rows):
        vals = [td.get_text(strip=True) for td in tr.find_all("td")]
        if (
            len(vals) > 1
            and all(re.fullmatch(r"\d+(\.\d+)?", v) for v in vals[1:])
        ):
            soil_headers = [float(v) for v in vals[1:]]
            start_idx = idx + 1
            break
    if soil_headers is None:
        raise RuntimeError("Numeric soil‑pH header row not detected.")

    # Build lookup dict
    look = {}
    for tr in rows[start_idx:]:
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cells) != len(soil_headers) + 1:
            continue
        if not re.fullmatch(r"\d+(\.\d+)?", cells[0]):
            continue
        buf_val = float(cells[0])
        look[buf_val] = {
            soil_headers[i]: int(cells[i + 1].replace(",", ""))
            for i in range(len(soil_headers))
        }
    return look


lime_table = build_lime_lookup()


def nearest(value: float, options):
    """Return the option value closest to *value*."""
    return min(options, key=lambda x: abs(x - value))


def lime_per_1000_sqft(buffer_pH: float, soil_pH: float) -> int:
    """
    lbs CaCO3 / 1 000 ft² for turf surface application.
    Conversion factor (lbs/acre → lbs/1 000 ft²) * CCE adjustment * 4‑in incorporation depth:
        1 / 43.56  * 100 / 85  * 4 / 8  ≈ 0.588
    """
    buf_key = nearest(buffer_pH, lime_table.keys())
    soil_key = nearest(soil_pH, lime_table[buf_key].keys())
    lbs_acre = lime_table[buf_key][soil_key]
    return round(lbs_acre * 0.588)


# ------------------------------------------------------------------ #
#  Scrape the results list and compute lime
# ------------------------------------------------------------------ #
if st.button("Start Scraping"):
    with st.spinner("Collecting summary rows and computing lime rates…"):
        records = []

        try:
            res = requests.get(results_url, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(res.text, "html.parser")

            # Find the summary table (contains both 'Sample No' and 'Soil pH')
            summary_tbl = next(
                (
                    t for t in soup.find_all("table")
                    if "Sample No" in t.get_text() and "Soil pH" in t.get_text()
                ),
                None,
            )
            if summary_tbl is None:
                st.error(
                    "❌  Soil‑results table not found. "
                    "Layout may have changed or the site blocked this request."
                )
                st.stop()

            rows = summary_tbl.find_all("tr")[1:]  # skip header
            st.write(f"🔍 Found **{len(rows)}** data rows.")

            for tr in rows:
                td = tr.find_all("td")
                if len(td) < 20:
                    continue  # skip incomplete rows

                sample_no = td[2].get_text(strip=True)
                soil_pH = float(td[4].get_text(strip=True))
                buffer_pH = float(td[5].get_text(strip=True))

                records.append(
                    {
                        "Account": re.sub(r"\D", "", sample_no),
                        "Sample No": sample_no,
                        "Lab #": td[3].get_text(strip=True),
                        "Date": td[1].get_text(strip=True),
                        "Soil pH": soil_pH,
                        "Buffer pH": buffer_pH,
                        "P (lbs/A)": td[6].get_text(strip=True),
                        "K (lbs/A)": td[7].get_text(strip=True),
                        "Ca (lbs/A)": td[8].get_text(strip=True),
                        "Mg (lbs/A)": td[9].get_text(strip=True),
                        "Lime (lbs/1 000 ft²)": lime_per_1000_sqft(
                            buffer_pH, soil_pH
                        ),
                    }
                )
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
