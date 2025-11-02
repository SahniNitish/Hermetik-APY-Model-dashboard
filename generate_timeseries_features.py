"""
Phase 3: Time-Series Feature Generation
Generates daily features for each pool across 30 days
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
from pathlib import Path

print("="*80)
print("PHASE 3: TIME-SERIES FEATURE GENERATION")
print("="*80)

# Paths
DATA_DIR = Path("updater/static")
POOL_LOGS = DATA_DIR / "pool_logs_30d_2025-11-02.csv"
POOL_METADATA = DATA_DIR / "pool_metadata.csv"
OUTPUT_FILE = "pool_timeseries_features.csv"

print("\n📂 Loading pool metadata...")
pools_df = pd.read_csv(POOL_METADATA)
print(f"   Loaded {len(pools_df)} pools")
print(f"   ETH pools: {len(pools_df[pools_df['poolType'] == 'eth_paired'])}")
print(f"   Stablecoin pools: {len(pools_df[pools_df['poolType'] == 'stablecoin'])}")
print(f"   Other pools: {len(pools_df[pools_df['poolType'] == 'other'])}")

print("\n📊 Loading transaction data (this may take a few minutes)...")
print("   Reading in chunks to save memory...")

# Read in chunks to save memory
chunk_size = 500000
chunks = []
total_rows = 0

for i, chunk in enumerate(pd.read_csv(POOL_LOGS, chunksize=chunk_size)):
    total_rows += len(chunk)

    # Convert timestamp to datetime and extract date
    chunk['timestamp'] = pd.to_datetime(chunk['timestamp'])
    chunk['date'] = chunk['timestamp'].dt.date

    # Lowercase pool addresses for matching
    chunk['poolAddress'] = chunk['poolAddress'].str.lower()

    chunks.append(chunk)

    if (i + 1) % 5 == 0:
        print(f"   Processed {total_rows:,} transactions...")

# Combine chunks
print(f"\n   Combining {len(chunks)} chunks...")
logs_df = pd.concat(chunks, ignore_index=True)
print(f"✅ Loaded {len(logs_df):,} total transactions")

# Get date range
min_date = logs_df['date'].min()
max_date = logs_df['date'].max()
print(f"\n📅 Date range: {min_date} to {max_date} ({(max_date - min_date).days + 1} days)")

print("\n🔄 Grouping transactions by pool and date...")
# Group by pool and date to get daily transaction counts
daily_stats = logs_df.groupby(['poolAddress', 'date']).agg({
    'txHash': 'count',  # transaction count
    'sender': 'nunique'  # unique users
}).reset_index()

daily_stats.columns = ['poolAddress', 'date', 'tx_count', 'unique_users']

print(f"✅ Generated {len(daily_stats):,} pool-day combinations")

print("\n🔗 Merging with pool metadata...")
# Merge with pool metadata
daily_stats = daily_stats.merge(
    pools_df[['poolAddress', 'token0Symbol', 'token1Symbol', 'fee', 'poolType']],
    on='poolAddress',
    how='left'
)

print("\n📊 Calculating additional features...")

# Calculate fee percentage
daily_stats['fee_percentage'] = daily_stats['fee'].astype(float) / 1000000

# Create pool name
daily_stats['pool_name'] = daily_stats['token0Symbol'] + '/' + daily_stats['token1Symbol']

# Sort by pool and date
daily_stats = daily_stats.sort_values(['poolAddress', 'date']).reset_index(drop=True)

print("\n📈 Generating time-series features...")

# Group by pool and calculate rolling metrics
def calculate_rolling_features(group):
    """Calculate rolling window features for a pool"""

    # Sort by date
    group = group.sort_values('date')

    # 3-day rolling average of transactions
    group['tx_count_3d_avg'] = group['tx_count'].rolling(window=3, min_periods=1).mean()

    # 7-day rolling average of transactions
    group['tx_count_7d_avg'] = group['tx_count'].rolling(window=7, min_periods=1).mean()

    # 7-day volatility (std dev) of transactions
    group['tx_count_7d_std'] = group['tx_count'].rolling(window=7, min_periods=1).std()

    # Cumulative transaction count
    group['tx_count_cumulative'] = group['tx_count'].cumsum()

    # Days since first transaction
    group['days_since_start'] = (pd.to_datetime(group['date']) - pd.to_datetime(group['date'].iloc[0])).dt.days

    # Transaction growth rate (vs previous day)
    group['tx_growth_rate'] = group['tx_count'].pct_change()

    return group

print("   Applying rolling calculations...")
timeseries_df = daily_stats.groupby('poolAddress', group_keys=False).apply(calculate_rolling_features)

# Fill NaN values for growth rate with 0
timeseries_df['tx_growth_rate'] = timeseries_df['tx_growth_rate'].fillna(0)
timeseries_df['tx_count_7d_std'] = timeseries_df['tx_count_7d_std'].fillna(0)

print("\n💾 Preparing output...")

# Select columns for output
output_columns = [
    'poolAddress',
    'date',
    'pool_name',
    'token0Symbol',
    'token1Symbol',
    'fee',
    'fee_percentage',
    'poolType',
    'tx_count',
    'unique_users',
    'tx_count_3d_avg',
    'tx_count_7d_avg',
    'tx_count_7d_std',
    'tx_count_cumulative',
    'days_since_start',
    'tx_growth_rate'
]

output_df = timeseries_df[output_columns].copy()

# Add day number (1-30)
output_df['day_number'] = output_df.groupby('poolAddress').cumcount() + 1

print(f"\n✅ Generated features for {output_df['poolAddress'].nunique():,} pools")
print(f"   Total rows: {len(output_df):,}")
print(f"   Average days per pool: {len(output_df) / output_df['poolAddress'].nunique():.1f}")

# Save to CSV
print(f"\n💾 Saving to {OUTPUT_FILE}...")
output_df.to_csv(OUTPUT_FILE, index=False)

file_size_mb = os.path.getsize(OUTPUT_FILE) / 1024 / 1024
print(f"✅ Saved! File size: {file_size_mb:.2f} MB")

print("\n📊 Summary Statistics:")
print(f"   Pools with full 30 days: {(output_df.groupby('poolAddress').size() == 30).sum()}")
print(f"   Pools with 20+ days: {(output_df.groupby('poolAddress').size() >= 20).sum()}")
print(f"   Pools with 10+ days: {(output_df.groupby('poolAddress').size() >= 10).sum()}")

print("\n🏆 Top 10 Most Active Pools:")
top_pools = output_df.groupby(['poolAddress', 'pool_name', 'poolType'])['tx_count'].sum().nlargest(10)
for (addr, name, ptype), count in top_pools.items():
    print(f"   {name:20s} ({ptype:12s}) - {count:,} total txs")

print("\n📊 Sample Data (first 5 rows):")
print(output_df.head())

print("\n" + "="*80)
print("✅ PHASE 3 COMPLETE!")
print("="*80)
print(f"\n📁 Output file: {OUTPUT_FILE}")
print(f"📊 Total pools: {output_df['poolAddress'].nunique():,}")
print(f"📅 Date range: {output_df['date'].min()} to {output_df['date'].max()}")
print(f"🔢 Total rows: {len(output_df):,}")
print(f"\n🔜 Next: Phase 4 (Create target variables for training)")
