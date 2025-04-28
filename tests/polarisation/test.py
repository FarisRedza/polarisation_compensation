import csv

import pymysql

# Database connection details
DB_HOST = "localhost"
DB_USER = "user"
DB_PASSWORD = "password"
DB_NAME = "polarisation"
TABLE_NAME = "full_sweep"
CSV_FILE = "data/720.csv"  # Update with your actual file path

# Connect to MariaDB
conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
cursor = conn.cursor()

# Create table if not exists
create_table_query = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    id INT AUTO_INCREMENT PRIMARY KEY,
    Time DATETIME,
    Elapsed_Time VARCHAR(20),
    Normalized_S_1 FLOAT,
    Normalized_S_2 FLOAT,
    Normalized_S_3 FLOAT,
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
    Warning VARCHAR(20)
);
"""
cursor.execute(create_table_query)
conn.commit()

# Read and insert CSV data
with open(CSV_FILE, newline='', encoding='utf-8') as csvfile:
    reader = csv.reader(csvfile, delimiter=';')
    rows = list(reader)

# Find the first data row (skip metadata)
for i, line in enumerate(rows):
    if "Time[date hh:mm:ss] " in line:
        header_index = i
        break

# Insert data into table
insert_query = f"""
INSERT INTO {TABLE_NAME} (
    Time,
    Elapsed_Time,
    Normalized_S_1,
    Normalized_S_2,
    Normalized_S_3,
    S_0_mW,
    S_1_mW,
    S_2_mW,
    S_3_mW,
    Azimuth_deg,
    Ellipticity_deg,
    DOP_pct,
    DOCP_pct,
    DOLP_pct,
    Power_mW,
    Pol_Power_mW,
    Unpol_Power_mW,
    Power_dBm,
    Pol_Power_dBm,
    Unpol_Power_dBm,
    Power_Split_Ratio,
    Phase_Difference_deg,
    Warning
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
"""
for row in rows[header_index+1:]:
    Time, Elapsed_Time, Normalized_S_1, Normalized_S_2, Normalized_S_3, S_0_mW, S_1_mW, S_2_mW, S_3_mW, Azimuth_deg, Ellipticity_deg, DOP_pct, DOCP_pct, DOLP_pct, Power_mW, Pol_Power_mW, Unpol_Power_mW, Power_dBm, Pol_Power_dBm, Unpol_Power_dBm, Power_Split_Ratio, Phase_Difference_deg, Warning = row
    cursor.execute(insert_query, (
        Time,
        Elapsed_Time,
        float(Normalized_S_1),
        float(Normalized_S_2),
        float(Normalized_S_3),
        float(S_0_mW),
        float(S_1_mW),
        float(S_2_mW),
        float(S_3_mW),
        float(Azimuth_deg),
        float(Ellipticity_deg),
        float(DOP_pct),
        float(DOCP_pct),
        float(DOLP_pct),
        float(Power_mW),
        float(Pol_Power_mW),
        float(Unpol_Power_mW),
        float(Power_dBm),
        float(Pol_Power_dBm),
        float(Unpol_Power_dBm),
        float(Power_Split_Ratio),
        float(Phase_Difference_deg),
        Warning if Warning != "" else None
))

conn.commit()
cursor.close()
conn.close()

print("CSV data imported successfully.")
