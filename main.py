import streamlit as st
import pandas as pd
from supabase import create_client
from io import BytesIO
import io
st.set_page_config(layout="wide")
def check_password():

    def password_entered():
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input(
            "Enter Password",
            type="password",
            on_change=password_entered,
            key="password",
        )
        st.stop()

    elif not st.session_state["password_correct"]:
        st.text_input(
            "Enter Password",
            type="password",
            on_change=password_entered,
            key="password",
        )
        st.error("Incorrect Password")
        st.stop()

check_password()

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

def load_dashboard_data():

    vehicles = load_vehicle_master()
    master = fetch_all_gps()

    if vehicles is None or master.empty:
        return None

    master["trip_date"] = pd.to_datetime(master["trip_date"])

    df = pd.merge(
        vehicles,
        master,
        on="plate_number",
        how="left"
    )

    return df        

with tab1:

    st.header("Fleet GPS Dashboard")

    # ==============================
    # CONFIGURABLE THRESHOLDS
    # ==============================
    WEEKLY_ACTIVE_DAYS = 5      # You can change later
    MONTHLY_ACTIVE_DAYS = 20    # You can change later
    DAILY_DISTANCE_THRESHOLD = 5

    df = load_dashboard_data()

    if df is None or df.empty:
        st.warning("Upload vehicle master & GPS data first.")
        st.stop()

    # Only GPS enabled vehicles & not US Embassy
    df = df[(df["GPS"] == "Yes") & (df["Client/QRT"].str.strip() != "US Embassy")].copy()

    latest_date = df["trip_date"].max()

    # ==============================
    # TOP METRICS (Daily - Latest Date)
    # ==============================
    today_df = df[df["trip_date"] == latest_date]

    total_gps = df["plate_number"].nunique()

    active_today = today_df[
        today_df["distance"] > DAILY_DISTANCE_THRESHOLD
    ]["plate_number"].nunique()

    inactive_today = today_df[
        (today_df["distance"] <= DAILY_DISTANCE_THRESHOLD)
        & (today_df["distance"].notna())
    ]["plate_number"].nunique()

    received_today = today_df["plate_number"].nunique()
    nodata_today = total_gps - received_today

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("GPS Vehicles", total_gps)
    c2.metric("Active (Daily)", active_today)
    c3.metric("Inactive (Daily)", inactive_today)
    c4.metric("No Data Received", nodata_today)

    st.divider()

    # ==============================
    # ANALYSIS FUNCTION (SAFE)
    # ==============================
    def analyse_daily(data, full_df):

        gps_master = (
            full_df[full_df["GPS"] == "Yes"]
            [["plate_number",
              "Hub Name",
              "Location",
              "Vendor Name",
              "Client/QRT"]]
            .drop_duplicates()
            .copy()
        )
    
        received = data.copy()
    
        received["status"] = "Inactive"
        received.loc[
            received["distance"] > DAILY_DISTANCE_THRESHOLD,
            "status"
        ] = "Active"
    
        merged = gps_master.merge(
            received[["plate_number", "status"]],
            on="plate_number",
            how="left"
        )
    
        merged["status"] = merged["status"].fillna("No Data")
    
        def summary(cols):
            if isinstance(cols, str):
                cols = [cols]
    
            return (
                merged.groupby(cols + ["status"])
                ["plate_number"]
                .nunique()
                .unstack(fill_value=0)
                .reset_index()
            )
    
        return (
            summary(["Hub Name", "Location"]),
            summary("Vendor Name"),
            summary("Client/QRT")
        )
    # ==============================
    # WEEKLY / MONTHLY VEHICLE STATUS
    # ==============================
    def analyse_period(data, full_df, required_days):

        gps_master = (
            full_df[full_df["GPS"] == "Yes"]
            [["plate_number",
              "Hub Name",
              "Location",
              "Vendor Name",
              "Client/QRT"]]
            .drop_duplicates()
            .copy()
        )
    
        if not data.empty:
    
            data = data.copy()
            data["active_flag"] = (
                data["distance"] > DAILY_DISTANCE_THRESHOLD
            )
    
            active_days = (
                data.groupby("plate_number")["active_flag"]
                .sum()
                .reset_index()
            )
    
            active_days["status"] = "Inactive"
            active_days.loc[
                active_days["active_flag"] >= required_days,
                "status"
            ] = "Active"
    
        else:
            active_days = pd.DataFrame(
                columns=["plate_number", "status"]
            )
    
        merged = gps_master.merge(
            active_days[["plate_number", "status"]],
            on="plate_number",
            how="left"
        )
    
        merged["status"] = merged["status"].fillna("No Data")
    
        def summary(cols):
            if isinstance(cols, str):
                cols = [cols]
    
            return (
                merged.groupby(cols + ["status"])
                ["plate_number"]
                .nunique()
                .unstack(fill_value=0)
                .reset_index()
            )
    
        return (
            summary(["Hub Name", "Location"]),
            summary("Vendor Name"),
            summary("Client/QRT")
            )
    # ==============================
    # PERIOD TABS
    # ==============================
    
    dtab, wtab, mtab = st.tabs(["Daily", "Weekly", "Monthly"])
    
    # ---------- DAILY ----------
    with dtab:
    
        daily = df[df["trip_date"] == latest_date]
    
        hub, vendor, client = analyse_daily(daily, df)
    
        st.subheader("Hub - Location")
        st.dataframe(hub, use_container_width=True)
    
        st.subheader("Vendor")
        st.dataframe(vendor, use_container_width=True)
    
        st.subheader("Client/QRT")
        st.dataframe(client, use_container_width=True)
    
    # ---------- WEEKLY ----------
    with wtab:
    
        week_start = latest_date - pd.Timedelta(days=6)
    
        weekly = df[
            df["trip_date"].between(week_start, latest_date)
        ]
    
        hub, vendor, client = analyse_period(
            weekly,
            df,
            WEEKLY_ACTIVE_DAYS
        )
    
        st.subheader("Hub - Location")
        st.dataframe(hub, use_container_width=True)
    
        st.subheader("Vendor")
        st.dataframe(vendor, use_container_width=True)
    
        st.subheader("Client/QRT")
        st.dataframe(client, use_container_width=True)
    
    # ---------- MONTHLY ----------
    with mtab:
    
        month_start = latest_date.replace(day=1)
    
        monthly = df[
            df["trip_date"].between(month_start, latest_date)
        ]
    
        hub, vendor, client = analyse_period(
            monthly,
            df,
            MONTHLY_ACTIVE_DAYS
        )
    
        st.subheader("Hub - Location")
        st.dataframe(hub, use_container_width=True)
    
        st.subheader("Vendor")
        st.dataframe(vendor, use_container_width=True)
    
        st.subheader("Client/QRT")
        st.dataframe(client, use_container_width=True)
    # ==============================
    # FOOTER
    # ==============================
    st.divider()
    st.caption(
        f"Dashboard is based on GPS data uploaded till "
        f"{latest_date.strftime('%d-%b-%Y')}."
        )
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
