import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from urllib.parse import urljoin

st.set_page_config(
    page_title="Clemson Soil Scraper + Exact Lime",
    layout="wide"
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
    Fallback: find “WarmSeasonGrsMaint” followed by a number + “lbs”
    anywhere in the HTML. Returns that integer, or None if not found.
    """
    match = re.search(
        r"WarmSeasonGrsMaint.*?(\d+)\s*lbs", html,
        re.IGNORECASE | re.DOTALL
    )
    return int(match.group(1)) if match else None

if st.button("Start Scraping"):
    with st.spinner("Gathering samples and fetching exact lime…"):
        records = []
        try:
            # Fetch the summary page
            resp = requests.get(MAIN, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Find the summary table
            summary_tbl = next(
                (
                    tbl for tbl in soup.find_all("table")
                    if "Sample No" in tbl.get_text() and "Soil pH" in tbl.get_text()
                ),
                None
            )
            if summary_tbl is None:
                st.error("❌ Could not find the main results table.")
                st.stop()

            # Iterate data rows
            for tr in summary_tbl.find_all("tr")[1:]:
                cols = tr.find_all("td")
                if len(cols) < 6:
                    continue

                sample_no = cols[2].get_text(strip=True)
                account   = re.sub(r"\D", "", sample_no)
                labnum    = cols[3].get_text(strip=True)
                date_s    = cols[1].get_text(strip=True)
                soil_pH   = cols[4].get_text(strip=True)
                buffer_pH = cols[5].get_text(strip=True)

                # Build and fetch detail page URL (use MAIN as base)
                href       = cols[3].find("a")["href"]
                detail_url = urljoin(MAIN, href)
                dresp      = requests.get(detail_url, headers={"User-Agent": "Mozilla/5.0"})
                dresp.raise_for_status()

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
                time.sleep(0.3)

            # Build DataFrame and display
            df = pd.DataFrame(records)
            st.success("✅ Done!")
            st.dataframe(df)
            st.download_button(
                "📥 Download CSV",
                df.to_csv(index=False),
                "soil_with_exact_lime.csv"
            )

        except Exception as e:
            st.error(f"Error fetching data: {e}")
