#!/usr/bin/env python3
"""
STABLECOIN TRANSACTION PROCESSOR
================================
Processes raw stablecoin transaction files into full feature dataset
with all required fields for APY prediction modeling.

Transforms raw data from:
  blockNumber,transactionHash,poolAddress,date

Into complete feature set:
  poolAddress,date,pool_name,token0Symbol,token1Symbol,fee,fee_percentage,poolType,
  tx_count,unique_users,tx_count_3d_avg,tx_count_7d_avg,tx_count_7d_std,
  tx_count_cumulative,days_since_start,tx_growth_rate,day_number,
  target_tx_3d_ahead,target_tx_7d_ahead,target_tx_3d_avg_ahead,target_tx_7d_avg_ahead,
  stablecoin_pair_type,activity_level,pool_maturity,volatility_level
"""

import pandas as pd
import numpy as np
import glob
import os
from datetime import datetime
from pathlib import Path

def load_raw_stablecoin_data():
    """Load all raw stablecoin transaction files"""
    print("📂 Loading raw stablecoin transaction files...")
    
    # Find all stablecoin transaction files
    static_dir = Path(__file__).parent / 'updater' / 'static'
    files = glob.glob(str(static_dir / 'stablecoin_txs_2025-*.csv'))
    
    if not files:
        print("❌ No stablecoin transaction files found!")
        return None
    
    print(f"   Found {len(files)} transaction files")
    
    # Load and combine all files
    dfs = []
    for file in sorted(files):
        try:
            df = pd.read_csv(file)
            dfs.append(df)
        except Exception as e:
            print(f"   ⚠️  Error loading {file}: {e}")
    
    if not dfs:
        print("❌ No valid transaction files loaded!")
        return None
    
    # Combine all dataframes
    combined_df = pd.concat(dfs, ignore_index=True)
    
    print(f"   ✅ Loaded {len(combined_df):,} total transactions")
    print(f"   📅 Date range: {combined_df['date'].min()} to {combined_df['date'].max()}")
    print(f"   🏊 Unique pools: {combined_df['poolAddress'].nunique()}")
    
    return combined_df

def load_pool_metadata():
    """Load pool metadata from existing files"""
    print("\n🔍 Loading pool metadata...")
    
    # Try to load from existing stablecoin metadata
    metadata_file = Path(__file__).parent / 'updater' / 'static' / 'stablecoin_pools_info.csv'
    
    if metadata_file.exists():
        metadata_df = pd.read_csv(metadata_file)
        print(f"   ✅ Loaded metadata for {len(metadata_df)} pools")
        return metadata_df
    
    # If no metadata file, create minimal metadata
    print("   ⚠️  No pool metadata file found, creating minimal metadata...")
    return None

def calculate_daily_metrics(df):
    """Calculate daily transaction metrics for each pool"""
    print("\n📊 Calculating daily transaction metrics...")
    
    # Group by pool and date to calculate daily metrics
    daily_metrics = []
    
    for pool_address in df['poolAddress'].unique():
        pool_data = df[df['poolAddress'] == pool_address].copy()
        pool_data['date'] = pd.to_datetime(pool_data['date'])
        pool_data = pool_data.sort_values('date')
        
        # Get unique dates for this pool
        date_range = pd.date_range(start=pool_data['date'].min(), 
                                 end=pool_data['date'].max(), 
                                 freq='D')
        
        for date in date_range:
            day_data = pool_data[pool_data['date'].dt.date == date.date()]
            
            # Basic metrics
            tx_count = len(day_data)
            unique_users = day_data['transactionHash'].nunique() if tx_count > 0 else 0
            
            daily_metrics.append({
                'poolAddress': pool_address,
                'date': date.strftime('%Y-%m-%d'),
                'tx_count': tx_count,
                'unique_users': unique_users
            })
    
    metrics_df = pd.DataFrame(daily_metrics)
    print(f"   ✅ Calculated metrics for {len(metrics_df)} pool-days")
    
    return metrics_df

def add_pool_metadata(df):
    """Add pool metadata (names, tokens, fees)"""
    print("\n🏷️  Adding pool metadata...")
    
    # Load existing metadata if available
    metadata = load_pool_metadata()
    
    if metadata is not None:
        # Map column names and merge with existing metadata
        metadata = metadata.rename(columns={
            'poolName': 'pool_name',
            'symbol0': 'token0Symbol', 
            'symbol1': 'token1Symbol'
        })
        df = df.merge(metadata[['poolAddress', 'pool_name', 'token0Symbol', 'token1Symbol', 'fee']], 
                     on='poolAddress', how='left')
        
        # Fill missing metadata with placeholders
        df['pool_name'] = df['pool_name'].fillna('Unknown Pool')
        df['token0Symbol'] = df['token0Symbol'].fillna('TOKEN0')
        df['token1Symbol'] = df['token1Symbol'].fillna('TOKEN1')
        df['fee'] = df['fee'].fillna(500.0)
    else:
        # Create placeholder metadata
        df['pool_name'] = 'Unknown Pool'
        df['token0Symbol'] = 'TOKEN0'
        df['token1Symbol'] = 'TOKEN1'
        df['fee'] = 500.0
    
    # Add derived fields
    df['fee_percentage'] = df['fee'] / 1000000
    df['poolType'] = 'stablecoin'
    
    print(f"   ✅ Added metadata for {df['poolAddress'].nunique()} unique pools")
    return df

def calculate_rolling_metrics(df):
    """Calculate rolling averages and cumulative metrics"""
    print("\n📈 Calculating rolling and cumulative metrics...")
    
    df = df.sort_values(['poolAddress', 'date']).copy()
    
    # Calculate metrics per pool
    for pool_address in df['poolAddress'].unique():
        mask = df['poolAddress'] == pool_address
        pool_df = df[mask].copy()
        
        # Rolling averages
        df.loc[mask, 'tx_count_3d_avg'] = pool_df['tx_count'].rolling(window=3, min_periods=1).mean()
        df.loc[mask, 'tx_count_7d_avg'] = pool_df['tx_count'].rolling(window=7, min_periods=1).mean()
        df.loc[mask, 'tx_count_7d_std'] = pool_df['tx_count'].rolling(window=7, min_periods=1).std().fillna(0)
        
        # Cumulative metrics
        df.loc[mask, 'tx_count_cumulative'] = pool_df['tx_count'].cumsum()
        df.loc[mask, 'days_since_start'] = range(len(pool_df))
        df.loc[mask, 'day_number'] = range(1, len(pool_df) + 1)
        
        # Growth rate
        tx_pct_change = pool_df['tx_count'].pct_change().fillna(0)
        df.loc[mask, 'tx_growth_rate'] = tx_pct_change
    
    print(f"   ✅ Calculated rolling metrics")
    return df

def calculate_target_features(df):
    """Calculate target features (future transaction counts)"""
    print("\n🎯 Calculating target features...")
    
    df = df.sort_values(['poolAddress', 'date']).copy()
    
    for pool_address in df['poolAddress'].unique():
        mask = df['poolAddress'] == pool_address
        pool_df = df[mask].copy()
        
        # 3-day ahead targets
        df.loc[mask, 'target_tx_3d_ahead'] = pool_df['tx_count'].shift(-3)
        df.loc[mask, 'target_tx_3d_avg_ahead'] = pool_df['tx_count_3d_avg'].shift(-3)
        
        # 7-day ahead targets  
        df.loc[mask, 'target_tx_7d_ahead'] = pool_df['tx_count'].shift(-7)
        df.loc[mask, 'target_tx_7d_avg_ahead'] = pool_df['tx_count_7d_avg'].shift(-7)
    
    # Fill NaN target values with forward fill (for last few days)
    target_cols = ['target_tx_3d_ahead', 'target_tx_7d_ahead', 
                   'target_tx_3d_avg_ahead', 'target_tx_7d_avg_ahead']
    
    for col in target_cols:
        df[col] = df.groupby('poolAddress')[col].fillna(method='ffill')
    
    print(f"   ✅ Calculated target features")
    return df

def add_derived_features(df):
    """Add derived categorical features"""
    print("\n🔬 Adding derived categorical features...")
    
    # Stablecoin pair type classification
    def classify_stablecoin_pair(pool_name):
        if not isinstance(pool_name, str) or '/' not in pool_name:
            return 'other'
        
        tokens = [t.strip().upper() for t in pool_name.split('/')]
        if len(tokens) != 2:
            return 'other'
        
        major_usd = {'USDC', 'USDT', 'DAI', 'FRAX'}
        yield_bearing = {'USDE', 'SUSDE', 'USDS', 'SUSDS'}
        eur_stables = {'EUROC', 'EURT'}
        other_usd = {'TUSD', 'GUSD', 'PYUSD', 'GHO', 'FRXUSD'}
        
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
    
    # Activity level
    df['activity_level'] = pd.cut(
        df['tx_count'], 
        bins=[0, 1, 5, 20, float('inf')], 
        labels=['very_low', 'low', 'medium', 'high']
    )
    
    # Pool maturity
    df['pool_maturity'] = pd.cut(
        df['days_since_start'],
        bins=[-1, 7, 30, 90, float('inf')],
        labels=['new', 'young', 'mature', 'established']
    )
    
    # Volatility level
    df['volatility_level'] = pd.cut(
        df['tx_count_7d_std'],
        bins=[0, 2, 10, 50, float('inf')],
        labels=['stable', 'low_vol', 'medium_vol', 'high_vol']
    )
    
    print(f"   ✅ Added derived categorical features")
    return df

def main():
    """Main processing function"""
    print("=" * 80)
    print("STABLECOIN TRANSACTION PROCESSOR")
    print("=" * 80)
    
    try:
        # Step 1: Load raw transaction data
        raw_df = load_raw_stablecoin_data()
        if raw_df is None:
            return
        
        # Step 2: Calculate daily metrics
        daily_df = calculate_daily_metrics(raw_df)
        
        # Step 3: Add pool metadata
        daily_df = add_pool_metadata(daily_df)
        
        # Step 4: Calculate rolling metrics
        daily_df = calculate_rolling_metrics(daily_df)
        
        # Step 5: Calculate target features
        daily_df = calculate_target_features(daily_df)
        
        # Step 6: Add derived features
        daily_df = add_derived_features(daily_df)
        
        # Step 7: Save processed dataset
        output_file = 'pool_full_dataset.csv'
        daily_df.to_csv(output_file, index=False)
        
        print(f"\n💾 Saved processed dataset: {output_file}")
        print(f"   📊 {len(daily_df):,} rows")
        print(f"   📅 {daily_df['date'].nunique()} unique dates") 
        print(f"   🏊 {daily_df['poolAddress'].nunique()} unique pools")
        print(f"   📋 {len(daily_df.columns)} features")
        
        print("\n" + "=" * 80)
        print("✅ STABLECOIN PROCESSING COMPLETE!")
        print("=" * 80)
        print("\n🎯 Next step: Run create_stablecoin_dataset.py to create specialized datasets")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise

if __name__ == "__main__":
    main()