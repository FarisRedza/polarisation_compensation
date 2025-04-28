import pandas as pd
import matplotlib.pyplot as plt

csv_file = "data/Sample.csv"
df = pd.read_csv(csv_file, delimiter=';', skiprows=8, engine='python')

df.columns = [col.strip() for col in df.columns]

df['Elapsed Time [ms]'] = df['Elapsed Time [hh:mm:ss:ms]'].apply(
    lambda x: sum(float(t) * f for t, f in zip(x.split(':'), [3600000, 60000, 1000, 1]))
)

plt.figure(figsize=(10, 6))
plt.plot(df['Elapsed Time [ms]'], df['Normalized s 1'], label='$S_0$', marker='o')
plt.plot(df['Elapsed Time [ms]'], df['Normalized s 2'], label='$S_1$', marker='s')
plt.plot(df['Elapsed Time [ms]'], df['Normalized s 3'], label='$S_2$', marker='^')

plt.xlabel('Elapsed Time (ms)')
plt.ylabel('Normalised Stokes Parameters')
plt.legend()
plt.grid()
plt.show()
