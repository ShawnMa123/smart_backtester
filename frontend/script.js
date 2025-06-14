// frontend/script.js
document.addEventListener('DOMContentLoaded', () => {
    // --- DOM元素获取 (initialCapitalInput label changed in HTML) ---
    const tickerInput = document.getElementById('tickerInput');
    const initialCapitalInput = document.getElementById('initialCapitalInput');
    const periodSelect = document.getElementById('periodSelect');
    const benchmarkSelect = document.getElementById('benchmarkSelect');
    const strategySelect = document.getElementById('strategySelect');
    const strategyParamsContainer = document.getElementById('strategyParams');
    const presetSelect = document.getElementById('presetSelect');
    const commissionTypeSelect = document.getElementById('commissionType');
    const commissionParamsContainer = document.getElementById('commissionParams');
    const takeProfitInput = document.getElementById('takeProfitInput');
    const stopLossInput = document.getElementById('stopLossInput');
    const runButton = document.getElementById('runButton');
    const loadingDiv = document.getElementById('loading');
    const errorDiv = document.getElementById('error-alert');
    const errorMessageSpan = document.getElementById('error-message');
    const resultsDiv = document.getElementById('results');
    const kpiContainer = document.getElementById('kpi-cards');
    const portfolioChartDiv = document.getElementById('portfolio-chart');
    const periodicReturnsChartDiv = document.getElementById('periodic-returns-chart');
    const chartTitleElement = document.getElementById('chartTitle');

    const portfolioChart = echarts.init(portfolioChartDiv);
    const periodicReturnsChart = echarts.init(periodicReturnsChartDiv);

    window.addEventListener('resize', () => {
        portfolioChart.resize();
        periodicReturnsChart.resize();
    });

    // Presets might need initialCapital adjusted if they used non-zero before
    const presets = {
        'a-share-core': {
            name: 'A股核心资产定投 (沪深300)',
            config: {
                ticker: '510300', initialCapital: 100000, period: '3y', benchmark: '000300', // initialCapital is ref
                strategy: { name: 'fixed_frequency', params: { frequency: 'M', amount: 1000, day_of_month: 5 } },
                commission: { type: 'percentage', rate: 3, min_fee: 5 },
                takeProfit: null, stopLoss: 10
            }
        },
         'tech-trend': {
            name: '科技股趋势跟踪 (QQQ)',
            config: {
                ticker: 'QQQ', initialCapital: 10000, period: '5y', benchmark: '^NDX', // initialCapital is ref
                strategy: { name: 'dma_cross', params: { fast: 20, slow: 50 } },
                commission: { type: 'percentage', rate: 1, min_fee: 1 },
                takeProfit: 30, stopLoss: 15
            }
        }
    };

    strategySelect.addEventListener('change', renderStrategyParams);
    commissionTypeSelect.addEventListener('change', renderCommissionParams);
    presetSelect.addEventListener('change', applyPreset);
    runButton.addEventListener('click', runBacktest);
    initializeUI();

    function initializeUI() { /* ... same ... */
        populatePresets();
        renderStrategyParams();
        renderCommissionParams();
    }
    function populatePresets() { /* ... same ... */
        presetSelect.innerHTML = '<option value="" selected>-- 选择一个预设 --</option>';
        for (const key in presets) {
            const option = document.createElement('option');
            option.value = key;
            option.textContent = presets[key].name;
            presetSelect.appendChild(option);
        }
    }
    function applyPreset() { /* ... same, ensure initialCapitalInput is correctly populated ... */
        const selectedPresetKey = presetSelect.value;
        if (!selectedPresetKey) return;
        const preset = presets[selectedPresetKey].config;
        tickerInput.value = preset.ticker;
        initialCapitalInput.value = preset.initialCapital; // This is now reference capital
        periodSelect.value = preset.period;
        benchmarkSelect.value = preset.benchmark || "";
        strategySelect.value = preset.strategy.name;
        renderStrategyParams();
        for (const paramKey in preset.strategy.params) {
            const input = document.getElementById(`param-${paramKey}`);
            if (input) input.value = preset.strategy.params[paramKey];
        }
        commissionTypeSelect.value = preset.commission.type;
        renderCommissionParams();
        for (const paramKey in preset.commission) {
            if (paramKey === 'type') continue;
            const input = document.getElementById(`param-${paramKey}`);
            if (input) {
                 if (paramKey === 'rate' && preset.commission.type === 'percentage') {
                    input.value = preset.commission[paramKey];
                 } else {
                    input.value = preset.commission[paramKey];
                 }
            }
        }
        takeProfitInput.value = preset.takeProfit || "";
        stopLossInput.value = preset.stopLoss || "";
        presetSelect.value = "";
    }

    async function runBacktest() { /* ... same basic structure ... */
        if (!tickerInput.value.trim()) {
            showError('请输入ETF或股票代码！');
            return;
        }
        // initialCapitalInput can be 0 or positive, used for reference in backend
        if (parseFloat(initialCapitalInput.value) < 0) {
            showError('回报计算基准资金不能为负！');
            return;
        }
        setLoading(true);
        const config = buildConfigFromUI();
        try {
            const response = await fetch('http://127.0.0.1:5001/api/backtest', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `服务器错误: ${response.status}`);
            }
            const results = await response.json();
            renderResults(results, config);
        } catch (error) {
            console.error("回测完整错误:", error);
            showError(`回测失败: ${error.message}`);
        } finally {
            setLoading(false);
        }
     }

    function buildConfigFromUI() { /* ... same, initialCapitalInput value is passed as is ... */
        const period = periodSelect.value;
        const endDate = new Date();
        const startDate = new Date();
        const daysMap = { '3m': 90, '6m': 180, '1y': 365, '3y': 365 * 3, '5y': 365 * 5, '10y': 365 * 10 };
        startDate.setDate(endDate.getDate() - (daysMap[period] || 365));
        const formatDate = (date) => date.toISOString().split('T')[0];

        const strategyName = strategySelect.value;
        const strategyParams = {};
        strategyParamsContainer.querySelectorAll('input, select').forEach(input => {
            const key = input.id.replace('param-', '');
            if (input.value === "" && (key === 'day_of_week' || key === 'day_of_month')) {
                strategyParams[key] = null;
            } else {
                strategyParams[key] = isNaN(parseFloat(input.value)) || input.value === '' ? input.value : parseFloat(input.value);
            }
        });

        const commissionType = commissionTypeSelect.value;
        const commissionParams = { type: commissionType };
        commissionParamsContainer.querySelectorAll('input').forEach(input => {
            const key = input.id.replace('param-', '');
            if (key === 'rate') {
                commissionParams[key] = parseFloat(input.value) / 10000;
            } else {
                commissionParams[key] = parseFloat(input.value);
            }
        });

        const takeProfit = takeProfitInput.value ? parseFloat(takeProfitInput.value) / 100 : null;
        const stopLoss = stopLossInput.value ? parseFloat(stopLossInput.value) / 100 : null;

        return {
            ticker: tickerInput.value.trim().toUpperCase(),
            initialCapital: parseFloat(initialCapitalInput.value) || 0, // Pass as is
            startDate: formatDate(startDate),
            endDate: formatDate(endDate),
            strategy: { name: strategyName, params: strategyParams },
            commission: commissionParams,
            benchmarkTicker: benchmarkSelect.value || null,
            takeProfit: takeProfit,
            stopLoss: stopLoss
        };
     }

    function renderResults(results, config) { /* ... same ... */
        const assetDisplayName = results.chart_data.assetName || config.ticker;
        chartTitleElement.textContent = `资金曲线: ${assetDisplayName} (${config.ticker})`;
        renderKPIs(results.metrics, results.chart_data, parseFloat(config.initialCapital)); // Pass ref capital
        renderPortfolioChart(results.chart_data, config);
        renderPeriodicReturnsChart(results.chart_data);
        resultsDiv.style.display = 'block';
    }

    function renderKPIs(metrics, chartData, initialCapitalRef) { // Added initialCapitalRef
        let benchmarkReturnDisplay = "N/A";
        // Use market_benchmark_curve if available, else asset_benchmark_curve
        const benchmarkDataSource = chartData.market_benchmark_curve && chartData.market_benchmark_curve.values.length > 0 ?
                                 chartData.market_benchmark_curve :
                                 (chartData.asset_benchmark_curve && chartData.asset_benchmark_curve.values.length > 0 ?
                                  chartData.asset_benchmark_curve : null);

        if (benchmarkDataSource) {
            if (initialCapitalRef > 0) { // If ref capital, benchmark is scaled to it
                const benchmarkFinalVal = benchmarkDataSource.values.slice(-1)[0];
                const benchmarkReturnPct = ((benchmarkFinalVal / initialCapitalRef - 1) * 100).toFixed(2);
                benchmarkReturnDisplay = `${benchmarkReturnPct}%`;
            } else { // If ref capital is 0, benchmark value itself might be 0 or not directly comparable as %
                 // Backend's benchmark calculation when ref_cap=0 needs to be consistent.
                 // For now, if the benchmark value itself is available and not just 0.
                 const benchmarkFinalVal = benchmarkDataSource.values.slice(-1)[0];
                 // If backend calculates benchmark as growth from 0, its final value is its PnL
                 // This display might need adjustment based on how backend sends benchmark for ref_cap=0
                 benchmarkReturnDisplay = benchmarkFinalVal !== 0 ? `${benchmarkFinalVal.toFixed(0)} (绝对值)` : "0";

            }
        }

        let totalReturnDisplay = `${metrics.totalReturn}%`;
        if (initialCapitalRef === 0) {
            // Backend now calculates PnL % based on total invested if ref_cap=0
            // Or it could be absolute PnL. Label should reflect this.
            // totalReturnDisplay = `${metrics.totalReturn.toFixed(0)} (绝对收益)`; // Example if backend sent absolute
        }


        kpiContainer.innerHTML = `
            <div class="col-md-3 col-6 mb-3"><div class="card p-3 text-center h-100"><div class="metric-value ${metrics.totalReturn >= 0 ? 'text-success' : 'text-danger'}">${totalReturnDisplay}</div><div class="metric-label">策略回报</div></div></div>
            <div class="col-md-3 col-6 mb-3"><div class="card p-3 text-center h-100"><div class="metric-value ${parseFloat(benchmarkReturnDisplay) >= 0 || benchmarkReturnDisplay === "N/A" || benchmarkReturnDisplay === "0" ? 'text-success' : 'text-danger'}">${benchmarkReturnDisplay}</div><div class="metric-label">基准回报</div></div></div>
            <div class="col-md-3 col-6 mb-3"><div class="card p-3 text-center h-100"><div class="metric-value ${metrics.annualizedReturn >= 0 ? 'text-success' : 'text-danger'}">${metrics.annualizedReturn}%</div><div class="metric-label">年化回报</div></div></div>
            <div class="col-md-3 col-6 mb-3"><div class="card p-3 text-center h-100"><div class="metric-value text-danger">${metrics.maxDrawdown}%</div><div class="metric-label">最大回撤</div></div></div>
        `;
    }

    // ---- MODIFIED: renderPortfolioChart for Dual Y-Axis ----
    function renderPortfolioChart(chartData, config) {
        console.log("Dual Y-Axis Chart Data:", JSON.parse(JSON.stringify(chartData)));
        const assetTicker = config.ticker.toUpperCase();
        const assetDisplayName = chartData.assetName || assetTicker;

        let tradeMarkersForAssetPrice = [];
        if (chartData.trade_markers) {
            chartData.trade_markers.buy_points.forEach(point => {
                tradeMarkersForAssetPrice.push({
                    name: '买入', value: 'B', xAxis: point.date, yAxis: point.asset_price,
                    symbol: 'triangle', symbolRotate: 0, itemStyle: { color: '#07c793' } // Brighter Green
                });
            });
            chartData.trade_markers.sell_points.forEach(point => {
                tradeMarkersForAssetPrice.push({
                    name: '卖出', value: 'S', xAxis: point.date, yAxis: point.asset_price,
                    symbol: 'triangle', symbolRotate: 180, itemStyle: { color: '#fb1031' } // Brighter Red
                });
            });
        }

        const series = [];
        const yAxisConfigs = [];
        const legendData = [];

        // Y-Axis 0: Asset Price (Left)
        if (chartData.asset_price_curve && chartData.asset_price_curve.values.length > 0) {
            const seriesName = `股价 (${assetDisplayName})`;
            legendData.push(seriesName);
            series.push({
                name: seriesName,
                type: 'line',
                yAxisIndex: 0, // Assign to left Y-axis
                data: chartData.asset_price_curve.values,
                showSymbol: false, smooth: true,
                lineStyle: { color: '#5470C6', width: 2 },
                markPoint: {
                    data: tradeMarkersForAssetPrice, symbolSize: 12,
                    label: { show: true, formatter: '{b}', fontSize: 9, offset: [0, -12], color: '#fff',
                             backgroundColor: 'rgba(0,0,0,0.5)', padding: [2,4], borderRadius: 3 },
                    tooltip: { formatter: p => `${p.name}<br/>日期: ${p.data.xAxis}<br/>价格: ${p.data.yAxis.toFixed(2)}` }
                }
            });
            yAxisConfigs.push({
                type: 'value', name: '价格', position: 'left', scale: true,
                axisLine: { show: true, lineStyle: { color: '#5470C6' } },
                axisLabel: { formatter: '{value}' }
            });
        } else { // Placeholder for left Y-axis if no asset price
            yAxisConfigs.push({ type: 'value', name: '价格', position: 'left' });
        }

        // Y-Axis 1: Portfolio Value & Market Benchmark (Right)
        let portfolioSeriesName = `策略市值 (${assetDisplayName})`; // NAV
        let marketBenchmarkSeriesName = `大盘基准 (${chartData.benchmarkAssetName || config.benchmarkTicker || 'N/A'})`;

        if (chartData.portfolio_curve && chartData.portfolio_curve.values.length > 0) {
            legendData.push(portfolioSeriesName);
            series.push({
                name: portfolioSeriesName,
                type: 'line',
                yAxisIndex: 1, // Assign to right Y-axis
                data: chartData.portfolio_curve.values,
                showSymbol: false, smooth: true,
                lineStyle: { color: '#91CC75', width: 2, type: 'line' }
            });
        }

        if (chartData.market_benchmark_curve && chartData.market_benchmark_curve.values.length > 0) {
            legendData.push(marketBenchmarkSeriesName);
            series.push({
                name: marketBenchmarkSeriesName,
                type: 'line',
                yAxisIndex: 1, // Assign to right Y-axis
                data: chartData.market_benchmark_curve.values,
                showSymbol: false, smooth: true,
                lineStyle: { color: '#FAC858', width: 2, type: 'dashed' }
            });
        }

        // Ensure there's a right Y-axis configuration if any series use yAxisIndex: 1
        if (series.some(s => s.yAxisIndex === 1)) {
            yAxisConfigs.push({
                type: 'value', name: '市值', position: 'right', scale: true,
                axisLine: { show: true, lineStyle: { color: '#91CC75' } }, // Use a color from one of the series on this axis
                axisLabel: { formatter: '{value}' },
                splitLine: { show: false } // Avoid clutter from right axis split lines
            });
        } else { // Placeholder for right Y-axis
             yAxisConfigs.push({ type: 'value', name: '市值', position: 'right' });
        }


        const option = {
            title: { text: chartTitleElement.textContent, left: 'center', top: 5 },
            tooltip: { trigger: 'axis', axisPointer: { type: 'cross', crossStyle: { color: '#999' } } },
            legend: { data: legendData, top: 'bottom', type: 'scroll' },
            grid: { left: '8%', right: '10%', bottom: '15%', containLabel: true }, // Adjust right for Y-axis name
            xAxis: {
                type: 'category',
                data: chartData.asset_price_curve ? chartData.asset_price_curve.dates : (chartData.portfolio_curve ? chartData.portfolio_curve.dates : []),
                axisPointer: {snap: true}
            },
            yAxis: yAxisConfigs, // Use the array of Y-axis configurations
            dataZoom: [{ type: 'inside' }, { type: 'slider', bottom: '6%' }],
            series: series
        };
        portfolioChart.setOption(option, true);
    }
    // ---- END MODIFIED ----

    function renderPeriodicReturnsChart(chartData) { /* ... same as before ... */
        if (!chartData.monthly_returns || chartData.monthly_returns.values.length === 0) {
            periodicReturnsChart.clear();
            return;
        }
        const returnsData = chartData.monthly_returns;
        const titleText = '月度收益率分布';
        const option = {
            title: { text: titleText, left: 'center' },
            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
            grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
            xAxis: { type: 'category', data: returnsData.dates },
            yAxis: { type: 'value', axisLabel: { formatter: '{value} %' } },
            series: [{
                name: '收益率', type: 'bar', data: returnsData.values,
                itemStyle: { color: (params) => params.value >= 0 ? '#5470c6' : '#ee6666' }
            }]
        };
        periodicReturnsChart.setOption(option, true);
    }
    function renderStrategyParams() { /* ... same ... */
        const strategy = strategySelect.value;
        let html = '';
        if (strategy === 'fixed_frequency') {
            html = `
                <div class="col-md-3"><label class="form-label">投资频率</label>
                    <select id="param-frequency" class="form-select">
                        <option value="W">每周</option>
                        <option value="M" selected>每月</option>
                    </select>
                </div>
                <div class="col-md-3"><label class="form-label">每次金额</label><input type="number" id="param-amount" class="form-control" value="1000"></div>
                <div class="col-md-3"><label class="form-label">周几买入 (0-6)</label><input type="number" id="param-day_of_week" class="form-control" placeholder="留空则周一"></div>
                <div class="col-md-3"><label class="form-label">几号买入 (1-31)</label><input type="number" id="param-day_of_month" class="form-control" placeholder="留空则1号"></div>
                <div class="col-12"><small class="form-text text-muted">选择频率后，填写对应的“周几”或“几号”。如不填，则默认为每周一或每月1号附近的交易日。</small></div>
            `;
        } else if (strategy === 'sma_cross') {
            html = `<div class="col-md-3"><label class="form-label">均线周期</label><input type="number" id="param-period" class="form-control" value="20"></div>`;
        } else if (strategy === 'dma_cross') {
            html = `
                <div class="col-md-3"><label class="form-label">快线</label><input type="number" id="param-fast" class="form-control" value="10"></div>
                <div class="col-md-3"><label class="form-label">慢线</label><input type="number" id="param-slow" class="form-control" value="30"></div>
            `;
        } else if (strategy === 'buy_and_hold') {
             html = `<div class="col-md-6"><small class="form-text text-muted">买入并持有策略将在回测期初投入“回报计算基准资金”全额（如果大于0），或首次定投金额（如果基准资金为0）。</small></div>`
        }
        strategyParamsContainer.innerHTML = html;
    }
    function renderCommissionParams() { /* ... same ... */
        const type = commissionTypeSelect.value;
        let html = '';
        if (type === 'percentage') {
            html = `
                <div class="col-md-4"><label class="form-label">费率(万分之)</label><input type="number" id="param-rate" class="form-control" value="3"></div>
                <div class="col-md-4"><label class="form-label">最低收费(元)</label><input type="number" id="param-min-fee" class="form-control" value="5"></div>
            `;
        } else if (type === 'fixed') {
            html = `<div class="col-md-4"><label class="form-label">每笔费用(元)</label><input type="number" id="param-fee" class="form-control" value="5"></div>`;
        }
        commissionParamsContainer.innerHTML = html;
    }
    function setLoading(isLoading) { /* ... same ... */
        runButton.disabled = isLoading;
        if (isLoading) {
            runButton.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> 回测中...`;
            loadingDiv.style.display = 'block';
            resultsDiv.style.display = 'none';
            errorDiv.style.display = 'none';
        } else {
            runButton.textContent = '开始回测';
            loadingDiv.style.display = 'none';
        }
    }
    function showError(message) { /* ... same ... */
        errorMessageSpan.textContent = message;
        errorDiv.style.display = 'block';
        resultsDiv.style.display = 'none';
    }
});