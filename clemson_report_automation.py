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
)

# --- Helper Functions ---

def txt_url_from_href(base_results_url: str, href: str) -> str:
    """
    Constructs the full URL for the plain-text version of a single report
    by adding '&format=txt' to the standard report link.
    """
    full = urljoin(base_results_url, href)
    parsed = urlparse(full)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    qs["format"] = ["txt"]
    new_query = urlencode(qs, doseq=True)
    return parsed._replace(query=new_query).geturl()

def extract_initial_data(txt: str):
    """
    Performs the first-pass extraction to get the general crop type and lime recommendation
    from the plain-text report.
    """
    crop = None
    lime = None
    # Find general crop type (e.g., "Crop : Centipedegrass")
    crop_match = re.search(r"^Crop\s*:\s*(.+)$", txt, re.MULTILINE)
    if crop_match:
        crop = crop_match.group(1).strip()
    
    # Find lime recommendation (e.g., "50 lbs/1000 sq ft")
    lime_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*lbs/1000", txt)
    if lime_match:
        lime = lime_match.group(1)
    elif "no lime" in txt.lower():
        lime = "None"
    return crop, lime

def find_specific_crop(txt: str):
    """
    Performs the second-pass screen to find one of the specific maintenance crop types.
    Returns the found text or None.
    """
    # Search for the specific maintenance strings
    specific_crop_patterns = [
        r"WarmSeasonGrsMaint\(sq ft\)",
        r"CoolSeasonGrsMaint\(sq ft\)",
        r"Centipedegrass\(sq ft\)"
    ]
    for pattern in specific_crop_patterns:
        match = re.search(pattern, txt)
        if match:
            return match.group(0) # Return the exact text that was found
    return None

# --- Main Application Logic ---

# Initialize session state to hold the DataFrame
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

        soup = BeautifulSoup(res.text, "html.parser")
        summary_tbl = next(
            (t for t in soup.find_all("table")
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

            # Reverting to original data extraction structure for clarity
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
            
            # We need the text URL for the second screening step later
            txt_report_url = txt_url_from_href(results_url, href) if href else ""

            crop_type, lime_val = (None, None)
            if txt_report_url:
                try:
                    txt_resp = session.get(txt_report_url, timeout=15)
                    if txt_resp.ok:
                        crop_type, lime_val = extract_initial_data(txt_resp.text)
                except Exception:
                    pass  # Silently continue

            records.append({
                "Account Number": account_no,
                "Name": name,
                "Date Sampled": date_samp,
                "Sample No": sample_no,
                "Lab Number": lab_num,
                "Soil pH": soil_pH,
                "Buffer pH": buffer_pH,
                "P (lbs/A)": p_lbs,
                "K (lbs/A)": k_lbs,
                "Ca (lbs/A)": ca_lbs,
                "Mg (lbs/A)": mg_lbs,
                "Zn (lbs/A)": zn_lbs,
                "Mn (lbs/A)": mn_lbs,
                "Cu (lbs/A)": cu_lbs,
                "B (lbs/A)": b_lbs,
                "Na (lbs/A)": na_lbs,
                "S (lbs/A)": s_lbs,
                "EC (mmhos/cm)": ec,
                "NO3-N (ppm)": no3_n,
                "OM (%)": om_pct,
                "Bulk Density (lbs/A)": bulk_den,
                "Crop Type": crop_type or "None",
                "Lime (lbs/1000 ft²)": lime_val or "None",
                "_report_url": txt_report_url # Store URL for the second step
            })
            time.sleep(0.1)  # Polite pause
            progress_bar.progress((i + 1) / len(rows), text=f"Scraping report {i+1}/{len(rows)}")

        progress_bar.empty()
        st.session_state.df_results = pd.DataFrame(records)
        st.success("✅ Initial extraction complete!")

# --- Display Area: Shows table and buttons if data exists ---

if st.session_state.df_results is not None:
    # Make a copy for display that doesn't show our internal URL column
    df_display = st.session_state.df_results.drop(columns=['_report_url'], errors='ignore')
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    # --- CSV Download Button ---
    # Use the display version for the download so the internal URL isn't in the CSV
    csv = df_display.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Download CSV",
        data=csv,
        file_name="soil_full_data.csv",
        mime="text/csv"
    )

    st.markdown("---") # Visual separator

    # --- "Run Crop Screen" Button ---
    if st.button("Run Crop Screen"):
        with st.spinner("Running detailed crop screen... This may take a moment."):
            df = st.session_state.df_results.copy()
            session = requests.Session()
            session.headers.update({"User-Agent": "Mozilla/5.0"})
            
            num_rows = len(df)
            progress_bar = st.progress(0, text="Starting crop screen...")
            updates_found = 0

            for index, row in df.iterrows():
                report_url = row["_report_url"]
                if report_url:
                    try:
                        txt_resp = session.get(report_url, timeout=15)
                        if txt_resp.ok:
                            specific_crop = find_specific_crop(txt_resp.text)
                            if specific_crop:
                                # Update the 'Crop Type' column with the specific finding
                                df.loc[index, 'Crop Type'] = specific_crop
                                updates_found += 1
                    except Exception as e:
                        st.warning(f"Could not process report {row['Lab Number']}: {e}")
                
                time.sleep(0.1) # Polite pause
                progress_bar.progress(
                    (index + 1) / num_rows, 
                    text=f"Screening report {index + 1}/{num_rows}..."
                )
            
            progress_bar.empty()
            st.session_state.df_results = df # Save the updated dataframe
            st.success(f"✅ Crop screen complete! Found and updated {updates_found} specific crop types.")
            # The script will auto-rerun here, refreshing the dataframe display
