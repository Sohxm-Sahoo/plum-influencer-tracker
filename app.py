import streamlit as st
from updater import update_csv
import os

st.set_page_config(
    page_title="Influencer Tracker",
    layout="wide"
)

st.title("Influencer CSV Updater")

uploaded_file = st.file_uploader(
    "Upload Influencer CSV",
    type=["csv"]
)

if uploaded_file is not None:

    input_file = "input.csv"

    with open(input_file, "wb") as f:
        f.write(uploaded_file.getbuffer())

    st.success("CSV uploaded successfully")

    if st.button("Update Metrics"):

        with st.spinner("Fetching Instagram and YouTube data..."):

            try:
                output_file = update_csv(input_file)

                st.success("Update Complete")

                with open(output_file, "rb") as f:
                    st.download_button(
                        label="Download Updated CSV",
                        data=f,
                        file_name="Influencer_V5_Updated.csv",
                        mime="text/csv"
                    )

            except Exception as e:
                st.error(str(e))
