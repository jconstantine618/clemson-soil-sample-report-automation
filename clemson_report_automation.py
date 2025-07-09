from __future__ import annotations

import io
import re
import time
from typing import List, Dict

import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

###############################################################################
# ---------- Selenium helpers -------------------------------------------------
###############################################################################

def _init_driver() -> webdriver.Chrome:
    """Return a headless Chrome driver configured for Streamlit Cloud."""
    chrome_opts = Options()
    chrome_opts.add_argument("--headless=new")  # Chrome 109+ headless mode
    chrome_opts.add_argument("--no-sandbox")
    chrome_opts.add_argument("--disable-dev-shm-usage")
    chrome_opts.add_argument("--disable-gpu")
    # Reduce resource use
    chrome_opts.add_argument("--window-size=1200,800")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_opts)

###############################################################################
# ---------- Core scraping routines ------------------------------------------
###############################################################################

NUTRIENT_KEYS = [
    "P", "K", "Ca", "Mg", "Zn", "Mn", "Cu", "B", "Na", "S", "EC", "NO3-N", "OM",
    "Bulk Density",
]

# Regex patterns pre‑compiled for speed
_RX_LIME  = re.compile(r"^Lime\s+(.+)", re.I | re.M)
_RX_CROP  = re.compile(r"^Crop\s+(.+)", re.I | re.M)
_RX_ELEM  = {
    key: re.compile(fr"^{key}.*?(\d+\.?\d*)", re.I | re.M) for key in NUTRIENT_KEYS
}


def _extract_report_fields(html: str) -> Dict[str, str]:
    """Parse a single *standardreport.aspx* page and return the target fields."""
    soup = BeautifulSoup(html, "html.parser")

    # ---------- easy keys: Lab #, Sample No, Date, pH values ----------------
    banner = soup.find(string=re.compile(r"Sample Id", re.I))
    labnum = soil_ph = buffer_ph = date_sampled = sample_no = ""
    if banner and banner.parent:
        # banner.row looks like "Sample Id: 10772SHULT   Soil Code: 4"
        maybe = banner.parent.text
        m = re.search(r"Sample Id:\s*(\w+)", maybe)
        if m:
            sample_no = m.group(1)
        m = re.search(r"LabNum:\s*(\d+)", html)
        if m:
            labnum = m.group(1)
    # pH values
    ph_match = re.search(r"Soil pH\s+(\d+\.\d+).*?Buffer pH\s+(\d+\.\d+)", html, re.S)
    if ph_match:
        soil_ph, buffer_ph = ph_match.group(1), ph_match.group(2)
    # date (use first mm/dd/yyyy on page)
    dt_match = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", html)
    if dt_match:
        date_sampled = dt_match.group(1)

    # ---------- crop & lime --------------------------------------------------
    body_text = soup.get_text("\n")
    crop_type = _RX_CROP.search(body_text)
    crop_type = crop_type.group(1).strip() if crop_type else ""

    lime = _RX_LIME.search(body_text)
    lime_val = lime.group(1).strip() if lime else "N/A"

    # ---------- nutrients ----------------------------------------------------
    nutrients = {}
    for key, rx in _RX_ELEM.items():
        m = rx.search(body_text)
        nutrients[key] = m.group(1) if m else "N/A"

    # ---------- account number from sample no (digits only) -----------------
    account = re.sub(r"\D", "", sample_no) if sample_no else ""

    return {
        "Account": account,
        "Sample No": sample_no,
        "Lab #": labnum,
        "Date": date_sampled,
        "Soil pH": soil_ph,
        "Buffer pH": buffer_ph,
        **{f"{k} (lbs/A)" if k in ["P", "K", "Ca", "Mg", "Zn", "Mn", "Cu", "B", "Na", "S"] else k: v for k, v in nutrients.items()},
        "Crop Type": crop_type,
        "Lime (lbs/1000 ft² or /A)": lime_val,
    }


def _collect_lab_links(driver: webdriver.Chrome, url: str) -> List[str]:
    """Return a list of *standardreport.aspx?id=...* URLs for each Lab # in a
    *results.aspx* page. If the user supplies a *standardreport* URL already,
    just return that.
    """
    if "standardreport.aspx" in url:
        return [url]

    driver.get(url)
    time.sleep(2)
    links = driver.find_elements("css selector", "a[href*='standardreport.aspx?id']")
    return [link.get_attribute("href") for link in links]

###############################################################################
# ---------- Streamlit interface --------------------------------------------
###############################################################################

def main():
    st.title("Clemson Soil Report Scraper – Full Data + Crop + Lime")
    st.markdown("Paste any **results.aspx** URL or a single **standardreport.aspx?id=...** link, click **Start Scraping**, and download the consolidated CSV.")

    url = st.text_input(
        "Results page URL",
        "https://psaweb.clemson.edu/soils/aspx/results.aspx?qs=1&LabNumA=25050901&LabNumB=25050930&DateA=&DateB=&Name=&UserName=AGSRVLB&AdminAuth=0&submit=SEARCH",
        placeholder="https://psaweb.clemson.edu/...",
    )

    if st.button("Start Scraping") and url:
        records = []
        try:
            driver = _init_driver()
        except WebDriverException as e:
            st.error(f"Failed to launch headless Chrome – {e}")
            st.stop()

        try:
            lab_urls = _collect_lab_links(driver, url)
            progress = st.progress(0, text=f"Fetched report 0/{len(lab_urls)}")
            for idx, lab_url in enumerate(lab_urls, 1):
                driver.get(lab_url)
                time.sleep(1.5)  # quick wait for render
                data = _extract_report_fields(driver.page_source)
                records.append(data)
                progress.progress(idx / len(lab_urls), text=f"Fetched report {idx}/{len(lab_urls)}")
            progress.empty()
        finally:
            driver.quit()

        if records:
            df = pd.DataFrame(records)
            st.success("Extraction complete! 🎉")
            st.dataframe(df, use_container_width=True)
            # download
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("Download CSV", csv, "clemson_soil_reports.csv", "text/csv")
        else:
            st.warning("No data extracted – check the URL and try again.")


if __name__ == "__main__":
    main()
