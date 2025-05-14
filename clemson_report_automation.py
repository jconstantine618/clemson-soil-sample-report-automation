import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from urllib.parse import urljoin
import re

st.set_page_config(page_title="Clemson Soil Report Scraper", layout="wide")
st.title("🌱 Clemson Soil Report Scraper + Lime Calculator")

base_url = "https://psaweb.clemson.edu"
results_url = urljoin(
    base_url,
    "/soils/aspx/results.aspx?qs=1&LabNumA=25050901&LabNumB=25050930"
    "&DateA=&DateB=&Name=&UserName=AGSRVLB&AdminAuth=0&submit=SEARCH"
)
lime_table_url = "https://www.clemson.edu/public/regulatory/ag-srvc-lab/soil-testing/lime-tables.html"

# ------------------------------------------------------------------ #
# Helper – pull the Target‑pH 6.5 table and build a lookup dictionary
# ------------------------------------------------------------------ #
@st.cache_data(show_spinner=False)
def build_lime_lookup():
    r = requests.get(lime_table_url, headers={"User-Agent": "Mozilla/5.0"})
    s = BeautifulSoup(r.text, "html.parser")

    # find the <h3> or <strong> tag that says "Target pH = 6.5"
    header = s.find(string=lambda x: x and "Target pH = 6.5" in x)
    table = header.find_next("table") if header else None
    if not table:
        st.error("Could not locate the 6.5 lime table.")
        st.stop()

    # first row after header row contains soil‑pH column labels
    rows = table.find_all("tr")
    soil_headers = [float(th.text.strip()) for th in rows[1].find_all("td")]

    lookup = {}
    for tr in rows[2:]:  # data rows
        cells = tr.find_all("td")
        buffer_val = float(cells[0].text.strip())
        lookup[buffer_val] = {
            soil_headers[i]: int(cells[i + 1].text.strip().replace(",", ""))  # lbs/acre
            for i in range(len(soil_headers))
        }
    return lookup

lime_lookup = build_lime_lookup()

# helper to round buffer & soil pH to the nearest table increment (0.05)
def nearest(val, options):
    return min(options, key=lambda x: abs(x - val))

def lime_per_1000_sqft(buffer_pH: float, soil_pH: float) -> int:
    buf_key = nearest(buffer_pH, lime_lookup.keys())
    soil_key = nearest(soil_pH, list(lime_lookup[buf_key].keys()))
    lbs_per_acre = lime_lookup[buf_key][soil_key]
    # Clemson turf surface‑app factor
    lbs_per_1000 = round(lbs_per_acre * 0.588)
    return lbs_per_1000

# ------------------------------------------------------------------ #
# Main scraping workflow
# ------------------------------------------------------------------ #
if st.button("Start Scraping"):
    with st.spinner("Scraping summary table and computing lime rates..."):
        records = []

        try:
            res = requests.get(results_url, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(res.text, "html.parser")

            # find the correct results table (contains "Sample No" & "Soil pH")
            data_table = None
            for t in soup.find_all("table"):
                if "Sample No" in t.text and "Soil pH" in t.text:
                    data_table = t
                    break
            if not data_table:
                st.error("
