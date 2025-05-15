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
    "Enter the **Clemson Soil Results** URL below, then click **Start Scraping**. "
    "This will pull each sample’s WarmSeasonGrsMaint (lbs / 1 000 ft²) exactly as the lab prints it."
)

# ─────────────────────────────────────────────────────────────── #
#  1) Let the user specify the initial “results.aspx” URL
# ─────────────────────────────────────────────────────────────── #
results_url = st.text_input(
    "Results page URL",
    value="https://psaweb.clemson.edu/soils/aspx/results.aspx?qs=1"
          "&LabNumA=25050901&LabNumB=25050930&DateA=&DateB=&Name=&UserName=AGSRVLB"
          "&AdminAuth=0&submit=SEARCH",
    help="Paste the full URL (including the query string) that lists your LabNumA/B or date range."
)

def extract_lime_rate(html: str) -> int | None:
    """
    1) Find the 'Recommendations' heading
    2) Grab the NEXT table
    3) In that table, find the row whose first cell contains 'WarmSeasonGrsMaint'
    4) Return the integer found in the second cell
    """
    soup = BeautifulSoup(html, "html.parser")
    rec = soup.find(string=re.compile(r"Recommendations", re.I))
    if not rec:
        return None
    tbl = rec.find_next("table")
    if not tbl:
        return None
    for tr in tbl.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if len(cells) >= 2 and "WarmSeasonGrsMaint" in cells[0].get_text():
            m = re.search(r"(\d+)", cells[1].get_text())
            return int(m.group(1)) if m else None
    return None

if st.button("Start Scraping"):
    if not results_url.strip():
        st.error("Please provide a valid results page URL above.")
    else:
        with st.spinner("Fetching summary rows and detail‑page lime rates…"):
            records = []
            try:
                # 2) Fetch the user‑provided results page
                main_resp = requests.get(results_url, headers={"User-Agent": "Mozilla/5.0"})
                main_resp.raise_for_status()
                main_soup = BeautifulSoup(main_resp.text, "html.parser")

                # 3) Locate the summary table by its headers
                summary_tbl = next(
                    (
                        t for t in main_soup.find_all("table")
                        if "Sample No" in t.get_text() and "Soil pH" in t.get_text()
                    ),
                    None
                )
                if summary_tbl is None:
                    st.error("❌ Could not find the main results table on that page.")
                    st.stop()

                # 4) Loop each row and fetch its detail page
                for row in summary_tbl.find_all("tr")[1:]:
                    cols = row.find_all("td")
                    if len(cols) < 6:
                        continue  # skip malformed rows

                    sample_no = cols[2].get_text(strip=True)
                    account   = re.sub(r"\D", "", sample_no)
                    labnum    = cols[3].get_text(strip=True)
                    date_s    = cols[1].get_text(strip=True)
                    soil_pH   = cols[4].get_text(strip=True)
                    buffer_pH = cols[5].get_text(strip=True)

                    # Build detail‑page URL relative to the results page
                    href       = cols[3].find("a")["href"]
                    detail_url = urljoin(results_url, href)
                    dresp      = requests.get(detail_url, headers={"User-Agent": "Mozilla/5.0"})
                    dresp.raise_for_status()

                    # Extract the lab’s own WarmSeasonGrsMaint value
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
                    time.sleep(0.25)  # be polite to the server

                # 5) Display and offer CSV download
                df = pd.DataFrame(records)
                st.success("✅ Scraping complete!")
                st.dataframe(df)
                st.download_button(
                    "📥 Download CSV",
                    data=df.to_csv(index=False),
                    file_name="soil_with_exact_lime.csv",
                    mime="text/csv"
                )

            except Exception as e:
                st.error(f"Error fetching data: {e}")
