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
    
    # --- Data Extraction ---
    # Helper function to safely find and extract text from the soup
    def get_data(label_text):
        element = soup.find('td', string=label_text)
        if element and element.find_next_sibling('td'):
            # The value is usually in the next 'td' element
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
        'CEC': soup.find('td', string='Cation Exchange Capacity(CEC)').find_next('td').get_text(strip=True),
    }

    # ====================================================================
    # === UPDATED SECTION: Robustly scrape Crop and Lime data ==========
    # ====================================================================
    # This new method finds the lime value first, then uses its position
    # to reliably locate the crop type.

    crop_type = "Not Found"
    lime_rate = "Not Found"

    # 1. Find the table cell containing the "Lime" recommendation using a regex pattern.
    lime_cell = soup.find('td', string=re.compile(r'lbs/1000sq ft'))

    # 2. If the lime cell is found, navigate from it.
    if lime_cell:
        lime_rate = lime_cell.get_text(strip=True)
        
        # 3. Find the parent table row (<tr>) of the lime cell.
        parent_row = lime_cell.find_parent('tr')
        
        if parent_row:
            # 4. Find the first table cell (<td>) in that row, which is the crop type.
            crop_cell = parent_row.find('td')
            if crop_cell:
                crop_type = crop_cell.get_text(strip=True)
    
    # Add the found values to our data dictionary
    data['Crop Type'] = crop_type
    data['Lime Rate'] = lime_rate
    # ====================================================================
    # === END OF UPDATED SECTION =======================================
    # ====================================================================

    # --- Extract Comments ---
    comment_426 = soup.find('td', string='426.')
    comment_429 = soup.find('td', string='429.')
    
    data['Comment 426'] = comment_426.find_next_sibling('td').get_text(strip=True) if comment_426 else "Not Found"
    data['Comment 429'] = comment_429.find_next_sibling('td').get_text(strip=True) if comment_429 else "Not Found"

    return data

if __name__ == '__main__':
    # Example usage with a sample URL.
    # Replace this with the actual URL from your app's input.
    # NOTE: This is a placeholder URL and will not work.
    example_url = "https://psaweb.clemson.edu/soils/aspx/standardreport.aspx?key=somekey"
    
    print(f"Scraping report from: {example_url}\n")
    
    report_data = scrape_clemson_report(example_url)
    
    if report_data:
        # Print the data in a readable format
        for key, value in report_data.items():
            print(f"{key}: {value}")
