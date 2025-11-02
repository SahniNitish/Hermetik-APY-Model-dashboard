"""
Data Viewer - View and analyze collected pool data
Provides easy access to see what data has been collected
"""

import pandas as pd
import boto3
from io import BytesIO
import argparse
import os
import sys
from apy_features import batch_calculate_features, is_eth_pool

# Set pandas display options for better readability
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
pd.set_option('display.max_colwidth', 50)


def load_local_csv(file_path):
    """Load CSV from local file system"""
    try:
        df = pd.read_csv(file_path)
        print(f"✅ Loaded {len(df)} rows from {file_path}")
        return df
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        return None
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        return None


def load_s3_csv(bucket, key):
    """Load CSV from S3"""
    try:
        s3 = boto3.client('s3')
        obj = s3.get_object(Bucket=bucket, Key=key)
        df = pd.read_csv(BytesIO(obj['Body'].read()))
        print(f"✅ Loaded {len(df)} rows from s3://{bucket}/{key}")
        return df
    except Exception as e:
        print(f"❌ Error loading from S3: {e}")
        return None


def list_s3_files(bucket, prefix=''):
    """List available files in S3 bucket"""
    try:
        s3 = boto3.client('s3')
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)

        if 'Contents' not in response:
            print(f"No files found in s3://{bucket}/{prefix}")
            return []

        files = []
        for obj in response['Contents']:
            size_mb = obj['Size'] / (1024 * 1024)
            files.append({
                'Key': obj['Key'],
                'Size (MB)': f"{size_mb:.2f}",
                'LastModified': obj['LastModified'].strftime('%Y-%m-%d %H:%M:%S')
            })

        files_df = pd.DataFrame(files)
        print(f"\n📁 Files in s3://{bucket}/{prefix}:")
        print(files_df.to_string(index=False))
        return files

    except Exception as e:
        print(f"❌ Error listing S3 files: {e}")
        return []


def analyze_logs(df):
    """Analyze transaction logs"""
    print("\n" + "="*80)
    print("📊 TRANSACTION LOGS ANALYSIS")
    print("="*80)

    print(f"\nTotal Transactions: {len(df):,}")
    print(f"Total Unique Contracts: {df['Contract Address'].nunique():,}")

    if 'Block Number' in df.columns:
        print(f"Block Range: {df['Block Number'].min():,} to {df['Block Number'].max():,}")
        print(f"Block Span: {df['Block Number'].max() - df['Block Number'].min():,} blocks")

    print("\n📈 Top 20 Most Active Contracts:")
    top_contracts = df['Contract Address'].value_counts().head(20)
    for i, (contract, count) in enumerate(top_contracts.items(), 1):
        print(f"  {i:2d}. {contract}: {count:,} txs")

    if 'Input Token' in df.columns and 'Output Token' in df.columns:
        print("\n🔄 Unique Tokens:")
        input_tokens = set(df['Input Token'].unique())
        output_tokens = set(df['Output Token'].unique())
        all_tokens = input_tokens | output_tokens
        print(f"  Total unique tokens: {len(all_tokens)}")

    if 'Protocol' in df.columns:
        print("\n🏦 Protocols:")
        print(df['Protocol'].value_counts().to_string())


def filter_eth_pools(df):
    """Filter for ETH pools only"""
    WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

    print("\n🔍 Filtering for ETH pools...")

    # Find pools that involve WETH
    eth_mask = (
        (df['Input Token'].str.lower() == WETH_ADDRESS.lower()) |
        (df['Output Token'].str.lower() == WETH_ADDRESS.lower())
    )

    eth_df = df[eth_mask]

    print(f"✅ Found {len(eth_df):,} transactions involving ETH")
    print(f"✅ Found {eth_df['Contract Address'].nunique():,} unique ETH pools")

    print("\n📈 Top 20 ETH Pools by Transaction Count:")
    eth_pools = eth_df['Contract Address'].value_counts().head(20)
    for i, (contract, count) in enumerate(eth_pools.items(), 1):
        # Get paired token
        pool_txs = eth_df[eth_df['Contract Address'] == contract]
        input_tokens = set(pool_txs['Input Token'].unique())
        output_tokens = set(pool_txs['Output Token'].unique())
        all_tokens = (input_tokens | output_tokens) - {WETH_ADDRESS}

        paired_token = list(all_tokens)[0][:10] + "..." if all_tokens else "Unknown"

        print(f"  {i:2d}. {contract}: {count:,} txs (ETH/{paired_token})")

    return eth_df


def show_pool_details(df, pool_address):
    """Show detailed information about a specific pool"""
    pool_df = df[df['Contract Address'] == pool_address]

    if pool_df.empty:
        print(f"❌ No data found for pool {pool_address}")
        return

    print("\n" + "="*80)
    print(f"🏊 POOL DETAILS: {pool_address}")
    print("="*80)

    print(f"\nTotal Transactions: {len(pool_df):,}")

    if 'Block Number' in pool_df.columns:
        print(f"Block Range: {pool_df['Block Number'].min():,} to {pool_df['Block Number'].max():,}")

    if 'Input Token' in pool_df.columns and 'Output Token' in pool_df.columns:
        print("\n🪙 Tokens:")
        input_tokens = pool_df['Input Token'].unique()
        output_tokens = pool_df['Output Token'].unique()
        all_tokens = set(list(input_tokens) + list(output_tokens))

        for i, token in enumerate(all_tokens, 1):
            print(f"  {i}. {token}")

    print("\n📊 Sample Transactions:")
    print(pool_df.head(10).to_string(index=False))


def generate_features_live(df, eth_price=2500, max_pools=20):
    """
    Generate live features for ETH pools from current data
    """
    print("\n" + "="*80)
    print("🔬 GENERATING LIVE FEATURES FOR ETH POOLS")
    print("="*80)

    features_df = batch_calculate_features(df, eth_price_usd=eth_price, max_pools=max_pools)

    if features_df.empty:
        print("❌ No features generated")
        return None

    print("\n✅ FEATURE SUMMARY:")
    print("="*80)
    print(features_df.to_string(index=False))

    # Save to file
    output_file = "eth_pool_features.csv"
    features_df.to_csv(output_file, index=False)
    print(f"\n💾 Features saved to {output_file}")

    return features_df


def main():
    parser = argparse.ArgumentParser(description="View and analyze DeFi pool data")
    parser.add_argument('--source', choices=['local', 's3'], default='local',
                        help='Data source: local file or S3')
    parser.add_argument('--bucket', default='defi-liquidity-data',
                        help='S3 bucket name (if using S3)')
    parser.add_argument('--key', help='S3 key or local file path')
    parser.add_argument('--list', action='store_true',
                        help='List available files in S3')
    parser.add_argument('--eth-only', action='store_true',
                        help='Filter for ETH pools only')
    parser.add_argument('--pool', help='Show details for a specific pool address')
    parser.add_argument('--generate-features', action='store_true',
                        help='Generate features for ETH pools')
    parser.add_argument('--eth-price', type=float, default=2500,
                        help='Current ETH price in USD (default: 2500)')
    parser.add_argument('--max-pools', type=int, default=20,
                        help='Maximum number of pools to process for features')

    args = parser.parse_args()

    # List files mode
    if args.list:
        if args.source == 's3':
            list_s3_files(args.bucket, args.key or '')
        else:
            print("❌ List mode only works with S3 source")
        return

    # Load data
    if not args.key:
        print("❌ Please provide --key for the file path or S3 key")
        print("\nExamples:")
        print("  View local file:")
        print("    python view_pool_data.py --source local --key updater/static/oneinch_logs_1D.csv")
        print("\n  View S3 file:")
        print("    python view_pool_data.py --source s3 --key rolling/oneinch_logs_1D.csv")
        print("\n  List S3 files:")
        print("    python view_pool_data.py --source s3 --list --key rolling/")
        print("\n  Generate features:")
        print("    python view_pool_data.py --source local --key updater/static/oneinch_logs_1D.csv --generate-features")
        return

    if args.source == 'local':
        df = load_local_csv(args.key)
    else:
        df = load_s3_csv(args.bucket, args.key)

    if df is None:
        return

    # Analyze data
    analyze_logs(df)

    # Filter for ETH pools
    if args.eth_only:
        df = filter_eth_pools(df)

    # Show specific pool
    if args.pool:
        show_pool_details(df, args.pool)

    # Generate features
    if args.generate_features:
        features_df = generate_features_live(df, eth_price=args.eth_price, max_pools=args.max_pools)


if __name__ == "__main__":
    main()
