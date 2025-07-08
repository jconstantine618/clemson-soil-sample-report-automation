import streamlit as st
import pandas as pd
import time
import base64
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs

# --- Selenium Imports ---
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType


# --- Selenium WebDriver Setup for Streamlit Cloud ---
@st.cache_resource
def get_driver():
    """Initializes and returns a Selenium WebDriver instance."""
    options = Options()
    options.add_argument("--disable-gpu")
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    service = ChromeService(
        ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()
    )
    return webdriver.Chrome(service=service, options=options)


# --- Data Parsing Functions ---
def get_analysis_data(table):
    """Parses the main analysis results table."""
    data = {}
    if not table: return data
    try:
        for row in table.find('tbody').find_all('tr'):
            header = row.find('th')
            if header:
                label = header.text.strip()
                value_cell = header.find_next_sibling('td')
                if value_cell:
                    if "Soil pH" in label: data['Soil pH'] = value_cell.text.strip()
                    elif "Buffer pH" in label: data['Buffer pH'] = value_cell.text.strip()
                    elif "Phosphorus (P)" in label: data['P (lbs/A)'] = value_cell.text.strip()
                    elif "Potassium (K)" in label: data['K (lbs/A)'] = value_cell.text.strip()
                    elif "Calcium (Ca)" in label: data['Ca (lbs/A)'] = value_cell.text.strip()
                    elif "Magnesium (Mg)" in label: data['Mg (lbs/A)'] = value_cell.text.strip()
                    elif "Zinc (Zn)" in label: data['Zn (lbs/A)'] = value_cell.text.strip()
                    elif "Manganese (Mn)" in label: data['Mn (lbs/A)'] = value_cell.text.strip()
                    elif "Copper (Cu)" in label: data['Cu (lbs/A)'] = value_cell.text.strip()
                    elif "Boron (B)" in label: data['B (lbs/A)'] = value_cell.text.strip()
                    elif "Sodium (Na)" in label: data['Na (lbs/A)'] = value_cell.text.strip()
                    elif "Sulfur (S)" in label: data['S (lbs/A)'] = value_cell.text.strip()
                    elif "Soluble Salts" in label: data['EC (mmhos/cm)'] = value_cell.text.strip()
                    elif "Nitrate Nitrogen" in label: data['NO3-N (ppm)'] = value_cell.text.strip()
                    elif "Organic Matter" in label: data['OM (%)'] = value_cell.text.strip()
    except Exception as e:
        st.warning(f"Could not parse analysis table: {e}")
    return data

def get_recommendation_data(table):
    """Parses the recommendations table for Crop Type and Lime."""
    crop_type, lime = "None", "N/A"
    if table:
        try:
            rec_rows = table.find('tbody').find_all('tr')
            if len(rec_rows) > 1:
                rec_cols = rec_rows[1].find_all('td')
                if len(rec_cols) > 0: crop_type = rec_cols[0].text.strip()
                if len(rec_cols) > 1: lime = rec_cols[1].text.strip()
        except Exception as e:
            st.warning(f"Could not parse recommendations table: {e}")
    return crop_type, lime

# --- Main Scraping Function (using Requests)---
def scrape_report_with_requests(session, url):
    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        parsed_url = urlparse(url)
        lab_num = parse_qs(parsed_url.query).get('id', [None])[0]

        analysis_table = soup.find('table', id='tblAnalysis')
        recommendations_table = soup.find('table', summary='Recommendations')

        report_data = get_analysis_data(analysis_table)
        report_data['LabNum'] = int(lab_num) if lab_num else None
        
        crop_type, lime = get_recommendation_data(recommendations_table)
        report_data['Crop Type'] = crop_type
        report_data['Lime (lbs/1,000 ft² or /A)'] = lime
        
        all_columns = [
            'LabNum', 'Soil pH', 'Buffer pH', 'P (lbs/A)', 'K (lbs/A)', 'Ca (lbs/A)',
            'Mg (lbs/A)', 'Zn (lbs/A)', 'Mn (lbs/A)', 'Cu (lbs/A)', 'B (lbs/A)',
            'Na (lbs/A)', 'S (lbs/A)', 'EC (mmhos/cm)', 'NO3-N (ppm)', 'OM (%)',
            'Bulk Density (lbs/A)', 'Crop Type', 'Lime (lbs/1,000 ft² or /A)'
        ]
        return {col: report_data.get(col, 'N/A') for col in all_columns}

    except Exception as e:
        st.error(f"Failed to scrape {url} with requests: {e}")
        return None

# --- Helper for CSV Download ---
def get_table_download_link(df):
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="clemson_soil_data.csv">Download CSV file</a>'

# --- Streamlit App UI ---
st.set_page_config(layout="wide", page_title="Clemson Soil Report Scraper")
st.title("🌱 Clemson Soil Report Scraper")
st.write("Paste a Clemson results URL, click **Start Scraping**, and get your data.")

if 'scraped_data' not in st.session_state:
    st.session_state.scraped_data = pd.DataFrame()

results_page_url = st.text_input("Results page URL", "https://psaweb.clemson.edu/soils/aspx/results.aspx?qs=1&LabNumA=25050901&LabNumB=25050930&DateA=&DateB=&Name=&UserName=AGSRVLB&AdminAuth=0&submit=SEARCH")

if st.button("Start Scraping", key='start_scraping'):
    if not results_page_url:
        st.warning("Please enter a URL.")
    else:
        all_data = []
        progress_bar = st.progress(0, text="Initializing...")
        
        try:
            # STEP 1: Use Selenium to get a valid session and cookies
            with st.spinner('Initializing browser to establish a session...'):
                driver = get_driver()
                driver.get(results_page_url)
                # Wait for links to appear to ensure the session is active
                WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.PARTIAL_LINK_TEXT, "View Report")))
                
                # Get links and cookies from the driver
                main_soup = BeautifulSoup(driver.page_source, "html.parser")
                report_links = [a['href'] for a in main_soup.find_all('a', href=lambda h: h and 'standardreport.aspx' in h)]
                selenium_cookies = driver.get_cookies()

            if not report_links:
                st.error("No report links found. Please check the URL.")
            else:
                st.info(f"Found {len(report_links)} reports. Now fetching with a lightweight client...")
                
                # STEP 2: Use a lightweight Requests session with the cookies for the actual scraping
                req_session = requests.Session()
                # Transfer cookies from Selenium to Requests
                for cookie in selenium_cookies:
                    req_session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])
                # Add a browser-like User-Agent
                req_session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"})

                existing_labs = set(st.session_state.scraped_data['LabNum']) if 'LabNum' in st.session_state.scraped_data.columns else set()

                for i, link_path in enumerate(report_links):
                    full_report_url = f"https://psaweb.clemson.edu/soils/aspx/{link_path}"
                    lab_num_str = parse_qs(urlparse(full_report_url).query).get('id', [None])[0]
                    
                    if lab_num_str and int(lab_num_str) in existing_labs:
                        st.write(f"Skipping already scraped LabNum: {lab_num_str}")
                    else:
                        report_data = scrape_report_with_requests(req_session, full_report_url)
                        if report_data:
                            all_data.append(report_data)
                    
                    progress_bar.progress((i + 1) / len(report_links), text=f"Fetched report {i+1}/{len(report_links)}")
                
                if all_data:
                    new_df = pd.DataFrame(all_data)
                    st.session_state.scraped_data = pd.concat([st.session_state.scraped_data, new_df], ignore_index=True).drop_duplicates(subset=['LabNum']).sort_values(by='LabNum').reset_index(drop=True)
                
                st.success("Extraction complete! 🎉")

        except Exception as e:
            st.error(f"A critical error occurred: {e}")

if not st.session_state.scraped_data.empty:
    st.markdown("---")
    st.subheader("Scraped Data")
    st.dataframe(st.session_state.scraped_data)
    st.markdown(get_table_download_link(st.session_state.scraped_data), unsafe_allow_html=True)
    if st.button("Clear All Data"):
        st.session_state.scraped_data = pd.DataFrame()
        st.rerun()
