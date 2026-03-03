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
    # KPI DISPLAY
    # =====================================
    def show_kpis(merged):

        total = merged["plate_number"].nunique()
        active = merged[merged["status"] == "Active"]["plate_number"].nunique()
        inactive = merged[merged["status"] == "Inactive"]["plate_number"].nunique()
        nodata = merged[merged["status"] == "No Data"]["plate_number"].nunique()

        c1, c2, c3, c4 = st.columns(4)

        c1.metric("Eligible GPS Vehicles", total)
        c2.metric("Active", active)
        c3.metric("Inactive", inactive)
        c4.metric("No Data Received", nodata)

        st.divider()

    # =====================================
    # DETAILED STATUS TABLES
    # =====================================
    def show_status_tables(df, group_cols, title):

        st.subheader(title)

        c1, c2, c3 = st.columns(3)

        with c1:
            st.markdown("### 🟢 Active")
            st.dataframe(
                df[df["status"] == "Active"]
                [group_cols + ["plate_number"]],
                use_container_width=True,
                height=300
            )

        with c2:
            st.markdown("### 🟠 Inactive")
            st.dataframe(
                df[df["status"] == "Inactive"]
                [group_cols + ["plate_number"]],
                use_container_width=True,
                height=300
            )

        with c3:
            st.markdown("### 🔴 No Data")
            st.dataframe(
                df[df["status"] == "No Data"]
                [group_cols + ["plate_number"]],
                use_container_width=True,
                height=300
            )

        st.divider()

    # =====================================
    # DAILY ANALYSIS
    # =====================================
    def analyse_daily(data, full_df):

        gps_master = (
            full_df[
                ["plate_number","Hub Name","Location",
                 "Vendor Name","Client/QRT"]
            ]
            .drop_duplicates()
        )

        received = data.copy()

        received["status"] = "Inactive"
        received.loc[
            received["distance"] > DAILY_DISTANCE_THRESHOLD,
            "status"
        ] = "Active"

        merged = gps_master.merge(
            received[["plate_number","status"]],
            on="plate_number",
            how="left"
        )

        merged["status"] = merged["status"].fillna("No Data")

        def summary(cols):
            if isinstance(cols,str):
                cols=[cols]

            return (
                merged.groupby(cols+["status"])
                ["plate_number"]
                .nunique()
                .unstack(fill_value=0)
                .reset_index()
            )

        return (
            summary(["Hub Name","Location"]),
            summary("Vendor Name"),
            summary("Client/QRT"),
            merged
        )

    # =====================================
    # WEEKLY / MONTHLY ANALYSIS
    # =====================================
    def analyse_period(data, full_df, required_days):

        gps_master = (
            full_df[
                ["plate_number","Hub Name","Location",
                 "Vendor Name","Client/QRT"]
            ]
            .drop_duplicates()
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
                columns=["plate_number","status"]
            )

        merged = gps_master.merge(
            active_days,
            on="plate_number",
            how="left"
        )

        merged["status"] = merged["status"].fillna("No Data")

        def summary(cols):
            if isinstance(cols,str):
                cols=[cols]

            return (
                merged.groupby(cols+["status"])
                ["plate_number"]
                .nunique()
                .unstack(fill_value=0)
                .reset_index()
            )

        return (
            summary(["Hub Name","Location"]),
            summary("Vendor Name"),
            summary("Client/QRT"),
            merged
        )

    # =====================================
    # PERIOD TABS
    # =====================================
    dtab, wtab, mtab = st.tabs(
        ["Daily","Weekly","Monthly"]
    )

    # ---------- DAILY ----------
    with dtab:

        daily = df[df["trip_date"] == latest_date]

        hub,vendor,client,merged = analyse_daily(
            daily, df
        )

        show_kpis(merged)

        col1, col2, col3 = st.columns(3)

        col1.subheader("Hub - Location")
        col1.dataframe(hub, use_container_width=True)

        col2.subheader("Vendor")
        col2.dataframe(vendor, use_container_width=True)

        col3.subheader("Client/QRT")
        col3.dataframe(client, use_container_width=True)

        st.divider()

        show_status_tables(
            merged,
            ["Hub Name","Location"],
            "📍 Vehicles by Hub & Location"
        )

        show_status_tables(
            merged,
            ["Vendor Name"],
            "🏢 Vehicles by Vendor"
        )

        show_status_tables(
            merged,
            ["Client/QRT"],
            "👤 Vehicles by Client/QRT"
        )

    # ---------- WEEKLY ----------
    with wtab:

        week_start = latest_date - pd.Timedelta(days=6)

        weekly = df[
            df["trip_date"].between(
                week_start,latest_date
            )
        ]

        hub,vendor,client,merged = analyse_period(
            weekly,df,WEEKLY_ACTIVE_DAYS
        )

        show_kpis(merged)

        col1, col2, col3 = st.columns(3)

        col1.subheader("Hub - Location")
        col1.dataframe(hub, use_container_width=True)

        col2.subheader("Vendor")
        col2.dataframe(vendor, use_container_width=True)

        col3.subheader("Client/QRT")
        col3.dataframe(client, use_container_width=True)

        st.divider()

        show_status_tables(
            merged,
            ["Hub Name","Location"],
            "📍 Vehicles by Hub & Location (Weekly)"
        )

        show_status_tables(
            merged,
            ["Vendor Name"],
            "🏢 Vehicles by Vendor (Weekly)"
        )

        show_status_tables(
            merged,
            ["Client/QRT"],
            "👤 Vehicles by Client/QRT (Weekly)"
        )

    # ---------- MONTHLY ----------
    with mtab:

        month_start = latest_date.replace(day=1)

        monthly = df[
            df["trip_date"].between(
                month_start,latest_date
            )
        ]

        hub,vendor,client,merged = analyse_period(
            monthly,df,MONTHLY_ACTIVE_DAYS
        )

        show_kpis(merged)

        col1, col2, col3 = st.columns(3)

        col1.subheader("Hub - Location")
        col1.dataframe(hub, use_container_width=True)

        col2.subheader("Vendor")
        col2.dataframe(vendor, use_container_width=True)

        col3.subheader("Client/QRT")
        col3.dataframe(client, use_container_width=True)

        st.divider()

        show_status_tables(
            merged,
            ["Hub Name","Location"],
            "📍 Vehicles by Hub & Location (Monthly)"
        )

        show_status_tables(
            merged,
            ["Vendor Name"],
            "🏢 Vehicles by Vendor (Monthly)"
        )

        show_status_tables(
            merged,
            ["Client/QRT"],
            "👤 Vehicles by Client/QRT (Monthly)"
        )

    # =====================================
    # FOOTER
    # =====================================
    st.divider()
    st.caption(
        f"Dashboard based on GPS data uploaded till "
        f"{latest_date.strftime('%d-%b-%Y')}"
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
    ### Yet to be Updated

    """)
