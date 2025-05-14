import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

st.set_page_config(page_title="Clemson Soil Report Scraper", layout="wide")

st.title("🌱 Clemson Soil Report Scraper")
st.markdown("Scrapes **`WarmSeasonGrsMaint`** data from Clemson's soil test reports.")

# Main URL of the soil results
base_url = "https://psaweb.clemson.edu"
main_url = base_url + "/soils/aspx/results.aspx?qs=1&LabNumA=25050901&LabNumB=25050930&DateA=&DateB=&Name=&UserName=AGSRVLB&AdminAuth=0&submit=SEARCH"

# Streamlit button to trigger scraping
if st.button("Start Scraping"):
    with st.spinner("Scraping Clemson soil lab reports..."):
        records = []  # Define this outside try block

        try:
            # Step 1: Load the results table
            main_response = requests.get(main_url, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(main_response.text, "html.parser")

            lab_links = []
            for a in soup.find_all('a', href=True):
                if "standardreport.aspx" in a['href']:
                    lab_links.append((a.text.strip(), base_url + a['href']))

            st.write(f"✅ Found {len(lab_links)} lab reports to process.")

            # Step 2: Loop through each lab report link and extract values
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

                time.sleep(0.5)  # Be kind to the server

            # Step 3: Display the results
            df = pd.DataFrame(records)
            st.success("🎉 Scraping complete!")
            st.dataframe(df)

            # Download button
            st.download_button(
                label="📥 Download CSV",
                data=df.to_csv(index=False),
                file_name="clemson_soil_reports.csv",
                mime="text/csv"
            )

        except Exception as e:
            st.error(f"❌ Scraping failed: {e}")
