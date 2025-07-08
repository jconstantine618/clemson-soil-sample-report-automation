import streamlit as st
import pandas as pd
from clemson_report_automation import scrape_clemson_report # Import the scraper function

# --- App Configuration ---
st.set_page_config(
    page_title="Clemson Soil Report Scraper",
    page_icon="🔎",
    layout="centered",
)

# --- App UI ---
st.title("Clemson Soil Report Scraper 🚜")

st.markdown(
    "Enter the full URL for a Clemson University soil report to extract the data."
)

# Input field for the URL
url = st.text_input(
    "Enter Report URL",
    placeholder="https://psaweb.clemson.edu/soils/aspx/standardreport.aspx?key=...",
)

# Scrape button
if st.button("Scrape Report Data"):
    if url:
        try:
            with st.spinner("Fetching and parsing the report... please wait."):
                # Call the scraping function from the other file
                report_data = scrape_clemson_report(url)

            if report_data:
                st.success("Successfully scraped the report!")
                st.balloons()

                # Display the data in a clean format
                st.subheader("📋 Report Data")
                
                # Create a DataFrame for better presentation
                df = pd.DataFrame(list(report_data.items()), columns=['Metric', 'Value'])
                st.table(df)

                # Specifically show the comments
                st.subheader("📝 Comments")
                st.text_area("Comment 426", report_data.get('Comment 426', 'Not Found'), height=100)
                st.text_area("Comment 429", report_data.get('Comment 429', 'Not Found'), height=100)

            else:
                st.error("Could not retrieve data. The URL may be invalid or the report structure has changed.")

        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")
            st.info("Please double-check the URL. If the URL is correct, the website structure may have changed.")
    else:
        st.warning("Please enter a URL to scrape.")
