import pandas as pd

from fxml4.ml.features import identify_trading_sessions


def test_overlap_session_detection():
    data = pd.DataFrame(
        {
            "time": pd.date_range("2023-01-01", periods=24, freq="h"),
            "open": 0,
            "high": 0,
            "low": 0,
            "close": 0,
            "volume": 0,
        }
    )

    # Use the available session identification function
    df = identify_trading_sessions(data)
    overlap_hours = df.loc[df["overlap_session"] == 1, "hour"].tolist()
    assert overlap_hours == list(range(7, 9)) + list(range(13, 17))
