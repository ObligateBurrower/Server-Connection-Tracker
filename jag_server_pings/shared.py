import pandas as pd
from pathlib import Path

app_dir = Path(__file__).parent

# Load the traceroute CSV
df = pd.read_csv(app_dir / "traceroute_data.csv")

# Convert any necessary columns for later use
df['Date'] = pd.to_datetime(df['Date'], format='%Y-%m-%d')
df['Time'] = pd.to_datetime(df['Time'], format='%H:%M:%S').dt.time
