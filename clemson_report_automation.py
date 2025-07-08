import requests
from bs4 import BeautifulSoup
import re
import pandas as pd

def scrape_clemson_report(url):
    """
    Scrapes a single Clemson University soil sample report page.

    Args:
        url (str): The URL of the soil sample report.

    Returns:
        dict: A dictionary containing the scraped soil report data.
              Returns None if the request fails.
    """
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL: {e}")
        return None

    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Helper function to safely find and extract text from the soup
    def get_data(label_text):
        element = soup.find('td', string=label_text)
        if element and element.find_next_sibling('td'):
            return element.find_next_sibling('td').get_text(strip=True)
        return "Not Found"

    # Dictionary to store all the scraped data
    data = {
        'Buffer pH': get_data('Buffer pH'),
        'Phosphorus (P)': get_data('Phosphorus (P)'),
        'Potassium (K)': get_data('Potassium (K)'),
        'Calcium (Ca)': get_data('Calcium (Ca)'),
        'Magnesium (Mg)': get_data('Magnesium (Mg)'),
        'Zinc (Zn)': get_data('Zinc (Zn)'),
        'Manganese (Mn)': get_data('Manganese (Mn)'),
        'Copper (Cu)': get_data('Copper (Cu)'),
        'Boron (B)': get_data('Boron (B)'),
        'Sodium (Na)': get_data('Sodium (Na)'),
    }

    # ====================================================================
    # === UPDATED SECTION: Safely scrape CEC value =======================
    # ====================================================================
    # This prevents the 'NoneType' error by checking if the element exists
    # before trying to get text from it. It also uses a more flexible search.
    try:
        cec_label = soup.find('td', string=re.compile(r'Cation Exchange Capacity'))
        if cec_label:
            data['CEC'] = cec_label.find_next('td').get_text(strip=True)
        else:
            data['CEC'] = "Not Found"
    except AttributeError:
        data['CEC'] = "Not Found"
    # ====================================================================
    # === END OF UPDATED SECTION =======================================
    # ====================================================================

    # Robustly scrape Crop and Lime data
    crop_type = "Not Found"
    lime_rate = "Not Found"

    lime_cell = soup.find('td', string=re.compile(r'lbs/1000sq ft'))
    if lime_cell:
        lime_rate = lime_cell.get_text(strip=True)
        parent_row = lime_cell.find_parent('tr')
        if parent_row:
            crop_cell = parent_row.find('td')
            if crop_cell:
                crop_type = crop_cell.get_text(strip=True)
    
    data['Crop Type'] = crop_type
    data['Lime Rate'] = lime_rate

    # --- Extract Comments ---
    comment_426 = soup.find('td', string='426.')
    comment_429 = soup.find('td', string='429.')
    
    data['Comment 426'] = comment_426.find_next_sibling('td').get_text(strip=True) if comment_426 else "Not Found"
    data['Comment 429'] = comment_429.find_next_sibling('td').get_text(strip=True) if comment_429 else "Not Found"

    return data

if __name__ == '__main__':
    # This block is for testing the script directly.
    # It will not run when the function is imported by Streamlit.
    # The error you saw happens when Streamlit runs this function with a real URL.
    # You would need to put a valid report URL here to test it.
    example_url = "https://psaweb.clemson.edu/soils/aspx/standardreport.aspx?key=somekey"
    
    print(f"--- Running Test with Placeholder URL ---\n")
    
    # Since the example_url is a placeholder, this will likely fail or return "Not Found"
    report_data = scrape_clemson_report(example_url)
    
    if report_data:
        for key, value in report_data.items():
            print(f"{key}: {value}")
    else:
        print("\nCould not retrieve data. This is expected when using a placeholder URL.")
