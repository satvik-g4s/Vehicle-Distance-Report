import streamlit as st
import pandas as pd
from supabase import create_client
from io import BytesIO
import io
st.set_page_config(layout="wide")
st.title("Vehicle-Distance-Report")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]



supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

VEHICLE_FILE_PATH = "vehicles/current_vehicles.xlsx"

tab1, tab2, tab3, tab4 = st.tabs(["Dashboard", "Fetch Report", "Update Data", "Guidelines"])




def fetch_all_gps():

    all_rows = []
    limit = 1000
    start = 0

    while True:

        response = (
            supabase.table("gps_distance")
            .select("*")
            .range(start, start + limit - 1)
            .execute()
        )

        data = response.data

        if not data:
            break

        all_rows.extend(data)
        start += limit

    return pd.DataFrame(all_rows)

def load_vehicle_master():

    try:
        vehicle_bytes = supabase.storage \
            .from_("app-data") \
            .download(VEHICLE_FILE_PATH)

        vehicles = pd.read_excel(
            BytesIO(vehicle_bytes),
            usecols="A:S"
        )

        vehicles = vehicles.rename(
            columns={"Reg. Vehicle Number": "plate_number"}
        )

        return vehicles

    except:
        return None

with tab1:
    st.write("Dashboard")

with tab2:
    st.write("Fetch Report")

    vehicles = load_vehicle_master()

    if vehicles is None:
        st.warning("Vehicle Master not found. Please upload in Update Data tab.")

    else:
        download_only = st.button("Fetch Existing Master Report")

        if download_only:

            st.write("Fetching master data...")

            master = fetch_all_gps()

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

                month_groups = (
                    master
                    .sort_values("MonthOrder")
                    .groupby(["MonthOrder", "Month"])
                )

                for (_, month), df_month in month_groups:

                    pivot = df_month.pivot_table(
                        index="plate_number",
                        columns="trip_date",
                        values="distance",
                        aggfunc="sum"
                    )

                    pivot = pivot.sort_index(axis=1)
                    pivot.reset_index(inplace=True)

                    pivot.columns = [
                        c.strftime("%d-%m-%Y")
                        if isinstance(c, pd.Timestamp)
                        else c
                        for c in pivot.columns
                    ]

                    pivot = pd.merge(
                        vehicles,
                        pivot,
                        how="left",
                        on="plate_number"
                    )

                    pivot.to_excel(writer,
                                sheet_name=month,
                                index=False)

            st.download_button(
                "Download Master Report",
                data=output.getvalue(),
                file_name="GPS_Master_Output.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
# =============================
# FILE UPLOADS
# =============================
with tab3:

    st.subheader("Vehicle Master Upload")

    uploaded_file_vehicles = st.file_uploader(
        "Upload Vehicle Master (xlsx)",
        type=["xlsx"]
    )

    if uploaded_file_vehicles:

        st.write("Saving Vehicle Master...")

        try:
            supabase.storage.from_("app-data") \
                .remove([VEHICLE_FILE_PATH])
        except:
            pass

        supabase.storage.from_("app-data") \
            .upload(
                VEHICLE_FILE_PATH,
                uploaded_file_vehicles.getvalue(),
                {"content-type":
                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
            )

        st.success("Vehicle Master Updated ✅")

    # =============================
    # LOAD STORED VEHICLES
    # =============================
    vehicles = load_vehicle_master()

    st.divider()

    uploaded_file_mmi = st.file_uploader(
        "Upload MapMyIndia Excel",
        type=["xlsx"]
    )

    uploaded_file_cautio = st.file_uploader(
        "Upload Cautio CSV",
        type=["csv"]
    )

    if uploaded_file_mmi or uploaded_file_cautio:

        run = st.button("Run Update")

        if run:

            st.write("Reading files...")

            # ---------- MMI ----------
            if uploaded_file_mmi:

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

                mmi.rename(
                    columns={"Device": "plate_number"},
                    inplace=True
                )

                mmi.columns = [
                    c.strftime("%d-%m-%Y")
                    if isinstance(c, pd.Timestamp)
                    else c
                    for c in mmi.columns
                ]

            else:
                mmi = pd.DataFrame(columns=["plate_number"])

            # ---------- CAUTIO ----------
            if uploaded_file_cautio:

                cautio = pd.read_csv(uploaded_file_cautio)

                date_cols = pd.to_datetime(
                    cautio.columns,
                    format="%d-%m-%Y",
                    errors="coerce"
                ).notna()

                cautio = cautio.loc[
                    :, ["plate_number"]
                    + list(cautio.columns[date_cols])
                ]

            else:
                cautio = pd.DataFrame(columns=["plate_number"])

            # ---------- COMBINE ----------
            combine = pd.concat(
                [cautio, mmi],
                ignore_index=True,
                sort=False
            )

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

            upload_df.dropna(
                subset=["distance", "trip_date"],
                inplace=True
            )

            st.write("Uploading to database...")

            supabase.table("gps_distance") \
                .upsert(
                    upload_df.to_dict("records"),
                    ignore_duplicates=True
                ).execute()

            st.success("Database Updated ✅")
with tab4:            
    st.markdown("""
    ### GPS Distance Processing – Guidelines

    ---

    #### ▶ Vehicle Master Data
    The **Vehicle Master file** contains all vehicle-related information associated with **G4S**.

    - If unavailable, kindly fetch the latest file from [here](https://docs.google.com/spreadsheets/d/1OBQgxo5vuVNwnvho-lZPplBpKLX1sDSbBadmQ08cu9w/edit?usp=sharing) in excel format and upload here.
    - In case of any vehicle additions or modifications, the same sheet should be updated for better usage for other employees.Kindly enter just the data, the column headers cant be modified.

    ---

    #### ▶ Download Existing Report
    To download the latest consolidated report:

    1. Upload the **Vehicles Data** file.
    2. Click **Fetch Existing Master Report**.
    3. Download the generated report.

    ---

    #### ▶ Updating Daily GPS Data

    ##### ✔ Updating Cautio Data
    - Upload the received **Cautio data** in the **3rd Upload**.
    - Ensure file is downloaded from the server in **CSV format**.

    ##### ✔ Updating MapMyIndia Data
    - Upload the received **MapMyIndia data** in the **2nd Upload**.
    - Ensure file is in **Excel format**.

    ---

    #### ▶ Updating Data Without Downloading Report
    If only database update is required:

    - Upload data in respective upload fields.
    - Click **Run**.
    - It is recommended to download the report once to verify updates.

    ---

    #### ▶ Important Instructions
    - Upload files **only in their respective upload fields**.
    - Incorrect uploads may cause the program to crash.
    - If this occurs, kindly **refresh the page and upload again**.
    - Ensure all column names match the required format exactly.

    ---

    #### ▶ Note
    If the **Vehicle Master file is not uploaded**,  
    the report can still be generated, however vehicle-related details will not be reflected.
    """)
