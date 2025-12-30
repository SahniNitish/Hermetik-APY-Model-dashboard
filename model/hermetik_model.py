import numpy as np
import pandas as pd
import joblib
import argparse
import json
from pathlib import Path
import lightgbm as lgb
from sklearn.model_selection import train_test_split

def write_to_json(file_name, dataset):
     with open(file_name, "w", encoding="utf-8") as f:
          json.dump(dataset, f, indent=4)

def open_json(file_name):
    with open(file_name, "r", encoding="utf-8") as f:
        return json.load(f)

#----------------------------------------------------------------------
# Takes a data frame of liquidity pool logs and builds a dataframe of features for the model.
# To maintain consistency for the contract column, we save the contract dictionary
# to a json file.
#----------------------------------------------------------------------
def build_features(df_features, max_lag=7, train=False):
    # we transform tx count using log. The log(tx_count) difference between days is then used to approximate growth rate
    df_features['tx_transform'] = np.log(df_features['tx_count'] + 1)

    df_features['growth_rate'] = (
        df_features
        .groupby('poolAddress')['tx_transform']
        .diff()
    )

    # get growth rate at previous lags to use as features
    for k in range(1, max_lag + 1):
        df_features[f'lag_{k}'] = (
            df_features
            .groupby('poolAddress')['growth_rate']
            .shift(k)
        )

    # get rolling means of grwoth rate to use as features
    rolling_list = [3, 5, 7, 14]
    for i in rolling_list:
        df_features[f'rolling_mean_{i}d'] = (
            df_features
            .groupby('poolAddress', group_keys=False)['growth_rate']
            .transform(lambda s: s.shift(1).rolling(window=i, min_periods=1).mean())
        )
    
    # transform pool address to an int so it can be used by the model. save the contracts dictionary if the features are for training. load a saved dictionary if for prediciton
    if train:
        contracts = df_features['poolAddress'].unique()
        contracts_dic = {v: i for i, v in enumerate(contracts)}
        df_features['contract'] = df_features['poolAddress'].map(contracts_dic)
        write_to_json(f"contracts_{max_lag}.json", contracts_dic)
    else:
        try:
            contracts_dic = open_json(f"contracts_{max_lag}.json")
        except:
            print("Contracts mapping not found")
            return 0
        df_features['contract'] = df_features['poolAddress'].map(contracts_dic).fillna(-1).astype(int)
    
    # get all desired columns
    cols = ['contract', 'date', 'tx_count', 'fee_percentage', 'tx_count_cumulative', 'growth_rate', 'day_number', 'tx_transform'] 
    for k in range(1, max_lag + 1):
        cols.append(f'lag_{k}')
    for i in rolling_list:
        cols.append(f'rolling_mean_{i}d')

    df_features = df_features[cols].copy()

    # sort by date and make date an ordinal feature so it can be used by the model
    df_features['date'] = pd.to_datetime(df_features['date']).map(pd.Timestamp.toordinal)
    df_features = df_features.sort_values('date')

    return df_features

#----------------------------------------------------------------------
# create targets/labels for model training
# forecast horizon indicates how many days in the future we calculate growth
# rate for.
#----------------------------------------------------------------------
def build_targets(df_features, forecast_horizon):
    forecast_horizon *= -1
    df_features['target'] = (
        df_features
        .groupby('contract')['tx_transform']
        .transform(lambda s: s.shift(forecast_horizon) - s)
    )

    df_features = df_features.dropna(subset=['target'])

    return df_features

#----------------------------------------------------------------------
# Filters a dataset by removing those that have missing entries for certain
# days. I.e. keeps those that have an entry in the dataset for every day
#----------------------------------------------------------------------
def filter_dataset(df_dataset):
    dates = df_dataset['date'].unique()
    intersec = set(df_dataset['poolAddress'].unique())
    for date in dates:
        df_date = df_dataset[df_dataset['date'] == date]
        contracts_date = set(df_date['poolAddress'].unique())
        intersec = intersec.intersection(contracts_date)
    
    df_dataset = df_dataset[df_dataset['poolAddress'].isin(intersec)]
    return df_dataset

#----------------------------------------------------------------------
# Train and save a volume growth prediction model.
#----------------------------------------------------------------------
def train_model(max_lag=7, forecast_horizon=1):
    try:
        df_dataset = pd.read_csv('pool_dataset_latest.csv')
    except:
        print("File Not Found.")
        return 0

    #build features and targets for the model
    df_dataset = filter_dataset(df_dataset)
    df_dataset = build_features(df_dataset, max_lag, True)
    df_dataset = build_targets(df_dataset, forecast_horizon)

    feature_cols = [c for c in df_dataset.columns if c not in ['target']]
    X = df_dataset[feature_cols]
    y = df_dataset['target']

    #split the data between training and validation.
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.1, shuffle=False)

    params = {
        "objective": "huber",
        "metric": "huber",
        "alpha": 0.9,
    }

    model = lgb.LGBMRegressor(**params)

    model.fit(
        X_train, y_train,
        eval_set = [(X_val, y_val)],
        callbacks=[lgb.early_stopping(stopping_rounds=10)]
    )

    # save model
    joblib.dump(model, f"growth_model_{forecast_horizon}_{max_lag}.pkl")

#----------------------------------------------------------------------
# predict using a trained model.
# Currently the model takes a file of liquidity pool logs, and makes its 
# prediction for the day after the most recent day in that log. 
#----------------------------------------------------------------------
def predict(max_lag=7, forecast_horizon=1):
    try:
        df_features = pd.read_csv('pool_dataset_latest.csv')
    except:
        print("File Not Found.")
        return 0
    
    df_features = filter_dataset(df_features)
    df_features = build_features(df_features, max_lag, False)
    pred_date = df_features["date"].max()
    df_features = df_features[df_features["date"] == pred_date] # extract most recent day

    model = joblib.load(f"growth_model_{forecast_horizon}_{max_lag}.pkl") #load a trained model.
    preds = model.predict(df_features)
    df_features.loc[:, "predictions"] = preds

    df_features['rank'] = (
        df_features
        .groupby('date')['predictions']
        .rank(ascending=False)
    )

    df_results = df_features[['date', 'contract', 'predictions', 'rank']].copy()
    
    df_results.sort_values('rank', ascending=True, inplace=True)

    # get top 5 pools.
    date = df_results.iloc[0]['date']
    print(f"Top 5 pools for predicted growth rate on {date}")
    for i in range(5):
        pool = df_results.iloc[i]['contract']
        pred = df_results.iloc[i]['predictions']
        print(f'Pool {i} by volume growth rate: poolAddress = {pool}, predicted growth rate = {pred}')

    return df_results

#----------------------------------------------------------------------
# Arg parser. the current commands are train and predict.
#----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="volume_growth_model.py")

    parser.add_argument("command", choices=["train", "predict"])
    parser.add_argument("--forecast_horizon", type=int, default=1)
    parser.add_argument("--max_lag", type=int, default=7)

    args = parser.parse_args()

    if args.command == 'train':
        train_model(args.max_lag, args.forecast_horizon)
    elif args.command == 'predict':
        predict(args.max_lag, args.forecast_horizon)

if __name__ == "__main__":
    main()
