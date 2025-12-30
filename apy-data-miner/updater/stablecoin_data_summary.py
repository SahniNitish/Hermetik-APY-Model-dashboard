#!/usr/bin/env python3
"""
STABLECOIN DATA SUMMARY
======================
Analyzes collected stablecoin transaction data from Jan 1 - Mar 1, 2025
"""

import os
import csv
from datetime import datetime, timedelta
import glob

def main():
    print("=" * 80)
    print("STABLECOIN DATA COLLECTION SUMMARY")
    print("=" * 80)
    
    # Find all stablecoin transaction files
    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    files = glob.glob(os.path.join(static_dir, 'stablecoin_txs_2025-*.csv'))
    
    if not files:
        print("❌ No stablecoin transaction files found!")
        return
    
    # Sort files by date
    files.sort()
    
    print(f"📁 Found {len(files)} data files")
    
    # Analyze each file
    total_transactions = 0
    dates_covered = []
    
    for file in files:
        filename = os.path.basename(file)
        date_str = filename.replace('stablecoin_txs_', '').replace('.csv', '')
        
        try:
            with open(file, 'r') as csvfile:
                reader = csv.reader(csvfile)
                next(reader)  # Skip header
                tx_count = sum(1 for row in reader)
                
            total_transactions += tx_count
            dates_covered.append(date_str)
            
            print(f"  📅 {date_str}: {tx_count:,} transactions")
            
        except Exception as e:
            print(f"  ❌ {date_str}: Error reading file - {e}")
    
    print(f"\n📊 SUMMARY:")
    print(f"   • Total transactions: {total_transactions:,}")
    print(f"   • Days covered: {len(dates_covered)}")
    print(f"   • Date range: {min(dates_covered)} to {max(dates_covered)}")
    
    # Check what dates are missing for Jan 1 - Mar 1 range
    start_date = datetime(2025, 1, 1)
    end_date = datetime(2025, 3, 1)
    
    expected_dates = []
    current_date = start_date
    while current_date <= end_date:
        expected_dates.append(current_date.strftime('%Y-%m-%d'))
        current_date += timedelta(days=1)
    
    covered_dates = set(dates_covered)
    missing_dates = [date for date in expected_dates if date not in covered_dates]
    
    if missing_dates:
        print(f"\n⚠️  MISSING DATES ({len(missing_dates)} days):")
        for date in missing_dates[:10]:  # Show first 10
            print(f"   • {date}")
        if len(missing_dates) > 10:
            print(f"   • ... and {len(missing_dates) - 10} more")
    else:
        print(f"\n✅ COMPLETE: All dates from Jan 1 - Mar 1, 2025 are covered!")
    
    print(f"\n🎯 NEXT STEPS:")
    if missing_dates:
        print(f"   • Continue data collection for {len(missing_dates)} remaining dates")
        print(f"   • Estimated completion: {len(missing_dates)} more days to fetch")
    else:
        print(f"   • Data collection complete!")
        print(f"   • Ready for analysis and modeling")
    
    # Pool analysis (sample from first file)
    if files:
        try:
            first_file = files[0]
            unique_pools = set()
            with open(first_file, 'r') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    unique_pools.add(row['poolAddress'])
            print(f"   • Unique stablecoin pools in sample: {len(unique_pools)}")
            
        except Exception as e:
            print(f"   • Pool analysis failed: {e}")

if __name__ == "__main__":
    main()