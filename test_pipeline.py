"""
Test Pipeline - Quick demo to collect data and generate features
"""

import subprocess
import os
import sys
from pathlib import Path
import pandas as pd
from apy_features import batch_calculate_features

# Set environment variable for Alchemy
os.environ['ALCHEMY_API_KEY'] = 'xZAA_UQS9ExBekaML58M0-T5BNvKZeRI'

def step1_collect_data():
    """Step 1: Collect transaction data using Node.js script"""
    print("\n" + "="*80)
    print("STEP 1: Collecting Transaction Data from Ethereum")
    print("="*80)

    updater_dir = Path(__file__).parent / 'updater'
    static_dir = updater_dir / 'static'
    static_dir.mkdir(exist_ok=True)

    output_file = static_dir / 'test_logs.csv'

    print(f"\n📡 Fetching last 1000 blocks of swap data from 1inch...")
    print(f"   Output: {output_file}")

    # Run oneinch_swaps.cjs to get data
    cmd = [
        'node',
        str(updater_dir / 'oneinch_swaps.cjs'),
        '--output', str(output_file)
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(updater_dir),
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0:
            print(f"\n✅ Data collection successful!")
            print(result.stdout)

            # Check if file exists and has data
            if output_file.exists():
                df = pd.read_csv(output_file)
                print(f"\n📊 Collected {len(df):,} transactions")
                print(f"📊 Unique contracts: {df['Contract Address'].nunique()}")
                return output_file
            else:
                print(f"❌ Output file not created")
                return None
        else:
            print(f"\n❌ Data collection failed!")
            print(result.stderr)
            return None

    except subprocess.TimeoutExpired:
        print("\n❌ Data collection timed out (>5 min)")
        return None
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return None


def step2_analyze_data(data_file):
    """Step 2: Analyze the collected data"""
    print("\n" + "="*80)
    print("STEP 2: Analyzing Collected Data")
    print("="*80)

    df = pd.read_csv(data_file)

    print(f"\n📊 Total Transactions: {len(df):,}")
    print(f"📊 Total Unique Contracts: {df['Contract Address'].nunique():,}")

    if 'Block Number' in df.columns:
        print(f"📊 Block Range: {df['Block Number'].min():,} - {df['Block Number'].max():,}")

    print("\n🏆 Top 10 Most Active Contracts:")
    top_10 = df['Contract Address'].value_counts().head(10)
    for i, (contract, count) in enumerate(top_10.items(), 1):
        print(f"   {i:2d}. {contract[:10]}...{contract[-8:]}: {count:,} txs")

    # Filter for ETH pools
    WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
    eth_mask = (
        (df['Input Token'].str.lower() == WETH.lower()) |
        (df['Output Token'].str.lower() == WETH.lower())
    )
    eth_df = df[eth_mask]

    print(f"\n🔷 ETH Pool Transactions: {len(eth_df):,} ({len(eth_df)/len(df)*100:.1f}%)")
    print(f"🔷 ETH Pool Unique Contracts: {eth_df['Contract Address'].nunique():,}")

    return df


def step3_generate_features(data_file):
    """Step 3: Generate APY prediction features"""
    print("\n" + "="*80)
    print("STEP 3: Generating APY Prediction Features")
    print("="*80)

    df = pd.read_csv(data_file)

    print(f"\n🧠 Processing ETH pools to generate features...")
    print(f"   This will query pool states via Alchemy API")
    print(f"   Processing top 10 pools by transaction volume...")

    features_df = batch_calculate_features(df, eth_price_usd=2500, max_pools=10)

    if features_df.empty:
        print("\n❌ No features generated")
        return None

    # Save features
    output_file = Path(__file__).parent / 'eth_pool_features_test.csv'
    features_df.to_csv(output_file, index=False)

    print("\n" + "="*80)
    print("✅ FEATURE GENERATION COMPLETE")
    print("="*80)

    print(f"\n💾 Features saved to: {output_file}")
    print(f"\n📊 Generated {len(features_df)} ETH pool feature sets")

    # Display summary
    print("\n📈 FEATURE SUMMARY:")
    print("-" * 80)

    summary_cols = [
        'contract', 'paired_token', 'current_tvl_usd',
        'tx_count', 'estimated_current_apy'
    ]

    available_cols = [col for col in summary_cols if col in features_df.columns]

    if available_cols:
        print(features_df[available_cols].to_string(index=False))

    return features_df


def step4_show_database_options():
    """Step 4: Show how to connect to databases"""
    print("\n" + "="*80)
    print("STEP 4: Database Connection Options")
    print("="*80)

    print("""
📊 Your data is now in CSV format. Here are your options to view it:

1️⃣  EXCEL / GOOGLE SHEETS (Easiest)
   - Open eth_pool_features_test.csv in Excel or Google Sheets
   - All your pool data with APY predictions visible

2️⃣  PANDAS (Python - Best for Analysis)
   import pandas as pd
   df = pd.read_csv('eth_pool_features_test.csv')
   print(df)

3️⃣  SQLITE (Local SQL Database)
   import sqlite3
   import pandas as pd

   # Load CSV to SQLite
   df = pd.read_csv('eth_pool_features_test.csv')
   conn = sqlite3.connect('pool_data.db')
   df.to_sql('eth_pools', conn, if_exists='replace', index=False)

   # Query with SQL
   query = "SELECT * FROM eth_pools WHERE estimated_current_apy > 10 ORDER BY current_tvl_usd DESC"
   results = pd.read_sql_query(query, conn)
   print(results)

4️⃣  POSTGRESQL (Production Database)
   import pandas as pd
   from sqlalchemy import create_engine

   # Create connection
   engine = create_engine('postgresql://user:password@localhost:5432/defi_data')

   # Load data
   df = pd.read_csv('eth_pool_features_test.csv')
   df.to_sql('eth_pools', engine, if_exists='replace', index=False)

   # Query
   query = "SELECT * FROM eth_pools WHERE paired_token = 'USDC'"
   results = pd.read_sql_query(query, engine)

5️⃣  MONGODB (NoSQL Database)
   import pandas as pd
   from pymongo import MongoClient

   # Connect
   client = MongoClient('mongodb://localhost:27017/')
   db = client['defi_database']
   collection = db['eth_pools']

   # Load data
   df = pd.read_csv('eth_pool_features_test.csv')
   records = df.to_dict('records')
   collection.insert_many(records)

   # Query
   high_apy_pools = collection.find({"estimated_current_apy": {"$gt": 10}})

6️⃣  AWS S3 + ATHENA (Cloud Data Lake)
   The data is already being saved to S3!
   Use AWS Athena to query S3 data with SQL:

   CREATE EXTERNAL TABLE eth_pools (
     contract STRING,
     paired_token STRING,
     current_tvl_usd DOUBLE,
     estimated_current_apy DOUBLE
   )
   ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
   LOCATION 's3://defi-liquidity-data/features/'

   Then query:
   SELECT * FROM eth_pools WHERE estimated_current_apy > 10;

7️⃣  VIEW WITH OUR SCRIPT (Quickest)
   python view_pool_data.py --source local --key updater/static/test_logs.csv

   Or generate features directly:
   python view_pool_data.py --source local --key updater/static/test_logs.csv --generate-features
    """)

    print("\n✅ Recommendation for starting:")
    print("   - Use Excel/Google Sheets to explore the CSV")
    print("   - Use our view_pool_data.py script for quick analysis")
    print("   - Set up PostgreSQL or MongoDB for production")


def main():
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║                                                                ║
    ║          ETH POOL APY PREDICTION - TEST PIPELINE              ║
    ║                                                                ║
    ║  This script will:                                            ║
    ║  1. Collect recent transaction data from Ethereum             ║
    ║  2. Analyze the data for ETH pools                            ║
    ║  3. Generate APY prediction features using Alchemy API        ║
    ║  4. Show you how to connect to databases                      ║
    ║                                                                ║
    ╚════════════════════════════════════════════════════════════════╝
    """)

    # Step 1: Collect data
    data_file = step1_collect_data()

    if not data_file:
        print("\n❌ Pipeline failed at Step 1")
        return

    # Step 2: Analyze
    step2_analyze_data(data_file)

    # Step 3: Generate features
    features_df = step3_generate_features(data_file)

    # Step 4: Database options
    step4_show_database_options()

    print("\n" + "="*80)
    print("✅ TEST PIPELINE COMPLETE!")
    print("="*80)
    print("\nNext steps:")
    print("1. Open eth_pool_features_test.csv in Excel to see your data")
    print("2. Run: python view_pool_data.py --source local --key updater/static/test_logs.csv")
    print("3. Set up a database using one of the options above")


if __name__ == "__main__":
    main()
