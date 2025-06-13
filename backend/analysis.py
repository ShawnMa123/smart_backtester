# backend/analysis.py
import pandas as pd
import numpy as np


def analyze_performance(data, initial_capital):
    final_value = data['Portfolio_Value'].iloc[-1]
    total_return = (final_value / initial_capital - 1) * 100
    days = (data.index[-1] - data.index[0]).days
    annualized_return = ((1 + total_return / 100) ** (365.0 / days) - 1) * 100 if days > 0 else 0
    peak = data['Portfolio_Value'].cummax()
    drawdown = (data['Portfolio_Value'] - peak) / peak
    max_drawdown = drawdown.min() * 100

    monthly_returns = data['Portfolio_Value'].resample('ME').last().pct_change().fillna(0)
    yearly_returns = data['Portfolio_Value'].resample('YE').last().pct_change().fillna(0)

    metrics = {
        'totalReturn': round(total_return, 2),
        'annualizedReturn': round(annualized_return, 2),
        'maxDrawdown': round(max_drawdown, 2),
    }

    chart_data = {
        'portfolio_curve': {'dates': data.index.strftime('%Y-%m-%d').tolist(),
                            'values': data['Portfolio_Value'].round(2).tolist()},
        'benchmark_curve': {'dates': data.index.strftime('%Y-%m-%d').tolist(),
                            'values': data['Benchmark_Value'].round(2).tolist()},
        'monthly_returns': {'dates': monthly_returns.index.strftime('%Y-%m').tolist(),
                            'values': (monthly_returns * 100).round(2).tolist()},
        'yearly_returns': {'dates': yearly_returns.index.strftime('%Y').tolist(),
                           'values': (yearly_returns * 100).round(2).tolist()}
    }

    return {'metrics': metrics, 'chart_data': chart_data}