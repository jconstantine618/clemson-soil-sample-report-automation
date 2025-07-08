import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import pandas as pd
import re
import os
import time

# Title and description
st.title("🌱 Clemson Soil Report Scraper + Exact Lime")
st.write("Pulls each sample’s **WarmSeasonGrsMaint** (lbs / 1000 ft²) exactly as the lab prints it.")

# Configure the range of lab numbers (or date range) to scrape – adjust these as needed
LABNUM_START = 25050901  # example start Lab #
LABNUM_END   = 25050915  # example end Lab #

if st.button("Start Scraping"):
    # Set up headless Chrome/Chromium options
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    # Specify Chromium binary location (Streamlit Cloud)
    if os.path.exists("/usr/bin/chromium"):
        chrome_options.binary_location = "/usr/bin/chromium"
    elif os.path.exists("/usr/bin/chromium-browser"):
        chrome_options.binary_location = "/usr/bin/chromium-browser"
    # Initialize WebDriver (Chromium + ChromeDriver)
    service = Service("/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(30)
    try:
        with st.spinner("Scraping Clemson lab reports..."):
            # Build the results page URL with the specified range and public user parameters
            results_url = (f"https://psaweb.clemson.edu/soils/aspx/results.aspx?qs=1"
                           f"&LabNumA={LABNUM_START}&LabNumB={LABNUM_END}"
                           f"&DateA=&DateB=&Name=&UserName=AGSRVLB&AdminAuth=0&submit=SEARCH")
            driver.get(results_url)
            # Wait until the results page loads the table (look for the "LabNum" header text)
            WebDriverWait(driver, 15).until(lambda d: "LabNum" in d.page_source)
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            table = soup.find("table")
            if not table:
                st.error("No results found or failed to retrieve the results page.")
                driver.quit()
                st.stop()
            # Identify table columns
            headers = [th.get_text(strip=True) for th in table.find_all("th")]
            try:
                name_idx   = headers.index("Name")
                date_idx   = headers.index("Date Sampled")
                sample_idx = headers.index("Sample No")
                lab_idx    = headers.index("LabNum")
                ph_idx     = headers.index("Soil pH")
                buffer_idx = headers.index("Buffer pH")
            except ValueError:
                st.error("Unexpected table format: expected column headers not found.")
                driver.quit()
                st.stop()
            # Parse each row in the results table
            data = []
            lab_numbers = []  # store lab numbers for later reference
            for row in table.find_all("tr")[1:]:  # skip header row
                cells = row.find_all("td")
                if not cells: 
                    continue
                # Extract fields from cells
                account    = cells[name_idx].get_text(strip=True)
                date_samp  = cells[date_idx].get_text(strip=True)
                sample_no  = cells[sample_idx].get_text(strip=True)
                lab_num    = cells[lab_idx].get_text(strip=True)
                soil_pH    = cells[ph_idx].get_text(strip=True)
                buffer_pH  = cells[buffer_idx].get_text(strip=True)
                # Save the lab number (text) for later clicking
                lab_numbers.append(lab_num)
                # Initialize output row
                data.append({
                    "Account": account,
                    "Sample No": sample_no,
                    "Lab #": lab_num,
                    "Date": date_samp,
                    "Soil pH": soil_pH,
                    "Buffer pH": buffer_pH,
                    "Crop": "",                       # to be filled in
                    "Lime (lbs/1000ft²)": ""          # to be filled in
                })
            # Iterate through each lab report, open it and extract Crop and Lime
            main_window = driver.current_window_handle
            for idx, lab_num in enumerate(lab_numbers):
                try:
                    # Refresh the results page (recommended by Clemson site for each report)
                    if idx > 0:
                        driver.get(results_url)
                        WebDriverWait(driver, 10).until(lambda d: "LabNum" in d.page_source)
                    # Find the link for this lab number and open it in a new tab
                    link_elem = driver.find_element(By.LINK_TEXT, lab_num)
                    lab_href = link_elem.get_attribute("href")
                    driver.execute_script("window.open(arguments[0]);", lab_href)
                    driver.switch_to.window(driver.window_handles[-1])
                    # Wait briefly for the report page to load
                    time.sleep(2)
                    page_html = driver.page_source
                    # If page timed out (session key invalid), refresh main page and retry
                    if "Page Timeout" in page_html or "REFRESH your Results page" in page_html:
                        driver.close()
                        driver.switch_to.window(main_window)
                        driver.refresh()
                        WebDriverWait(driver, 10).until(lambda d: "LabNum" in d.page_source)
                        link_elem = driver.find_element(By.LINK_TEXT, lab_num)
                        lab_href = link_elem.get_attribute("href")
                        driver.execute_script("window.open(arguments[0]);", lab_href)
                        driver.switch_to.window(driver.window_handles[-1])
                        time.sleep(2)
                        page_html = driver.page_source
                    # Parse the standard report page content
                    soup_report = BeautifulSoup(page_html, "html.parser")
                    text = soup_report.get_text(" ", strip=True)
                    # Determine crop type from the Recommendations section text
                    crop_type = "N/A"
                    if "Cool-Season" in text:
                        crop_type = "Cool-Season"
                    elif "Warm-Season" in text:
                        crop_type = "Warm-Season"
                    elif "Centipede" in text:
                        crop_type = "Centipede"
                    # Extract the lime recommendation (lbs/1000ft²) exactly as printed
                    lime_value = "None"
                    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*lb/1000", text)
                    if match:
                        lime_value = match.group(1)  # e.g. "25.0" or "25"
                    elif "no lime" in text.lower():
                        lime_value = "None"
                    # Update the data for this sample
                    data[idx]["Crop"] = crop_type
                    data[idx]["Lime (lbs/1000ft²)"] = lime_value
                except Exception as e:
                    st.warning(f"⚠️ Failed to retrieve report for lab {lab_num}: {e}")
                finally:
                    # Close the report tab if open, and switch back to main results window
                    if len(driver.window_handles) > 1:
                        driver.close()
                    driver.switch_to.window(main_window)
            # All done – convert to DataFrame and display
            df = pd.DataFrame(data)
            driver.quit()  # clean up the browser
            st.success("Done!")
            st.dataframe(df)
            # Provide CSV download
            csv_data = df.to_csv(index=False).encode("utf-8")
            st.download_button("Download CSV", data=csv_data, file_name="soil_reports.csv", mime="text/csv")
    except Exception as ex:
        driver.quit()
        st.error(f"Error during scraping: {ex}")
