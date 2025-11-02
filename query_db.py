#!/usr/bin/env python3
"""
Database Query Interface - Easy access to ETH pool data
"""

import sqlite3
import pandas as pd
import sys

DB_FILE = 'eth_pools.db'

def connect():
    """Connect to database"""
    try:
        conn = sqlite3.connect(DB_FILE)
        return conn
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        print(f"Make sure {DB_FILE} exists. Run: python3 test_pipeline.py")
        sys.exit(1)

def show_all():
    """Show all pools"""
    conn = connect()
    query = """
    SELECT
        paired_token,
        ROUND(current_tvl_usd/1000000, 2) as tvl_millions,
        tx_count,
        ROUND(estimated_current_apy, 2) as apy_percent,
        ROUND(fee_percentage * 100, 3) as fee_percent
    FROM pools
    ORDER BY estimated_current_apy DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    print("\n📊 All ETH Pools")
    print("="*80)
    print(df.to_string(index=False))
    print(f"\nTotal pools: {len(df)}")

def show_top_apy(n=3):
    """Show top N pools by APY"""
    conn = connect()
    query = f"""
    SELECT
        contract,
        paired_token,
        ROUND(current_tvl_usd, 2) as tvl_usd,
        tx_count,
        ROUND(estimated_current_apy, 2) as apy_percent
    FROM pools
    ORDER BY estimated_current_apy DESC
    LIMIT {n}
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    print(f"\n🏆 Top {n} Pools by APY")
    print("="*80)
    print(df.to_string(index=False))

def show_high_tvl(min_tvl=5000000):
    """Show pools with TVL above threshold"""
    conn = connect()
    query = f"""
    SELECT
        contract,
        paired_token,
        ROUND(current_tvl_usd/1000000, 2) as tvl_millions,
        ROUND(estimated_current_apy, 2) as apy_percent,
        tx_count
    FROM pools
    WHERE current_tvl_usd > {min_tvl}
    ORDER BY current_tvl_usd DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    print(f"\n💰 Pools with TVL > ${min_tvl/1000000:.1f}M")
    print("="*80)
    if len(df) > 0:
        print(df.to_string(index=False))
    else:
        print(f"No pools with TVL > ${min_tvl/1000000:.1f}M")

def show_token(token):
    """Show pools for specific token"""
    conn = connect()
    query = f"""
    SELECT
        contract,
        paired_token,
        ROUND(current_tvl_usd/1000000, 2) as tvl_millions,
        ROUND(estimated_current_apy, 2) as apy_percent,
        tx_count,
        ROUND(fee_percentage * 100, 3) as fee_percent
    FROM pools
    WHERE paired_token = '{token}'
    ORDER BY estimated_current_apy DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    print(f"\n🪙 {token}/ETH Pools")
    print("="*80)
    if len(df) > 0:
        print(df.to_string(index=False))
    else:
        print(f"No {token}/ETH pools found")

def show_stats():
    """Show summary statistics"""
    conn = connect()

    # Overall stats
    query_overall = """
    SELECT
        COUNT(*) as total_pools,
        ROUND(SUM(current_tvl_usd)/1000000, 2) as total_tvl_millions,
        ROUND(AVG(estimated_current_apy), 2) as avg_apy,
        ROUND(MAX(estimated_current_apy), 2) as max_apy,
        ROUND(MIN(estimated_current_apy), 2) as min_apy,
        SUM(tx_count) as total_transactions
    FROM pools
    """
    overall = pd.read_sql_query(query_overall, conn)

    # By token
    query_by_token = """
    SELECT
        paired_token,
        COUNT(*) as pool_count,
        ROUND(AVG(current_tvl_usd)/1000000, 2) as avg_tvl_millions,
        ROUND(AVG(estimated_current_apy), 2) as avg_apy,
        SUM(tx_count) as total_txs
    FROM pools
    GROUP BY paired_token
    ORDER BY avg_apy DESC
    """
    by_token = pd.read_sql_query(query_by_token, conn)

    conn.close()

    print("\n📈 Database Statistics")
    print("="*80)
    print("\nOverall:")
    print(overall.to_string(index=False))

    print("\n\nBy Token:")
    print(by_token.to_string(index=False))

def custom_query(sql):
    """Run custom SQL query"""
    conn = connect()
    try:
        df = pd.read_sql_query(sql, conn)
        conn.close()
        print("\n🔍 Custom Query Results")
        print("="*80)
        print(df.to_string(index=False))
        print(f"\nRows: {len(df)}")
    except Exception as e:
        conn.close()
        print(f"❌ Query error: {e}")

def show_menu():
    """Show interactive menu"""
    print("\n" + "="*80)
    print("ETH POOL DATABASE QUERY INTERFACE")
    print("="*80)
    print("\nAvailable commands:")
    print("  1) all          - Show all pools")
    print("  2) top [N]      - Show top N pools by APY (default: 3)")
    print("  3) tvl [MIN]    - Show pools with TVL > MIN (default: $5M)")
    print("  4) token TOKEN  - Show pools for specific token (USDC, USDT, etc.)")
    print("  5) stats        - Show summary statistics")
    print("  6) query SQL    - Run custom SQL query")
    print("  7) exit         - Exit")
    print()

def main():
    if len(sys.argv) > 1:
        # Command line mode
        cmd = sys.argv[1].lower()

        if cmd == 'all':
            show_all()
        elif cmd == 'top':
            n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
            show_top_apy(n)
        elif cmd == 'tvl':
            min_tvl = float(sys.argv[2]) if len(sys.argv) > 2 else 5000000
            show_high_tvl(min_tvl)
        elif cmd == 'token':
            if len(sys.argv) < 3:
                print("Usage: python3 query_db.py token USDC")
                sys.exit(1)
            show_token(sys.argv[2].upper())
        elif cmd == 'stats':
            show_stats()
        elif cmd == 'query':
            if len(sys.argv) < 3:
                print("Usage: python3 query_db.py query \"SELECT * FROM pools\"")
                sys.exit(1)
            custom_query(' '.join(sys.argv[2:]))
        else:
            print(f"Unknown command: {cmd}")
            print("Usage: python3 query_db.py [all|top|tvl|token|stats|query]")
    else:
        # Interactive mode
        while True:
            show_menu()
            choice = input("Enter command: ").strip().lower().split()

            if not choice:
                continue

            cmd = choice[0]

            if cmd == '1' or cmd == 'all':
                show_all()
            elif cmd == '2' or cmd == 'top':
                n = int(choice[1]) if len(choice) > 1 else 3
                show_top_apy(n)
            elif cmd == '3' or cmd == 'tvl':
                min_tvl = float(choice[1]) if len(choice) > 1 else 5000000
                show_high_tvl(min_tvl)
            elif cmd == '4' or cmd == 'token':
                if len(choice) < 2:
                    print("Please specify token (e.g., USDC)")
                    continue
                show_token(choice[1].upper())
            elif cmd == '5' or cmd == 'stats':
                show_stats()
            elif cmd == '6' or cmd == 'query':
                sql = input("Enter SQL query: ")
                custom_query(sql)
            elif cmd == '7' or cmd == 'exit' or cmd == 'quit':
                print("Goodbye!")
                break
            else:
                print(f"Unknown command: {cmd}")

            input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()
