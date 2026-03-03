import streamlit as st
import pandas as pd
from supabase import create_client
from io import BytesIO
import io

# ======================================================
# PAGE CONFIG
# ======================================================
st.set_page_config(
    page_title="Vehicle Distance Report",
    layout="wide"
)

# ======================================================
# CORPORATE THEME
# ======================================================
st.markdown("""
<style>

/* Main background */
.stApp {
    background-color: #f4f6f9;
}

/* Headers */
h1, h2, h3 {
    color: #1f2937;
    font-weight: 600;
}

/* Metric cards */
div[data-testid="stMetric"] {
    background-color: white;
    padding: 15px;
    border-radius: 10px;
    border-left: 5px solid #1f4e79;
    box-shadow: 0px 2px 6px rgba(0,0,0,0.05);
}

/* DataFrames */
[data-testid="stDataFrame"] {
    border-radius: 10px;
    border: 1px solid #e5e7eb;
}

/* Buttons */
.stButton > button {
    background-color: #1f4e79;
    color: white;
    border-radius: 6px;
    font-weight: 500;
}
.stButton > button:hover {
    background-color: #163a5c;
    color: white;
}

/* Active / Inactive / No Data boxes */
.active-box {
    background-color: #e6f4ea;
    border-left: 6px solid #1e7e34;
    padding: 15px;
    border-radius: 10px;
}
.inactive-box {
    background-color: #fdecea;
    border-left: 6px solid #c82333;
    padding: 15px;
    border-radius: 10px;
}
.nodata-box {
    background-color: #fff4e5;
    border-left: 6px solid #ff9800;
    padding: 15px;
    border-radius: 10px;
}

</style>
""", unsafe_allow_html=True)

# ======================================================
# PASSWORD
# ======================================================
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Enter Password", type="password",
                      on_change=password_entered, key="password")
        st.stop()

    elif not st.session_state["password_correct"]:
        st.text_input("Enter Password", type="password",
                      on_change=password_entered, key="password")
        st.error("Incorrect Password")
        st.stop()

check_password()

# ======================================================
# TITLE
# ======================================================
st.title("Vehicle Distance Report")
st.markdown("### Corporate Fleet Monitoring Dashboard")

# ======================================================
# SUPABASE
# ======================================================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

VEHICLE_FILE_PATH = "vehicles/current_vehicles.xlsx"

# ======================================================
# HELPERS
# ======================================================
def normalize_plate(x):
    if pd.isna(x):
        return x
    return str(x).strip().upper().replace(" ", "").replace("-", "")

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
        vehicle_bytes = supabase.storage.from_("app-data").download(VEHICLE_FILE_PATH)
        vehicles = pd.read_excel(BytesIO(vehicle_bytes), usecols="A:S")
        vehicles = vehicles.rename(columns={"Reg. Vehicle Number": "plate_number"})
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

    df = pd.merge(vehicles, master, on="plate_number", how="left")
    return df

# ======================================================
# TABS
# ======================================================
tab1, tab2, tab3, tab4 = st.tabs(
    ["Dashboard", "Fetch Report", "Update Data", "Guidelines"]
)

# ======================================================
# DASHBOARD
# ======================================================
with tab1:

    st.header("Fleet GPS Dashboard")

    DAILY_DISTANCE_THRESHOLD = 5
    WEEKLY_ACTIVE_DAYS = 4

    df = load_dashboard_data()

    if df is None or df.empty:
        st.warning("Upload vehicle master & GPS data first.")
        st.stop()

    df = df[(df["GPS"] == "Yes") &
            (df["Client/QRT"] != "US Embassy")].copy()

    latest_date = df["trip_date"].max()

    dtab, wtab = st.tabs(["Daily", "Weekly"])

    def show_dashboard(merged):

        total = merged["plate_number"].nunique()
        active_total = merged[merged["status"] == "Active"]["plate_number"].nunique()
        inactive_total = merged[merged["status"] == "Inactive"]["plate_number"].nunique()
        nodata_total = merged[merged["status"] == "No Data"]["plate_number"].nunique()

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Eligible Vehicles", total)
        k2.metric("Active Vehicles", active_total)
        k3.metric("Inactive Vehicles", inactive_total)
        k4.metric("No Data Vehicles", nodata_total)

        st.divider()

        active = merged[merged["status"] == "Active"]
        inactive = merged[merged["status"] == "Inactive"]
        nodata = merged[merged["status"] == "No Data"]

        c1, c2, c3 = st.columns(3)

        with c1:
            st.markdown('<div class="active-box">', unsafe_allow_html=True)
            st.metric("Active", active["plate_number"].nunique())
            st.dataframe(active, use_container_width=True, height=300)
            st.markdown('</div>', unsafe_allow_html=True)

        with c2:
            st.markdown('<div class="inactive-box">', unsafe_allow_html=True)
            st.metric("Inactive", inactive["plate_number"].nunique())
            st.dataframe(inactive, use_container_width=True, height=300)
            st.markdown('</div>', unsafe_allow_html=True)

        with c3:
            st.markdown('<div class="nodata-box">', unsafe_allow_html=True)
            st.metric("No Data", nodata["plate_number"].nunique())
            st.dataframe(nodata, use_container_width=True, height=300)
            st.markdown('</div>', unsafe_allow_html=True)

    # ---------------- DAILY ----------------
    with dtab:

        daily = df[df["trip_date"] == latest_date].copy()

        gps_master = df[
            ["plate_number", "Hub Name", "Location",
             "Vendor Name", "Client/QRT"]
        ].drop_duplicates()

        received = daily.copy()
        received["status"] = "Inactive"
        received.loc[
            received["distance"] >= DAILY_DISTANCE_THRESHOLD,
            "status"
        ] = "Active"

        merged = gps_master.merge(
            received[["plate_number", "status"]],
            on="plate_number",
            how="left"
        )

        merged["status"] = merged["status"].fillna("No Data")
        show_dashboard(merged)

    # ---------------- WEEKLY ----------------
    with wtab:

        week_start = latest_date - pd.Timedelta(days=6)

        weekly = df[df["trip_date"].between(week_start, latest_date)].copy()
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

        gps_master = df[
            ["plate_number", "Hub Name", "Location",
             "Vendor Name", "Client/QRT"]
        ].drop_duplicates()

        merged = gps_master.merge(
            active_days[["plate_number", "status"]],
            on="plate_number",
            how="left"
        )

        merged["status"] = merged["status"].fillna("No Data")
        show_dashboard(merged)

    st.divider()
    st.caption(
        f"Dashboard based on GPS data uploaded till {latest_date.strftime('%d-%b-%Y')}"
    )
