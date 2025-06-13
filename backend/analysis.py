# backend/analysis.py

"""
性能分析模块。
接收带有回测结果（如投资组合净值）的DataFrame，
计算各项性能指标和图表所需的数据。
"""

import pandas as pd
import numpy as np


def analyze_performance(data, initial_capital):
    """
    对回测结果进行全面分析。

    Args:
        data (pd.DataFrame): 包含'Portfolio_Value'和其他净值曲线的DataFrame。
        initial_capital (float): 初始资金。

    Returns:
        dict: 包含 'metrics' 和 'chart_data' 的字典。
    """
    # --- 1. 计算核心性能指标 (KPIs) ---
    final_value = data['Portfolio_Value'].iloc[-1]
    total_return = (final_value / initial_capital - 1) * 100

    days = (data.index[-1] - data.index[0]).days
    # 避免days为0时除零错误
    if days > 0:
        annualized_return = ((1 + total_return / 100) ** (365.0 / days) - 1) * 100
    else:
        annualized_return = 0

    # 计算最大回撤
    peak = data['Portfolio_Value'].cummax()
    drawdown = (data['Portfolio_Value'] - peak) / peak
    max_drawdown = drawdown.min() * 100

    # --- 2. 计算周期性收益率 ---
    # 月度收益率
    monthly_returns = data['Portfolio_Value'].resample('M').last().pct_change().fillna(0)

    # 年度收益率
    yearly_returns = data['Portfolio_Value'].resample('Y').last().pct_change().fillna(0)

    # --- 3. 准备返回给前端的数据结构 ---
    metrics = {
        'totalReturn': round(total_return, 2),
        'annualizedReturn': round(annualized_return, 2),
        'maxDrawdown': round(max_drawdown, 2),
    }

    chart_data = {
        'portfolio_curve': {
            'dates': data.index.strftime('%Y-%m-%d').tolist(),
            'values': data['Portfolio_Value'].round(2).tolist(),
        },
        'benchmark_curve': {
            'dates': data.index.strftime('%Y-%m-%d').tolist(),
            'values': data['Benchmark_Value'].round(2).tolist(),
        },
        'monthly_returns': {
            'dates': monthly_returns.index.strftime('%Y-%m').tolist(),
            'values': (monthly_returns * 100).round(2).tolist(),
        },
        'yearly_returns': {
            'dates': yearly_returns.index.strftime('%Y').tolist(),
            'values': (yearly_returns * 100).round(2).tolist(),
        }
    }

    return {'metrics': metrics, 'chart_data': chart_data}