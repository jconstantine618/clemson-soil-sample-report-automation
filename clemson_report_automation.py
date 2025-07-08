import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
import base64
import time

# --- Selenium Imports ---
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
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
    
    # This will automatically download and manage the correct chromedriver
    # for the version of Chromium installed in the Streamlit Cloud environment.
    service = ChromeService(
        ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()
    )
    return webdriver.Chrome(service=service, options=options)


# A robust function to find a value within the main analysis table
def get_analysis_data(table):
    data = {}
    if not table:
        return data
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

# Function to scrape a single report using Selenium
def scrape_report_with_selenium(driver, url, existing_df):
    try:
        # Use the driver to get the page
        driver.get(url)
        # It's good practice to wait a bit for any dynamic content, though it may not be needed here
        time.sleep(1) 
        
        # Get page source and parse with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, "html.parser")

        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        lab_num = query_params.get('id', [None])[0]

        if lab_num and 'LabNum' in existing_df.columns and int(lab_num) in existing_df['LabNum'].values:
            st.warning(f"Skipping duplicate report for LabNum: {lab_num}")
            return None

        analysis_table = soup.find('table', id='tblAnalysis')
        recommendations_table = soup.find('table', summary='Recommendations')

        report_data = get_analysis_data(analysis_table)
        report_data['LabNum'] = int(lab_num) if lab_num else None

        crop_type = "None"
        lime_recommendation = "N/A"
        if recommendations_table:
            rec_rows = recommendations_table.find('tbody').find_all('tr')
            if len(rec_rows) > 1:
                rec_cols = rec_rows[1].find_all('td')
                if len(rec_cols) > 0: crop_type = rec_cols[0].text.strip()
                if len(rec_cols) > 1: lime_recommendation = rec_cols[1].text.strip()

        report_data['Crop Type'] = crop_type
        report_data['Lime (lbs/1,000 ft² or /A)'] = lime_recommendation
        report_data['Bulk Density (lbs/A)'] = "N/A"

        all_columns = [
            'LabNum', 'Soil pH', 'Buffer pH', 'P (lbs/A)', 'K (lbs/A)', 'Ca (lbs/A)',
            'Mg (lbs/A)', 'Zn (lbs/A)', 'Mn (lbs/A)', 'Cu (lbs/A)', 'B (lbs/A)',
            'Na (lbs/A)', 'S (lbs/A)', 'EC (mmhos/cm)', 'NO3-N (ppm)', 'OM (%)',
            'Bulk Density (lbs/A)', 'Crop Type', 'Lime (lbs/1,000 ft² or /A)'
        ]
        
        return {col: report_data.get(col, 'N/A') for col in all_columns}

    except Exception as e:
        st.error(f"An error occurred while scraping {url}: {e}")
        return None

# Function to generate a download link for the DataFrame
def get_table_download_link(df):
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="clemson_soil_report_data.csv">Download CSV file</a>'


# --- Streamlit App ---
st.set_page_config(layout="wide", page_title="Clemson Soil Report Scraper")
st.title("🌱 Clemson Soil Report Scraper – Full Data + Crop Type")
st.write("Paste any Clemson results.aspx URL, click **Start Scraping**, and get a CSV with full soil data.")

if 'scraped_data' not in st.session_state:
    st.session_state.scraped_data = pd.DataFrame()

results_page_url = st.text_input("Results page URL", "https://psaweb.clemson.edu/soils/aspx/results.aspx?qs=1&LabNumA=25050901&LabNumB=25050930&DateA=&DateB=&Name=&UserName=AGSRVLB&AdminAuth=0&submit=SEARCH")

if st.button("Start Scraping", key='start_scraping'):
    if not results_page_url:
        st.warning("Please enter a URL.")
    else:
        with st.spinner('Initializing browser and starting scrape... This may take a moment.'):
            driver = get_driver()
            try:
                # First, get the main page to find the links
                driver.get(results_page_url)
                time.sleep(1) # Wait for page to load
                main_soup = BeautifulSoup(driver.page_source, "html.parser")
                
                report_links = main_soup.find_all('a', href=lambda href: href and 'standardreport.aspx' in href)

                if not report_links:
                    st.error("No individual report links found. The server may have blocked the request or the URL is incorrect.")
                else:
                    st.info(f"Found {len(report_links)} reports to scrape.")
                    all_data = []
                    progress_bar = st.progress(0, text="Scraping reports...")
                    temp_df = st.session_state.scraped_data.copy()

                    for i, link in enumerate(report_links):
                        report_path = link['href']
                        full_report_url = f"https://psaweb.clemson.edu/soils/aspx/{report_path}"
                        
                        report_data = scrape_report_with_selenium(driver, full_report_url, temp_df)
                        
                        if report_data:
                            all_data.append(report_data)
                            new_df_row = pd.DataFrame([report_data])
                            temp_df = pd.concat([temp_df, new_df_row], ignore_index=True)

                        progress_bar.progress((i + 1) / len(report_links), text=f"Scraping report {i+1}/{len(report_links)}")
                    
                    if all_data:
                        new_data_df = pd.DataFrame(all_data)
                        st.session_state.scraped_data = pd.concat([st.session_state.scraped_data, new_data_df], ignore_index=True).drop_duplicates(subset=['LabNum']).sort_values(by='LabNum').reset_index(drop=True)
                    
                    st.success("Extraction complete!")

            except Exception as e:
                st.error(f"A critical error occurred: {e}")
            finally:
                # It's good practice to close the driver, but st.cache_resource manages this.
                # If not using cache_resource, you would call driver.quit() here.
                pass

if not st.session_state.scraped_data.empty:
    st.markdown("---")
    st.subheader("Scraped Data")
    display_columns = [
        'LabNum', 'Soil pH', 'Buffer pH', 'P (lbs/A)', 'K (lbs/A)', 'Ca (lbs/A)',
        'Mg (lbs/A)', 'Zn (lbs/A)', 'Mn (lbs/A)', 'Cu (lbs/A)', 'B (lbs/A)',
        'Na (lbs/A)', 'S (lbs/A)', 'EC (mmhos/cm)', 'NO3-N (ppm)', 'OM (%)',
        'Bulk Density (lbs/A)', 'Crop Type', 'Lime (lbs/1,000 ft² or /A)'
    ]
    # Ensure all columns exist before trying to display them
    display_df = st.session_state.scraped_data.copy()
    for col in display_columns:
        if col not in display_df.columns:
            display_df[col] = "N/A"
            
    st.dataframe(display_df[display_columns])
    st.markdown(get_table_download_link(display_df), unsafe_allow_html=True)
    if st.button("Clear All Data"):
        st.session_state.scraped_data = pd.DataFrame()
        st.rerun()
