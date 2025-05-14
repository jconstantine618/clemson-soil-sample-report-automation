import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from urllib.parse import urljoin

st.set_page_config(page_title="Clemson Soil Report Scraper", layout="wide")

st.title("🌱 Clemson Soil Report Scraper")
st.markdown("Scrapes **`WarmSeasonGrsMaint`** data from Clemson's soil test reports.")

# Define base and full page URL
base_url = "https://psaweb.clemson.edu"
main_url = urljoin(base_url, "/soils/aspx/results.aspx?qs=1&LabNumA=25050901&LabNumB=25050930&DateA=&DateB=&Name=&UserName=AGSRVLB&AdminAuth=0&submit=SEARCH")

if st.button("Start Scraping"):
    with st.spinner("Scraping Clemson soil lab reports..."):
        records = []  # Initialize the list before try block

        try:
            # Step 1: Load the results list
            main_response = requests.get(main_url, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(main_response.text, "html.parser")

            # Step 2: Extract all valid lab links
            lab_links = []
            for a in soup.find_all('a', href=True):
                if "standardreport.aspx" in a['href']:
                    full_link = urljoin(base_url, a['href'])
                    lab_links.append((a.text.strip(), full_link))

            st.success(f"✅ Found {len(lab_links)} lab reports to process.")

            # Step 3: Visit each lab link and extract WarmSeasonGrsMaint
            for labnum, url in lab_links:
                r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
                rsoup = BeautifulSoup(r.text, "html.parser")

                text_blocks = rsoup.find_all(text=True)
                value = ""

                for i, t in enumerate(text_blocks):
                    if "WarmSeasonGrsMaint" in t:
                        for j in range(i, i + 5):
                            if "lbs/1000sq ft" in text_blocks[j]:
                                value = text_blocks[j].strip()
                                break
                        break

                records.append({
                    "Lab Number": labnum,
                    "Report URL": url,
                    "WarmSeasonGrsMaint": value
                })

                time.sleep(0.5)  # Throttle requests

            # Step 4: Show results
            df = pd.DataFrame(records)
            st.success("🎉 Scraping complete!")
            st.dataframe(df)

            # Step 5: Allow download
            st.download_button(
                label="📥 Download CSV",
                data=df.to_csv(index=False),
                file_name="clemson_soil_reports.csv",
                mime="text/csv"
            )

        except Exception as e:
            st.error(f"❌ Scraping failed: {e}")
