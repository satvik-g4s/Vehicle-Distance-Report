import streamlit as st
import pandas as pd
from supabase import create_client
import io

st.set_page_config(layout="wide")
st.title("GPS Distance Management")

# =====================================================
# SUPABASE CONNECTION
# =====================================================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =====================================================
# LOAD VEHICLE MASTER FROM STORAGE
# =====================================================
@st.cache_data
def load_vehicle_master():

    files = supabase.storage.from_("Vehicles").list()

    if len(files) == 0:
        return pd.DataFrame()

    latest_file = sorted(
        files,
        key=lambda x: x["created_at"],
        reverse=True
    )[0]["name"]

    file_bytes = supabase.storage \
        .from_("Vehicles") \
        .download(latest_file)

    vehicles = pd.read_excel(
        io.BytesIO(file_bytes),
        usecols="A:S"
    )

    vehicles.columns = vehicles.columns.str.strip()

    vehicles.rename(
        columns={"Reg. Vehicle Number": "plate_number"},
        inplace=True
    )

    vehicles["plate_number"] = (
        vehicles["plate_number"]
        .astype(str)
        .str.strip()
    )

    return vehicles


# =====================================================
# TABS
# =====================================================
tab1, tab2, tab3 = st.tabs(
    ["📥 Download Report",
     "⬆ Update Data",
     "🚗 Vehicles Data"]
)

# =====================================================
# TAB 1 — DOWNLOAD REPORT
# =====================================================
with tab1:

    if st.button("Fetch Existing Master Report"):

        gps = pd.DataFrame(
            supabase.table("gps_distance")
            .select("*")
            .execute().data
        )

        if gps.empty:
            st.warning("No GPS data available")
            st.stop()

        vehicles = load_vehicle_master()

        gps["plate_number"] = gps["plate_number"].astype(str).str.strip()
        gps["trip_date"] = pd.to_datetime(gps["trip_date"])

        master = pd.merge(
            vehicles,
            gps,
            how="left",
            on="plate_number"
        )

        master["Month"] = master["trip_date"].dt.strftime("%b-%Y")
        master["MonthOrder"] = master["trip_date"].dt.to_period("M")

        vehicle_cols = vehicles.columns.tolist()

        output = io.BytesIO()

        with pd.ExcelWriter(output, engine="openpyxl") as writer:

            for month, df_month in (
                master.sort_values("MonthOrder")
                .groupby("Month")
            ):

                pivot = df_month.pivot_table(
                    index=vehicle_cols,
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

                pivot.to_excel(
                    writer,
                    sheet_name=month,
                    index=False
                )

        st.download_button(
            "Download Master Report",
            output.getvalue(),
            "GPS_Master_Report.xlsx"
        )

# =====================================================
# TAB 2 — UPDATE GPS DATA
# =====================================================
with tab2:

    uploaded_file_mmi = st.file_uploader(
        "Upload MapMyIndia Excel",
        type=["xlsx"]
    )

    uploaded_file_cautio = st.file_uploader(
        "Upload Cautio CSV",
        type=["csv"]
    )

    if st.button("Run Update"):

        frames = []

        # ---------- MMI ----------
        if uploaded_file_mmi:

            mmi = pd.read_excel(
                uploaded_file_mmi,
                header=5,
                usecols=["Device","Date","Distance (km)"]
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
                columns={"Device":"plate_number"},
                inplace=True
            )

            mmi.columns = [
                c.strftime("%d-%m-%Y")
                if isinstance(c,pd.Timestamp)
                else c
                for c in mmi.columns
            ]

            frames.append(mmi)

        # ---------- CAUTIO ----------
        if uploaded_file_cautio:

            cautio = pd.read_csv(uploaded_file_cautio)

            date_cols = pd.to_datetime(
                cautio.columns,
                format="%d-%m-%Y",
                errors="coerce"
            ).notna()

            cautio = cautio.loc[
                :,["plate_number"]
                + list(cautio.columns[date_cols])
            ]

            frames.append(cautio)

        if not frames:
            st.warning("Upload at least one file")
            st.stop()

        combine = pd.concat(frames, ignore_index=True)

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

        upload_df.dropna(inplace=True)

        supabase.table("gps_distance")\
            .upsert(
                upload_df.to_dict("records"),
                ignore_duplicates=True
            ).execute()

        st.success("GPS Data Updated ✅")

# =====================================================
# TAB 3 — VEHICLE MASTER UPDATE
# =====================================================
with tab3:

    st.subheader("Upload / Replace Vehicle Master")

    vehicle_upload = st.file_uploader(
        "Upload Vehicles Excel",
        type=["xlsx"]
    )

    if vehicle_upload:

        supabase.storage \
            .from_("Vehicles") \
            .upload(
                path=vehicle_upload.name,
                file=vehicle_upload.getvalue(),
                file_options={"upsert": True}
            )

        st.cache_data.clear()

        st.success("Vehicle Master Updated ✅")

    files = supabase.storage.from_("Vehicles").list()

    st.write("Files currently in Vehicles bucket:")
    st.write([f["name"] for f in files])
