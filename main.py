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
    if uploaded_file_mmi is None or uploaded_file_cautio is None:
        st.warning("Please upload both files")
    else:
        st.write("Reading files...")

        mmi = pd.read_excel(
            uploaded_file_mmi,
            header=5,
            usecols=["Device", "Date", "Distance (km)"]
        )

        cautio = pd.read_csv(uploaded_file_cautio, index_col=False)

        st.write("Processing Cautio data...")

        date_cols = pd.to_datetime(
            cautio.columns,
            format="%d-%m-%Y",
            errors="coerce"
        ).notna()

        cautio = cautio.loc[:, ["plate_number"] + list(cautio.columns[date_cols])]

        st.write("Processing MapMyIndia data...")

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

        st.write("Combining data...")

        combine = pd.concat([cautio, mmi], axis=0)

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

        st.write("Uploading to Database...")

        SUPABASE_URL = st.secrets["SUPABASE_URL"]
        SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

        data = upload_df.to_dict("records")

        supabase.table("gps_distance") \
            .upsert(data, ignore_duplicates=True) \
            .execute()

        st.write("Fetching master data...")

        response = supabase.table("gps_distance") \
            .select("*") \
            .execute()

        master = pd.DataFrame(response.data)

        master["trip_date"] = pd.to_datetime(master["trip_date"])
        master["Month"] = master["trip_date"].dt.strftime("%b-%Y")

        st.write("Creating Excel output...")

        output = io.BytesIO()

        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            for month, df_month in master.groupby("Month"):

                pivot = df_month.pivot_table(
                    index="plate_number",
                    columns="trip_date",
                    values="distance",
                    aggfunc="sum"
                )

                pivot = pivot.sort_index(axis=1)

                pivot.reset_index(inplace=True)
                pivot.columns.name = None
                pivot.columns = [
                    col.strftime("%d-%m-%Y") if isinstance(col, pd.Timestamp) else col
                    for col in pivot.columns
                ]

                pivot.to_excel(
                    writer,
                    sheet_name=month,
                    index=False
                )

        st.success("Process Completed")

        st.download_button(
            label="Download Output",
            data=output.getvalue(),
            file_name="output.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
