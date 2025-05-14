import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from urllib.parse import urljoin
import re

st.set_page_config(page_title="Clemson Soil Report Scraper", layout="wide")
st.title("🌱 Clemson Soil Report Scraper")
st.markdown("Scrapes full soil test data and **`WarmSeasonGrsMaint`**, including account number from Sample No.")

base_url = "https://psaweb.clemson.edu"
main_url = urljoin(base_url, "/soils/aspx/results.aspx?qs=1&LabNumA=25050901&LabNumB=25050930&DateA=&DateB=&Name=&UserName=AGSRVLB&AdminAuth=0&submit=SEARCH")

if st.button("Start Scraping"):
    with st.spinner("Scraping report list and detailed pages..."):
        records = []

        try:
            response = requests.get(main_url, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(response.text, "html.parser")

            # Find the correct table based on expected column headers
            tables = soup.find_all("table")
            table = None
            for t in tables:
                if "Sample No" in t.text and "Soil pH" in t.text and "Buffer pH" in t.text:
                    table = t
                    break

            if not table:
                st.error("❌ Could not find the soil test data table. The site may have blocked us or changed layout.")
                st.stop()

            rows = table.find_all("tr")
            st.write(f"🔍 Found {len(rows) - 1} data rows (excluding header).")

            if len(rows) <= 1:
                st.error("❌ No data rows found. The table structure may have changed or is blocked.")
                st.stop()

            st.write("🧪 First row contents:", rows[1].text.strip())

            for row in rows[1:]:
                cells = row.find_all("td")
                if len(cells) < 20:
                    continue

                name = cells[0].text.strip()
                date_sampled = cells[1].text.strip()
                sample_no = cells[2].text.strip()
                account_number = re.sub(r"\D", "", sample_no)
                lab_num = cells[3].text.strip()
                detail_link = urljoin(base_url, cells[3].find("a")["href"]) if cells[3].find("a") else ""

                soil_data = {
                    "Account Number": account_number,
                    "Name": name,
                    "Date Sampled": date_sampled,
                    "Sample No": sample_no,
                    "Lab Number": lab_num,
                    "Report URL": detail_link,
                    "Soil pH": cells[4].text.strip(),
                    "Buffer pH": cells[5].text.strip(),
                    "P (lbs/A)": cells[6].text.strip(),
                    "K (lbs/A)": cells[7].text.strip(),
                    "Ca (lbs/A)": cells[8].text.strip(),
                    "Mg (lbs/A)": cells[9].text.strip(),
                    "Zn (lbs/A)": cells[10].text.strip(),
                    "Mn (lbs/A)": cells[11].text.strip(),
                    "Cu (lbs/A)": cells[12].text.strip(),
                    "B (lbs/A)": cells[13].text.strip(),
                    "Na (lbs/A)": cells[14].text.strip(),
                    "S (lbs/A)": cells[15].text.strip(),
                    "EC (mmhos/cm)": cells[16].text.strip(),
                    "NO3-N (ppm)": cells[17].text.strip(),
                    "OM (%)": cells[18].text.strip(),
                    "Bulk Density (lbs/A)": cells[19].text.strip()
                }

                # Scrape WarmSeasonGrsMaint from detail page
                warm_value = ""
                if detail_link:
                    try:
                        detail_response = requests.get(detail_link, headers={"User-Agent": "Mozilla/5.0"})
                        detail_soup = BeautifulSoup(detail_response.text, "html.parser")
                        detail_rows = detail_soup.find_all('tr')
                        for drow in detail_rows:
                            dcells = drow.find_all('td')
                            if len(dcells) == 2 and "WarmSeasonGrsMaint" in dcells[0].text:
                                warm_value = dcells[1].text.strip()
                                break
                    except Exception as e:
                        warm_value = f"Error: {e}"

                soil_data["WarmSeasonGrsMaint"] = warm_value
                records.append(soil_data)
                time.sleep(0.5)

            df = pd.DataFrame(records)
            if df.empty:
                st.warning("⚠️ Scraping completed, but no rows were added. Double-check parsing logic or site access.")
            else:
                st.success("✅ Scraping complete!")
                st.dataframe(df)
                st.download_button("📥 Download CSV", df.to_csv(index=False), "clemson_soil_data.csv")

        except Exception as e:
            st.error(f"❌ Error during scraping: {e}")
