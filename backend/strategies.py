# backend/strategies.py
import pandas as pd
import numpy as np

def generate_signals(data, strategy_name, params):
    strategy_function = globals().get(f"strategy_{strategy_name}")
    if not strategy_function:
        raise ValueError(f"未知的策略名称: '{strategy_name}'")
    return strategy_function(data.copy(), **params)

def strategy_buy_and_hold(data):
    data['Signal'] = 0
    if not data.empty:
        data['Signal'].iloc[0] = 1
    return data

def strategy_fixed_frequency(data, frequency='M', amount=1000):
    freq_map = {'W': 'W-FRI', 'M': 'ME', 'Y': 'YE'}
    actual_frequency = freq_map.get(frequency, frequency)
    data['Signal'] = 0
    resampled_dates = data.resample(actual_frequency).first().index
    buy_dates = data.index.intersection(resampled_dates)
    data.loc[buy_dates, 'Signal'] = 1
    data['InvestmentAmount'] = amount
    return data

def strategy_sma_cross(data, period=20):
    if period > len(data): raise ValueError("数据长度小于均线周期。")
    data['MA'] = data['Close'].rolling(window=period).mean()
    data['Signal'] = np.where(data['Close'] > data['MA'], 1, -1)
    return data

def strategy_dma_cross(data, fast=10, slow=30):
    if slow > len(data) or fast > len(data): raise ValueError("数据长度小于均线周期。")
    data['SMA_fast'] = data['Close'].rolling(window=fast).mean()
    data['SMA_slow'] = data['Close'].rolling(window=slow).mean()
    data['Signal'] = np.where(data['SMA_fast'] > data['SMA_slow'], 1, -1)
    return data