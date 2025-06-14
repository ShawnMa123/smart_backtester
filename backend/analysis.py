# backend/analysis.py
import pandas as pd
import numpy as np


def analyze_performance(data, initial_capital_ref, config):
    final_portfolio_value = 0
    if not data.empty and 'Portfolio_Value' in data.columns:
        final_portfolio_value = data['Portfolio_Value'].iloc[-1]

    total_return = 0
    total_invested_by_strategy = 0
    if not data.empty and 'Cumulative_Investment' in data.columns and not data['Cumulative_Investment'].empty:
        total_invested_by_strategy = data['Cumulative_Investment'].iloc[-1]

    if initial_capital_ref > 0:
        # If ref capital is set, return is based on that (initial_capital_ref + final_portfolio_value) / initial_capital_ref -1
        # because portfolio_value is PnL from 0 cash.
        # So, total value relative to ref = initial_capital_ref + final_portfolio_value (if portfolio_value is PnL)
        # This interpretation of portfolio_value needs to be consistent.
        # If portfolio_value = cash_balance (neg) + shares_value (pos), then it is already the NAV.
        # Return = (final_NAV / initial_ref_capital) - 1
        total_return = (final_portfolio_value / initial_capital_ref - 1) * 100 if initial_capital_ref > 0 else 0
        # This formula is correct if final_portfolio_value is the *final total value if one started with initial_capital_ref*.
        # But our final_portfolio_value IS the NAV starting from 0 cash.
        # So if initial_capital_ref is set, it means we compare the PnL (final_portfolio_value) against this ref.
        # Example: ref=100k, PnL=10k. Return = 10k/100k = 10%.
        # The current formula (final_portfolio_value / initial_capital_ref - 1) assumes final_portfolio_value itself is the total end value.
        # Let's adjust: if ref > 0, return is final_portfolio_value (which is PnL) / initial_capital_ref
        total_return = (final_portfolio_value / initial_capital_ref) * 100 if initial_capital_ref > 0 else 0


    elif total_invested_by_strategy > 0:
        total_return = (final_portfolio_value / total_invested_by_strategy) * 100
    else:  # No investment made and no ref capital
        total_return = 0

    days = 0
    if not data.empty:
        days = (data.index[-1] - data.index[0]).days

    annualized_return = 0
    if days > 0 and (initial_capital_ref > 0 or total_invested_by_strategy > 0):  # Avoid issues if no investment base
        annualized_return = ((1 + total_return / 100) ** (365.0 / days) - 1) * 100

    max_drawdown = 0
    if not data.empty and 'Portfolio_Value' in data.columns:
        # Max drawdown for portfolio_value that starts at 0 and grows (is PnL)
        # Drawdown is from the peak PnL achieved.
        # (Current PnL - Peak PnL) / (Initial Investment for that peak OR Peak PnL itself if >0)
        # Using simple (Current - Peak) / Peak (if Peak > 0)
        peak_pnl = data['Portfolio_Value'].cummax()
        drawdown_val = data['Portfolio_Value'] - peak_pnl  # This is absolute drawdown

        # Relative drawdown: drawdown_val / peak_pnl (if peak_pnl > 0)
        # Or drawdown_val / (total_invested_at_peak_time)
        # For simplicity with PnL curve:
        relative_drawdown = pd.Series(index=data.index, dtype=float).fillna(0.0)
        # Calculate drawdown only where peak_pnl is positive, otherwise drawdown is 0 or undefined.
        # If using total_invested_by_strategy as base:
        # Base for drawdown % = total_invested_by_strategy if > 0 else initial_capital_ref if >0 else 1 (to avoid /0)
        drawdown_base = total_invested_by_strategy if total_invested_by_strategy > 0 else (
            initial_capital_ref if initial_capital_ref > 0 else 0)

        if drawdown_base > 0:
            # Drawdown relative to the capital that generated the peak.
            # This is complex. Let's use a simpler (value - peak)/peak for positive peaks.
            positive_peak_indices = peak_pnl > 0
            relative_drawdown[positive_peak_indices] = (data['Portfolio_Value'][positive_peak_indices] - peak_pnl[
                positive_peak_indices]) / peak_pnl[positive_peak_indices]
            max_drawdown = relative_drawdown.min() * 100
        elif np.any(data['Portfolio_Value'] < 0):  # If PnL goes negative
            max_drawdown = (data['Portfolio_Value'].min() / config.get('first_investment_amount',
                                                                       1)) * 100 if config.get(
                'first_investment_amount', 0) > 0 else data['Portfolio_Value'].min()
        else:
            max_drawdown = 0.0

    monthly_returns_series = pd.Series(dtype=float)
    yearly_returns_series = pd.Series(dtype=float)
    if not data.empty and 'Portfolio_Value' in data.columns:
        # To calculate meaningful percentage returns, we need a basis.
        # If portfolio is PnL from 0, use daily PnL changes relative to cumulative investment.
        # Daily return = daily_change_in_PnL / cumulative_investment_at_start_of_day
        # This is more involved. For now, use pct_change on PnL if PnL is mostly positive.
        pv_for_returns = data['Portfolio_Value']
        # Shift to make values positive for pct_change if it starts near 0. Or use diff / previous_cumulative_investment.
        # If many values are zero or negative, pct_change is problematic.
        # Let's use diff() for absolute changes, then normalize by cumulative investment.
        daily_pnl_change = data['Portfolio_Value'].diff().fillna(0)
        cumulative_investment_shifted = data['Cumulative_Investment'].shift(1).fillna(0)  # Investment at start of day

        # Avoid division by zero if no investment yet for that day
        valid_investment_base = cumulative_investment_shifted > 0
        daily_returns_pct = pd.Series(index=data.index, dtype=float).fillna(0.0)
        daily_returns_pct[valid_investment_base] = daily_pnl_change[valid_investment_base] / \
                                                   cumulative_investment_shifted[valid_investment_base]

        if not daily_returns_pct.empty:
            # Resample these daily % returns to get aggregate monthly/yearly returns
            # This requires compounding, not just resampling pct_change.
            # Simplified: (1+r1)(1+r2)... For monthly, resample daily returns, then compound.
            # Or, stick to simpler Portfolio_Value.pct_change if it's mostly positive after some trades.
            pv_positive_for_returns = data['Portfolio_Value'][
                data['Portfolio_Value'] > 0]  # Use only positive part for pct_change
            if not pv_positive_for_returns.empty:
                monthly_returns_series = pv_positive_for_returns.resample('ME').last().pct_change().fillna(0)
                yearly_returns_series = pv_positive_for_returns.resample('YE').last().pct_change().fillna(0)

    metrics = {
        'totalReturn': round(total_return, 2),
        'annualizedReturn': round(annualized_return, 2),
        'maxDrawdown': round(max_drawdown, 2),
    }

    # Chart data prep remains largely the same, just ensure keys match frontend
    asset_price_dates = data.index.strftime('%Y-%m-%d').tolist() if not data.empty else []
    asset_price_values = data['Close'].round(2).tolist() if not data.empty else []
    portfolio_curve_dates = data.index.strftime('%Y-%m-%d').tolist() if not data.empty else []
    portfolio_curve_values = data['Portfolio_Value'].round(
        2).tolist() if not data.empty and 'Portfolio_Value' in data.columns else []
    asset_benchmark_dates = data.index.strftime('%Y-%m-%d').tolist() if not data.empty else []
    asset_benchmark_values = data['Asset_Benchmark_Value'].round(
        2).tolist() if not data.empty and 'Asset_Benchmark_Value' in data.columns else []
    market_benchmark_dates = data.index.strftime('%Y-%m-%d').tolist() if not data.empty else []
    market_benchmark_values = data['Market_Benchmark_Value'].round(
        2).tolist() if not data.empty and 'Market_Benchmark_Value' in data.columns else []
    monthly_ret_dates = monthly_returns_series.index.strftime(
        '%Y-%m').tolist() if not monthly_returns_series.empty else []
    monthly_ret_values = (monthly_returns_series * 100).round(2).tolist() if not monthly_returns_series.empty else []
    yearly_ret_dates = yearly_returns_series.index.strftime('%Y').tolist() if not yearly_returns_series.empty else []
    yearly_ret_values = (yearly_returns_series * 100).round(2).tolist() if not yearly_returns_series.empty else []

    chart_data = {
        'asset_price_curve': {'dates': asset_price_dates, 'values': asset_price_values},
        'portfolio_curve': {'dates': portfolio_curve_dates, 'values': portfolio_curve_values},
        'asset_benchmark_curve': {'dates': asset_benchmark_dates, 'values': asset_benchmark_values},
        'market_benchmark_curve': {'dates': market_benchmark_dates, 'values': market_benchmark_values},
        'monthly_returns': {'dates': monthly_ret_dates, 'values': monthly_ret_values},
        'yearly_returns': {'dates': yearly_ret_dates, 'values': yearly_ret_values},
        'assetName': config.get('assetName', config.get('ticker')),
        'benchmarkAssetName': config.get('benchmarkAssetName', config.get('benchmarkTicker'))
    }

    # Trade markers logic remains the same (using point.portfolio_value and point.asset_price)
    buy_points = []
    sell_points = []
    if not data.empty and 'Signal' in data.columns:
        strategy_name_from_config = config.get('strategy', {}).get('name')
        is_fixed_frequency_strategy = 'InvestmentAmount' in data.columns and strategy_name_from_config == 'fixed_frequency'

        if data['Signal'].iloc[0] == 1:
            buy_points.append({
                'date': data.index[0].strftime('%Y-%m-%d'),
                'portfolio_value': round(data['Portfolio_Value'].iloc[0], 2),
                'asset_price': round(data['Close'].iloc[0], 2)
            })

        for i in range(1, len(data)):
            current_signal = data['Signal'].iloc[i]
            prev_data_signal = data['Signal'].iloc[i - 1]
            current_date_str = data.index[i].strftime('%Y-%m-%d')
            current_portfolio_value = round(data['Portfolio_Value'].iloc[i], 2)
            current_asset_price = round(data['Close'].iloc[i], 2)

            if is_fixed_frequency_strategy:
                if current_signal == 1 and data['InvestmentAmount'].iloc[i] > 0:
                    buy_points.append({'date': current_date_str, 'portfolio_value': current_portfolio_value,
                                       'asset_price': current_asset_price})
            else:
                if current_signal == 1 and prev_data_signal <= 0:
                    buy_points.append({'date': current_date_str, 'portfolio_value': current_portfolio_value,
                                       'asset_price': current_asset_price})
                elif current_signal == -1 and prev_data_signal >= 0:
                    sell_points.append({'date': current_date_str, 'portfolio_value': current_portfolio_value,
                                        'asset_price': current_asset_price})

        buy_points = [dict(t) for t in {tuple(sorted(d.items())) for d in buy_points}]
        sell_points = [dict(t) for t in {tuple(sorted(d.items())) for d in sell_points}]
        buy_points.sort(key=lambda x: x['date'])
        sell_points.sort(key=lambda x: x['date'])

    chart_data['trade_markers'] = {'buy_points': buy_points, 'sell_points': sell_points}
    return {'metrics': metrics, 'chart_data': chart_data}