# backend/analysis.py
import pandas as pd
import numpy as np


def analyze_performance(data, initial_capital, config):  # Added config parameter
    # --- 基本性能指标计算 ---
    final_value = data['Portfolio_Value'].iloc[-1] if not data.empty and initial_capital > 0 else initial_capital
    total_return = (final_value / initial_capital - 1) * 100 if initial_capital > 0 else 0

    days = 0
    if not data.empty:
        days = (data.index[-1] - data.index[0]).days

    annualized_return = 0
    if initial_capital > 0 and days > 0:
        annualized_return = ((1 + total_return / 100) ** (365.0 / days) - 1) * 100

    max_drawdown = 0
    if not data.empty and initial_capital > 0:
        peak = data['Portfolio_Value'].cummax()
        drawdown = (data['Portfolio_Value'] - peak) / peak
        max_drawdown = drawdown.min() * 100

    monthly_returns = pd.Series(dtype=float)
    yearly_returns = pd.Series(dtype=float)
    if not data.empty and initial_capital > 0:
        monthly_returns = data['Portfolio_Value'].resample('ME').last().pct_change().fillna(0)
        yearly_returns = data['Portfolio_Value'].resample('YE').last().pct_change().fillna(0)

    metrics = {
        'totalReturn': round(total_return, 2),
        'annualizedReturn': round(annualized_return, 2),
        'maxDrawdown': round(max_drawdown, 2),
    }

    # --- 图表数据准备 ---
    # ---- MODIFIED: Add raw asset price for chart ----
    asset_price_dates = []
    asset_price_values = []
    if not data.empty:
        asset_price_dates = data.index.strftime('%Y-%m-%d').tolist()
        asset_price_values = data['Close'].round(2).tolist()
    # ---- END MODIFIED ----

    portfolio_curve_dates = []
    portfolio_curve_values = []
    benchmark_curve_dates = []
    benchmark_curve_values = []
    monthly_ret_dates = []
    monthly_ret_values = []
    yearly_ret_dates = []
    yearly_ret_values = []

    if not data.empty:
        portfolio_curve_dates = data.index.strftime('%Y-%m-%d').tolist()
        portfolio_curve_values = data['Portfolio_Value'].round(2).tolist()
        if 'Benchmark_Value' in data.columns:
            benchmark_curve_dates = data.index.strftime('%Y-%m-%d').tolist()  # Same dates
            benchmark_curve_values = data['Benchmark_Value'].round(2).tolist()
        if not monthly_returns.empty:
            monthly_ret_dates = monthly_returns.index.strftime('%Y-%m').tolist()
            monthly_ret_values = (monthly_returns * 100).round(2).tolist()
        if not yearly_returns.empty:
            yearly_ret_dates = yearly_returns.index.strftime('%Y').tolist()
            yearly_ret_values = (yearly_returns * 100).round(2).tolist()

    chart_data = {
        'asset_price_curve': {'dates': asset_price_dates, 'values': asset_price_values},  # New
        'portfolio_curve': {'dates': portfolio_curve_dates, 'values': portfolio_curve_values},
        'benchmark_curve': {'dates': benchmark_curve_dates, 'values': benchmark_curve_values},  # This is asset B&H
        'monthly_returns': {'dates': monthly_ret_dates, 'values': monthly_ret_values},
        'yearly_returns': {'dates': yearly_ret_dates, 'values': yearly_ret_values},
        'assetName': config.get('assetName', config.get('ticker')),  # Get asset name
        'benchmarkAssetName': config.get('benchmarkAssetName', config.get('benchmarkTicker'))  # Get benchmark name
    }

    # --- 提取交易点 (买入/卖出标记) ---
    # ---- MODIFIED: Include asset_price for markers to be plotted on asset_price_curve ----
    buy_points = []
    sell_points = []

    if not data.empty:
        strategy_name_from_config = config.get('strategy', {}).get('name')  # Get strategy name from config
        is_fixed_frequency_strategy = 'InvestmentAmount' in data.columns and strategy_name_from_config == 'fixed_frequency'

        # Check the first day for buy_and_hold or initial signal
        # For buy_and_hold, signal is 1 on first day.
        # For fixed_frequency, if first day is an investment day, Signal is 1.
        if data['Signal'].iloc[0] == 1 and data['Portfolio_Value'].iloc[0] != initial_capital:  # Trade happened
            buy_points.append({
                'date': data.index[0].strftime('%Y-%m-%d'),
                'value': round(data['Portfolio_Value'].iloc[0], 2),  # Portfolio value at trade time
                'asset_price': round(data['Close'].iloc[0], 2)  # Asset price at trade time
            })

        for i in range(1, len(data)):
            current_signal = data['Signal'].iloc[i]
            prev_signal = data['Signal'].iloc[i - 1]  # Strategy signal from previous day
            current_date_str = data.index[i].strftime('%Y-%m-%d')
            current_portfolio_value = round(data['Portfolio_Value'].iloc[i], 2)
            current_asset_price = round(data['Close'].iloc[i], 2)

            if is_fixed_frequency_strategy:
                if current_signal == 1 and data['InvestmentAmount'].iloc[i] > 0:  # Actual investment day
                    buy_points.append({
                        'date': current_date_str,
                        'value': current_portfolio_value,
                        'asset_price': current_asset_price
                    })
            else:  # Signal-driven strategies (including SL/TP overrides)
                # Buy: signal changes from non-buy to buy
                if current_signal == 1 and prev_signal <= 0:
                    buy_points.append({
                        'date': current_date_str,
                        'value': current_portfolio_value,
                        'asset_price': current_asset_price
                    })
                # Sell: signal changes from non-sell to sell
                elif current_signal == -1 and prev_signal >= 0:
                    sell_points.append({
                        'date': current_date_str,
                        'value': current_portfolio_value,
                        'asset_price': current_asset_price
                    })

        # Deduplication (optional, but good practice)
        buy_points = [dict(t) for t in {tuple(d.items()) for d in buy_points}]
        sell_points = [dict(t) for t in {tuple(d.items()) for d in sell_points}]
        buy_points.sort(key=lambda x: x['date'])
        sell_points.sort(key=lambda x: x['date'])

    chart_data['trade_markers'] = {
        'buy_points': buy_points,
        'sell_points': sell_points
    }
    # ---- END MODIFIED ----

    # Add extra benchmark (market index) if available
    if 'Benchmark_Index_Value' in data.columns and not data.empty:
        chart_data['market_benchmark_curve'] = {  # New name
            'name': config.get('benchmarkAssetName', config.get('benchmarkTicker', '大盘指数')),
            'dates': data.index.strftime('%Y-%m-%d').tolist(),
            'values': data['Benchmark_Index_Value'].round(2).tolist(),
        }

    return {'metrics': metrics, 'chart_data': chart_data}