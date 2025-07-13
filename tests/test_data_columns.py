import pandas as pd

def test_rate_columns_exist():
    df = pd.read_csv('data/all_data.csv')
    assert {'Rate', 'Bond10', 'Rate_US', 'Bond10_US'}.issubset(df.columns)
