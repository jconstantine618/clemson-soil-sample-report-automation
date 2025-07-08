import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode
import re
import base64
import time

# Function to generate a download link for the DataFrame
def get_table_download_link(df):
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="clemson_soil_report_data.csv">Download CSV file</a>'

# Function to find a value in the soup by its label
def find_value_by_label(soup, label_text):
    try:
        # Find the 'th' or 'td' element containing the label text
        label_element = soup.find(lambda tag: tag.name in ['th', 'td'] and label_text in tag.get_text())
        if label_element:
            # The value is usually in the next 'td' sibling element
            value_element = label_element.find_next_sibling('td')
            if value_element:
                return value_element.text.strip()
    except Exception as e:
        st.warning(f"Could not find value for label '{label_text}': {e}")
    return "N/A"

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

        # Check for duplicates in the DataFrame
        if lab_num and 'LabNum' in existing_df.columns and int(lab_num) in existing_df['LabNum'].values:
            st.warning(f"Skipping duplicate report for LabNum: {lab_num}")
            return None

        # --- EXTRACTING DATA ---
        soil_ph = find_value_by_label(soup, "Soil pH")
        buffer_ph = find_value_by_label(soup, "Buffer pH")
        phosphorus = find_value_by_label(soup, "Phosphorus (P)")
        potassium = find_value_by_label(soup, "Potassium (K)")
        calcium = find_value_by_label(soup, "Calcium (Ca)")
        magnesium = find_value_by_label(soup, "Magnesium (Mg)")
        zinc = find_value_by_label(soup, "Zinc (Zn)")
        manganese = find_value_by_label(soup, "Manganese (Mn)")
        copper = find_value_by_label(soup, "Copper (Cu)")
        boron = find_value_by_label(soup, "Boron (B)")
        sodium = find_value_by_label(soup, "Sodium (Na)")
        sulfur = find_value_by_label(soup, "Sulfur (S)")
        ec = find_value_by_label(soup, "Soluble Salts")
        no3_n = find_value_by_label(soup, "Nitrate Nitrogen")
        om = find_value_by_label(soup, "Organic Matter")
        bulk_density = "N/A" # Assuming Bulk Density is not on the standard report

        # --- CROP TYPE ---
        crop_type = "None"
        recommendations_table = soup.find('table', summary='Recommendations')
        if recommendations_table:
            rows = recommendations_table.find('tbody').find_all('tr')
            # The data is in the second row (index 1), the first row (index 0) is the header.
            if len(rows) > 1:
                # Find all 'td' (table data) elements in the second row
                data_cols = rows[1].find_all('td')
                if len(data_cols) > 0:
                    # The crop type is in the first column (index 0) of that data row
                    crop_type = data_cols[0].text.strip()

        # --- LIME RECOMMENDATION ---
        lime_recommendation = "N/A"
        if recommendations_table:
            rows = recommendations_table.find_all('tr')
            if len(rows) > 1:
                # Lime is in the second column of the second row
                cols = rows[1].find_all('td')
                if len(cols) > 1:
                    lime_recommendation = cols[1].text.strip()
        
        # Create a dictionary with the scraped data
        new_row_data = {
            'LabNum': int(lab_num) if lab_num else None,
            'Soil pH': soil_ph,
            'Buffer pH': buffer_ph,
            'P (lbs/A)': phosphorus,
            'K (lbs/A)': potassium,
            'Ca (lbs/A)': calcium,
            'Mg (lbs/A)': magnesium,
            'Zn (lbs/A)': zinc,
            'Mn (lbs/A)': manganese,
            'Cu (lbs/A)': copper,
            'B (lbs/A)': boron,
            'Na (lbs/A)': sodium,
            'S (lbs/A)': sulfur,
            'EC (mmhos/cm)': ec,
            'NO3-N (ppm)': no3_n,
            'OM (%)': om,
            'Bulk Density (lbs/A)': bulk_density,
            'Crop Type': crop_type,
            'Lime (lbs/1,000 ft² or /A)': lime_recommendation
        }
        return new_row_data

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

# Input URL
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
                
                # Find all hyperlinks that lead to a standardreport.aspx page
                report_links = main_soup.find_all('a', href=lambda href: href and 'standardreport.aspx' in href)

                if not report_links:
                    st.error("No individual report links found on the provided URL. Please check the URL and ensure it leads to a results page with report links.")
                else:
                    st.info(f"Found {len(report_links)} reports to scrape.")
                    
                    all_data = []
                    progress_bar = st.progress(0)

                    # Create a new DataFrame for this scraping session
                    temp_df = st.session_state.scraped_data.copy()

                    for i, link in enumerate(report_links):
                        report_path = link['href']
                        # Construct the full URL
                        full_report_url = f"https://psaweb.clemson.edu/soils/aspx/{report_path}"
                        
                        # Scrape the report
                        report_data = scrape_report(full_report_url, temp_df)
                        
                        if report_data:
                            all_data.append(report_data)
                            # Add new data to the temp_df to check for duplicates within the same run
                            new_df_row = pd.DataFrame([report_data])
                            temp_df = pd.concat([temp_df, new_df_row], ignore_index=True)

                        # Update progress bar
                        progress_bar.progress((i + 1) / len(report_links))
                        time.sleep(0.1) # Small delay to be polite to the server
                    
                    # Convert the list of dictionaries to a DataFrame
                    if all_data:
                        new_data_df = pd.DataFrame(all_data)
                        # Concatenate with existing data in session state
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
    st.dataframe(st.session_state.scraped_data)
    st.markdown(get_table_download_link(st.session_state.scraped_data), unsafe_allow_html=True)
    if st.button("Clear All Data"):
        st.session_state.scraped_data = pd.DataFrame()
        st.session_state.scraping_done = False
        st.rerun()
