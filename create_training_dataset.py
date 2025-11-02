"""
Phase 4: Create Training Dataset with Target Variables
Adds future performance targets and splits into train/test
"""

import pandas as pd
import numpy as np
from datetime import timedelta

print("="*80)
print("PHASE 4: CREATE TRAINING DATASET")
print("="*80)

# Load time-series features
INPUT_FILE = "pool_timeseries_features.csv"
OUTPUT_TRAIN = "pool_training_data.csv"
OUTPUT_TEST = "pool_test_data.csv"
OUTPUT_FULL = "pool_full_dataset.csv"

print(f"\n📂 Loading time-series features from {INPUT_FILE}...")
df = pd.read_csv(INPUT_FILE)
df['date'] = pd.to_datetime(df['date'])

print(f"✅ Loaded {len(df):,} rows for {df['poolAddress'].nunique():,} pools")

print("\n🎯 Creating target variables...")
print("   Target: Predict transaction activity 3 and 7 days ahead")

# Sort by pool and date
df = df.sort_values(['poolAddress', 'date']).reset_index(drop=True)

def add_target_variables(group):
    """Add future targets for each pool"""

    # Target: transaction count 3 days ahead
    group['target_tx_3d_ahead'] = group['tx_count'].shift(-3)

    # Target: transaction count 7 days ahead
    group['target_tx_7d_ahead'] = group['tx_count'].shift(-7)

    # Target: average tx count over next 3 days
    group['target_tx_3d_avg_ahead'] = group['tx_count'].shift(-3).rolling(window=3, min_periods=1).mean()

    # Target: average tx count over next 7 days
    group['target_tx_7d_avg_ahead'] = group['tx_count'].shift(-7).rolling(window=7, min_periods=1).mean()

    return group

print("   Applying target calculations...")
df = df.groupby('poolAddress', group_keys=False).apply(add_target_variables)

print(f"✅ Created target variables")

# Calculate how many valid training samples we have
valid_3d = df['target_tx_3d_ahead'].notna().sum()
valid_7d = df['target_tx_7d_ahead'].notna().sum()

print(f"\n📊 Target Variable Statistics:")
print(f"   Valid 3-day targets: {valid_3d:,} rows")
print(f"   Valid 7-day targets: {valid_7d:,} rows")

print("\n✂️  Splitting into train/test sets...")

# Get the date range
min_date = df['date'].min()
max_date = df['date'].max()
total_days = (max_date - min_date).days + 1

print(f"   Date range: {min_date.date()} to {max_date.date()} ({total_days} days)")

# Split: Use last 7 days for testing, rest for training
test_cutoff_date = max_date - timedelta(days=6)

train_df = df[df['date'] < test_cutoff_date].copy()
test_df = df[df['date'] >= test_cutoff_date].copy()

# Remove rows with NaN targets from training set
train_df_clean = train_df.dropna(subset=['target_tx_3d_ahead', 'target_tx_7d_ahead'])

print(f"\n📊 Train/Test Split:")
print(f"   Training set: {len(train_df_clean):,} rows")
print(f"   Test set: {len(test_df):,} rows")
print(f"   Training pools: {train_df_clean['poolAddress'].nunique():,}")
print(f"   Test pools: {test_df['poolAddress'].nunique():,}")

print("\n💾 Saving datasets...")

# Save full dataset (with NaN targets)
df.to_csv(OUTPUT_FULL, index=False)
print(f"✅ Saved full dataset: {OUTPUT_FULL}")

# Save training set (clean, no NaN targets)
train_df_clean.to_csv(OUTPUT_TRAIN, index=False)
print(f"✅ Saved training set: {OUTPUT_TRAIN}")

# Save test set
test_df.to_csv(OUTPUT_TEST, index=False)
print(f"✅ Saved test set: {OUTPUT_TEST}")

print("\n📊 Training Set Summary:")
print(f"   Total rows: {len(train_df_clean):,}")
print(f"   Unique pools: {train_df_clean['poolAddress'].nunique():,}")
print(f"   Date range: {train_df_clean['date'].min().date()} to {train_df_clean['date'].max().date()}")

print("\n📊 Test Set Summary:")
print(f"   Total rows: {len(test_df):,}")
print(f"   Unique pools: {test_df['poolAddress'].nunique():,}")
print(f"   Date range: {test_df['date'].min().date()} to {test_df['date'].max().date()}")

print("\n🏆 Top 10 Pools by Average Daily Transactions:")
top_pools = train_df_clean.groupby(['pool_name', 'poolType'])['tx_count'].mean().nlargest(10)
for (name, ptype), avg_tx in top_pools.items():
    print(f"   {name:20s} ({ptype:12s}) - {avg_tx:,.0f} avg daily txs")

print("\n📋 Features for Nolan's Model:")
feature_columns = [
    'tx_count',
    'unique_users',
    'tx_count_3d_avg',
    'tx_count_7d_avg',
    'tx_count_7d_std',
    'tx_count_cumulative',
    'days_since_start',
    'tx_growth_rate',
    'fee_percentage',
    'poolType'  # categorical
]
print("   Input features:")
for i, feat in enumerate(feature_columns, 1):
    print(f"     {i}. {feat}")

print("\n   Target variables:")
print("     1. target_tx_3d_ahead (predict txs 3 days from now)")
print("     2. target_tx_7d_ahead (predict txs 7 days from now)")
print("     3. target_tx_3d_avg_ahead (predict avg txs over next 3 days)")
print("     4. target_tx_7d_avg_ahead (predict avg txs over next 7 days)")

print("\n📊 Sample Training Data:")
print(train_df_clean[['date', 'pool_name', 'tx_count', 'tx_count_7d_avg', 'target_tx_7d_ahead']].head(10))

print("\n" + "="*80)
print("✅ PHASE 4 COMPLETE!")
print("="*80)
print(f"\n📁 Output files:")
print(f"   - {OUTPUT_TRAIN} (for training Nolan's model)")
print(f"   - {OUTPUT_TEST} (for validation)")
print(f"   - {OUTPUT_FULL} (complete dataset)")
print(f"\n🔜 Next: Phase 5 (Package everything for Nolan)")
