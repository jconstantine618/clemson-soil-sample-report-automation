import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

base_url = "https://psaweb.clemson.edu"
main_url = base_url + "/soils/aspx/results.aspx?qs=1&LabNumA=25050901&LabNumB=25050930&DateA=&DateB=&Name=&UserName=AGSRVLB&AdminAuth=0&submit=SEARCH"

headers = {
    "User-Agent": "Mozilla/5.0"
}

# Step 1: Scrape main page for lab report links
main_response = requests.get(main_url, headers=headers)
soup = BeautifulSoup(main_response.text, "html.parser")

lab_links = []
for a in soup.find_all('a', href=True):
    if "standardreport.aspx" in a['href']:
        full_url = base_url + a['href']
        lab_links.append((a.text.strip(), full_url))  # (LabNum, URL)

print(f"Found {len(lab_links)} lab reports.")

# Step 2: Visit each report and extract WarmSeasonGrsMaint
records = []
for labnum, url in lab_links:
    try:
        r = requests.get(url, headers=headers)
        rsoup = BeautifulSoup(r.text, "html.parser")

        # Search for WarmSeasonGrsMaint and the associated lbs value
        text_blocks = rsoup.find_all(text=True)
        warm_season_value = ""
        for i, t in enumerate(text_blocks):
            if "WarmSeasonGrsMaint" in t:
                for j in range(i, i + 5):
                    if "lbs/1000sq ft" in text_blocks[j]:
                        warm_season_value = text_blocks[j].strip()
                        break
                break

        records.append({
            "Lab Number": labnum,
            "Report URL": url,
            "WarmSeasonGrsMaint": warm_season_value
        })
        time.sleep(0.5)  # Be polite
    except Exception as e:
        print(f"Error on {url}: {e}")

# Step 3: Save to CSV
df = pd.DataFrame(records)
df.to_csv("clemson_soil_reports.csv", index=False)
print("Data saved to clemson_soil_reports.csv")
