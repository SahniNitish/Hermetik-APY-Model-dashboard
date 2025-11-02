"""
Quick Test - Verify everything is working
"""
import os
os.environ['ALCHEMY_API_KEY'] = 'xZAA_UQS9ExBekaML58M0-T5BNvKZeRI'

print("="*80)
print("QUICK TEST - ETH Pool APY Prediction Setup")
print("="*80)

# Test 1: Check Web3 connection
print("\n[1/5] Testing Web3/Alchemy connection...")
try:
    from web3 import Web3
    w3 = Web3(Web3.HTTPProvider(f'https://eth-mainnet.g.alchemy.com/v2/{os.environ["ALCHEMY_API_KEY"]}'))

    if w3.is_connected():
        current_block = w3.eth.block_number
        print(f"  ✅ Connected to Ethereum!")
        print(f"  ✅ Current block: {current_block:,}")
    else:
        print("  ❌ Connection failed")
except Exception as e:
    print(f"  ❌ Error: {e}")

# Test 2: Check dependencies
print("\n[2/5] Checking Python dependencies...")
try:
    import pandas
    import boto3
    import networkx
    import sklearn
    print("  ✅ pandas")
    print("  ✅ boto3")
    print("  ✅ networkx")
    print("  ✅ scikit-learn")
    print("  ✅ All dependencies installed!")
except ImportError as e:
    print(f"  ❌ Missing: {e}")

# Test 3: Check modules
print("\n[3/5] Checking custom modules...")
try:
    from apy_features import is_eth_pool, calculate_all_features
    print("  ✅ apy_features.py loaded")
except Exception as e:
    print(f"  ❌ Error loading apy_features: {e}")

# Test 4: Query a real pool
print("\n[4/5] Querying a real ETH pool...")
try:
    # ETH/USDC 0.05% pool on Uniswap V3 (highest volume)
    POOL_ADDRESS = "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640"

    from apy_features import get_pool_state, calculate_tvl_features

    print(f"  Pool: {POOL_ADDRESS}")
    print("  Fetching pool state via Alchemy API...")

    pool_state = get_pool_state(POOL_ADDRESS)

    if pool_state:
        print(f"  ✅ Pool found!")
        print(f"     Token Pair: {pool_state['symbol0']}/{pool_state['symbol1']}")
        print(f"     ETH Reserve: {pool_state['eth_reserve']/1e18:.2f} ETH")
        print(f"     Fee Tier: {pool_state['fee_tier']/10000}%")

        tvl = calculate_tvl_features(pool_state, eth_price_usd=2500)
        print(f"     TVL: ${tvl.get('current_tvl_usd', 0):,.2f}")
    else:
        print("  ❌ Could not fetch pool state")

except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 5: File structure
print("\n[5/5] Checking file structure...")
import os
files = [
    'apy_features.py',
    'view_pool_data.py',
    'test_pipeline.py',
    'updater/pool_state_fetcher.mjs',
    'updater/oneinch_swaps.cjs',
    '.env'
]

for f in files:
    if os.path.exists(f):
        print(f"  ✅ {f}")
    else:
        print(f"  ⚠️  {f} (missing)")

print("\n" + "="*80)
print("SETUP CHECK COMPLETE!")
print("="*80)

print("\n🚀 Next Steps:")
print("   1. Run full pipeline: python3 test_pipeline.py")
print("   2. View data: python3 view_pool_data.py --help")
print("   3. Read docs: cat QUICKSTART.md")
