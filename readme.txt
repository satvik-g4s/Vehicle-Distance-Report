Vehicle Distance MIS Tool
-------------------------

Overview
This application generates vehicle distance MIS reports and dashboards for G4S vehicles based on daily distance reports received from external systems.

The application is built using Streamlit and is deployed as a web application.

Platform
Streamlit – Opensource Python framework used to build lightweight data applications and dashboards accessible through a web browser.
Supabase - Postgres development platform, used for database.

Current Deployment
The application is currently deployed on Streamlit Cloud.

Code Structure
main.py
Contains the main application logic including:
- File uploads
- Data processing
- Dashboard generation
- Output export

Database
The database is hosted on Supabase (PostgreSQL) and is currently under the developer organization email account.

Tables Stored in Database

1. vehicle_distance
Contains vehicle-wise distance travelled data stored historically till date.

The application uses a PostgreSQL database hosted on Supabase. The primary table used is vehicle_distance, which stores historical vehicle distance records. The table contains three columns: plate_number (text) representing the vehicle registration number, trip_date (date) representing the date of the trip, and distance (numeric) representing the distance travelled by the vehicle in kilometers. This table maintains vehicle-wise distance data historically and is updated whenever new daily distance reports are processed by the application.

2. vehicle_master
Contains master data for all vehicles currently active with G4S.


Processing Logic

1. Employees upload daily vehicle distance reports received from:
   - Cautio
   - MapMyIndia

2. The application processes the uploaded files and maps the data with the G4S vehicle master.

3. The processed data is used to:
   - Update vehicle distance records
   - Generate dashboards and MIS reports

Deployment

If required, the application can be deployed on:
- Internal company server
- Cloud VM
- Any environment supporting Python and Streamlit

Dependencies
- streamlit
- pandas
- numpy
- supabase client (if used)

Notes
All necessary configuration and connection details are handled within the application environment.
