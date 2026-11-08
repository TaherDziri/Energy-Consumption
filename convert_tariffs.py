import pandas as pd
import os

# Read the Excel tariffs file
t = pd.read_excel(
    r"C:\Users\rahma\Desktop\Premiere  master\big data\PROJET\Energy-Consumption\data\Tariffs.xlsx"
)

# Save as CSV
out = r"C:\Users\rahma\Desktop\Premiere  master\big data\PROJET\Energy-Consumption\data\tariffs_2013.csv"
t.to_csv(out, index=False)

print(f"Saved {len(t)} rows to: {out}")
print(t.head(3).to_string())
print(f"\nColumns: {t.columns.tolist()}")