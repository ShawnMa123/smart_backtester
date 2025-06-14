# backend/analysis.py
import pandas as pd
import numpy as np


def analyze_performance(data, initial_capital):
    # --- 基本性能指标计算 ---
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

    # --- 图表数据准备 ---
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

    # --- 提取交易点 (买入/卖出标记) ---
    buy_points = []
    sell_points = []

    if not data.empty:
        # 检查是否为定投策略 (通过是否存在 InvestmentAmount 列判断)
        is_fixed_frequency_strategy = 'InvestmentAmount' in data.columns

        # 处理第一个数据点可能的交易 (例如：买入并持有，或策略在第一天就发出信号)
        if data['Signal'].iloc[0] == 1:
            buy_points.append({
                'date': data.index[0].strftime('%Y-%m-%d'),
                'value': round(data['Portfolio_Value'].iloc[0], 2)
            })
        # 注意：标准策略不应在第一天就发出卖出信号，但为完整性可添加（如果适用）
        # elif data['Signal'].iloc[0] == -1:
        #     sell_points.append({
        #         'date': data.index[0].strftime('%Y-%m-%d'),
        #         'value': round(data['Portfolio_Value'].iloc[0], 2)
        #     })

        # 从第二个数据点开始遍历，判断信号变化
        for i in range(1, len(data)):
            current_signal = data['Signal'].iloc[i]
            prev_signal = data['Signal'].iloc[i - 1]
            current_date_str = data.index[i].strftime('%Y-%m-%d')
            current_portfolio_value = round(data['Portfolio_Value'].iloc[i], 2)

            if is_fixed_frequency_strategy:
                # 定投策略：只要信号为1，就视为一次买入（投资）
                # (第一天的买入已在上面处理，这里处理后续的投资点)
                if current_signal == 1:
                    # 避免与首日判断重复添加 (理论上i从1开始不会重复)
                    # 确保这个点不是已经被首日逻辑添加的同一点（虽然不太可能，但作为防御性编程）
                    is_already_added = any(
                        p['date'] == current_date_str and p['value'] == current_portfolio_value for p in buy_points if
                        i == 0)
                    if not is_already_added:
                        buy_points.append({
                            'date': current_date_str,
                            'value': current_portfolio_value
                        })
            else:
                # 信号驱动策略：信号从非买入转为买入，或从非卖出转为卖出
                if current_signal == 1 and prev_signal <= 0:  # 从0或-1变为1
                    buy_points.append({
                        'date': current_date_str,
                        'value': current_portfolio_value
                    })
                elif current_signal == -1 and prev_signal >= 0:  # 从0或1变为-1
                    sell_points.append({
                        'date': current_date_str,
                        'value': current_portfolio_value
                    })

        # 可选：去重，以防万一有策略或数据导致在同一天同一净值重复记录
        # （对于日线数据和当前逻辑，通常不需要，但保留作为健壮性措施）
        unique_buy_points = []
        seen_buy_coords = set()
        for point in buy_points:
            coord = (point['date'], point['value'])
            if coord not in seen_buy_coords:
                unique_buy_points.append(point)
                seen_buy_coords.add(coord)
        buy_points = unique_buy_points

        unique_sell_points = []
        seen_sell_coords = set()
        for point in sell_points:
            coord = (point['date'], point['value'])
            if coord not in seen_sell_coords:
                unique_sell_points.append(point)
                seen_sell_coords.add(coord)
        sell_points = unique_sell_points

    chart_data['trade_markers'] = {
        'buy_points': buy_points,
        'sell_points': sell_points
    }

    return {'metrics': metrics, 'chart_data': chart_data}