import csv

import pymysql
import matplotlib.pyplot as plt
import numpy


# Database connection details
DB_HOST = "localhost"
DB_USER = "user"
DB_PASSWORD = "password"
DB_NAME = "polarisation"
TABLE_NAME = "full_sweep"

conn = pymysql.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME
)
cursor = conn.cursor()

x = 'Time'
y = 'Normalized_S_1'

cursor.execute(f'SELECT {x}, {y} FROM {TABLE_NAME}')

rows = cursor.fetchall()

# Close connection
cursor.close()
conn.close()

# Separate data into X and Y lists
x_values, y_values = zip(*rows)  # Unzips into two separate lists

# Plot the data
plt.figure(figsize=(8, 6))
plt.plot(x_values, y_values, marker='o', linestyle='-', color='b')  # Line plot with markers
plt.xlabel(x)
plt.ylabel(y)
plt.title(f"Plot of {y} vs {x}")
plt.grid(True)
plt.show()