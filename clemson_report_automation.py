import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from urllib.parse import urljoin

st.set_page_config(page_title="Clemson Soil Report Scraper", layout="wide")

st.title("🌱 Clemson Soil Report Scraper")
st.markdown("Scrapes **`WarmSeasonGrsMaint`** data from Clemson's soil test reports.")

base_url = "https://psaweb.clemson.edu"
main_url = urljoin(base_url, "/soils/aspx/results.aspx?qs=1&LabNumA=25050901&LabNumB=25050930&DateA=&DateB=&Name=&UserName=AGSRVLB&AdminAuth=0&submit=SEARCH")

if st.button("Start Scraping"):
    with st.spinner("Scraping Clemson soil lab reports..."):
        records = []

        try:
            main_response = requests.get(main_url, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(main_response.text, "html.parser")

            lab_links = []
            for a in soup.find_all('a', href=True):
                if "standardreport.aspx" in a['href']:
                    full_link = urljoin(base_url, a['href'])
                    lab_links.append((a.text.strip(), full_link))

            st.success(f"✅ Found {len(lab_links)} lab reports to process.")

            for labnum, url in lab_links:
                r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
                rsoup = BeautifulSoup(r.text, "html.parser")

                # Look specifically in the "Recommendations" or "Lime" section
                warm_value = ""
                for b in rsoup.find_all("b"):
                    if "WarmSeasonGrsMaint" in b.get_text():
                        parent = b.find_parent()
                        if parent and "lbs/1000sq ft" in parent.text:
                            warm_value = parent.text.strip().split()[-2]  # Just the number, like "78"
                        break

                records.append({
                    "Lab Number": labnum,
                    "Report URL": url,
                    "WarmSeasonGrsMaint": warm_value
                })

                time.sleep(0.5)

            df = pd.DataFrame(records)
            st.success("🎉 Scraping complete!")
            st.dataframe(df)

            st.download_button(
                label="📥 Download CSV",
                data=df.to_csv(index=False),
                file_name="clemson_soil_reports.csv",
                mime="text/csv"
            )

        except Exception as e:
            st.error(f"❌ Scraping failed: {e}")
