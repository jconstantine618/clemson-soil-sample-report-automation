import streamlit as st
import requests
import re
import time
import pandas as pd
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import openai

# --- Page Configuration ---
st.set_page_config(page_title="Clemson Soil Scraper – OpenAI Powered", layout="wide")

# --- App Title and Description ---
st.title("🤖 Clemson Soil Report Scraper – OpenAI Powered")
st.markdown(
    "This version uses OpenAI's GPT model to read the report pages. "
    "It securely uses your OpenAI API key from Streamlit's secrets management."
)
st.info("To use this app, add your OpenAI API key to your Streamlit secrets file as `OPENAI_API_KEY`.")

# --- User Input ---
results_url = st.text_input(
    "Results page URL",
    "https://psaweb.clemson.edu/soils/aspx/results.aspx?"
    "qs=1&LabNumA=25050901&LabNumB=25050930&DateA=&DateB=&Name=&"
    "UserName=AGSRVLB&AdminAuth=0&submit=SEARCH",
    key="results_url_input" 
)

# --- Helper Functions ---

def get_report_url(base_results_url: str, href: str) -> str:
    """Constructs the full URL for the report page."""
    return urljoin(base_results_url, href)

def extract_data_with_openai(client: openai.OpenAI, html_content: str, mode: str = "initial"):
    """
    Uses an OpenAI model to extract data from the report's HTML content.
    
    Args:
        client: The initialized OpenAI client.
        html_content: The raw HTML of the report page.
        mode: 'initial' for general crop/lime, 'specific' for the second pass.
    
    Returns:
        A tuple (crop, lime) for 'initial' mode, or just crop for 'specific' mode.
    """
    if not html_content:
        return ("None", "None") if mode == "initial" else "None"

    if mode == "initial":
        system_prompt = """
        You are an expert data extractor. Analyze the provided HTML and extract the general "Crop" and the "Lime" recommendation.
        The lime value should be a number (e.g., '78'). If no lime is recommended, the value should be 'None'.
        Return a single JSON object with keys "crop" and "lime".
        """
    else: # specific mode
        system_prompt = """
        You are an expert data extractor. Analyze the provided HTML. Your task is to find if one of the following exact crop names exists in the text: 
        "WarmSeasonGrsMaint(sq ft)", "CoolSeasonGrsMaint(sq ft)", "Centipedegrass(sq ft)".
        If you find an exact match, return a JSON object with a single key "crop" and the found crop name as the value.
        If you do not find an exact match, the value for "crop" should be "None".
        """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": html_content}
            ]
        )
        data = json.loads(response.choices[0].message.content)
        
        if mode == "initial":
            crop = data.get("crop", "None")
            lime = data.get("lime", "None")
            return crop, str(lime) # Ensure lime is a string
        else:
            return data.get("crop", "None")

    except (json.JSONDecodeError, AttributeError, Exception) as e:
        st.warning(f"AI extraction failed for one report. Details: {e}")
        return ("None", "None") if mode == "initial" else "None"


# --- Main Application Logic ---

if 'df_results' not in st.session_state:
    st.session_state.df_results = None

if st.button("Start Scraping", type="primary"):
    # Check for the API key in secrets
    if "OPENAI_API_KEY" not in st.secrets:
        st.error("OpenAI API key not found. Please add it to your Streamlit secrets.")
        st.stop()
        
    if not results_url.strip():
        st.error("Please enter a valid results.aspx URL.")
        st.stop()

    # Initialize the OpenAI client with the secret key
    client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

    with st.spinner("Scraping Clemson soil reports... (AI Initial Pass)"):
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        try:
            res = session.get(results_url, timeout=30)
            res.raise_for_status()
        except Exception as exc:
            st.error(f"Failed to load results page: {exc}")
            st.stop()

        main_soup = BeautifulSoup(res.text, "html.parser")
        summary_tbl = next((t for t in main_soup.find_all("table") if "Sample No" in t.get_text()), None)
        if not summary_tbl:
            st.error("Could not find the main results table on that page.")
            st.stop()

        records = []
        rows = summary_tbl.find_all("tr")[1:]
        progress_bar = st.progress(0, text="Scraping initial data...")

        for i, tr in enumerate(rows):
            td = tr.find_all("td")
            if len(td) < 20: continue

            href_tag = td[3].find("a")
            href = href_tag["href"] if href_tag else ""
            report_url = get_report_url(results_url, href) if href else ""
            
            report_html_content = ""
            if report_url:
                try:
                    report_resp = session.get(report_url, timeout=15)
                    if report_resp.ok:
                        report_html_content = report_resp.text
                except Exception:
                    pass

            crop_type, lime_val = extract_data_with_openai(client, report_html_content, mode="initial")

            records.append({
                "Account Number": re.sub(r"\D", "", td[2].get_text(strip=True)),
                "Name": td[0].get_text(strip=True),
                "Date Sampled": td[1].get_text(strip=True),
                "Sample No": td[2].get_text(strip=True),
                "Lab Number": td[3].get_text(strip=True),
                "Soil pH": td[4].get_text(strip=True), "Buffer pH": td[5].get_text(strip=True),
                "P (lbs/A)": td[6].get_text(strip=True), "K (lbs/A)": td[7].get_text(strip=True),
                "Ca (lbs/A)": td[8].get_text(strip=True), "Mg (lbs/A)": td[9].get_text(strip=True),
                "Zn (lbs/A)": td[10].get_text(strip=True), "Mn (lbs/A)": td[11].get_text(strip=True),
                "Cu (lbs/A)": td[12].get_text(strip=True), "B (lbs/A)": td[13].get_text(strip=True),
                "Na (lbs/A)": td[14].get_text(strip=True), "S (lbs/A)": td[15].get_text(strip=True),
                "EC (mmhos/cm)": td[16].get_text(strip=True), "NO3-N (ppm)": td[17].get_text(strip=True),
                "OM (%)": td[18].get_text(strip=True), "Bulk Density (lbs/A)": td[19].get_text(strip=True),
                "Crop Type": crop_type, "Lime (lbs/1000 ft²)": lime_val,
                "_report_html": report_html_content
            })
            time.sleep(0.2) # Be polite
            progress_bar.progress((i + 1) / len(rows), text=f"AI processing report {i+1}/{len(rows)}")

        progress_bar.empty()
        st.session_state.df_results = pd.DataFrame(records)
        st.success("✅ AI initial extraction complete!")

# --- Display Area ---
if st.session_state.df_results is not None:
    df_display = st.session_state.df_results.drop(columns=['_report_html'], errors='ignore')
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    csv = df_display.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Download CSV", data=csv, file_name="soil_full_data.csv", mime="text/csv")

    st.markdown("---")

    if st.button("Run Crop Screen"):
        if "OPENAI_API_KEY" not in st.secrets:
            st.error("OpenAI API key not found. Please add it to your Streamlit secrets.")
            st.stop()
        
        client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

        with st.spinner("Running detailed AI crop screen..."):
            df = st.session_state.df_results.copy()
            updates_found = 0
            progress_bar_specific = st.progress(0, text="Starting detailed crop screen...")

            for index, row in df.iterrows():
                report_html = row["_report_html"]
                if report_html:
                    specific_crop = extract_data_with_openai(client, report_html, mode="specific")
                    if specific_crop and specific_crop.lower() != "none":
                        df.loc[index, 'Crop Type'] = specific_crop
                        updates_found += 1
                progress_bar_specific.progress((index + 1) / len(df), text=f"AI screening report {index + 1}/{len(df)}")
            
            progress_bar_specific.empty()
            st.session_state.df_results = df
            st.success(f"✅ AI crop screen complete! Found and updated {updates_found} specific crop types.")
