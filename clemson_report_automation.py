import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from urllib.parse import urljoin

st.set_page_config(page_title="Clemson Soil + Lime Calculator", layout="wide")
st.title("🌱 Clemson Soil Report Scraper + Lime Calculator")
st.markdown(
    """
    1. Paste your Clemson **results.aspx** URL below.  
    2. App will scrape soil pH, buffer pH, crop type,  
       and the lab’s printed lime rate (lbs/1 000 ft²).  
    3. It will also compute your own lime rate using Adams–Evans +  
       purity, depth, and split‐application adjustments.  
    """
)

# ────────────────────────────────────────────────────────────────────────────────
#  User inputs
# ────────────────────────────────────────────────────────────────────────────────
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

cce_pct = st.number_input(
    "Lime purity (CCE %)",
    min_value=50.0, max_value=120.0, value=100.0, step=1.0,
    help="Neutralizing value of your lime product (100 % = pure CaCO₃)."
)

depth_in = st.number_input(
    "Mixing depth (inches)",
    min_value=1.0, max_value=12.0, value=4.0, step=1.0,
    help="Depth you intend to incorporate lime into the soil."
)

split_app = st.checkbox(
    "Split into two applications",
    value=True,
    help="If checked, total rate will be split into two passes (spring/fall)."
)

# ────────────────────────────────────────────────────────────────────────────────
#  Helper functions
# ────────────────────────────────────────────────────────────────────────────────
def extract_lime_and_crop(html: str):
    """
    Returns (crop_key, printed_lime_lbs) from the Recommendations table.
    """
    soup = BeautifulSoup(html, "html.parser")
    rec_label = soup.find(string=re.compile(r"Recommendations", re.I))
    if not rec_label:
        return None, None
    rec_tbl = rec_label.find_next("table")
    if not rec_tbl:
        return None, None

    crop_key = None
    printed_lime = None

    for tr in rec_tbl.find_all("tr"):
        cells = tr.find_all(["td","th"])
        txt = cells[0].get_text(strip=True)
        if any(term in txt for term in ["WarmSeasonGrsMaint","CoolSeasonGrsMaint","Centipede"]):
            crop_key = txt
            if len(cells) > 1:
                m = re.search(r"(\d+)", cells[1].get_text())
                printed_lime = int(m.group(1)) if m else None
            break

    return crop_key, printed_lime

def target_pH_from_crop(crop_key: str) -> float:
    """Map crop type to Clemson target pH."""
    ck = (crop_key or "").lower()
    if "coolseason" in ck:
        return 6.2
    if "warmseason" in ck:
        return 6.0
    if "centipede" in ck:
        return 5.5
    return 6.2  # fallback

def calc_adams_evans(buffer_pH: float, soil_pH: float, target_pH: float,
                     cce_frac: float, depth: float, split: bool) -> int:
    """
    Compute lime (lbs/1 000 ft²) via:
      1) Adams–Evans tons/acre
      2) Convert to lbs/1 000 ft²
      3) Adjust for CCE (purity)
      4) Adjust for mixing depth & split
    """
    # 1) Adams–Evans in tons/acre
    delta = target_pH - soil_pH
    if delta <= 0:
        return 0
    tons_acre = (0.6 + (6.6 - buffer_pH)) * delta

    # 2) tons→lb/1 000 ft²
    lb_1000 = tons_acre * 2000.0 / 43.56

    # 3) purity adjustment
    lb_adj = lb_1000 / cce_frac

    # 4) depth & split
    depth_factor = depth / 8.0
    split_factor = 0.5 if split else 1.0
    final = round(lb_adj * depth_factor * split_factor)
    return max(final, 0)

# ────────────────────────────────────────────────────────────────────────────────
#  Main scraping & calculation
# ────────────────────────────────────────────────────────────────────────────────
if st.button("Start Scraping"):
    if not results_url.strip():
        st.error("Please enter a valid results.aspx URL above.")
    else:
        with st.spinner("Scraping summary and computing lime rates…"):
            records = []
            try:
                # fetch summary page
                main_resp = requests.get(results_url, headers={"User-Agent":"Mozilla/5.0"})
                main_resp.raise_for_status()
                main_soup = BeautifulSoup(main_resp.text, "html.parser")

                # find the summary table
                summary_tbl = next(
                    (
                        t for t in main_soup.find_all("table")
                        if "Sample No" in t.get_text() and "Soil pH" in t.get_text()
                    ),
                    None
                )
                if not summary_tbl:
                    st.error("Could not find the main results table.")
                    st.stop()

                # loop rows
                for row in summary_tbl.find_all("tr")[1:]:
                    cols = row.find_all("td")
                    if len(cols) < 6:
                        continue

                    sample_no = cols[2].get_text(strip=True)
                    account   = re.sub(r"\D","", sample_no)
                    labnum    = cols[3].get_text(strip=True)
                    date_s    = cols[1].get_text(strip=True)
                    soil_pH   = float(cols[4].get_text(strip=True))
                    buffer_pH = float(cols[5].get_text(strip=True))

                    # detail page
                    href       = cols[3].find("a")["href"]
                    detail_url = urljoin(results_url, href)
                    dresp      = requests.get(detail_url, headers={"User-Agent":"Mozilla/5.0"})
                    dresp.raise_for_status()

                    # extract lab’s printed rate & crop
                    crop_key, printed = extract_lime_and_crop(dresp.text)
                    target      = target_pH_from_crop(crop_key)
                    cce_fraction = cce_pct / 100.0

                    calculated = calc_adams_evans(
                        buffer_pH, soil_pH, target,
                        cce_fraction, depth_in, split_app
                    )

                    records.append({
                        "Account": account,
                        "Sample No": sample_no,
                        "Lab #": labnum,
                        "Date": date_s,
                        "Soil pH": soil_pH,
                        "Buffer pH": buffer_pH,
                        "Crop": crop_key,
                        "Target pH": target,
                        "Lab Lime (lbs/1k ft²)": printed,
                        "Calc Lime(lbs/1k ft²)": calculated,
                    })
                    time.sleep(0.25)

                df = pd.DataFrame(records)
                st.success("✅ All done!")
                st.dataframe(df)
                st.download_button(
                    "📥 Download CSV",
                    data=df.to_csv(index=False),
                    file_name="soil_lime_results.csv",
                    mime="text/csv"
                )

            except Exception as e:
                st.error(f"Error fetching or parsing data: {e}")
