#!/bin/bash

# ETH Pool APY Prediction - Easy Run Script

cd "$(dirname "$0")"

# Activate virtual environment
source updater/venv/bin/activate

# Set Alchemy API key
export ALCHEMY_API_KEY=xZAA_UQS9ExBekaML58M0-T5BNvKZeRI

# Show menu
echo "╔════════════════════════════════════════════════════════════╗"
echo "║         ETH Pool APY Prediction - Run Menu                ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Choose an option:"
echo ""
echo "  1) Quick Test - Verify setup (30 seconds)"
echo "  2) Full Pipeline - Collect data & generate features (5 min)"
echo "  3) View Data - Interactive data viewer"
echo "  4) Generate Features Only - From existing logs"
echo "  5) Exit"
echo ""
read -p "Enter choice [1-5]: " choice

case $choice in
    1)
        echo ""
        echo "Running quick test..."
        python3 quick_test.py
        ;;
    2)
        echo ""
        echo "Running full pipeline..."
        echo "This will:"
        echo "  - Collect recent swap data from Ethereum"
        echo "  - Analyze ETH pools"
        echo "  - Generate APY prediction features"
        echo ""
        python3 test_pipeline.py
        ;;
    3)
        echo ""
        echo "Data Viewer Options:"
        echo ""
        echo "Available commands:"
        echo "  a) View local logs summary"
        echo "  b) View ETH pools only"
        echo "  c) Generate features from local data"
        echo "  d) Custom command"
        echo ""
        read -p "Enter choice [a-d]: " view_choice

        case $view_choice in
            a)
                python3 view_pool_data.py --source local --key updater/static/oneinch_logs_1D.csv 2>/dev/null || \
                python3 view_pool_data.py --source local --key updater/static/test_logs.csv 2>/dev/null || \
                echo "No data files found. Run option 2 first to collect data."
                ;;
            b)
                python3 view_pool_data.py --source local --key updater/static/oneinch_logs_1D.csv --eth-only 2>/dev/null || \
                python3 view_pool_data.py --source local --key updater/static/test_logs.csv --eth-only 2>/dev/null || \
                echo "No data files found. Run option 2 first to collect data."
                ;;
            c)
                echo ""
                read -p "Enter max pools to process [default: 20]: " max_pools
                max_pools=${max_pools:-20}
                python3 view_pool_data.py --source local --key updater/static/oneinch_logs_1D.csv --generate-features --max-pools $max_pools 2>/dev/null || \
                python3 view_pool_data.py --source local --key updater/static/test_logs.csv --generate-features --max-pools $max_pools 2>/dev/null || \
                echo "No data files found. Run option 2 first to collect data."
                ;;
            d)
                echo ""
                echo "Available options:"
                python3 view_pool_data.py --help
                ;;
            *)
                echo "Invalid choice"
                ;;
        esac
        ;;
    4)
        echo ""
        echo "Generating features from existing logs..."
        read -p "Enter max pools [default: 20]: " max_pools
        max_pools=${max_pools:-20}

        if [ -f "updater/static/oneinch_logs_1D.csv" ]; then
            python3 view_pool_data.py --source local --key updater/static/oneinch_logs_1D.csv --generate-features --max-pools $max_pools
        elif [ -f "updater/static/test_logs.csv" ]; then
            python3 view_pool_data.py --source local --key updater/static/test_logs.csv --generate-features --max-pools $max_pools
        else
            echo "No log files found. Run option 2 first to collect data."
        fi
        ;;
    5)
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    Operation Complete                      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "📁 Check these files for output:"
echo "   - eth_pool_features_test.csv"
echo "   - eth_pool_features.csv"
echo "   - updater/static/*.csv"
echo ""
echo "📖 For more info:"
echo "   - Read QUICKSTART.md"
echo "   - Read README_APY_MODEL.md"
echo ""
