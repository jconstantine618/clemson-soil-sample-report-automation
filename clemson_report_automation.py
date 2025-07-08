import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
import base64
import time

# Function to generate a download link for the DataFrame
def get_table_download_link(df):
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="clemson_soil_report_data.csv">Download CSV file</a>'

# A more robust function to find a value within the main analysis table
def get_analysis_data(table):
    data = {}
    if not table:
        return data
    try:
        # Iterate over each row in the table body
        for row in table.find('tbody').find_all('tr'):
            header = row.find('th')
            if header:
                label = header.text.strip()
                value_cell = header.find_next_sibling('td')
                if value_cell:
                    # Map the label found on the page to the column name we want
                    if "Soil pH" in label:
                        data['Soil pH'] = value_cell.text.strip()
                    elif "Buffer pH" in label:
                        data['Buffer pH'] = value_cell.text.strip()
                    elif "Phosphorus (P)" in label:
                        data['P (lbs/A)'] = value_cell.text.strip()
                    elif "Potassium (K)" in label:
                        data['K (lbs/A)'] = value_cell.text.strip()
                    elif "Calcium (Ca)" in label:
                        data['Ca (lbs/A)'] = value_cell.text.strip()
                    elif "Magnesium (Mg)" in label:
                        data['Mg (lbs/A)'] = value_cell.text.strip()
                    elif "Zinc (Zn)" in label:
                        data['Zn (lbs/A)'] = value_cell.text.strip()
                    elif "Manganese (Mn)" in label:
                        data['Mn (lbs/A)'] = value_cell.text.strip()
                    elif "Copper (Cu)" in label:
                        data['Cu (lbs/A)'] = value_cell.text.strip()
                    elif "Boron (B)" in label:
                        data['B (lbs/A)'] = value_cell.text.strip()
                    elif "Sodium (Na)" in label:
                        data['Na (lbs/A)'] = value_cell.text.strip()
                    elif "Sulfur (S)" in label:
                        data['S (lbs/A)'] = value_cell.text.strip()
                    elif "Soluble Salts" in label:
                        data['EC (mmhos/cm)'] = value_cell.text.strip()
                    elif "Nitrate Nitrogen" in label:
                        data['NO3-N (ppm)'] = value_cell.text.strip()
                    elif "Organic Matter" in label:
                        data['OM (%)'] = value_cell.text.strip()
    except Exception as e:
        st.warning(f"Could not parse analysis table: {e}")
    return data

# Function to scrape a single report
def scrape_report(url, existing_df):
    try:
        page = requests.get(url, timeout=10)
        page.raise_for_status()
        soup = BeautifulSoup(page.content, "html.parser")

        # Extract LabNum from URL to check for duplicates
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        lab_num = query_params.get('id', [None])[0]

        if lab_num and 'LabNum' in existing_df.columns and int(lab_num) in existing_df['LabNum'].values:
            st.warning(f"Skipping duplicate report for LabNum: {lab_num}")
            return None

        # --- Isolate Tables ---
        analysis_table = soup.find('table', id='tblAnalysis')
        recommendations_table = soup.find('table', summary='Recommendations')

        # --- EXTRACT DATA ---
        report_data = get_analysis_data(analysis_table)
        report_data['LabNum'] = int(lab_num) if lab_num else None

        # --- CROP TYPE & LIME ---
        crop_type = "None"
        lime_recommendation = "N/A"
        if recommendations_table:
            rec_rows = recommendations_table.find('tbody').find_all('tr')
            # Data is in the second row (index 1)
            if len(rec_rows) > 1:
                rec_cols = rec_rows[1].find_all('td')
                # Crop Type is in the first column
                if len(rec_cols) > 0:
                    crop_type = rec_cols[0].text.strip()
                # Lime is in the second column
                if len(rec_cols) > 1:
                    lime_recommendation = rec_cols[1].text.strip()

        report_data['Crop Type'] = crop_type
        report_data['Lime (lbs/1,000 ft² or /A)'] = lime_recommendation
        report_data['Bulk Density (lbs/A)'] = "N/A" # Not on standard report

        # Define all expected columns to ensure consistent DataFrame structure
        all_columns = [
            'LabNum', 'Soil pH', 'Buffer pH', 'P (lbs/A)', 'K (lbs/A)', 'Ca (lbs/A)',
            'Mg (lbs/A)', 'Zn (lbs/A)', 'Mn (lbs/A)', 'Cu (lbs/A)', 'B (lbs/A)',
            'Na (lbs/A)', 'S (lbs/A)', 'EC (mmhos/cm)', 'NO3-N (ppm)', 'OM (%)',
            'Bulk Density (lbs/A)', 'Crop Type', 'Lime (lbs/1,000 ft² or /A)'
        ]
        
        # Ensure all columns are present, filling missing ones with N/A
        final_data = {col: report_data.get(col, 'N/A') for col in all_columns}
        
        return final_data

    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching URL {url}: {e}")
        return None
    except Exception as e:
        st.error(f"An error occurred while scraping {url}: {e}")
        return None

# Streamlit App
st.set_page_config(layout="wide", page_title="Clemson Soil Report Scraper")

st.title("🌱 Clemson Soil Report Scraper – Full Data + Crop Type")
st.write("Paste any Clemson results.aspx URL (with your LabNum range or date range), click **Start Scraping**, and get a CSV with full soil data plus the Crop type and the lab's lime recommendation.")

# Initialize or clear session state
if 'scraped_data' not in st.session_state:
    st.session_state.scraped_data = pd.DataFrame()

if 'scraping_done' not in st.session_state:
    st.session_state.scraping_done = False

results_page_url = st.text_input("Results page URL", "https://psaweb.clemson.edu/soils/aspx/results.aspx?qs=1&LabNumA=25050901&LabNumB=25050930&DateA=&DateB=&Name=&UserName=AGSRVLB&AdminAuth=0&submit=SEARCH")

if st.button("Start Scraping", key='start_scraping'):
    if not results_page_url:
        st.warning("Please enter a URL.")
    else:
        with st.spinner('Scraping in progress... Please wait.'):
            try:
                main_page = requests.get(results_page_url, timeout=10)
                main_page.raise_for_status()
                main_soup = BeautifulSoup(main_page.content, "html.parser")
                
                report_links = main_soup.find_all('a', href=lambda href: href and 'standardreport.aspx' in href)

                if not report_links:
                    st.error("No individual report links found on the provided URL. Please check the URL and ensure it leads to a results page with report links.")
                else:
                    st.info(f"Found {len(report_links)} reports to scrape.")
                    
                    all_data = []
                    progress_bar = st.progress(0)

                    temp_df = st.session_state.scraped_data.copy()

                    for i, link in enumerate(report_links):
                        report_path = link['href']
                        full_report_url = f"https://psaweb.clemson.edu/soils/aspx/{report_path}"
                        
                        report_data = scrape_report(full_report_url, temp_df)
                        
                        if report_data:
                            all_data.append(report_data)
                            new_df_row = pd.DataFrame([report_data])
                            temp_df = pd.concat([temp_df, new_df_row], ignore_index=True)

                        progress_bar.progress((i + 1) / len(report_links))
                        time.sleep(0.1)
                    
                    if all_data:
                        new_data_df = pd.DataFrame(all_data)
                        st.session_state.scraped_data = pd.concat([st.session_state.scraped_data, new_data_df], ignore_index=True).drop_duplicates(subset=['LabNum']).sort_values(by='LabNum').reset_index(drop=True)

                    st.session_state.scraping_done = True
            
            except requests.exceptions.RequestException as e:
                st.error(f"Failed to access the results URL: {e}")
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")

if st.session_state.scraping_done:
    st.success("Extraction complete!")

if not st.session_state.scraped_data.empty:
    st.markdown("---")
    st.subheader("Scraped Data")
    # Ensure column order is correct for display
    display_columns = [
        'LabNum', 'Soil pH', 'Buffer pH', 'P (lbs/A)', 'K (lbs/A)', 'Ca (lbs/A)',
        'Mg (lbs/A)', 'Zn (lbs/A)', 'Mn (lbs/A)', 'Cu (lbs/A)', 'B (lbs/A)',
        'Na (lbs/A)', 'S (lbs/A)', 'EC (mmhos/cm)', 'NO3-N (ppm)', 'OM (%)',
        'Bulk Density (lbs/A)', 'Crop Type', 'Lime (lbs/1,000 ft² or /A)'
    ]
    st.dataframe(st.session_state.scraped_data[display_columns])
    st.markdown(get_table_download_link(st.session_state.scraped_data), unsafe_allow_html=True)
    if st.button("Clear All Data"):
        st.session_state.scraped_data = pd.DataFrame()
        st.session_state.scraping_done = False
        st.rerun()
