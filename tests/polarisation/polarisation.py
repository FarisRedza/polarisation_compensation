import pymysql
import pandas as pd

# Database connection details
DB_HOST = "localhost"
DB_USER = "user"
DB_PASSWORD = "password"
DB_NAME = "polarisation"
TABLE_NAME = "sample"

# Path to the CSV file
csv_file = "data/Sample.csv"

connection = pymysql.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME
)

cursor = connection.cursor()

create_table_query = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    Time DATETIME,
    Elapsed_Time VARCHAR(20),
    Normalized_s_1 FLOAT,
    Normalized_s_2 FLOAT,
    Normalized_s_3 FLOAT,
    S_0_mW FLOAT,
    S_1_mW FLOAT,
    S_2_mW FLOAT,
    S_3_mW FLOAT,
    Azimuth_deg FLOAT,
    Ellipticity_deg FLOAT,
    DOP_pct FLOAT,
    DOCP_pct FLOAT,
    DOLP_pct FLOAT,
    Power_mW FLOAT,
    Pol_Power_mW FLOAT,
    Unpol_Power_mW FLOAT,
    Power_dBm FLOAT,
    Pol_Power_dBm FLOAT,
    Unpol_Power_dBm FLOAT,
    Power_Split_Ratio FLOAT,
    Phase_Difference_deg FLOAT,
    Warning VARCHAR(255)
);
"""
cursor.execute(create_table_query)
connection.commit()

# Step 1: Read CSV and find the header row
with open(csv_file, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Find the header row (assumed to be the first line containing "Time[date hh:mm:ss]")
for i, line in enumerate(lines):
    if "Time[date hh:mm:ss]" in line:
        header_index = i
        break

# Read the actual data into a DataFrame
df = pd.read_csv(csv_file, skiprows=header_index, delimiter=";", encoding="utf-8")


# Convert column names to match database column names (optional)
df.columns = [col.replace("[", "").replace("]", "").replace("°", "deg").replace("%", "pct").replace(" ", "_") for col in df.columns]

# Convert NaN values to None (NULL in SQL)
df = df.where(pd.notna(df), None)

# Create an INSERT query dynamically
columns = ", ".join(df.columns)
placeholders = ", ".join(["%s"] * len(df.columns))
insert_query = f"INSERT INTO {TABLE_NAME} ({columns}) VALUES ({placeholders})"

# Insert data row by row
for _, row in df.iterrows():
    cursor.execute(insert_query, tuple(row))

# Commit changes and close the connection
connection.commit()
cursor.close()
connection.close()

print("CSV data imported successfully!")