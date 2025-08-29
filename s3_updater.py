"""
Standalone S3 updater that uses the copied Node updater under liquidity-model/updater
(no cross-dependency on router-flow).

Usage:
  cd liquidity-model
  python3 s3_updater.py --bucket <bucket-name> [--date YYYY-MM-DD] [--skip-node]

Requires:
  - Node.js and npm installed
  - npm ci run in liquidity-model/updater
  - ALCHEMY_API_KEY set in env
  - AWS credentials available for boto3
"""
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
from typing import Optional

import boto3

BASE_DIR = Path(__file__).resolve().parent
UPDATER_DIR = BASE_DIR / "updater"
STATIC_DIR = UPDATER_DIR / "static"


def run_node_update(skip_node: bool = False) -> None:
    if skip_node:
        return
    env = os.environ.copy()
    if not env.get("ALCHEMY_API_KEY"):
        raise RuntimeError("ALCHEMY_API_KEY must be set in the environment")
    script = UPDATER_DIR / "update_token_graphs.mjs"
    cmd = ["node", str(script), "--no-upload"]
    print("Running updater (node, no-upload) to generate files locally...")
    subprocess.run(cmd, cwd=str(UPDATER_DIR), check=True)


def upload_file_to_s3(bucket: str, local_path: Path, s3_key: str) -> None:
    s3 = boto3.client("s3")
    print(f"Uploading to s3://{bucket}/{s3_key}")
    s3.upload_file(str(local_path), bucket, s3_key)


def sync_outputs_to_s3(bucket: str, date_str: Optional[str] = None) -> None:
    # Rolling
    for tf in ["1D", "3D", "1W", "3W", "1M"]:
        log_file = STATIC_DIR / f"oneinch_logs_{tf}.csv"
        if log_file.exists():
            upload_file_to_s3(bucket, log_file, f"rolling/oneinch_logs_{tf}.csv")
        graph_file = STATIC_DIR / f"token_graph{tf}.csv"
        if graph_file.exists():
            upload_file_to_s3(bucket, graph_file, f"rolling/token_graph{tf}.csv")

    # Daily
    daily_logs_dir = STATIC_DIR / "daily_logs"
    daily_graphs_dir = STATIC_DIR / "daily_graphs"
    if date_str:
        logs = [daily_logs_dir / f"{date_str}-oneinch_logs.csv"]
        graphs = [daily_graphs_dir / f"{date_str}-token_graph.csv"]
    else:
        logs = sorted(daily_logs_dir.glob("*-oneinch_logs.csv")) if daily_logs_dir.exists() else []
        graphs = sorted(daily_graphs_dir.glob("*-token_graph.csv")) if daily_graphs_dir.exists() else []

    for log in logs:
        if log.exists():
            upload_file_to_s3(bucket, log, f"logs/{log.name}")
    for graph in graphs:
        if graph.exists():
            upload_file_to_s3(bucket, graph, f"graphs/{graph.name}")


def main():
    parser = argparse.ArgumentParser(description="Standalone updater: generate logs/graphs and sync to S3")
    parser.add_argument("--bucket", required=True, help="S3 bucket name")
    parser.add_argument("--date", help="Specific date YYYY-MM-DD to process; defaults to today")
    parser.add_argument("--skip-node", action="store_true", help="Skip running node updater and only upload existing files")
    args = parser.parse_args()

    # 1) Run Node updater to generate files locally (uses copied scripts)
    run_node_update(skip_node=args.skip_node)

    # 2) Sync to S3
    sync_outputs_to_s3(args.bucket, date_str=args.date)


if __name__ == "__main__":
    main()
