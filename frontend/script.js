document.addEventListener('DOMContentLoaded', () => {
    // --- DOM元素获取 ---
    const tickerInput = document.getElementById('tickerInput');
    const periodSelect = document.getElementById('periodSelect');
    const benchmarkSelect = document.getElementById('benchmarkSelect');
    const strategySelect = document.getElementById('strategySelect');
    const strategyParamsContainer = document.getElementById('strategyParams');
    const presetSelect = document.getElementById('presetSelect');
    const commissionTypeSelect = document.getElementById('commissionType');
    const commissionParamsContainer = document.getElementById('commissionParams');
    const runButton = document.getElementById('runButton');
    const loadingDiv = document.getElementById('loading');
    const errorDiv = document.getElementById('error-alert');
    const errorMessageSpan = document.getElementById('error-message');
    const resultsDiv = document.getElementById('results');
    const kpiContainer = document.getElementById('kpi-cards');
    const portfolioChartDiv = document.getElementById('portfolio-chart');
    const periodicReturnsChartDiv = document.getElementById('periodic-returns-chart');

    // --- 初始化ECharts实例 ---
    const portfolioChart = echarts.init(portfolioChartDiv);
    const periodicReturnsChart = echarts.init(periodicReturnsChartDiv);

    // --- ECharts 响应式处理 ---
    window.addEventListener('resize', () => {
        portfolioChart.resize();
        periodicReturnsChart.resize();
    });

    // --- 数据与配置 ---
    const presets = {
        'a-share-core': {
            name: 'A股核心资产定投 (沪深300)',
            config: {
                ticker: '510300',
                benchmark: '000300',
                strategy: { name: 'fixed_frequency', params: { frequency: 'M', amount: 1000 } },
                commission: { type: 'percentage', rate: 3, min_fee: 5 } // rate是万分之几
            }
        },
        'tech-power': {
            name: '科技巨头动力组合 (QQQ)',
            config: {
                ticker: 'QQQ',
                benchmark: '^NDX',
                strategy: { name: 'dma_cross', params: { fast: 20, slow: 50 } },
                commission: { type: 'percentage', rate: 3, min_fee: 1 }
            }
        },
        'sp500-buy-hold': {
            name: '标普500指数投资 (SPY)',
            config: {
                ticker: 'SPY',
                benchmark: '^GSPC',
                strategy: { name: 'buy_and_hold', params: {} },
                commission: { type: 'none' }
            }
        }
    };

    // --- 事件监听 ---
    strategySelect.addEventListener('change', renderStrategyParams);
    commissionTypeSelect.addEventListener('change', renderCommissionParams);
    presetSelect.addEventListener('change', applyPreset);
    runButton.addEventListener('click', runBacktest);

    // --- 初始化 ---
    initializeUI();

    function initializeUI() {
        populatePresets();
        renderStrategyParams();
        renderCommissionParams();
    }

    function populatePresets() {
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
        benchmarkSelect.value = preset.benchmark;
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
            if (input) input.value = preset.commission[paramKey];
        }
        presetSelect.value = "";
    }

    async function runBacktest() {
        if (!tickerInput.value.trim()) {
            showError('请输入ETF或股票代码！');
            return;
        }
        setLoading(true);
        const config = buildConfigFromUI(); // 从UI获取配置

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

            // 将config传递给渲染函数，以便动态生成图例
            renderResults(results, config);

        } catch (error) {
            showError(`回测失败: ${error.message}`);
        } finally {
            setLoading(false);
        }
    }

    function buildConfigFromUI() {
        const period = periodSelect.value;
        const endDate = new Date();
        const startDate = new Date();
        const daysMap = { '3m': 90, '6m': 180, '1y': 365, '5y': 365 * 5 };
        startDate.setDate(endDate.getDate() - (daysMap[period] || 365));
        const formatDate = (date) => date.toISOString().split('T')[0];

        const strategyName = strategySelect.value;
        const strategyParams = {};
        strategyParamsContainer.querySelectorAll('input, select').forEach(input => {
            const key = input.id.replace('param-', '');
            strategyParams[key] = isNaN(input.value) || input.value === '' ? input.value : parseFloat(input.value);
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

        return {
            ticker: tickerInput.value.trim(),
            startDate: formatDate(startDate),
            endDate: formatDate(endDate),
            initialCapital: 100000,
            strategy: { name: strategyName, params: strategyParams },
            commission: commissionParams,
            benchmarkTicker: benchmarkSelect.value || null
        };
    }

    function renderResults(results, config) {
        renderKPIs(results.metrics, results.chart_data);
        renderPortfolioChart(results.chart_data, config); // 传入config
        renderPeriodicReturnsChart(results.chart_data);
        resultsDiv.style.display = 'block';
    }

    function renderKPIs(metrics, chartData) {
        let benchmarkReturn = 0.00;
        if (chartData.benchmark_curve.values.length > 0) {
            benchmarkReturn = ((chartData.benchmark_curve.values.slice(-1)[0] / 100000 - 1) * 100).toFixed(2);
        }

        kpiContainer.innerHTML = `
            <div class="col-md-3 col-6 mb-3"><div class="card p-3 text-center h-100"><div class="metric-value ${metrics.totalReturn >= 0 ? 'text-success' : 'text-danger'}">${metrics.totalReturn}%</div><div class="metric-label">策略总回报</div></div></div>
            <div class="col-md-3 col-6 mb-3"><div class="card p-3 text-center h-100"><div class="metric-value ${benchmarkReturn >= 0 ? 'text-success' : 'text-danger'}">${benchmarkReturn}%</div><div class="metric-label">基准总回报</div></div></div>
            <div class="col-md-3 col-6 mb-3"><div class="card p-3 text-center h-100"><div class="metric-value ${metrics.annualizedReturn >= 0 ? 'text-success' : 'text-danger'}">${metrics.annualizedReturn}%</div><div class="metric-label">年化回报</div></div></div>
            <div class="col-md-3 col-6 mb-3"><div class="card p-3 text-center h-100"><div class="metric-value text-danger">${metrics.maxDrawdown}%</div><div class="metric-label">最大回撤</div></div></div>
        `;
    }

    function renderPortfolioChart(chartData, config) {
        const strategyTicker = config.ticker.toUpperCase();
        const benchmarkTicker = config.benchmarkTicker;

        // 动态构建图例名称
        const strategyName = `策略 (${strategyTicker})`;
        const assetBenchmarkName = `标的基准 (${strategyTicker})`;

        const series = [
            { name: strategyName, type: 'line', data: chartData.portfolio_curve.values, showSymbol: false, smooth: true },
            { name: assetBenchmarkName, type: 'line', data: chartData.benchmark_curve.values, showSymbol: false, smooth: true, lineStyle: { type: 'dashed' } }
        ];

        if (chartData.extra_benchmark_curve) {
             const marketBenchmarkName = `大盘基准 (${(benchmarkTicker || 'N/A').toUpperCase()})`;
             series.push({
                 name: marketBenchmarkName,
                 type: 'line',
                 data: chartData.extra_benchmark_curve.values,
                 showSymbol: false,
                 smooth: true,
                 lineStyle: { type: 'dotted' }
             });
        }

        const option = {
            title: { text: '资金曲线', left: 'center' },
            tooltip: { trigger: 'axis', axisPointer: { type: 'line' } },
            legend: {
                data: series.map(s => s.name),
                top: 'bottom',
                type: 'scroll'
            },
            grid: { left: '10%', right: '10%', bottom: '15%', containLabel: true },
            xAxis: { type: 'category', data: chartData.portfolio_curve.dates },
            yAxis: { type: 'value', scale: true, axisLabel: { formatter: '{value}' } },
            dataZoom: [{ type: 'inside' }, { type: 'slider' }],
            series: series
        };
        portfolioChart.setOption(option, true);
    }

    function renderPeriodicReturnsChart(chartData) {
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
                <div class="col-auto"><label class="form-label">投资频率</label><select id="param-frequency" class="form-select"><option value="W">每周</option><option value="M" selected>每月</option><option value="Y">每年</option></select></div>
                <div class="col-auto"><label class="form-label">每次金额</label><input type="number" id="param-amount" class="form-control" value="1000"></div>
            `;
        } else if (strategy === 'sma_cross') {
            html = `<div class="col-auto"><label class="form-label">均线周期</label><input type="number" id="param-period" class="form-control" value="20"></div>`;
        } else if (strategy === 'dma_cross') {
            html = `
                <div class="col-auto"><label class="form-label">快线</label><input type="number" id="param-fast" class="form-control" value="10"></div>
                <div class="col-auto"><label class="form-label">慢线</label><input type="number" id="param-slow" class="form-control" value="30"></div>
            `;
        }
        strategyParamsContainer.innerHTML = html;
    }

    function renderCommissionParams() {
        const type = commissionTypeSelect.value;
        let html = '';
        if (type === 'percentage') {
            html = `
                <div class="col-auto"><label class="form-label">费率(万分之)</label><input type="number" id="param-rate" class="form-control" value="3"></div>
                <div class="col-auto"><label class="form-label">最低收费(元)</label><input type="number" id="param-min-fee" class="form-control" value="5"></div>
            `;
        } else if (type === 'fixed') {
            html = `<div class="col-auto"><label class="form-label">每笔费用(元)</label><input type="number" id="param-fee" class="form-control" value="5"></div>`;
        }
        commissionParamsContainer.innerHTML = html;
    }

    function setLoading(isLoading) {
        if (isLoading) {
            runButton.disabled = true;
            runButton.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> 回测中...`;
            loadingDiv.style.display = 'block';
            resultsDiv.style.display = 'none';
            errorDiv.style.display = 'none';
        } else {
            runButton.disabled = false;
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