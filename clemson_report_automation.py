import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd

st.set_page_config(page_title="Clemson Soil Scraper", layout="wide")

st.title("🌱 Clemson Soil Report Scraper")
st.write("Scrapes `WarmSeasonGrsMaint` data from Clemson's soil test reports.")

# Main URL
base_url = "https://psaweb.clemson.edu"
main_url = base_url + "/soils/aspx/results.aspx?qs=1&LabNumA=25050901&LabNumB=25050930&DateA=&DateB=&Name=&UserName=AGSRVLB&AdminAuth=0&submit=SEARCH"

# Scrape when button is pressed
if st.button("Start Scraping"):
    with st.spinner("Scraping lab reports..."):
        try:
            main_response = requests.get(main_url, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(main_response.text, "html.parser")

            lab_links = []
            for a in soup.find_all('a', href=True):
                if "standardreport.aspx" in a['href']:
                    lab_links.append((a.text.strip(), base_url + a['href']))

            records = []
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

            df = pd.DataFrame(records)
            st.success("Scraping complete!")
            st.dataframe(df)
            st.download_button("Download CSV", df.to_csv(index=False), file_name="clemson_reports.csv")
        except Exception as e:
            st.error(f"Scraping failed: {e}")

# Step 3: Save to CSV
df = pd.DataFrame(records)
df.to_csv("clemson_soil_reports.csv", index=False)
print("Data saved to clemson_soil_reports.csv")
