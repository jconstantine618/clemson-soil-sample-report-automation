import streamlit as st
import requests, re, time
from bs4 import BeautifulSoup
import pandas as pd
from urllib.parse import urljoin, urlparse, parse_qs, urlencode

st.set_page_config(page_title="Clemson Soil Scraper – Full Data + Crop", layout="wide")
st.title("🌱 Clemson Soil Report Scraper – Full Data + Crop Type")

st.markdown(
    "Paste any Clemson **results.aspx** URL (with your LabNum range or date range), "
    "click **Start Scraping**, and get a CSV with full soil data **plus** the Crop type "
    "and the lab’s lime recommendation."
)

results_url = st.text_input(
    "Results page URL",
    "https://psaweb.clemson.edu/soils/aspx/results.aspx?"
    "qs=1&LabNumA=25050901&LabNumB=25050930&DateA=&DateB=&Name=&"
    "UserName=AGSRVLB&AdminAuth=0&submit=SEARCH",
)

# ---------------------------------------------------------------------------
def txt_url_from_href(base_results_url: str, href: str) -> str:
    """
    Clemson's Lab # link is something like
    standardreport.aspx?key=...&pval=...&id=25050901
    Add &format=txt to get the plain‑text report.
    """
    full = urljoin(base_results_url, href)
    parsed = urlparse(full)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    qs["format"] = ["txt"]
    new_query = urlencode(qs, doseq=True)
    return parsed._replace(query=new_query).geturl()

def extract_crop_and_lime(txt: str):
    """Return (crop_type, lime_lbs_1000) from plain‑text report."""
    crop = None
    lime = None
    crop_match = re.search(r"^Crop\s*:\s*(.+)$", txt, re.MULTILINE)
    if crop_match:
        crop = crop_match.group(1).strip()
    lime_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*lbs/1000", txt)
    if lime_match:
        lime = lime_match.group(1)
    elif "no lime" in txt.lower():
        lime = "None"
    return crop, lime

# ---------------------------------------------------------------------------
if st.button("Start Scraping"):
    if not results_url.strip():
        st.error("Please enter a valid results.aspx URL.")
        st.stop()

    with st.spinner("Scraping Clemson soil reports…"):
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
        for tr in summary_tbl.find_all("tr")[1:]:
            td = tr.find_all("td")
            if len(td) < 20:
                continue  # skip blank / malformed rows

            name         = td[0].get_text(strip=True)
            date_samp    = td[1].get_text(strip=True)
            sample_no    = td[2].get_text(strip=True)
            account_no   = re.sub(r"\D", "", sample_no)
            lab_num      = td[3].get_text(strip=True)
            href         = td[3].find("a")["href"] if td[3].find("a") else ""
            soil_pH      = td[4].get_text(strip=True)
            buffer_pH    = td[5].get_text(strip=True)
            p_lbs, k_lbs, ca_lbs, mg_lbs = [td[i].get_text(strip=True) for i in range(6,10)]
            zn_lbs, mn_lbs, cu_lbs, b_lbs = [td[i].get_text(strip=True) for i in range(10,14)]
            na_lbs      = td[14].get_text(strip=True)
            s_lbs       = td[15].get_text(strip=True)
            ec          = td[16].get_text(strip=True)
            no3_n       = td[17].get_text(strip=True)
            om_pct      = td[18].get_text(strip=True)
            bulk_den    = td[19].get_text(strip=True)

            crop_type, lime_val = (None, None)
            if href:
                txt_url = txt_url_from_href(results_url, href)
                try:
                    txt_resp = session.get(txt_url, timeout=15)
                    if txt_resp.ok:
                        crop_type, lime_val = extract_crop_and_lime(txt_resp.text)
                except Exception:
                    pass  # silently continue; leave None if failed

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
                "NO3‑N (ppm)": no3_n,
                "OM (%)": om_pct,
                "Bulk Density (lbs/A)": bulk_den,
                "Crop Type": crop_type or "None",
                "Lime (lbs/1000 ft²)": lime_val or "None",
            })
            time.sleep(0.25)  # polite pause

        df = pd.DataFrame(records)
        st.success("✅ Extraction complete!")
        st.dataframe(df, use_container_width=True)
        st.download_button(
            "📥 Download CSV",
            df.to_csv(index=False).encode("utf-8"),
            "soil_full_data.csv",
            mime="text/csv"
        )
