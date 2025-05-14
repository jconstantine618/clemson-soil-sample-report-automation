import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from urllib.parse import urljoin

st.set_page_config(page_title="Clemson Soil Scraper + Exact Lime", layout="wide")
st.title("🌱 Clemson Soil Report Scraper + Exact Lime")
st.markdown("Pulls the lab’s own WarmSeasonGrsMaint (lbs/1000 ft²) directly from each detail page.")

BASE = "https://psaweb.clemson.edu"
MAIN = BASE + "/soils/aspx/results.aspx?qs=1&LabNumA=25050901&LabNumB=25050930" \
             "&DateA=&DateB=&Name=&UserName=AGSRVLB&AdminAuth=0&submit=SEARCH"

if st.button("Start Scraping"):
    with st.spinner("Gathering samples and fetching detail‑page lime…"):
        records = []
        resp = requests.get(MAIN, headers={"User-Agent":"Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "html.parser")

        # 1) find the correct summary table
        summary = next(
            (t for t in soup.find_all("table")
             if "Sample No" in t.text and "Soil pH" in t.text),
            None
        )
        if not summary:
            st.error("❌ Couldn’t find the main results table.")
            st.stop()

        # 2) loop each data row
        for tr in summary.find_all("tr")[1:]:
            td = tr.find_all("td")
            if len(td) < 5:
                continue

            sample = td[2].text.strip()
            acct   = re.sub(r"\D","", sample)
            labnum = td[3].text.strip()
            date   = td[1].text.strip()
            ph     = td[4].text.strip()
            buf    = td[5].text.strip()

            # build and fetch the detail page
            href = td[3].find("a")["href"]
            detail_url = urljoin(BASE, href)
            dresp = requests.get(detail_url, headers={"User-Agent":"Mozilla/5.0"})
            dsoup = BeautifulSoup(dresp.text, "html.parser")

            # pull the WarmSeasonGrsMaint row
            lime_txt = ""
            for row in dsoup.find_all("tr"):
                cells = row.find_all("td")
                if len(cells)==2 and "WarmSeasonGrsMaint" in cells[0].text:
                    lime_txt = cells[1].text.strip()
                    break

            # extract just the number
            match = re.search(r"(\d+)", lime_txt)
            lime_num = int(match.group(1)) if match else None

            records.append({
                "Account": acct,
                "Sample No": sample,
                "Lab #": labnum,
                "Date": date,
                "Soil pH": ph,
                "Buffer pH": buf,
                "Lime (lbs/1000 ft²)": lime_num
            })
            time.sleep(0.3)

        df = pd.DataFrame(records)
        st.success("✅ Done!")
        st.dataframe(df)
        st.download_button("📥 Download CSV", df.to_csv(index=False), "soil_with_exact_lime.csv")
