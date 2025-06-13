# backend/strategies.py
import pandas as pd
import numpy as np

def generate_signals(data, strategy_name, params):
    """策略信号生成器的调度中心"""
    strategy_func = globals().get(f"strategy_{strategy_name}")
    if not strategy_func:
        raise ValueError(f"Unknown strategy: {strategy_name}")
    return strategy_func(data.copy(), **params)

def strategy_buy_and_hold(data):
    """买入并持有策略"""
    data['Signal'] = 0
    data['Signal'].iloc[0] = 1  # 1: 买入信号
    return data

def strategy_fixed_frequency(data, frequency='M', amount=1000):
    """定期定额策略"""
    data['Signal'] = 0
    resampled_dates = data.resample(frequency).first().index
    buy_dates = data.index.intersection(resampled_dates)
    data.loc[buy_dates, 'Signal'] = 1 # 在每个周期的第一个交易日标记买入
    data['InvestmentAmount'] = amount # 附加每次投资金额
    return data

def strategy_sma_cross(data, period=20):
    """单均线交叉策略"""
    data['MA'] = data['Close'].rolling(window=period).mean()
    # 简单的版本：在均线之上持有，之下空仓
    data['Signal'] = np.where(data['Close'] > data['MA'], 1, -1) # 1: 买入/持有, -1: 卖出/空仓
    return data

def strategy_dma_cross(data, fast=10, slow=30):
    """双均线交叉策略"""
    data['SMA_fast'] = data['Close'].rolling(window=fast).mean()
    data['SMA_slow'] = data['Close'].rolling(window=slow).mean()
    data['Signal'] = np.where(data['SMA_fast'] > data['SMA_slow'], 1, -1)
    return data

# 未来可以继续在这里添加更多策略...
# def strategy_rsi(data, period=14, buy_threshold=30, sell_threshold=70):
#     ...