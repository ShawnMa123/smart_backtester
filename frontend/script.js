document.addEventListener('DOMContentLoaded', () => {
    // --- DOM元素获取 ---
    const tickerInput = document.getElementById('tickerInput');
    const initialCapitalInput = document.getElementById('initialCapitalInput'); // New
    const periodSelect = document.getElementById('periodSelect');
    const benchmarkSelect = document.getElementById('benchmarkSelect');
    const strategySelect = document.getElementById('strategySelect');
    const strategyParamsContainer = document.getElementById('strategyParams');
    const presetSelect = document.getElementById('presetSelect');
    const commissionTypeSelect = document.getElementById('commissionType');
    const commissionParamsContainer = document.getElementById('commissionParams');
    const takeProfitInput = document.getElementById('takeProfitInput'); // New
    const stopLossInput = document.getElementById('stopLossInput');     // New
    const runButton = document.getElementById('runButton');
    const loadingDiv = document.getElementById('loading');
    const errorDiv = document.getElementById('error-alert');
    const errorMessageSpan = document.getElementById('error-message');
    const resultsDiv = document.getElementById('results');
    const kpiContainer = document.getElementById('kpi-cards');
    const portfolioChartDiv = document.getElementById('portfolio-chart');
    const periodicReturnsChartDiv = document.getElementById('periodic-returns-chart');
    const chartTitleElement = document.getElementById('chartTitle'); // New for dynamic title

    // --- 初始化ECharts实例 ---
    const portfolioChart = echarts.init(portfolioChartDiv);
    const periodicReturnsChart = echarts.init(periodicReturnsChartDiv);

    window.addEventListener('resize', () => {
        portfolioChart.resize();
        periodicReturnsChart.resize();
    });

    const presets = { // Update presets if needed
        'a-share-core': {
            name: 'A股核心资产定投 (沪深300)',
            config: {
                ticker: '510300', initialCapital: 100000, period: '3y', benchmark: '000300',
                strategy: { name: 'fixed_frequency', params: { frequency: 'M', amount: 1000, day_of_month: 5 } },
                commission: { type: 'percentage', rate: 3, min_fee: 5 },
                takeProfit: null, stopLoss: 10 // Example: 10% stop loss
            }
        },
         'tech-trend': {
            name: '科技股趋势跟踪 (QQQ)',
            config: {
                ticker: 'QQQ', initialCapital: 10000, period: '5y', benchmark: '^NDX',
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

    function initializeUI() {
        populatePresets();
        renderStrategyParams();
        renderCommissionParams();
    }

    function populatePresets() {
        presetSelect.innerHTML = '<option value="" selected>-- 选择一个预设 --</option>'; // Clear existing
        for (const key in presets) {
            const option = document.createElement('option');
            option.value = key;
            option.textContent = presets[key].name;
            presetSelect.appendChild(option);
        }
    }

    function applyPreset() {
        const selectedPresetKey = presetSelect.value;
        if (!selectedPresetKey) return;
        const preset = presets[selectedPresetKey].config;
        tickerInput.value = preset.ticker;
        initialCapitalInput.value = preset.initialCapital;
        periodSelect.value = preset.period;
        benchmarkSelect.value = preset.benchmark || "";
        strategySelect.value = preset.strategy.name;
        renderStrategyParams(); // Important to render before setting values
        for (const paramKey in preset.strategy.params) {
            const input = document.getElementById(`param-${paramKey}`);
            if (input) input.value = preset.strategy.params[paramKey];
        }
        commissionTypeSelect.value = preset.commission.type;
        renderCommissionParams(); // Important
        for (const paramKey in preset.commission) {
            if (paramKey === 'type') continue;
            const input = document.getElementById(`param-${paramKey}`);
            if (input) { //万分率转换
                 if (paramKey === 'rate' && preset.commission.type === 'percentage') {
                    input.value = preset.commission[paramKey]; // Presets store万分之X
                 } else {
                    input.value = preset.commission[paramKey];
                 }
            }
        }
        takeProfitInput.value = preset.takeProfit || "";
        stopLossInput.value = preset.stopLoss || "";
        presetSelect.value = ""; // Reset dropdown
    }

    async function runBacktest() {
        if (!tickerInput.value.trim()) {
            showError('请输入ETF或股票代码！');
            return;
        }
        if (parseFloat(initialCapitalInput.value) < 0) {
            showError('初始资金不能为负！');
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
            renderResults(results, config); // Pass config for names
        } catch (error) {
            console.error("回测完整错误:", error);
            showError(`回测失败: ${error.message}`);
        } finally {
            setLoading(false);
        }
    }

    function buildConfigFromUI() {
        const period = periodSelect.value;
        const endDate = new Date();
        const startDate = new Date();
        // More periods
        const daysMap = { '3m': 90, '6m': 180, '1y': 365, '3y': 365 * 3, '5y': 365 * 5, '10y': 365 * 10 };
        startDate.setDate(endDate.getDate() - (daysMap[period] || 365));
        const formatDate = (date) => date.toISOString().split('T')[0];

        const strategyName = strategySelect.value;
        const strategyParams = {};
        strategyParamsContainer.querySelectorAll('input, select').forEach(input => {
            const key = input.id.replace('param-', '');
            // Handle empty strings for optional params like day_of_week/month
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
            if (key === 'rate') { // 万分之X to decimal
                commissionParams[key] = parseFloat(input.value) / 10000;
            } else {
                commissionParams[key] = parseFloat(input.value);
            }
        });

        const takeProfit = takeProfitInput.value ? parseFloat(takeProfitInput.value) / 100 : null;
        const stopLoss = stopLossInput.value ? parseFloat(stopLossInput.value) / 100 : null;

        return {
            ticker: tickerInput.value.trim().toUpperCase(),
            initialCapital: parseFloat(initialCapitalInput.value) || 0,
            startDate: formatDate(startDate),
            endDate: formatDate(endDate),
            strategy: { name: strategyName, params: strategyParams },
            commission: commissionParams,
            benchmarkTicker: benchmarkSelect.value || null,
            takeProfit: takeProfit,
            stopLoss: stopLoss
        };
    }

    function renderResults(results, config) { // Added config
        // Dynamic Chart Title
        const assetDisplayName = results.chart_data.assetName || config.ticker;
        chartTitleElement.textContent = `资金曲线: ${assetDisplayName} (${config.ticker})`;

        renderKPIs(results.metrics, results.chart_data); // Pass chart_data for benchmark return
        renderPortfolioChart(results.chart_data, config); // Pass config and full chart_data
        renderPeriodicReturnsChart(results.chart_data);
        resultsDiv.style.display = 'block';
    }

    function renderKPIs(metrics, chartData) { // chartData for benchmark
        let benchmarkReturn = 0.00;
        // Use market_benchmark_curve if available, else asset B&H (benchmark_curve)
        const benchmarkSource = chartData.market_benchmark_curve || chartData.benchmark_curve;
        const initialCapForBenchmark = parseFloat(initialCapitalInput.value) || (benchmarkSource && benchmarkSource.values.length > 0 ? benchmarkSource.values[0] : 1);


        if (benchmarkSource && benchmarkSource.values.length > 0 && initialCapForBenchmark > 0) {
            benchmarkReturn = ((benchmarkSource.values.slice(-1)[0] / initialCapForBenchmark - 1) * 100).toFixed(2);
        } else if (initialCapForBenchmark === 0) {
            benchmarkReturn = "N/A"; // Or 0.00 if preferred
        }


        kpiContainer.innerHTML = `
            <div class="col-md-3 col-6 mb-3"><div class="card p-3 text-center h-100"><div class="metric-value ${metrics.totalReturn >= 0 ? 'text-success' : 'text-danger'}">${metrics.totalReturn}%</div><div class="metric-label">策略总回报</div></div></div>
            <div class="col-md-3 col-6 mb-3"><div class="card p-3 text-center h-100"><div class="metric-value ${parseFloat(benchmarkReturn) >= 0 || benchmarkReturn === "N/A" ? 'text-success' : 'text-danger'}">${benchmarkReturn === "N/A" ? benchmarkReturn : benchmarkReturn + '%'}</div><div class="metric-label">基准总回报</div></div></div>
            <div class="col-md-3 col-6 mb-3"><div class="card p-3 text-center h-100"><div class="metric-value ${metrics.annualizedReturn >= 0 ? 'text-success' : 'text-danger'}">${metrics.annualizedReturn}%</div><div class="metric-label">年化回报</div></div></div>
            <div class="col-md-3 col-6 mb-3"><div class="card p-3 text-center h-100"><div class="metric-value text-danger">${metrics.maxDrawdown}%</div><div class="metric-label">最大回撤</div></div></div>
        `;
    }

    function renderPortfolioChart(chartData, config) {
        const assetTicker = config.ticker.toUpperCase();
        const assetDisplayName = chartData.assetName || assetTicker;

        // --- Prepare Mark Points for Asset Price Line ---
        let tradeMarkersForAssetPrice = [];
        if (chartData.trade_markers) {
            chartData.trade_markers.buy_points.forEach(point => {
                tradeMarkersForAssetPrice.push({
                    name: '买入', value: 'B', xAxis: point.date, yAxis: point.asset_price, // Use asset_price
                    symbol: 'triangle', symbolRotate: 0, itemStyle: { color: '#07c793' }
                });
            });
            chartData.trade_markers.sell_points.forEach(point => {
                tradeMarkersForAssetPrice.push({
                    name: '卖出', value: 'S', xAxis: point.date, yAxis: point.asset_price, // Use asset_price
                    symbol: 'triangle', symbolRotate: 180, itemStyle: { color: '#fb1031' }
                });
            });
        }

        const series = [];

        // 1. 股票/ETF价格线 (with B/S markers)
        if (chartData.asset_price_curve && chartData.asset_price_curve.values.length > 0) {
            series.push({
                name: `股票价格 (${assetDisplayName})`,
                type: 'line',
                data: chartData.asset_price_curve.values,
                showSymbol: false,
                smooth: true,
                lineStyle: { color: '#5470c6', width: 2 }, // Example color
                markPoint: {
                    data: tradeMarkersForAssetPrice,
                    symbolSize: 12,
                    label: { show: true, formatter: '{b}', fontSize: 9, offset: [0, -12], color: '#fff',
                             backgroundColor: 'rgba(0,0,0,0.4)', padding: [2,4], borderRadius: 2 },
                    tooltip: { formatter: p => `${p.name}<br/>日期: ${p.data.xAxis}<br/>价格: ${p.data.yAxis.toFixed(2)}` }
                }
            });
        }

        // 2. 策略曲线 (Portfolio Value)
        if (chartData.portfolio_curve && chartData.portfolio_curve.values.length > 0) {
            series.push({
                name: `策略市值 (${assetDisplayName})`,
                type: 'line',
                data: chartData.portfolio_curve.values,
                showSymbol: false,
                smooth: true,
                lineStyle: { color: '#91cc75', width: 2, type: 'dashed' } // Example color
            });
        }

        // 3. 大盘对比线 (Market Benchmark)
        if (chartData.market_benchmark_curve && chartData.market_benchmark_curve.values.length > 0) {
            const marketBenchmarkName = chartData.market_benchmark_curve.name || `大盘基准 (${config.benchmarkTicker || 'N/A'})`;
            series.push({
                name: marketBenchmarkName,
                type: 'line',
                data: chartData.market_benchmark_curve.values,
                showSymbol: false,
                smooth: true,
                lineStyle: { color: '#fac858', width: 2, type: 'dotted' } // Example color
            });
        }


        const option = {
            title: { text: chartTitleElement.textContent, left: 'center', top: 5 }, // Use dynamic title
            tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
            legend: {
                data: series.map(s => s.name),
                top: 'bottom',
                type: 'scroll' // In case of many series or long names
            },
            grid: { left: '8%', right: '8%', bottom: '15%', containLabel: true },
            xAxis: { type: 'category', data: chartData.asset_price_curve.dates, axisPointer: {snap: true} }, // Use asset dates as primary
            yAxis: { type: 'value', scale: true, axisLabel: { formatter: '{value}' }, splitLine: { show: true } },
            dataZoom: [{ type: 'inside', start: 0, end: 100 }, { type: 'slider', start: 0, end: 100, bottom: '5%' }],
            series: series
        };
        portfolioChart.setOption(option, true);
    }

    function renderPeriodicReturnsChart(chartData) {
        if (!chartData.monthly_returns || chartData.monthly_returns.values.length === 0) {
            periodicReturnsChart.clear(); // Clear if no data
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

    function renderStrategyParams() {
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
        }
        strategyParamsContainer.innerHTML = html;
    }

    function renderCommissionParams() {
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

    function setLoading(isLoading) {
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

    function showError(message) {
        errorMessageSpan.textContent = message;
        errorDiv.style.display = 'block';
        resultsDiv.style.display = 'none';
    }
});