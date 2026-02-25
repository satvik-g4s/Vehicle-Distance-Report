import streamlit as st
import pandas as pd
from supabase import create_client
import io

st.set_page_config(layout="wide")

st.title("GPS Distance Processing")

uploaded_file_mmi = st.file_uploader(
    "Upload MapMyIndia Excel File (xlsx)",
    type=["xlsx"]
)
st.caption("Required columns: Device, Date, Distance (km)")

uploaded_file_cautio = st.file_uploader(
    "Upload Cautio CSV File (csv)",
    type=["csv"]
)
st.caption("Required columns: plate_number + date columns in dd-mm-yyyy format")

run = st.button("Run")

if run:

    if uploaded_file_mmi is None and uploaded_file_cautio is None:
        st.warning("Please upload at least one file")
        st.stop()

    processed_frames = []

    # ======================
    # MAPMYINDIA PROCESSING
    # ======================
    if uploaded_file_mmi is not None:

        st.write("Processing MapMyIndia file...")

        mmi = pd.read_excel(
            uploaded_file_mmi,
            header=5,
            usecols=["Device", "Date", "Distance (km)"]
        )

        mmi = (
            mmi.pivot_table(
                index="Device",
                columns="Date",
                values="Distance (km)",
                aggfunc="sum"
            )
            .reset_index()
        )

        mmi = mmi.rename(columns={"Device": "plate_number"})

        processed_frames.append(mmi)

    # ======================
    # CAUTIO PROCESSING
    # ======================
    if uploaded_file_cautio is not None:

        st.write("Processing Cautio file...")

        cautio = pd.read_csv(uploaded_file_cautio, index_col=False)

        date_cols = pd.to_datetime(
            cautio.columns,
            format="%d-%m-%Y",
            errors="coerce"
        ).notna()

        cautio = cautio.loc[
            :, ["plate_number"] + list(cautio.columns[date_cols])
        ]

        processed_frames.append(cautio)

    # ======================
    # COMBINE AVAILABLE DATA
    # ======================
    combine = pd.concat(processed_frames, axis=0)

    upload_df = combine.melt(
        id_vars="plate_number",
        var_name="trip_date",
        value_name="distance"
    )

    upload_df["trip_date"] = pd.to_datetime(
        upload_df["trip_date"],
        dayfirst=True
    ).dt.strftime("%Y-%m-%d")

    upload_df = upload_df.dropna(subset=["distance"])
