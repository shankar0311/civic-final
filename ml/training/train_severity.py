import argparse
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split


FEATURE_COLUMNS = [
    "depth_score",
    "spread_score",
    "emotion_score",
    "location_score",
    "upvote_score",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Train a road severity regressor")
    parser.add_argument("--csv", required=True, help="CSV with feature columns and severity_score")
    parser.add_argument("--output", required=True, help="Output .joblib file")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    return parser.parse_args()


def main():
    args = parse_args()
    df = pd.read_csv(args.csv)

    required = FEATURE_COLUMNS + ["severity_score"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    X = df[FEATURE_COLUMNS].astype(float)
    y = df["severity_score"].astype(float)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=args.test_size,
        random_state=args.random_state,
    )

    model = RandomForestRegressor(
        n_estimators=300,
        max_depth=8,
        random_state=args.random_state,
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "feature_columns": FEATURE_COLUMNS,
            "metrics": {
                "mae": float(mae),
                "rows": int(len(df)),
            },
        },
        output_path,
    )

    print(f"Saved severity model to: {output_path}")
    print(f"Validation MAE: {mae:.4f}")


if __name__ == "__main__":
    main()
