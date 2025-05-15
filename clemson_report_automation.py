import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time, re
from urllib.parse import urljoin

st.set_page_config(page_title="Clemson Soil + Lime Calculator", layout="wide")
st.title("🌱 Clemson Soil Report Scraper + Lime Calculator")
st.markdown(
    "Enter a Clemson **results.aspx** URL and scrap soil pH, buffer pH, crop type, "
    "the lab’s WarmSeasonGrsMaint lime rate, plus a calculated rate via Adams–Evans."
)

# 1) URL input
results_url = st.text_input(
    "Results page URL",
    "https://psaweb.clemson.edu/soils/aspx/results.aspx?"
    "qs=1&LabNumA=25050901&LabNumB=25050930&DateA=&DateB=&Name=&"
    "UserName=AGSRVLB&AdminAuth=0&submit=SEARCH"
)

# 2) Helpers --------------------------------------------------

def extract_lime_and_crop(html: str):
    """Returns (crop_key, printed_lime_lbs) from the Recommendations table."""
    soup = BeautifulSoup(html, "html.parser")
    rec_label = soup.find(string=re.compile(r"Recommendations", re.I))
    if not rec_label:
        return None, None
    rec_tbl = rec_label.find_next("table")
    if not rec_tbl:
        return None, None

    crop_key = None
    printed = None

    for tr in rec_tbl.find_all("tr"):
        cells = tr.find_all(["td","th"])
        text0 = cells[0].get_text(strip=True)
        # find the Warm/Cool/Centipede row
        if "WarmSeasonGrsMaint" in text0 or "CoolSeasonGrsMaint" in text0 or "Centipede" in text0:
            crop_key = text0
            # extract the number from the next cell
            if len(cells) > 1:
                m = re.search(r"(\d+)", cells[1].get_text())
                printed = int(m.group(1)) if m else None
            break
    return crop_key, printed

def calc_adams_evans(buffer_pH: float, soil_pH: float, target_pH: float) -> int:
    """
    LR tons/acre = [0.6 + (6.6 - buffer_pH)] * (target_pH - soil_pH)
    Convert to lbs/1k ft²: *2000 (lb/ton) /43.56
    """
    df = target_pH - soil_pH
    if df <= 0:
        return 0
    tons_per_acre = (0.6 + (6.6 - buffer_pH)) * df
    lbs_1000 = round(tons_per_acre * 2000 / 43.56)
    return max(lbs_1000, 0)

def target_pH_from_crop(crop_key: str) -> float:
    ck = crop_key.lower()
    if "coolseason" in ck:
        return 6.2
    if "warmseason" in ck:
        return 6.0
    if "centipede" in ck:
        return 5.5
    # default fallback
    return 6.2

# 3) Main scrape + compute -----------------------------------
if st.button("Start Scraping"):
    if not results_url:
        st.error("Please enter a results.aspx URL above.")
    else:
        with st.spinner("Scraping summary and computing lime…"):
            records=[]
            try:
                # Summary page
                r = requests.get(results_url, headers={"User-Agent":"Mozilla/5.0"})
                r.raise_for_status()
                summary_soup = BeautifulSoup(r.text, "html.parser")

                # Locate the table with "Sample No" + "Soil pH"
                summary_tbl = next(
                    (t for t in summary_soup.find_all("table")
                     if "Sample No" in t.get_text() and "Soil pH" in t.get_text()),
                    None
                )
                if not summary_tbl:
                    st.error("Could not find the summary table.")
                    st.stop()

                for tr in summary_tbl.find_all("tr")[1:]:
                    td = tr.find_all("td")
                    if len(td) < 6:
                        continue

                    sample_no  = td[2].get_text(strip=True)
                    account    = re.sub(r"\D","", sample_no)
                    labnum     = td[3].get_text(strip=True)
                    date_s     = td[1].get_text(strip=True)
                    soil_pH     = float(td[4].get_text(strip=True))
                    buffer_pH   = float(td[5].get_text(strip=True))

                    href       = td[3].find("a")["href"]
                    detail_url = urljoin(results_url, href)
                    d = requests.get(detail_url, headers={"User-Agent":"Mozilla/5.0"})
                    d.raise_for_status()

                    crop_key, printed_lime = extract_lime_and_crop(d.text)
                    targ = target_pH_from_crop(crop_key or "")
                    calc_lime = calc_adams_evans(buffer_pH, soil_pH, targ)

                    records.append({
                        "Account": account,
                        "Sample No": sample_no,
                        "Lab #": labnum,
                        "Date": date_s,
                        "Soil pH": soil_pH,
                        "Buffer pH": buffer_pH,
                        "Crop Key": crop_key,
                        "Target pH": targ,
                        "Printed Lime (lbs/1k ft²)": printed_lime,
                        "Calc Lime  (lbs/1k ft²)": calc_lime,
                    })
                    time.sleep(0.3)

                df = pd.DataFrame(records)
                st.success("✅ Done!")
                st.dataframe(df)
                st.download_button(
                    "📥 Download CSV",
                    df.to_csv(index=False),
                    "soil_lime_results.csv",
                    mime="text/csv",
                )
            except Exception as e:
                st.error(f"Error fetching data: {e}")
