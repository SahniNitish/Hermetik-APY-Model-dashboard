#!/usr/bin/env python3
"""
STABLECOIN-SPECIALIZED DATASET CREATOR
=====================================
This script creates pure stablecoin-to-stablecoin pool datasets,
optimized for stablecoin APY prediction modeling.

Key Features:
- Filters for poolType == 'stablecoin' only
- Removes ETH-paired and other token noise  
- Creates specialized features for stablecoin dynamics
- Produces clean training/test splits for stablecoin-only models
"""

import pandas as pd
import numpy as np
from pathlib import Path

def load_data():
    """Load the full dataset"""
    print("📂 Loading full dataset...")
    df = pd.read_csv('pool_full_dataset.csv')
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
    print(f"\n📊 Stablecoin Pool Analysis:")
    
    # Unique pools
    unique_pools = df['poolAddress'].nunique()
    print(f"   Unique stablecoin pools: {unique_pools}")
    
    # Pool names frequency
    pool_names = df['pool_name'].value_counts()
    print(f"\n🏆 Top 10 Most Active Stablecoin Pools:")
    for i, (pool_name, count) in enumerate(pool_names.head(10).items(), 1):
        avg_daily_tx = df[df['pool_name'] == pool_name]['tx_count'].mean()
        print(f"   {i:2d}. {pool_name:<20} - {count:>4} days, {avg_daily_tx:>6.1f} avg daily txs")
    
    # Token pair analysis
    token_pairs = set()
    for pool_name in df['pool_name'].unique():
        if '/' in pool_name:
            token_pairs.add(tuple(sorted(pool_name.split('/'))))
    
    print(f"\n💰 Unique Stablecoin Pairs: {len(token_pairs)}")
    for pair in sorted(token_pairs):
        print(f"   {pair[0]}/{pair[1]}")
    
    return df

def create_stablecoin_features(df):
    """Create specialized features for stablecoin analysis"""
    print(f"\n🔬 Creating stablecoin-specialized features...")
    
    # Make a copy to avoid warnings
    df = df.copy()
    
    # 1. Pool pair classification
    def classify_stablecoin_pair(pool_name):
        """Classify stablecoin pairs by type"""
        if not isinstance(pool_name, str) or '/' not in pool_name:
            return 'unknown'
        
        tokens = [t.strip().upper() for t in pool_name.split('/')]
        if len(tokens) != 2:
            return 'unknown'
        
        # Major USD stablecoins
        major_usd = {'USDC', 'USDT', 'DAI', 'FRAX'}
        # Yield-bearing stablecoins
        yield_bearing = {'USDE', 'SUSDE', 'USDS', 'SUSDS', 'OUSD', 'SYRUPUSDC'}
        # Euro stablecoins  
        eur_stables = {'EUROC', 'EURT'}
        # Other USD stablecoins
        other_usd = {'TUSD', 'GUSD', 'PYUSD', 'GHO', 'FRXUSD', 'RLUSD', 'MUSD', 'USDP', 'USDD', 'USTC', 'WCUSD'}
        
        token_set = set(tokens)
        
        if token_set.issubset(major_usd):
            return 'major_usd'
        elif any(t in yield_bearing for t in tokens):
            return 'yield_bearing'
        elif any(t in eur_stables for t in tokens):
            return 'eur_stablecoin'
        elif token_set.issubset(major_usd | other_usd):
            return 'mixed_usd'
        else:
            return 'other'
    
    df['stablecoin_pair_type'] = df['pool_name'].apply(classify_stablecoin_pair)
    
    # 2. Activity intensity classification
    df['activity_level'] = pd.cut(
        df['tx_count'], 
        bins=[0, 1, 5, 20, float('inf')], 
        labels=['very_low', 'low', 'medium', 'high']
    )
    
    # 3. Pool maturity (days since start)
    df['pool_maturity'] = pd.cut(
        df['days_since_start'],
        bins=[0, 7, 30, 90, float('inf')],
        labels=['new', 'young', 'mature', 'established']
    )
    
    # 4. Volatility indicators (using 7-day std)
    df['volatility_level'] = pd.cut(
        df['tx_count_7d_std'],
        bins=[0, 2, 10, 50, float('inf')],
        labels=['stable', 'low_vol', 'medium_vol', 'high_vol']
    )
    
    print(f"   ✅ Added 4 stablecoin-specific features")
    
    # Show feature distributions
    print(f"\n📊 Stablecoin Feature Distributions:")
    for feature in ['stablecoin_pair_type', 'activity_level', 'pool_maturity', 'volatility_level']:
        print(f"\n   {feature}:")
        counts = df[feature].value_counts()
        for value, count in counts.items():
            percentage = (count / len(df)) * 100
            print(f"     {str(value):<15}: {count:>5} ({percentage:>5.1f}%)")
    
    return df

def split_stablecoin_data(df):
    """Create train/test splits optimized for stablecoin pools"""
    print(f"\n✂️  Creating stablecoin-specific train/test split...")
    
    # Sort by date to ensure temporal split
    df = df.sort_values(['date', 'poolAddress'])
    
    # Use temporal split: first 80% for training, last 20% for testing
    unique_dates = sorted(df['date'].unique())
    split_idx = int(len(unique_dates) * 0.8)
    train_end_date = unique_dates[split_idx-1]
    
    train_df = df[df['date'] <= train_end_date].copy()
    test_df = df[df['date'] > train_end_date].copy()
    
    print(f"   Training set: {len(train_df):,} rows")
    print(f"   Test set:     {len(test_df):,} rows")
    print(f"   Train dates:  {train_df['date'].min()} to {train_df['date'].max()}")
    print(f"   Test dates:   {test_df['date'].min()} to {test_df['date'].max()}")
    print(f"   Train pools:  {train_df['poolAddress'].nunique()}")
    print(f"   Test pools:   {test_df['poolAddress'].nunique()}")
    
    return train_df, test_df

def save_stablecoin_datasets(train_df, test_df, full_df):
    """Save the specialized stablecoin datasets"""
    print(f"\n💾 Saving stablecoin-specialized datasets...")
    
    # Save datasets
    full_df.to_csv('pool_stablecoin_full.csv', index=False)
    train_df.to_csv('pool_stablecoin_training.csv', index=False)
    test_df.to_csv('pool_stablecoin_test.csv', index=False)
    
    print(f"   ✅ Saved: pool_stablecoin_full.csv ({len(full_df):,} rows)")
    print(f"   ✅ Saved: pool_stablecoin_training.csv ({len(train_df):,} rows)")
    print(f"   ✅ Saved: pool_stablecoin_test.csv ({len(test_df):,} rows)")
    
    # Generate summary statistics
    print(f"\n📊 Final Stablecoin Dataset Summary:")
    print(f"   Unique stablecoin pools: {full_df['poolAddress'].nunique()}")
    print(f"   Date range: {full_df['date'].min()} to {full_df['date'].max()}")
    print(f"   Total days: {full_df['date'].nunique()}")
    print(f"   Average transactions per day: {full_df['tx_count'].mean():.1f}")
    print(f"   Median transactions per day: {full_df['tx_count'].median():.1f}")
    
    # Show most active stablecoin pools in training set
    if len(train_df) > 0:
        print(f"\n🏆 Top 5 Most Active Stablecoin Pools (Training Set):")
        pool_activity = train_df.groupby('pool_name')['tx_count'].agg(['count', 'mean', 'sum']).round(1)
        pool_activity = pool_activity.sort_values('sum', ascending=False)
        
        for i, (pool_name, stats) in enumerate(pool_activity.head().iterrows(), 1):
            print(f"   {i}. {pool_name:<20} - {stats['count']} days, {stats['mean']} avg, {int(stats['sum'])} total txs")

def main():
    """Main execution function"""
    print("=" * 80)
    print("STABLECOIN-SPECIALIZED DATASET CREATION")
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
        
        # Create specialized features
        stablecoin_df = create_stablecoin_features(stablecoin_df)
        
        # Split into train/test
        train_df, test_df = split_stablecoin_data(stablecoin_df)
        
        # Save datasets
        save_stablecoin_datasets(train_df, test_df, stablecoin_df)
        
        print("\n" + "=" * 80)
        print("✅ STABLECOIN DATASET CREATION COMPLETE!")
        print("=" * 80)
        print("\n🎯 Ready for stablecoin-specialized APY prediction modeling!")
        print("\n📁 Output files:")
        print("   - pool_stablecoin_training.csv (for training stablecoin models)")
        print("   - pool_stablecoin_test.csv (for validation)")
        print("   - pool_stablecoin_full.csv (complete stablecoin dataset)")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise

if __name__ == "__main__":
    main()