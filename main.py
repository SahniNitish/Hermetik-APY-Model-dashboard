import modal

stub = modal.Stub("liquidity-model")

# Define the image with necessary libraries
image = modal.Image.debian_slim().pip_install(
    "pandas", "boto3", "networkx", "scikit-learn"
)


@stub.function(
    image=image,
    secret=modal.Secret.from_name("my-aws-secret"),  # Assumes you have a Modal secret for AWS keys
)
def generate_training_data(start_date: str, end_date: str):
    """
    Generates a historical training dataset by processing daily log and graph data from S3.
    """
    import pandas as pd
    import boto3
    import networkx as nx
    from io import BytesIO
    from datetime import datetime, timedelta

    def daterange(start, end):
        curr = start
        while curr <= end:
            yield curr
            curr += timedelta(days=1)

    s3 = boto3.client("s3")
    all_rows = []
    bucket_name = "defi-liquidity-data"

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    for day in daterange(start, end):
        day_str = day.strftime("%Y-%m-%d")
        print(f"Processing {day_str}...")

        try:
            # Load graph for the day
            graph_key = f"graphs/{day_str}-token_graph.csv"
            g_obj = s3.get_object(Bucket=bucket_name, Key=graph_key)
            g_df = pd.read_csv(BytesIO(g_obj["Body"].read()))
            G = nx.from_pandas_edgelist(g_df, "node1", "node2", edge_attr=True)

            # Load logs for the day
            logs_key = f"logs/{day_str}-oneinch_logs.csv"
            l_obj = s3.get_object(Bucket=bucket_name, Key=logs_key)
            logs_df = pd.read_csv(BytesIO(l_obj["Body"].read()))

            # --- FEATURE ENGINEERING ---
            features = logs_df.groupby("Contract Address").agg(
                tx_count=("Transaction Hash", "count"),
                min_block=("Block Number", "min"),
                max_block=("Block Number", "max"),
            ).reset_index()
            features.columns = [
                "contract",
                "tx_count",
                "min_block",
                "max_block",
            ]
            features["activity_span"] = (
                features["max_block"] - features["min_block"]
            )
            features["degree"] = (
                features["contract"].map(dict(G.degree())).fillna(0)
            )
            features["centrality"] = (
                features["contract"]
                .map(nx.degree_centrality(G))
                .fillna(0)
            )

            # --- LABEL GENERATION ---
            # Get logs from the next 3 days to create the label
            future_logs = []
            for i in range(1, 4):
                future_date_str = (day + timedelta(days=i)).strftime("%Y-%m-%d")
                try:
                    future_logs_key = f"logs/{future_date_str}-oneinch_logs.csv"
                    future_obj = s3.get_object(
                        Bucket=bucket_name, Key=future_logs_key
                    )
                    df_future = pd.read_csv(BytesIO(future_obj["Body"].read()))
                    future_logs.append(df_future)
                except s3.exceptions.NoSuchKey:
                    print(f"No logs found for {future_date_str}, skipping.")
                    pass  # Missing data is okay

            if not future_logs:
                print(f"No future logs to create a label for {day_str}, skipping window.")
                continue

            future_df = pd.concat(future_logs)
            liq_df = (
                future_df.groupby("Contract Address")
                .agg(future_tx_count=("Transaction Hash", "count"))
                .reset_index()
            )
            
            # Label top 10% most active pools as "high liquidity"
            threshold = liq_df["future_tx_count"].quantile(0.9)
            liq_df["label"] = (liq_df["future_tx_count"] >= threshold).astype(int)

            # --- MERGE FEATURES AND LABELS ---
            merged = pd.merge(features, liq_df[["contract", "label"]], on="contract")
            merged["date"] = day_str
            all_rows.append(merged)

        except Exception as e:
            print(f"Error processing {day_str}: {e}")
            continue

    if all_rows:
        final_df = pd.concat(all_rows, ignore_index=True)
        out_buffer = BytesIO()
        final_df.to_csv(out_buffer, index=False)
        out_buffer.seek(0)
        s3.put_object(
            Bucket=bucket_name,
            Key="training/full_training_dataset.csv",
            Body=out_buffer,
        )
        print("Successfully generated and uploaded training dataset to S3.")


@stub.function(image=image, secret=modal.Secret.from_name("my-aws-secret"))
def train_model():
    """
    Trains a RandomForestClassifier on the generated training data from S3.
    """
    import pandas as pd
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    import boto3
    from io import BytesIO

    s3 = boto3.client("s3")
    bucket_name = "defi-liquidity-data"
    dataset_key = "training/full_training_dataset.csv"

    try:
        obj = s3.get_object(Bucket=bucket_name, Key=dataset_key)
        df = pd.read_csv(BytesIO(obj["Body"].read()))

        features = ["tx_count", "activity_span", "degree", "centrality"]
        target = "label"

        X = df[features]
        y = df[target]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        model.fit(X_train, y_train)

        accuracy = model.score(X_test, y_test)
        print(f"Model training complete. Test Accuracy: {accuracy:.4f}")

    except s3.exceptions.NoSuchKey:
        print(f"Dataset not found at s3://{bucket_name}/{dataset_key}")
    except Exception as e:
        print(f"An error occurred during model training: {e}")

if __name__ == "__main__":
    # Example local entrypoint to run the Modal functions
    # Make sure you have the Modal CLI installed and configured
    
    # To generate data:
    # modal run main.py --function-name generate_training_data --start-date YYYY-MM-DD --end-date YYYY-MM-DD
    
    # To train the model:
    # modal run main.py --function-name train_model
    pass 