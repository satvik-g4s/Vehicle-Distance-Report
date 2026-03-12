#Finalised
import streamlit as st
import pandas as pd
from supabase import create_client
import time
from io import BytesIO
import io

st.set_page_config(layout="wide")

st.set_page_config(
    page_title="Vehicle Tracker",
    page_icon="favicon-16x16.png"
)

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

    st.header("Vehicles Dashboard")

    DAILY_DISTANCE_THRESHOLD = 5
    WEEKLY_ACTIVE_DAYS = 4
    MONTHLY_ACTIVE_DAYS = 20

    vehicles = load_vehicle_master()
    master = fetch_all_gps()

    if vehicles is None:
        st.warning("Vehicle master not uploaded.")
        st.stop()

    if master.empty:
        st.warning("GPS database empty.")
        st.stop()

    master["trip_date"] = pd.to_datetime(master["trip_date"], errors="coerce")
    master["plate_number"] = master["plate_number"].apply(normalize_plate)

    vehicles["plate_number"] = vehicles["plate_number"].apply(normalize_plate)

    # ---------------- FILTER VEHICLES ----------------

    vehicles["GPS"] = vehicles["GPS"].astype(str).str.strip().str.upper()

    vehicles = vehicles[
        (vehicles["GPS"] == "YES") &
        (~vehicles["Client/QRT"].astype(str).str.contains("US Embassy", case=False, na=False))
    ].copy()

    # merge vehicle master + gps
    df = pd.merge(
        vehicles,
        master,
        on="plate_number",
        how="left"
    )

    latest_date = master["trip_date"].dropna().max()

    if pd.isna(latest_date):
        st.warning("No valid trip dates found.")
        st.stop()

    # ---------------- DASHBOARD FUNCTION ----------------

    def show_dashboard(merged, prefix, extra_col=None):

        total = vehicles["plate_number"].nunique()

        active_total = merged[merged["status"] == "Active"]["plate_number"].nunique()
        inactive_total = merged[merged["status"] == "Inactive"]["plate_number"].nunique()
        nodata_total = merged[merged["status"] == "No Data"]["plate_number"].nunique()

        k1, k2, k3, k4 = st.columns(4)

        k1.metric("GPS Available", total)
        k2.metric("Active", active_total)
        k3.metric("Inactive", inactive_total)
        k4.metric("No Data", nodata_total)

        st.divider()

        with st.container(border=True):

            st.markdown("### Filters")

            f1, f2, f3, f4 = st.columns(4)

            with f1:
                hub_filter = st.selectbox(
                    "Hub",
                    ["All"] + sorted(merged["Hub Name"].dropna().unique()),
                    key=f"{prefix}_hub"
                )

            with f2:
                location_filter = st.selectbox(
                    "Location",
                    ["All"] + sorted(merged["Location"].dropna().unique()),
                    key=f"{prefix}_location"
                )

            with f3:
                client_filter = st.selectbox(
                    "Client",
                    ["All"] + sorted(merged["Client/QRT"].dropna().unique()),
                    key=f"{prefix}_client"
                )

            with f4:
                vendor_filter = st.selectbox(
                    "Vendor",
                    ["All"] + sorted(merged["Vendor Name"].dropna().unique()),
                    key=f"{prefix}_vendor"
                )

        filtered = merged.copy()

        if hub_filter != "All":
            filtered = filtered[filtered["Hub Name"] == hub_filter]

        if location_filter != "All":
            filtered = filtered[filtered["Location"] == location_filter]

        if client_filter != "All":
            filtered = filtered[filtered["Client/QRT"] == client_filter]

        if vendor_filter != "All":
            filtered = filtered[filtered["Vendor Name"] == vendor_filter]

        st.divider()

        active = filtered[filtered["status"] == "Active"]
        inactive = filtered[filtered["status"] == "Inactive"]
        nodata = filtered[filtered["status"] == "No Data"]

        cols = [
            "Hub Name",
            "Location",
            "Vendor Name",
            "Client/QRT",
            "plate_number"
        ]

        if extra_col:
            cols.append(extra_col)

        c1, c2, c3 = st.columns(3)

        with c1:
            with st.container(border=True):
                st.metric("Active", active["plate_number"].nunique())
                st.dataframe(
                    active[cols],
                    width="stretch",
                    height=280,
                    hide_index=True
                )

        with c2:
            with st.container(border=True):
                st.metric("Inactive", inactive["plate_number"].nunique())
                st.dataframe(
                    inactive[cols],
                    width="stretch",
                    height=280,
                    hide_index=True
                )

        with c3:
            with st.container(border=True):
                st.metric("No Data", nodata["plate_number"].nunique())
                st.dataframe(
                    nodata[cols],
                    width="stretch",
                    height=280,
                    hide_index=True
                )

    # ---------------- PERIOD TABS ----------------

    dtab, wtab, mtab = st.tabs(["Daily", "Weekly", "Monthly"])

    # ---------------- DAILY ----------------

    with dtab:

        selected_date = st.date_input(
            "Select Date",
            value=latest_date.date(),
            key="daily_date"
        )

        selected_date = pd.Timestamp(selected_date)

        st.subheader(f"Daily Status — {selected_date.strftime('%d %b %Y')}")

        gps_master = vehicles[
            ["plate_number","Hub Name","Location","Vendor Name","Client/QRT"]
        ]

        daily = df[df["trip_date"] == selected_date].copy()

        daily["status"] = "Inactive"
        daily.loc[
            daily["distance"] >= DAILY_DISTANCE_THRESHOLD,
            "status"
        ] = "Active"

        daily["KM"] = daily["distance"]

        merged = gps_master.merge(
            daily[["plate_number","status","KM"]],
            on="plate_number",
            how="left"
        )

        merged["status"] = merged["status"].fillna("No Data")
        merged["KM"] = merged["KM"].fillna(0)

        show_dashboard(merged, "daily", extra_col="KM")

    # ---------------- WEEKLY ----------------

    with wtab:

        df["week_start"] = df["trip_date"] - pd.to_timedelta(
            df["trip_date"].dt.weekday,
            unit="d"
        )

        df["week_end"] = df["week_start"] + pd.Timedelta(days=6)

        weeks = (
            df[["week_start","week_end"]]
            .dropna()
            .drop_duplicates()
            .sort_values("week_start")
        )

        weeks["label"] = (
            weeks["week_start"].dt.strftime("%d %b %Y")
            + " - "
            + weeks["week_end"].dt.strftime("%d %b %Y")
        )

        selected_week = st.selectbox(
            "Select Week",
            weeks["label"],
            index=len(weeks)-1,
            key="weekly_select"
        )

        week_row = weeks[weeks["label"] == selected_week].iloc[0]

        week_start = week_row["week_start"]
        week_end = week_row["week_end"]

        st.subheader(f"Weekly Status — {selected_week}")

        weekly = df[df["trip_date"].between(week_start, week_end)].copy()

        gps_master = vehicles[
            ["plate_number","Hub Name","Location","Vendor Name","Client/QRT"]
        ]

        weekly["active_flag"] = weekly["distance"] >= DAILY_DISTANCE_THRESHOLD

        active_days = (
            weekly.groupby("plate_number")["active_flag"]
            .sum()
            .reset_index()
        )

        active_days.rename(
            columns={"active_flag": "Active Days"},
            inplace=True
        )

        active_days["status"] = "Inactive"

        active_days.loc[
            active_days["Active Days"] >= WEEKLY_ACTIVE_DAYS,
            "status"
        ] = "Active"

        merged = gps_master.merge(
            active_days[["plate_number","status","Active Days"]],
            on="plate_number",
            how="left"
        )

        merged["status"] = merged["status"].fillna("No Data")
        merged["Active Days"] = merged["Active Days"].fillna(0)

        show_dashboard(merged, "weekly", extra_col="Active Days")

    # ---------------- MONTHLY ----------------

    with mtab:

        df["month"] = df["trip_date"].dt.to_period("M")

        months = sorted(df["month"].dropna().unique())

        month_labels = [m.strftime("%b %Y") for m in months]

        selected_month = st.selectbox(
            "Select Month",
            month_labels,
            index=len(month_labels)-1,
            key="month_select"
        )

        month_period = pd.Period(selected_month)

        month_start = month_period.start_time
        month_end = month_period.end_time

        st.subheader(f"Monthly Status — {selected_month}")

        monthly = df[
            df["trip_date"].between(month_start, month_end)
        ].copy()

        gps_master = vehicles[
            ["plate_number","Hub Name","Location","Vendor Name","Client/QRT"]
        ]

        monthly["active_flag"] = monthly["distance"] >= DAILY_DISTANCE_THRESHOLD

        active_days = (
            monthly.groupby("plate_number")["active_flag"]
            .sum()
            .reset_index()
        )

        active_days.rename(
            columns={"active_flag": "Active Days"},
            inplace=True
        )

        active_days["status"] = "Inactive"

        active_days.loc[
            active_days["Active Days"] >= MONTHLY_ACTIVE_DAYS,
            "status"
        ] = "Active"

        merged = gps_master.merge(
            active_days[["plate_number","status","Active Days"]],
            on="plate_number",
            how="left"
        )

        merged["status"] = merged["status"].fillna("No Data")
        merged["Active Days"] = merged["Active Days"].fillna(0)

        show_dashboard(merged, "monthly", extra_col="Active Days")

    st.divider()

    st.caption(f"Data till {latest_date.strftime('%d-%b-%Y')}")
    st.caption(f"Daily Active ≥ {DAILY_DISTANCE_THRESHOLD} Km")
    st.caption(f"Weekly Active ≥ {WEEKLY_ACTIVE_DAYS} days")
    st.caption(f"Monthly Active ≥ {MONTHLY_ACTIVE_DAYS} days")
    st.caption("US Embassy excluded")    
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
            time.sleep(2.5)
            st.rerun()
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
            st.rerun()
with tab4:
    st.markdown("""
    ### Dashboard Guidelines
    
    #### Vehicle Activity Rules
    • **Daily Active:** A vehicle is considered *Active* if it has travelled **more than 5 KM in a day**.  
    
    • **Weekly Active:** A vehicle is considered *Active* if it was active for **4 or more days in the current week**.  
    
    • **Monthly Active:** A vehicle is considered *Active* if it was active for **20 or more days in the current month**.  


    
    #### Weekly & Monthly Calculation Notes
    
    • **Weekly calculations start from Monday** (first day of the week).  
    • **Monthly calculations start from the 1st day of the month**.  
    
    Because of this:
    
    • Vehicles may appear **Inactive during the first 3 days of a new week**.  
    • Vehicles may appear **Inactive during the first 19 days of a new month**.
    

    
    #### Data Accuracy Note
    
    Some discrepancies may occur if the **plate numbers received in GPS data do not exactly match the plate numbers in the Vehicle Master**.  
    Ensure that plate numbers in uploaded files match the master data to maintain accurate reporting.



    #### Data Upload Instructions
    
    • **Cautio Data:** Upload in **CSV format only**.  
    • **MapMyIndia Data:** Upload in **Excel (.xlsx) format only**.  
    ⚠ Please upload the files in their **respective upload sections** and **do not change the format or interchange the files**.

        
    The **Vehicle Master** file contains the complete list of vehicles and related details.  
    Upload a new Vehicle Master **only if the vehicle details have changed**.
    
    The column order must be exactly as follows:
    S.No, Lease/Rental, Type, Hub Name, Location, Client/QRT, plate_number, Vehicle Contract Status, Make, Vendor Name, Lease Start, Contrat End/Extension, Expiring Year, Lease Tenure, Lease Mileage, Billing Company, Monthly EMI, ADAS, GPS

    
    """)


    
