import sys
import pathlib
import csv

import numpy
import matplotlib
import matplotlib.pyplot

matplotlib.use('GTK4Agg')

file_name = 'multiple_overpass-pol_control_after-h_north.csv'
file_path = pathlib.Path(pathlib.Path.cwd(),'tests','hogs','data',file_name)

def elapsed_time_to_seconds(elapsed_time: str) -> float:
    print(elapsed_time)
    hrs, mins, s, ms = elapsed_time.split(':')
    hrs_s = float(hrs) * 60 * 60
    mins_s = float(mins) * 60
    ms_s = float(ms) / 1000
    total_s = hrs_s + mins_s + float(s) + ms_s
    return total_s

elapsed_time = []
normalised_s1 = []
normalised_s2 = []
normalised_s3 = []
azimuth = []
ellipticity = []
with open(file=file_path, mode='r', newline='') as csvfile:
    for i in range(8):
        next(csvfile)
    reader = csv.DictReader(csvfile, delimiter=';')
    print(reader.fieldnames)
    for row in reader:
        elapsed_time.append(
            elapsed_time_to_seconds(elapsed_time=row[' Elapsed Time [hh:mm:ss:ms]'])
        )
        # normalised_s1.append(float(row[' Normalized s 1 ']))
        # normalised_s2.append(float(row[' Normalized s 2 ']))
        # normalised_s3.append(float(row[' Normalized s 3 ']))
        azimuth.append(float(row[' Azimuth[°] ']))
        ellipticity.append(float(row[' Ellipticity[°] ']))

# matplotlib.pyplot.plot(
#     elapsed_time,
#     normalised_s1,
#     label='s1'
# )
# matplotlib.pyplot.plot(
#     elapsed_time,
#     normalised_s2,
#     label='s2'
# )
# matplotlib.pyplot.plot(
#     elapsed_time,
#     normalised_s3,
#     label='s3'
# )
matplotlib.pyplot.plot(
    elapsed_time,
    azimuth,
    label='Azimuth'
)
matplotlib.pyplot.plot(
    elapsed_time,
    ellipticity,
    label='Ellipticity'
)
matplotlib.pyplot.legend()
matplotlib.pyplot.xticks(numpy.linspace(min(elapsed_time),max(elapsed_time),30))
matplotlib.pyplot.xlabel(xlabel='Seconds (s)')
matplotlib.pyplot.grid(True)
matplotlib.pyplot.show()