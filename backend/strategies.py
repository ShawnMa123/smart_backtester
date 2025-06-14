# backend/strategies.py
import pandas as pd
import numpy as np
from pandas.tseries.offsets import Day, BusinessDay, WeekOfMonth


def generate_signals(data, strategy_name, params):
    strategy_function = globals().get(f"strategy_{strategy_name}")
    if not strategy_function:
        raise ValueError(f"未知的策略名称: '{strategy_name}'")
    return strategy_function(data.copy(), **params)


def strategy_buy_and_hold(data):
    data['Signal'] = 0
    if not data.empty:
        data['Signal'].iloc[0] = 1  # Buy on the first available day
    return data


def strategy_fixed_frequency(data, frequency='M', amount=1000, day_of_week=None, day_of_month=None):
    """
    定投策略.
    frequency: 'W' (每周), 'M' (每月)
    day_of_week: 0-6 (周一至周日), for 'W' frequency. If None, uses first trading day of week.
    day_of_month: 1-31, for 'M' frequency. If None, uses first trading day of month.
                  If day_of_month > days in month, uses last trading day of month.
    """
    data['Signal'] = 0
    data['InvestmentAmount'] = 0  # Initialize investment amount column

    if data.empty:
        return data

    # Ensure day_of_week and day_of_month are integers if provided
    if day_of_week is not None: day_of_week = int(day_of_week)
    if day_of_month is not None: day_of_month = int(day_of_month)

    buy_dates = []

    # Generate potential investment dates based on frequency
    if frequency == 'W':
        # Get all unique weeks in the data's index
        potential_weeks = data.index.to_period('W').unique()
        for week_start_period in potential_weeks:
            week_start_date = week_start_period.start_time  # Monday of that week
            if day_of_week is not None:
                # Target specific day of the week
                target_date = week_start_date + pd.Timedelta(days=day_of_week)
            else:
                # Default to first day of the week (Monday)
                target_date = week_start_date

            # Find the first actual trading day on or after the target_date within that week
            # Ensure the target date is within the data's range
            if target_date < data.index.min() or target_date > data.index.max() + pd.Timedelta(
                    days=7):  # give some buffer for week end
                continue

            # Get trading days within the week of the target_date
            days_in_week_of_target = data.loc[target_date.strftime('%Y-%m-%d'): (
                        target_date + pd.Timedelta(days=6 - target_date.weekday())).strftime('%Y-%m-%d')].index

            actual_buy_date = None
            if not days_in_week_of_target.empty:
                # Find the first trading day >= target_date
                future_dates = days_in_week_of_target[days_in_week_of_target >= target_date]
                if not future_dates.empty:
                    actual_buy_date = future_dates.min()

            if actual_buy_date:
                buy_dates.append(actual_buy_date)

    elif frequency == 'M':
        potential_months = data.index.to_period('M').unique()
        for month_start_period in potential_months:
            month_start_date = month_start_period.start_time  # First day of the month

            if day_of_month is not None:
                try:
                    # Construct target date: year, month, day_of_month
                    target_date = pd.Timestamp(year=month_start_date.year, month=month_start_date.month,
                                               day=day_of_month)
                except ValueError:  # Invalid date (e.g., Feb 30th)
                    # Use last day of the month
                    target_date = month_start_date + pd.offsets.MonthEnd(0)
            else:
                # Default to first day of the month
                target_date = month_start_date

            if target_date < data.index.min() or target_date > data.index.max() + pd.Timedelta(
                    days=31):  # buffer for month end
                continue

            # Get trading days within the month of the target_date
            days_in_month_of_target = data.loc[
                                      target_date.strftime('%Y-%m-01'): (target_date + pd.offsets.MonthEnd(0)).strftime(
                                          '%Y-%m-%d')].index

            actual_buy_date = None
            if not days_in_month_of_target.empty:
                future_dates = days_in_month_of_target[days_in_month_of_target >= target_date]
                if not future_dates.empty:
                    actual_buy_date = future_dates.min()
                else:  # If target_day is past all trading days in month (e.g. 31st but last trading day is 28th)
                    # Use last trading day of this month if it's not before the original target day
                    if not days_in_month_of_target.empty:
                        last_trading_day_of_month = days_in_month_of_target.max()
                        if last_trading_day_of_month >= target_date:  # should not happen if future_dates is empty
                            actual_buy_date = last_trading_day_of_month
                        elif target_date.day > last_trading_day_of_month.day:  # e.g. target 31st, last trade day 28th
                            actual_buy_date = last_trading_day_of_month

            if actual_buy_date:
                buy_dates.append(actual_buy_date)
    else:  # Default for other frequencies (e.g., 'Y' or custom, though not fully supported with day selection here)
        freq_map = {'W': 'W-FRI', 'M': 'ME', 'Y': 'YE'}  # Simplified for original logic
        actual_frequency = freq_map.get(frequency, frequency)
        resampled_dates = data.resample(actual_frequency).first().index
        # Intersect with actual trading days in data
        buy_dates_pd = data.index.intersection(resampled_dates)
        buy_dates = buy_dates_pd.tolist()

    # Remove duplicates and sort, then filter by data range again
    # And ensure they are actual trading days present in the data.index
    valid_buy_dates = sorted(list(set(buy_dates)))
    valid_buy_dates = [d for d in valid_buy_dates if
                       d >= data.index.min() and d <= data.index.max() and d in data.index]

    if valid_buy_dates:
        data.loc[valid_buy_dates, 'Signal'] = 1
        data.loc[valid_buy_dates, 'InvestmentAmount'] = amount

    return data


def strategy_sma_cross(data, period=20):
    if period > len(data): raise ValueError("数据长度小于均线周期。")
    data['MA'] = data['Close'].rolling(window=int(period)).mean()
    data['Signal'] = 0  # Default to hold
    # Buy when Close crosses above MA, Sell when Close crosses below MA
    data.loc[data['Close'] > data['MA'], 'Signal'] = 1
    data.loc[data['Close'] < data['MA'], 'Signal'] = -1
    # Avoid trading on NaNs from rolling mean
    data.loc[data['MA'].isnull(), 'Signal'] = 0
    return data


def strategy_dma_cross(data, fast=10, slow=30):
    if slow > len(data) or fast > len(data): raise ValueError("数据长度小于均线周期。")
    data['SMA_fast'] = data['Close'].rolling(window=int(fast)).mean()
    data['SMA_slow'] = data['Close'].rolling(window=int(slow)).mean()
    data['Signal'] = 0  # Default to hold
    # Buy on golden cross, Sell on death cross
    data.loc[data['SMA_fast'] > data['SMA_slow'], 'Signal'] = 1
    data.loc[data['SMA_fast'] < data['SMA_slow'], 'Signal'] = -1
    # Avoid trading on NaNs
    data.loc[data['SMA_fast'].isnull() | data['SMA_slow'].isnull(), 'Signal'] = 0
    return data