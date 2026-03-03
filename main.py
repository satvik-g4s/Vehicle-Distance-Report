import streamlit as st
import pandas as pd
from supabase import create_client
from io import BytesIO
import io

st.set_page_config(layout="wide")

# =====================================
# ADD COLOR STYLING (UI enhancement only)
# =====================================
st.markdown("""
<style>
    /* Main app background */
    .stApp {
        background-color: #f8f9fa;
    }
    /* Headers */
    h1, h2, h3, h4, h5, h6 {
        color: #2c3e50;
    }
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #e9ecef;
        border-radius: 4px 4px 0 0;
        padding: 10px 20px;
        color: #495057;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1f77b4;
        color: white;
    }
    /* Buttons */
    .stButton button {
        background-color: #1f77b4;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 0.5rem 1rem;
        font-weight: 500;
    }
    .stButton button:hover {
        background-color: #135a8f;
        color: white;
        border: none;
    }
    /* Metrics */
    [data-testid="stMetricValue"] {
        color: #1f77b4;
        font-weight: 600;
    }
    [data-testid="stMetricLabel"] {
        color: #6c757d;
    }
    /* Dataframes */
    .stDataFrame thead tr th {
        background-color: #1f77b4;
        color: white;
        font-weight: 500;
    }
    .stDataFrame tbody tr:nth-child(even) {
        background-color: #f2f2f2;
    }
    /* Containers with border */
    .stContainer [data-testid="stContainer"] {
        border: 1px solid #dee2e6;
        border-radius: 5px;
        padding: 1rem;
        background-color: white;
    }
    /* Dividers */
    hr {
        border-color: #dee2e6;
    }
    /* Alert boxes */
    .stAlert {
        border-radius: 4px;
    }
</style>
""", unsafe_allow_html=True)

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

def normalize_plate(x):
    if pd.isna(x):
        return x
    return (
        str(x)
        .strip()
        .upper()
        .replace(" ", "")
        .replace("-", "")
    )


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
    
@st.cache_data
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
        vehicles["plate_number"] = vehicles["plate_number"].apply(normalize_plate)

        return vehicles

    except:
        return None

def load_dashboard_data():

    vehicles = load_vehicle_master()
    master = fetch_all_gps()

    if vehicles is None or master.empty:
        return None

    master["trip_date"] = pd.to_datetime(master["trip_date"])
    master["plate_number"] = master["plate_number"].apply(normalize_plate)

    df = pd.merge(
        vehicles,
        master,
        on="plate_number",
        how="left"
    )

    return df        

with tab1:

    st.header("Fleet GPS Dashboard")

    # =====================================
    # CONFIGURABLE RULES
    # =====================================
    DAILY_DISTANCE_THRESHOLD = 5
    WEEKLY_ACTIVE_DAYS = 4
    MONTHLY_ACTIVE_DAYS = 15

    df = load_dashboard_data()

    if df is None or df.empty:
        st.warning("Upload vehicle master & GPS data first.")
        st.stop()

    # =====================================
    # FILTER ELIGIBLE VEHICLES
    # =====================================
    df = df[
        (df["GPS"] == "Yes") &
        (df["Client/QRT"] != "US Embassy")
    ].copy()

    latest_date = df["trip_date"].max()

    # =====================================
    # PERIOD TABS
    # =====================================
    dtab, wtab= st.tabs(["Daily", "Weekly"])

    # =====================================
    # STATUS PANEL FUNCTION
    # =====================================
    def show_dashboard(merged, prefix):
    
        # ---------------- OVERALL KPI (UNFILTERED) ----------------
        total = merged["plate_number"].nunique()
        active_total = merged[merged["status"] == "Active"]["plate_number"].nunique()
        inactive_total = merged[merged["status"] == "Inactive"]["plate_number"].nunique()
        nodata_total = merged[merged["status"] == "No Data"]["plate_number"].nunique()
    
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Eligible", total)
        k2.metric("Active", active_total)
        k3.metric("Inactive", inactive_total)
        k4.metric("No Data", nodata_total)
    
        st.divider()
    
        # ---------------- FILTER SECTION ----------------
        with st.container(border=True):
    
            st.markdown("### Filters")
    
            f1, f2, f3, f4 = st.columns(4)
    
            with f1:
                hub_filter = st.selectbox(
                    "Hub",
                    ["All"] + sorted(merged["Hub Name"].dropna().unique().tolist()),
                    key=f"{prefix}_hub"
                )
    
            with f2:
                location_filter = st.selectbox(
                    "Location",
                    ["All"] + sorted(merged["Location"].dropna().unique().tolist()),
                    key=f"{prefix}_location"
                )
    
            with f3:
                client_filter = st.selectbox(
                    "Client",
                    ["All"] + sorted(merged["Client/QRT"].dropna().unique().tolist()),
                    key=f"{prefix}_client"
                )
    
            with f4:
                vendor_filter = st.selectbox(
                    "Vendor",
                    ["All"] + sorted(merged["Vendor Name"].dropna().unique().tolist()),
                    key=f"{prefix}_vendor"
                )
    
        # ---------------- APPLY FILTERS ----------------
        filtered = merged.copy()
    
        if hub_filter != "All":
            filtered = filtered[filtered["Hub Name"] == hub_filter]
    
        if vendor_filter != "All":
            filtered = filtered[filtered["Vendor Name"] == vendor_filter]
    
        if client_filter != "All":
            filtered = filtered[filtered["Client/QRT"] == client_filter]
    
        if location_filter != "All":
            filtered = filtered[filtered["Location"] == location_filter]
        
        # ---------------- STATUS PANELS (FILTERED) ----------------
        active = filtered[filtered["status"] == "Active"]
        inactive = filtered[filtered["status"] == "Inactive"]
        nodata = filtered[filtered["status"] == "No Data"]
    
        c1, c2, c3 = st.columns(3)
    
        # -------- ACTIVE --------
        with c1:
            with st.container(border=True):
                st.metric("## Active", active["plate_number"].nunique())
    
                st.dataframe(
                    active[
                        ["Hub Name", "Location",
                         "Vendor Name", "Client/QRT", "plate_number"]
                    ].reset_index(drop=True),
                    width="stretch",
                    height=280
                )
    
        # -------- INACTIVE --------
        with c2:
            with st.container(border=True):
                st.metric("## Inactive", inactive["plate_number"].nunique())
    
                st.dataframe(
                    inactive[
                        ["Hub Name", "Location",
                         "Vendor Name", "Client/QRT", "plate_number"]
                    ].reset_index(drop=True),
                    width="stretch",
                    height=280
                )
    
        # -------- NO DATA --------
        with c3:
            with st.container(border=True):
                st.metric("## No Data", nodata["plate_number"].nunique())
    
                st.dataframe(
                    nodata[
                        ["Hub Name", "Location",
                         "Vendor Name", "Client/QRT", "plate_number"]
                    ].reset_index(drop=True),
                    width="stretch",
                    height=280
                )

    # =====================================
    # DAILY
    # =====================================
    with dtab:

        daily = df[df["trip_date"] == latest_date].copy()

        gps_master = df[
            ["plate_number","Hub Name","Location",
             "Vendor Name","Client/QRT"]
        ].drop_duplicates()

        received = daily.copy()
        received["status"] = "Inactive"
        received.loc[
            received["distance"] >= DAILY_DISTANCE_THRESHOLD,
            "status"
        ] = "Active"

        merged = gps_master.merge(
            received[["plate_number","status"]],
            on="plate_number",
            how="left"
        )

        merged["status"] = merged["status"].fillna("No Data")

        show_dashboard(merged, "daily")

    # =====================================
    # WEEKLY
    # =====================================
    with wtab:

        week_start = latest_date - pd.Timedelta(days=6)

        weekly = df[
            df["trip_date"].between(week_start, latest_date)
        ].copy()

        gps_master = df[
            ["plate_number","Hub Name","Location",
             "Vendor Name","Client/QRT"]
        ].drop_duplicates()

        weekly["active_flag"] = weekly["distance"] >= DAILY_DISTANCE_THRESHOLD

        active_days = (
            weekly.groupby("plate_number")["active_flag"]
            .sum()
            .reset_index()
        )

        active_days["status"] = "Inactive"
        active_days.loc[
            active_days["active_flag"] >= WEEKLY_ACTIVE_DAYS,
            "status"
        ] = "Active"

        merged = gps_master.merge(
            active_days[["plate_number","status"]],
            on="plate_number",
            how="left"
        )

        merged["status"] = merged["status"].fillna("No Data")

        show_dashboard(merged, "weekly")



    # =====================================
    # FOOTER
    # =====================================
    st.divider()
    st.caption(
        f"""
        Dashboard based on GPS data uploaded till {latest_date.strftime('%d-%b-%Y')}

        • Daily Active: > {DAILY_DISTANCE_THRESHOLD} Km  
        • Weekly Active: ≥ {WEEKLY_ACTIVE_DAYS} days  
        • Monthly Active: ≥ {MONTHLY_ACTIVE_DAYS} days  
        """
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
            upload_df["plate_number"] = upload_df["plate_number"].apply(normalize_plate)
            st.write("Uploading to database...")

            supabase.table("gps_distance") \
                .upsert(
                    upload_df.to_dict("records"),
                    ignore_duplicates=True
                ).execute()

            st.success("Database Updated ✅")
    st.subheader("Vehicle Master Upload")

    st.divider()


    uploaded_file_vehicles = st.file_uploader(
        "Upload Vehicle Master (xlsx) - Only to be updated when Vehicles data changed, not to be uploaded otherwise",
        type=["xlsx"]
    )

    if uploaded_file_vehicles:

        st.warning("⚠ Kindly update Vehicle Master only if data has changed.")
    
        confirm_update = st.button("Update Vehicle Master")
    
        if confirm_update:
    
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
                    {
                        "content-type":
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    }
                )
    
            # Clear cache so dashboard reloads new file
            load_vehicle_master.clear()
    
            st.success("Vehicle Master Updated Successfully ✅")
with tab4:            
    st.markdown("""
    ###Yet to be Added

    """)
