import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

# --- App Configuration ---
st.set_page_config(
    page_title="Clemson Soil Report Scraper",
    page_icon="🌿",
    layout="wide",
)

# --- Core Scraping Logic ---

def scrape_individual_report(report_url):
    """Scrapes the 'Crop' type from a single report page."""
    try:
        response = requests.get(report_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # This robust method finds the Lime value, then finds its parent row,
        # and then grabs the first cell in that row, which is the Crop type.
        lime_cell = soup.find('td', string=re.compile(r'lbs/1000sq ft'))
        if lime_cell:
            parent_row = lime_cell.find_parent('tr')
            if parent_row:
                crop_cell = parent_row.find('td')
                if crop_cell:
                    return crop_cell.get_text(strip=True)
    except requests.exceptions.RequestException as e:
        st.warning(f"Could not fetch report {report_url}: {e}")
    except Exception as e:
        st.warning(f"Error parsing report {report_url}: {e}")
    return "Not Found"


def scrape_main_table(url):
    """
    Scrapes the main results table and then scrapes the crop type from each
    individual lab report link.
    """
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        table = soup.find('table')
        if not table:
            st.error("Could not find the main data table on the page.")
            return None

        headers = [th.get_text(strip=True) for th in table.find_all('th')]
        headers.append('Crop') # Add our new column header

        all_rows_data = []
        
        # Find all rows in the table body
        table_rows = table.find('tbody').find_all('tr')
        
        # Set up a progress bar
        progress_bar = st.progress(0, text="Scraping in progress...")

        for i, row in enumerate(table_rows):
            cols = row.find_all('td')
            row_data = [col.get_text(strip=True) for col in cols]
            
            # Find the link in the 'LabNum' column (4th column, index 3)
            lab_num_cell = cols[3]
            link_tag = lab_num_cell.find('a')
            
            crop_type = "Not Found"
            if link_tag and 'href' in link_tag.attrs:
                # Construct the full URL for the individual report
                report_link = urljoin(url, link_tag['href'])
                # Scrape the crop type from that report
                crop_type = scrape_individual_report(report_link)
            
            row_data.append(crop_type)
            all_rows_data.append(row_data)

            # Update the progress bar
            progress_bar.progress((i + 1) / len(table_rows), text=f"Scraping report {i+1} of {len(table_rows)}...")

        progress_bar.empty() # Clear the progress bar
        
        # Create a pandas DataFrame
        df = pd.DataFrame(all_rows_data, columns=headers)
        return df

    except requests.exceptions.RequestException as e:
        st.error(f"Failed to fetch the main URL: {e}")
        return None
    except Exception as e:
        st.error(f"An error occurred while parsing the main table: {e}")
        return None


# --- Streamlit User Interface ---

st.title("🌿 Clemson University Soil Report Scraper")
st.markdown("This tool scrapes all data from a results table and follows each lab number link to retrieve the associated **Crop Type**.")

url_to_scrape = st.text_input(
    "Enter Results URL",
    "https://psaweb.clemson.edu/soils/aspx/results.aspx?qs=1&LabNumA=25050901&LabNumB=25050930&DateA=&DateB=&Name=&UserName=AGSRVLB&AdminAuth=0&submit=SEARCH"
)

if st.button("Start Scraping", type="primary"):
    if url_to_scrape:
        scraped_df = scrape_main_table(url_to_scrape)
        
        if scraped_df is not None:
            # Store the result in session state to persist it
            st.session_state['scraped_data'] = scraped_df
    else:
        st.warning("Please enter a URL.")


# Display the DataFrame and download button if data exists in session state
if 'scraped_data' in st.session_state:
    st.subheader("Combined Soil Report Data")
    
    df_to_display = st.session_state['scraped_data']
    st.dataframe(df_to_display)
    
    csv = df_to_display.to_csv(index=False).encode('utf-8')
    
    st.download_button(
        label="📥 Download data as CSV",
        data=csv,
        file_name='clemson_soil_reports.csv',
        mime='text/csv',
    )
