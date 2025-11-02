"""
APY Feature Engineering Module
Calculates advanced features for ETH pool APY prediction
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from io import BytesIO
import boto3
from web3 import Web3
import os
import json
import time

# WETH address on Ethereum mainnet
WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

# Alchemy setup
ALCHEMY_KEY = os.getenv('ALCHEMY_API_KEY', 'xZAA_UQS9ExBekaML58M0-T5BNvKZeRI')
w3 = Web3(Web3.HTTPProvider(f'https://eth-mainnet.g.alchemy.com/v2/{ALCHEMY_KEY}'))

# ABIs
UNISWAP_V3_POOL_ABI = [
    {
        "inputs": [],
        "name": "token0",
        "outputs": [{"type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "token1",
        "outputs": [{"type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "fee",
        "outputs": [{"type": "uint24"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "slot0",
        "outputs": [
            {"type": "uint160", "name": "sqrtPriceX96"},
            {"type": "int24", "name": "tick"},
            {"type": "uint16", "name": "observationIndex"},
            {"type": "uint16", "name": "observationCardinality"},
            {"type": "uint16", "name": "observationCardinalityNext"},
            {"type": "uint8", "name": "feeProtocol"},
            {"type": "bool", "name": "unlocked"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "liquidity",
        "outputs": [{"type": "uint128"}],
        "stateMutability": "view",
        "type": "function"
    }
]

ERC20_ABI = [
    {
        "inputs": [{"type": "address"}],
        "name": "balanceOf",
        "outputs": [{"type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"type": "uint8"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "symbol",
        "outputs": [{"type": "string"}],
        "stateMutability": "view",
        "type": "function"
    }
]


def is_eth_pool(contract_address, logs_df):
    """
    Determine if a pool involves ETH/WETH
    """
    pool_logs = logs_df[logs_df['Contract Address'] == contract_address]

    if pool_logs.empty:
        return False

    # Check if WETH is in input or output tokens
    all_tokens = set(pool_logs['Input Token'].unique()) | set(pool_logs['Output Token'].unique())

    return WETH_ADDRESS.lower() in [t.lower() for t in all_tokens]


def get_eth_paired_token(contract_address, logs_df):
    """
    Get the token paired with ETH in this pool
    """
    pool_logs = logs_df[logs_df['Contract Address'] == contract_address]

    if pool_logs.empty:
        return None

    all_tokens = set(pool_logs['Input Token'].unique()) | set(pool_logs['Output Token'].unique())

    # Remove WETH to get paired token
    paired_tokens = [t for t in all_tokens if t.lower() != WETH_ADDRESS.lower()]

    return paired_tokens[0] if paired_tokens else None


def get_pool_state(pool_address):
    """
    Fetch current pool state using Alchemy/Web3
    Returns: dict with token0, token1, reserves, fee tier, etc.
    """
    try:
        # Convert to checksum address
        pool_address = Web3.to_checksum_address(pool_address)

        # Create contract instance
        pool = w3.eth.contract(address=pool_address, abi=UNISWAP_V3_POOL_ABI)

        # Fetch pool data
        token0 = pool.functions.token0().call()
        token1 = pool.functions.token1().call()
        fee_tier = pool.functions.fee().call()
        slot0 = pool.functions.slot0().call()
        liquidity = pool.functions.liquidity().call()

        # Get reserves
        token0_contract = w3.eth.contract(address=token0, abi=ERC20_ABI)
        token1_contract = w3.eth.contract(address=token1, abi=ERC20_ABI)

        reserve0 = token0_contract.functions.balanceOf(pool_address).call()
        reserve1 = token1_contract.functions.balanceOf(pool_address).call()

        decimals0 = token0_contract.functions.decimals().call()
        decimals1 = token1_contract.functions.decimals().call()

        # Get symbols
        try:
            symbol0 = token0_contract.functions.symbol().call()
            symbol1 = token1_contract.functions.symbol().call()
        except:
            symbol0 = 'UNKNOWN'
            symbol1 = 'UNKNOWN'

        # Check if ETH pool
        is_eth = (token0.lower() == WETH_ADDRESS.lower() or
                  token1.lower() == WETH_ADDRESS.lower())

        if not is_eth:
            return None

        eth_is_token0 = token0.lower() == WETH_ADDRESS.lower()

        return {
            'pool_address': pool_address,
            'token0': token0,
            'token1': token1,
            'symbol0': symbol0,
            'symbol1': symbol1,
            'reserve0': reserve0,
            'reserve1': reserve1,
            'decimals0': decimals0,
            'decimals1': decimals1,
            'fee_tier': fee_tier,
            'fee_percentage': fee_tier / 1000000,  # Convert to decimal
            'sqrtPriceX96': slot0[0],
            'tick': slot0[1],
            'liquidity': liquidity,
            'is_eth_pool': is_eth,
            'eth_is_token0': eth_is_token0,
            'eth_reserve': reserve0 if eth_is_token0 else reserve1,
            'paired_token_reserve': reserve1 if eth_is_token0 else reserve0,
            'paired_token_address': token1 if eth_is_token0 else token0,
            'paired_token_symbol': symbol1 if eth_is_token0 else symbol0
        }

    except Exception as e:
        print(f"Error fetching pool state for {pool_address}: {e}")
        return None


def calculate_tvl_features(pool_state, eth_price_usd=2500):
    """
    Calculate TVL-related features
    """
    if not pool_state:
        return {}

    try:
        eth_reserve = pool_state['eth_reserve'] / 1e18  # Convert to ETH

        # TVL = 2 * ETH reserve value (assuming balanced pool)
        tvl_usd = 2 * eth_reserve * eth_price_usd
        tvl_eth = 2 * eth_reserve

        return {
            'current_tvl_eth': tvl_eth,
            'current_tvl_usd': tvl_usd,
            'eth_reserve': eth_reserve,
            'fee_tier': pool_state['fee_tier'],
            'fee_percentage': pool_state['fee_percentage']
        }
    except Exception as e:
        print(f"Error calculating TVL: {e}")
        return {}


def calculate_volume_features(logs_df, contract_address, lookback_blocks=7200):
    """
    Calculate trading volume and activity features
    """
    pool_logs = logs_df[logs_df['Contract Address'] == contract_address]

    if pool_logs.empty:
        return {}

    # Get recent transactions
    if 'Block Number' in pool_logs.columns:
        max_block = pool_logs['Block Number'].max()
        recent_logs = pool_logs[pool_logs['Block Number'] >= max_block - lookback_blocks]
    else:
        recent_logs = pool_logs

    # Calculate features
    tx_count = len(recent_logs)
    unique_users = recent_logs['Transaction Hash'].nunique() if 'Transaction Hash' in recent_logs.columns else 0

    # Calculate activity span
    if 'Block Number' in recent_logs.columns and len(recent_logs) > 1:
        min_block = recent_logs['Block Number'].min()
        max_block = recent_logs['Block Number'].max()
        activity_span = max_block - min_block
    else:
        activity_span = 0

    return {
        'tx_count': tx_count,
        'unique_users': unique_users,
        'activity_span': activity_span,
        'avg_tx_per_block': tx_count / max(activity_span, 1) if activity_span > 0 else 0
    }


def estimate_fee_revenue(pool_state, volume_features, lookback_days=1):
    """
    Estimate fee revenue based on volume and fee tier
    This is an approximation - actual fee collection requires swap event analysis
    """
    if not pool_state or not volume_features:
        return {}

    try:
        # Rough estimate: assume average swap size is 1% of TVL
        tvl_features = calculate_tvl_features(pool_state)
        avg_swap_size_usd = tvl_features.get('current_tvl_usd', 0) * 0.01

        tx_count = volume_features.get('tx_count', 0)
        estimated_volume_usd = avg_swap_size_usd * tx_count

        fee_revenue = estimated_volume_usd * pool_state['fee_percentage']

        return {
            'estimated_volume_usd': estimated_volume_usd,
            'estimated_fee_revenue': fee_revenue,
            'avg_swap_size_usd': avg_swap_size_usd
        }
    except Exception as e:
        print(f"Error estimating fee revenue: {e}")
        return {}


def calculate_apy(fee_revenue, tvl, days=1):
    """
    Calculate APY from fee revenue and TVL
    APY = (Fee Revenue / TVL) * (365 / Days) * 100
    """
    if tvl == 0:
        return 0

    apy = (fee_revenue / tvl) * (365 / days) * 100
    return apy


def calculate_all_features(contract_address, logs_df, eth_price_usd=2500):
    """
    Calculate all features for a given pool
    Returns: dict with all features for ML model
    """
    features = {
        'contract': contract_address,
        'timestamp': datetime.now().isoformat()
    }

    # Check if ETH pool
    if not is_eth_pool(contract_address, logs_df):
        return None  # Skip non-ETH pools

    # Get pool state from blockchain
    pool_state = get_pool_state(contract_address)
    if not pool_state:
        return None

    # Calculate TVL features
    tvl_features = calculate_tvl_features(pool_state, eth_price_usd)
    features.update(tvl_features)

    # Calculate volume features
    volume_features = calculate_volume_features(logs_df, contract_address)
    features.update(volume_features)

    # Estimate fee revenue
    fee_features = estimate_fee_revenue(pool_state, volume_features)
    features.update(fee_features)

    # Add paired token info
    features['paired_token'] = pool_state['paired_token_symbol']
    features['paired_token_address'] = pool_state['paired_token_address']

    # Calculate estimated current APY (1 day basis)
    if 'estimated_fee_revenue' in features and 'current_tvl_usd' in features:
        features['estimated_current_apy'] = calculate_apy(
            features['estimated_fee_revenue'],
            features['current_tvl_usd'],
            days=1
        )

    return features


def batch_calculate_features(logs_df, eth_price_usd=2500, max_pools=50):
    """
    Calculate features for all pools in the logs
    Returns: DataFrame with all features
    """
    print(f"\n📊 Calculating features for ETH pools...")
    print(f"Total contracts in logs: {logs_df['Contract Address'].nunique()}")

    all_features = []
    contracts = logs_df['Contract Address'].unique()

    # Limit to top N pools by transaction count
    contract_tx_counts = logs_df['Contract Address'].value_counts().head(max_pools)
    contracts_to_process = contract_tx_counts.index.tolist()

    print(f"Processing top {len(contracts_to_process)} pools by transaction count...")

    for i, contract in enumerate(contracts_to_process, 1):
        print(f"\n[{i}/{len(contracts_to_process)}] Processing {contract}...")

        features = calculate_all_features(contract, logs_df, eth_price_usd)

        if features:
            all_features.append(features)
            print(f"  ✅ ETH Pool: {features.get('paired_token', 'UNKNOWN')}/ETH")
            print(f"  📈 TVL: ${features.get('current_tvl_usd', 0):,.2f}")
            print(f"  💰 Est. APY: {features.get('estimated_current_apy', 0):.2f}%")
        else:
            print(f"  ⏭️  Skipped (not an ETH pool or error)")

        # Rate limiting to avoid API throttling
        time.sleep(0.2)

    if not all_features:
        print("\n❌ No ETH pools found!")
        return pd.DataFrame()

    features_df = pd.DataFrame(all_features)
    print(f"\n✅ Successfully processed {len(features_df)} ETH pools")

    return features_df


def save_features_to_csv(features_df, output_path):
    """
    Save features to CSV file
    """
    features_df.to_csv(output_path, index=False)
    print(f"\n💾 Saved features to {output_path}")


def save_features_to_s3(features_df, bucket_name, key):
    """
    Save features to S3
    """
    s3 = boto3.client('s3')
    csv_buffer = BytesIO()
    features_df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)

    s3.put_object(Bucket=bucket_name, Key=key, Body=csv_buffer.getvalue())
    print(f"\n☁️  Saved features to s3://{bucket_name}/{key}")


if __name__ == "__main__":
    print("APY Features Module - Test Mode")
    print(f"Web3 Connected: {w3.is_connected()}")
    print(f"Current Block: {w3.eth.block_number}")
