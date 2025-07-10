import streamlit as st
import requests
import re
import time
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs, urlencode

# --- Page Configuration ---
st.set_page_config(page_title="Clemson Soil Scraper – Full Data + Crop", layout="wide")

# --- App Title and Description ---
st.title("🌱 Clemson Soil Report Scraper – Full Data + Crop Type")
st.markdown(
    "Paste any Clemson **results.aspx** URL (with your LabNum range or date range), "
    "click **Start Scraping**, and get a CSV with full soil data. Then, you can optionally "
    "run a second, more detailed scan to find specific crop types."
)

# --- User Input ---
results_url = st.text_input(
    "Results page URL",
    "https://psaweb.clemson.edu/soils/aspx/results.aspx?"
    "qs=1&LabNumA=25050901&LabNumB=25050930&DateA=&DateB=&Name=&"
    "UserName=AGSRVLB&AdminAuth=0&submit=SEARCH",
    key="results_url_input" 
)

# --- Helper Functions ---

def txt_url_from_href(base_results_url: str, href: str) -> str:
    """
    Constructs the full URL for the report page.
    The '&format=txt' parameter returns HTML, not text, so we'll parse it.
    """
    full = urljoin(base_results_url, href)
    parsed = urlparse(full)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    # The page still returns HTML even with this, but we'll keep it for consistency
    qs["format"] = ["txt"] 
    new_query = urlencode(qs, doseq=True)
    return parsed._replace(query=new_query).geturl()

def extract_data_from_report_html(soup: BeautifulSoup):
    """
    Extracts the general crop type and lime recommendation from the parsed HTML of a report page.
    """
    crop = "None"
    lime = "None"
    
    try:
        # Find the 'Crop' label and get the text from the next bold tag, which is the crop name
        crop_label = soup.find(lambda tag: tag.name == 'td' and 'Crop' in tag.get_text())
        if crop_label:
            # The crop name is in a <b> tag in the next table cell
            crop_tag = crop_label.find_next('td').find('b')
            if crop_tag:
                crop = crop_tag.get_text(strip=True)
    except Exception:
        pass # If we can't find it, it remains "None"

    try:
        # Lime value is typically in a <b> tag next to the crop name
        lime_text_raw = soup.find(text=re.compile(r'lbs/1000sq ft'))
        if lime_text_raw:
            lime_match = re.search(r"([0-9]+(?:\.[0-9]+)?)", lime_text_raw)
            if lime_match:
                lime = lime_match.group(1)
        elif soup.find(text=re.compile(r'no lime', re.IGNORECASE)):
            lime = "None"
    except Exception:
        pass # If we can't find it, it remains "None"

    return crop, lime

def find_specific_crop(soup: BeautifulSoup):
    """
    Performs the second-pass screen on the parsed HTML to find a specific crop type.
    """
    specific_crop_patterns = [
        "WarmSeasonGrsMaint(sq ft)",
        "CoolSeasonGrsMaint(sq ft)",
        "Centipedegrass(sq ft)"
    ]
    
    # The specific crop name is usually inside a <b> tag.
    bold_tags = soup.find_all('b')
    for tag in bold_tags:
        tag_text = tag.get_text(strip=True)
        if tag_text in specific_crop_patterns:
            return tag_text
            
    return None

# --- Main Application Logic ---

# Initialize session state
if 'df_results' not in st.session_state:
    st.session_state.df_results = None

# "Start Scraping" button logic
if st.button("Start Scraping", type="primary"):
    if not results_url.strip():
        st.error("Please enter a valid results.aspx URL.")
        st.stop()

    with st.spinner("Scraping Clemson soil reports... (Initial Pass)"):
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        try:
            res = session.get(results_url, timeout=30)
            res.raise_for_status()
        except Exception as exc:
            st.error(f"Failed to load results page: {exc}")
            st.stop()

        main_soup = BeautifulSoup(res.text, "html.parser")
        summary_tbl = next(
            (t for t in main_soup.find_all("table")
             if "Sample No" in t.get_text() and "Soil pH" in t.get_text()),
            None
        )
        if not summary_tbl:
            st.error("Could not find the main results table on that page.")
            st.stop()

        records = []
        rows = summary_tbl.find_all("tr")[1:]
        progress_bar = st.progress(0, text="Scraping initial data...")

        for i, tr in enumerate(rows):
            td = tr.find_all("td")
            if len(td) < 20:
                continue

            name         = td[0].get_text(strip=True)
            date_samp    = td[1].get_text(strip=True)
            sample_no    = td[2].get_text(strip=True)
            account_no   = re.sub(r"\D", "", sample_no)
            lab_num      = td[3].get_text(strip=True)
            href_tag     = td[3].find("a")
            href         = href_tag["href"] if href_tag else ""
            soil_pH      = td[4].get_text(strip=True)
            buffer_pH    = td[5].get_text(strip=True)
            p_lbs, k_lbs, ca_lbs, mg_lbs = [td[i].get_text(strip=True) for i in range(6,10)]
            zn_lbs, mn_lbs, cu_lbs, b_lbs = [td[i].get_text(strip=True) for i in range(10,14)]
            na_lbs       = td[14].get_text(strip=True)
            s_lbs        = td[15].get_text(strip=True)
            ec           = td[16].get_text(strip=True)
            no3_n        = td[17].get_text(strip=True)
            om_pct       = td[18].get_text(strip=True)
            bulk_den     = td[19].get_text(strip=True)
            
            report_url = txt_url_from_href(results_url, href) if href else ""

            # Store the HTML content for the second pass to avoid re-downloading
            report_html_content = ""
            crop_type, lime_val = ("None", "None")
            if report_url:
                try:
                    report_resp = session.get(report_url, timeout=15)
                    if report_resp.ok:
                        report_html_content = report_resp.text
                        report_soup = BeautifulSoup(report_html_content, "html.parser")
                        crop_type, lime_val = extract_data_from_report_html(report_soup)
                except Exception:
                    pass

            records.append({
                "Account Number": account_no, "Name": name, "Date Sampled": date_samp,
                "Sample No": sample_no, "Lab Number": lab_num, "Soil pH": soil_pH,
                "Buffer pH": buffer_pH, "P (lbs/A)": p_lbs, "K (lbs/A)": k_lbs,
                "Ca (lbs/A)": ca_lbs, "Mg (lbs/A)": mg_lbs, "Zn (lbs/A)": zn_lbs,
                "Mn (lbs/A)": mn_lbs, "Cu (lbs/A)": cu_lbs, "B (lbs/A)": b_lbs,
                "Na (lbs/A)": na_lbs, "S (lbs/A)": s_lbs, "EC (mmhos/cm)": ec,
                "NO3-N (ppm)": no3_n, "OM (%)": om_pct, "Bulk Density (lbs/A)": bulk_den,
                "Crop Type": crop_type or "None", "Lime (lbs/1000 ft²)": lime_val or "None",
                "_report_html": report_html_content # Store the full HTML
            })
            time.sleep(0.1)
            progress_bar.progress((i + 1) / len(rows), text=f"Scraping report {i+1}/{len(rows)}")

        progress_bar.empty()
        st.session_state.df_results = pd.DataFrame(records)
        st.success("✅ Initial extraction complete!")

# --- Display Area: Shows table and buttons if data exists ---

if st.session_state.df_results is not None:
    df_display = st.session_state.df_results.drop(columns=['_report_html'], errors='ignore')
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    csv = df_display.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Download CSV", data=csv, file_name="soil_full_data.csv", mime="text/csv"
    )

    st.markdown("---")

    # --- "Run Crop Screen" Button ---
    if st.button("Run Crop Screen"):
        with st.spinner("Running detailed crop screen... This may take a moment."):
            df = st.session_state.df_results.copy()
            updates_found = 0

            for index, row in df.iterrows():
                report_html = row["_report_html"]
                if report_html:
                    try:
                        report_soup = BeautifulSoup(report_html, "html.parser")
                        specific_crop = find_specific_crop(report_soup)
                        if specific_crop:
                            df.loc[index, 'Crop Type'] = specific_crop
                            updates_found += 1
                    except Exception as e:
                        st.warning(f"Could not process report for {row['Lab Number']}: {e}")
            
            st.session_state.df_results = df
            st.success(f"✅ Crop screen complete! Found and updated {updates_found} specific crop types.")
