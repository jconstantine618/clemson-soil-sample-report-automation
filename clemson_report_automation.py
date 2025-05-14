import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from urllib.parse import urljoin

st.set_page_config(
    page_title="Clemson Soil Scraper + Exact Lime",
    layout="wide",
)
st.title("🌱 Clemson Soil Report Scraper + Exact Lime")
st.markdown(
    "Pulls each sample’s **WarmSeasonGrsMaint** (lbs / 1 000 ft²) exactly as the lab prints it."
)

BASE = "https://psaweb.clemson.edu"
MAIN = (
    BASE
    + "/soils/aspx/results.aspx?"
    + "qs=1&LabNumA=25050901&LabNumB=25050930"
    + "&DateA=&DateB=&Name=&UserName=AGSRVLB&AdminAuth=0&submit=SEARCH"
)

def extract_lime_rate(html: str) -> int | None:
    """
    1) Find the 'Recommendations' heading
    2) Grab the NEXT table
    3) In that table, find the row whose first cell contains 'WarmSeasonGrsMaint'
    4) Return the integer found in the second cell
    """
    soup = BeautifulSoup(html, "html.parser")

    # 1) Locate the Recommendations heading
    rec = soup.find(string=re.compile(r"Recommendations", re.I))
    if not rec:
        return None

    # 2) The table immediately after it
    tbl = rec.find_next("table")
    if not tbl:
        return None

    # 3) Scan its rows for WarmSeasonGrsMaint
    for tr in tbl.find_all("tr"):
        tds = tr.find_all(["td", "th"])
        if len(tds) >= 2 and "WarmSeasonGrsMaint" in tds[0].get_text():
            # 4) Extract the integer from the second cell
            m = re.search(r"(\d+)", tds[1].get_text())
            return int(m.group(1)) if m else None

    return None


if st.button("Start Scraping"):
    with st.spinner("Gathering samples and fetching exact lime…"):
        records = []
        try:
            # 1) get the summary page
            r = requests.get(MAIN, headers={"User-Agent":"Mozilla/5.0"})
            r.raise_for_status()
            summary = BeautifulSoup(r.text, "html.parser")

            # 2) find the main results table
            main_tbl = next(
                (
                    t for t in summary.find_all("table")
                    if "Sample No" in t.get_text() and "Soil pH" in t.get_text()
                ),
                None,
            )
            if not main_tbl:
                st.error("❌ Main results table not found.")
                st.stop()

            # 3) loop data rows
            for row in main_tbl.find_all("tr")[1:]:
                cols = row.find_all("td")
                if len(cols) < 6:
                    continue

                sample_no = cols[2].get_text(strip=True)
                account   = re.sub(r"\D", "", sample_no)
                labnum    = cols[3].get_text(strip=True)
                date_s    = cols[1].get_text(strip=True)
                soil_pH   = cols[4].get_text(strip=True)
                buffer_pH = cols[5].get_text(strip=True)

                # build detail URL correctly in the same folder
                href       = cols[3].find("a")["href"]
                detail_url = urljoin(MAIN, href)
                dresp      = requests.get(detail_url, headers={"User-Agent":"Mozilla/5.0"})
                dresp.raise_for_status()

                # 4) extract the lab’s lime rate
                lime_rate = extract_lime_rate(dresp.text)

                records.append({
                    "Account": account,
                    "Sample No": sample_no,
                    "Lab #": labnum,
                    "Date": date_s,
                    "Soil pH": soil_pH,
                    "Buffer pH": buffer_pH,
                    "Lime (lbs/1000 ft²)": lime_rate,
                })
                time.sleep(0.25)

            # 5) show results & CSV
            df = pd.DataFrame(records)
            st.success("✅ Done!")
            st.dataframe(df)
            st.download_button(
                "📥 Download CSV",
                df.to_csv(index=False),
                "soil_with_exact_lime.csv",
                mime="text/csv",
            )

        except Exception as e:
            st.error(f"Error fetching data: {e}")
