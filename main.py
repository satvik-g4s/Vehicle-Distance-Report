import streamlit as st
import pandas as pd
from supabase import create_client
import io

st.set_page_config(layout="wide")

st.title("GPS Distance Processing")
download_only = st.button(" Fetch Existing Master Report")
if download_only:

    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    st.write("Fetching master data...")

    response = supabase.table("gps_distance") \
        .select("*") \
        .execute()

    master = pd.DataFrame(response.data)

    if master.empty:
        st.warning("Database is empty")
        st.stop()

    master["trip_date"] = pd.to_datetime(master["trip_date"])

    master = master.drop_duplicates(
        subset=["plate_number", "trip_date"]
    )

    master["Month"] = master["trip_date"].dt.strftime("%b-%Y")
    master["MonthOrder"] = master["trip_date"].dt.to_period("M")

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:

        for month, df_month in (
            master.sort_values("MonthOrder")
                  .groupby("Month")
        ):

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
                c.strftime("%d-%m-%Y")
                if isinstance(c, pd.Timestamp)
                else c
                for c in pivot.columns
            ]

            pivot.to_excel(writer,
                           sheet_name=month,
                           index=False)

    st.download_button(
        label="Download Master Report",
        data=output.getvalue(),
        file_name="GPS_Master_Output.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.stop()

# =============================
# FILE UPLOADS
# =============================
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

# =============================
# MAIN PROCESS
# =============================
if run:

    if uploaded_file_mmi is None and uploaded_file_cautio is None:
        st.warning("Upload at least one file")
        st.stop()

    st.write("Reading files...")

    # =============================
    # MAPMYINDIA PROCESSING
    # =============================
    if uploaded_file_mmi is not None:

        st.write("Processing MapMyIndia data...")

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

        # Convert datetime columns → dd-mm-yyyy
        mmi.columns = [
            c.strftime("%d-%m-%Y")
            if isinstance(c, pd.Timestamp)
            else c
            for c in mmi.columns
        ]

    else:
        st.info("MMI file not uploaded")
        mmi = pd.DataFrame(columns=["plate_number"])

    # =============================
    # CAUTIO PROCESSING
    # =============================
    if uploaded_file_cautio is not None:

        st.write("Processing Cautio data...")

        cautio = pd.read_csv(uploaded_file_cautio, index_col=False)

        date_cols = pd.to_datetime(
            cautio.columns,
            format="%d-%m-%Y",
            errors="coerce"
        ).notna()

        cautio = cautio.loc[
            :, ["plate_number"] + list(cautio.columns[date_cols])
        ]

        cautio.columns = cautio.columns.astype(str)

    else:
        st.info("Cautio file not uploaded")
        cautio = pd.DataFrame(columns=["plate_number"])

    # =============================
    # COMBINE DATA
    # =============================
    st.write("Combining data...")

    combine = pd.concat(
        [cautio, mmi],
        axis=0,
        ignore_index=True,
        sort=False
    )

    if combine.shape[0] == 0:
        st.warning("No usable data found")
        st.stop()

    # =============================
    # MELT DATA
    # =============================
    upload_df = combine.melt(
        id_vars="plate_number",
        var_name="trip_date",
        value_name="distance"
    )

    upload_df["trip_date"] = pd.to_datetime(
        upload_df["trip_date"],
        dayfirst=True,
        errors="coerce"
    ).dt.strftime("%Y-%m-%d")

    upload_df = upload_df.dropna(subset=["distance", "trip_date"])

    # =============================
    # SUPABASE UPLOAD
    # =============================
    st.write("Uploading to Database...")

    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    data = upload_df.to_dict("records")

    supabase.table("gps_distance") \
        .upsert(data, ignore_duplicates=True) \
        .execute()

    # =============================
    # FETCH MASTER DATA
    # =============================
    st.write("Fetching master data...")

    response = supabase.table("gps_distance") \
        .select("*") \
        .execute()

    master = pd.DataFrame(response.data)

    master["trip_date"] = pd.to_datetime(master["trip_date"])

    # remove accidental duplicates
    master = master.drop_duplicates(
        subset=["plate_number", "trip_date"]
    )

    master["Month"] = master["trip_date"].dt.strftime("%b-%Y")
    master["MonthOrder"] = master["trip_date"].dt.to_period("M")

    # =============================
    # CREATE EXCEL
    # =============================
    st.write("Creating Excel output...")

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:

        for month, df_month in (
            master.sort_values("MonthOrder")
                  .groupby("Month")
        ):

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
                col.strftime("%d-%m-%Y")
                if isinstance(col, pd.Timestamp)
                else col
                for col in pivot.columns
            ]

            pivot.to_excel(
                writer,
                sheet_name=month,
                index=False
            )

    st.success("Process Completed ✅")

    st.download_button(
        label="Download Output",
        data=output.getvalue(),
        file_name="GPS_Master_Output.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
