# backend/strategies.py

"""
策略库模块。
每个策略函数接收一个DataFrame和一些参数，返回一个带有'Signal'列的DataFrame。
Signal: 1 表示买入/持有, -1 表示卖出/空仓, 0 表示无操作。
"""

import pandas as pd
import numpy as np


def generate_signals(data, strategy_name, params):
    """
    策略信号生成的调度中心。
    它根据传入的策略名称，动态调用对应的策略函数。
    """
    # globals() 返回一个全局符号表的字典，可以用来动态查找函数
    strategy_function = globals().get(f"strategy_{strategy_name}")

    if not strategy_function:
        raise ValueError(f"未知的策略名称: '{strategy_name}'")

    # data.copy()确保原始数据不被修改
    return strategy_function(data.copy(), **params)


def strategy_buy_and_hold(data):
    """买入并持有策略。在第一天买入，然后一直持有。"""
    data['Signal'] = 0
    if not data.empty:
        data['Signal'].iloc[0] = 1
    return data


def strategy_fixed_frequency(data, frequency='M', amount=1000):
    """定期定额投资策略。"""
    data['Signal'] = 0
    # resample方法可以按指定的频率（W-周, M-月, Y-年）对时间序列数据进行重采样
    resampled_dates = data.resample(frequency).first().index
    # 找到原始数据中与重采样日期匹配的实际交易日
    buy_dates = data.index.intersection(resampled_dates)
    data.loc[buy_dates, 'Signal'] = 1
    # 将每次投资的金额附加到DataFrame中，方便回测引擎使用
    data['InvestmentAmount'] = amount
    return data


def strategy_sma_cross(data, period=20):
    """单移动平均线策略。价格在均线之上时持有，之下时空仓。"""
    if period > len(data):
        raise ValueError("数据长度小于均线周期，无法计算。")
    data['MA'] = data['Close'].rolling(window=period).mean()
    data['Signal'] = np.where(data['Close'] > data['MA'], 1, -1)
    return data


def strategy_dma_cross(data, fast=10, slow=30):
    """双移动平均线交叉策略。快线上穿慢线时买入，下穿时卖出。"""
    if slow > len(data) or fast > len(data):
        raise ValueError("数据长度小于均线周期，无法计算。")
    data['SMA_fast'] = data['Close'].rolling(window=fast).mean()
    data['SMA_slow'] = data['Close'].rolling(window=slow).mean()
    data['Signal'] = np.where(data['SMA_fast'] > data['SMA_slow'], 1, -1)
    return data