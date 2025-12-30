#!/usr/bin/env python3
"""
MARCH-JUNE STABLECOIN DATASET CREATOR
====================================
Creates stablecoin-specialized datasets from March-June 2025 data,
optimized for stablecoin APY prediction modeling.
"""

import pandas as pd
import numpy as np
from pathlib import Path

def load_data():
    """Load the March-June dataset"""
    print("📂 Loading March-June 2025 dataset...")
    df = pd.read_csv('pool_march_june_dataset.csv')
    print(f"   Loaded {len(df):,} total rows")
    
    # Show pool type distribution
    pool_counts = df['poolType'].value_counts()
    print(f"\n📊 Pool Type Distribution:")
    for pool_type, count in pool_counts.items():
        percentage = (count / len(df)) * 100
        print(f"   {pool_type:<12}: {count:>6,} rows ({percentage:>5.1f}%)")
    
    return df

def filter_stablecoin_pools(df):
    """Filter for pure stablecoin pools only"""
    print(f"\n🔍 Filtering for stablecoin pools only...")
    
    # Filter for stablecoin pools
    stablecoin_df = df[df['poolType'] == 'stablecoin'].copy()
    
    print(f"   Before filtering: {len(df):,} rows")
    print(f"   After filtering:  {len(stablecoin_df):,} rows")
    print(f"   Reduction factor: {len(df)/len(stablecoin_df) if len(stablecoin_df) > 0 else 0:.1f}x")
    
    if len(stablecoin_df) == 0:
        print("   ⚠️  No stablecoin pools found!")
        return None
    
    return stablecoin_df

def analyze_stablecoin_pairs(df):
    """Analyze the stablecoin pairs we captured"""
    print(f"\n📊 March-June 2025 Stablecoin Pool Analysis:")
    
    # Unique pools
    unique_pools = df['poolAddress'].nunique()
    print(f"   Unique stablecoin pools: {unique_pools}")
    
    # Pool names frequency
    pool_names = df['pool_name'].value_counts()
    print(f"\n🏆 Top 10 Most Active Stablecoin Pools:")
    for i, (pool_name, count) in enumerate(pool_names.head(10).items(), 1):
        if len(df[df['pool_name'] == pool_name]) > 0:
            avg_daily_tx = df[df['pool_name'] == pool_name]['tx_count'].mean()
            print(f"   {i:2d}. {pool_name:<20} - {count:>4} days, {avg_daily_tx:>6.1f} avg daily txs")
    
    # Token pair analysis
    token_pairs = set()
    for pool_name in df['pool_name'].unique():
        if isinstance(pool_name, str) and '/' in pool_name:
            token_pairs.add(tuple(sorted(pool_name.split('/'))))
    
    print(f"\n💰 Unique Stablecoin Pairs: {len(token_pairs)}")
    for pair in sorted(token_pairs):
        print(f"   {pair[0]}/{pair[1]}")
    
    return df

def create_stablecoin_features(df):
    """Verify and enhance stablecoin-specialized features"""
    print(f"\n🔬 Verifying stablecoin-specialized features...")
    
    # Verify features already exist (they should from processing)
    required_features = ['stablecoin_pair_type', 'activity_level', 'pool_maturity', 'volatility_level']
    
    for feature in required_features:
        if feature not in df.columns:
            print(f"   ⚠️  Missing feature: {feature}")
        else:
            print(f"   ✅ Feature present: {feature}")
    
    print(f"\n📊 March-June Stablecoin Feature Distributions:")
    for feature in required_features:
        if feature in df.columns:
            print(f"\n   {feature}:")
            counts = df[feature].value_counts()
            for value, count in counts.items():
                percentage = (count / len(df)) * 100
                print(f"     {str(value):<15}: {count:>5} ({percentage:>5.1f}%)")
    
    return df

def split_stablecoin_data(df):
    """Create train/test splits optimized for March-June stablecoin pools"""
    print(f"\n✂️  Creating March-June stablecoin train/test split...")
    
    # Sort by date to ensure temporal split
    df = df.sort_values(['date', 'poolAddress'])
    
    # For small datasets, use a different split strategy
    unique_dates = sorted(df['date'].unique())
    print(f"   Available dates: {len(unique_dates)} days ({unique_dates[0]} to {unique_dates[-1]})")
    
    if len(unique_dates) < 7:
        # Very small dataset - use 80/20 split by rows, not dates
        print("   Using row-based split due to limited date range...")
        split_idx = int(len(df) * 0.8)
        train_df = df.iloc[:split_idx].copy()
        test_df = df.iloc[split_idx:].copy()
    else:
        # Use temporal split: first 80% for training, last 20% for testing
        split_idx = int(len(unique_dates) * 0.8)
        train_end_date = unique_dates[split_idx-1]
        
        train_df = df[df['date'] <= train_end_date].copy()
        test_df = df[df['date'] > train_end_date].copy()
    
    print(f"   Training set: {len(train_df):,} rows")
    print(f"   Test set:     {len(test_df):,} rows")
    if len(train_df) > 0:
        print(f"   Train dates:  {train_df['date'].min()} to {train_df['date'].max()}")
    if len(test_df) > 0:
        print(f"   Test dates:   {test_df['date'].min()} to {test_df['date'].max()}")
    print(f"   Train pools:  {train_df['poolAddress'].nunique()}")
    print(f"   Test pools:   {test_df['poolAddress'].nunique()}")
    
    return train_df, test_df

def save_stablecoin_datasets(train_df, test_df, full_df):
    """Save the March-June specialized stablecoin datasets"""
    print(f"\n💾 Saving March-June stablecoin datasets...")
    
    # Save datasets with March-June prefix
    full_df.to_csv('pool_march_june_stablecoin_full.csv', index=False)
    train_df.to_csv('pool_march_june_stablecoin_training.csv', index=False)
    test_df.to_csv('pool_march_june_stablecoin_test.csv', index=False)
    
    print(f"   ✅ Saved: pool_march_june_stablecoin_full.csv ({len(full_df):,} rows)")
    print(f"   ✅ Saved: pool_march_june_stablecoin_training.csv ({len(train_df):,} rows)")
    print(f"   ✅ Saved: pool_march_june_stablecoin_test.csv ({len(test_df):,} rows)")
    
    # Generate summary statistics
    print(f"\n📊 Final March-June Stablecoin Dataset Summary:")
    print(f"   Unique stablecoin pools: {full_df['poolAddress'].nunique()}")
    print(f"   Date range: {full_df['date'].min()} to {full_df['date'].max()}")
    print(f"   Total days: {full_df['date'].nunique()}")
    if len(full_df) > 0:
        print(f"   Average transactions per day: {full_df['tx_count'].mean():.1f}")
        print(f"   Median transactions per day: {full_df['tx_count'].median():.1f}")
    
    # Show most active stablecoin pools in training set
    if len(train_df) > 0:
        print(f"\n🏆 Top 5 Most Active Stablecoin Pools (March-June Training Set):")
        pool_activity = train_df.groupby('pool_name')['tx_count'].agg(['count', 'mean', 'sum']).round(1)
        pool_activity = pool_activity.sort_values('sum', ascending=False)
        
        for i, (pool_name, stats) in enumerate(pool_activity.head().iterrows(), 1):
            print(f"   {i}. {pool_name:<20} - {stats['count']} days, {stats['mean']} avg, {int(stats['sum'])} total txs")

def main():
    """Main execution function for March-June dataset"""
    print("=" * 80)
    print("MARCH-JUNE 2025 STABLECOIN DATASET CREATION")
    print("=" * 80)
    
    try:
        # Load data
        df = load_data()
        
        # Filter for stablecoin pools only
        stablecoin_df = filter_stablecoin_pools(df)
        if stablecoin_df is None:
            return
        
        # Analyze stablecoin pairs
        stablecoin_df = analyze_stablecoin_pairs(stablecoin_df)
        
        # Verify specialized features
        stablecoin_df = create_stablecoin_features(stablecoin_df)
        
        # Split into train/test
        train_df, test_df = split_stablecoin_data(stablecoin_df)
        
        # Save datasets
        save_stablecoin_datasets(train_df, test_df, stablecoin_df)
        
        print("\n" + "=" * 80)
        print("✅ MARCH-JUNE 2025 STABLECOIN DATASET CREATION COMPLETE!")
        print("=" * 80)
        print("\n🎯 Ready for March-June stablecoin APY prediction modeling!")
        print("\n📁 Output files:")
        print("   - pool_march_june_stablecoin_training.csv (for training)")
        print("   - pool_march_june_stablecoin_test.csv (for validation)")
        print("   - pool_march_june_stablecoin_full.csv (complete dataset)")
        
        # Note about data availability
        print(f"\n📝 Note: Currently processing {len(stablecoin_df)} rows from available data.")
        print(f"   To get complete March-June coverage, continue running:")
        print(f"   node updater/fetch_march_to_june_2025.mjs")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise

if __name__ == "__main__":
    main()