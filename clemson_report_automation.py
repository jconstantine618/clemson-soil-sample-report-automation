import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
from urllib.parse import urljoin

# ──────────────────────  Streamlit UI  ──────────────────────
st.set_page_config(page_title="Clemson Soil – Full Data + Crop Type", layout="wide")
st.title("🌱 Clemson Soil Report Scraper – Full Data + Crop Type")
st.markdown(
    "Paste any **results.aspx** URL, click **Start Scraping**, and get a CSV "
    "with full soil data, account number, and crop type (Cool‑Season, Warm‑Season, Centipede)."
)

results_url = st.text_input(
    "Results page URL",
    value=(
        "https://psaweb.clemson.edu/soils/aspx/results.aspx?"
        "qs=1&LabNumA=25050901&LabNumB=25050930"
        "&DateA=&DateB=&Name=&UserName=AGSRVLB&AdminAuth=0&submit=SEARCH"
    ),
    help="Any Clemson results.aspx link that lists your samples."
)

# ──────────────────────  Helpers  ───────────────────────────
def extract_crop_type(detail_html: str) -> str | None:
    """Return the crop description from the Recommendations section."""
    soup = BeautifulSoup(detail_html, "html.parser")
    # find the first TD that starts with 'Crop'
    for td in soup.find_all("td"):
        txt = td.get_text(strip=True)
        if txt.startswith("Crop"):
            parts = txt.split(":", 1)
            if len(parts) == 2:
                return parts[1].strip()
    return None

# ──────────────────────  Main scrape  ───────────────────────
if st.button("Start Scraping"):
    if not results_url.strip():
        st.error("Please enter a valid results.aspx URL.")
        st.stop()

    with st.spinner("Scraping summary table and detail pages…"):
        records = []

        try:
            # 1️⃣  keep one session (cookies + VIEWSTATE)
            sess = requests.Session()
            sess.headers.update({"User-Agent": "Mozilla/5.0"})

            # 2️⃣  GET the results page (this sets ASP.NET cookies)
            res = sess.get(results_url)
            res.raise_for_status()
            summary_soup = BeautifulSoup(res.text, "html.parser")

            # 3️⃣  find the main results table
            summary_tbl = next(
                (
                    t for t in summary_soup.find_all("table")
                    if "Sample No" in t.get_text() and "Soil pH" in t.get_text()
                ),
                None,
            )
            if summary_tbl is None:
                st.error("Could not locate the summary table.")
                st.stop()

            # 4️⃣  iterate rows
            for tr in summary_tbl.find_all("tr")[1:]:
                td = tr.find_all("td")
                if len(td) < 20:
                    continue  # malformed row

                name           = td[0].get_text(strip=True)
                date_sampled   = td[1].get_text(strip=True)
                sample_no      = td[2].get_text(strip=True)
                account_number = re.sub(r"\D", "", sample_no)
                lab_num        = td[3].get_text(strip=True)
                href           = td[3].find("a")["href"] if td[3].find("a") else ""
                soil_pH        = td[4].get_text(strip=True)
                buffer_pH      = td[5].get_text(strip=True)
                p_lbs, k_lbs, ca_lbs, mg_lbs = (td[i].get_text(strip=True) for i in range(6,10))
                zn_lbs, mn_lbs, cu_lbs, b_lbs = (td[i].get_text(strip=True) for i in range(10,14))
                na_lbs, s_lbs = td[14].get_text(strip=True), td[15].get_text(strip=True)
                ec, no3_n, om_pct, bulk_den = (td[i].get_text(strip=True) for i in range(16,20))

                # 5️⃣  follow the Lab# link with SAME session (cookies intact)
                crop_type = None
                if href:
                    detail_url = urljoin(results_url, href)
                    d = sess.get(detail_url, headers={"Referer": results_url})
                    if d.ok:
                        crop_type = extract_crop_type(d.text)

                records.append({
                    "Account Number": account_number,
                    "Name": name,
                    "Date Sampled": date_sampled,
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
                    "Crop Type": crop_type,
                })
                time.sleep(0.25)

            df = pd.DataFrame(records)
            st.success("✅ Extraction complete!")
            st.dataframe(df)
            st.download_button(
                "📥 Download CSV",
                df.to_csv(index=False),
                "soil_full_data.csv",
                mime="text/csv"
            )

        except Exception as exc:
            st.error(f"Error: {exc}")
