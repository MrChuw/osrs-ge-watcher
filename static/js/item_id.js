let myChart;
let currentMode = 'live';
let dataSell = [];
let dataBuy = [];

const getCSSVar = (varName) => getComputedStyle(document.documentElement).getPropertyValue(varName).trim();

function initChart() {
    const chartDom = document.getElementById('chart-container');
    myChart = echarts.init(chartDom, 'dark');
    const colors = {
        bgChart: getCSSVar('--bg-chart'),
        primary: getCSSVar('--primary'),
        green: getCSSVar('--green'),
        blue: getCSSVar('--blue'),
        textMuted: getCSSVar('--text-muted'),
        textMain: getCSSVar('--text-main'),
        border: getCSSVar('--border'),
        line: getCSSVar('--line'),
        white: getCSSVar('--white'),
        blackAlpha: getCSSVar('--black-alpha-09')
    };

    const option = {
        backgroundColor: colors.bgChart,
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'cross' },
            backgroundColor: colors.blackAlpha,
            borderColor: colors.border,
            textStyle: { color: colors.white }
        },
        legend: {
            data: ['Sell Price', 'Buy Price'],
            top: 10,
            textStyle: { color: colors.textMain }
        },
        grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
        xAxis: {
            type: 'time',
            boundaryGap: false,
            axisLine: { lineStyle: { color: colors.line } },
            axisLabel: { color: colors.textMuted },
            splitLine: { show: false }
        },
        yAxis: {
            type: 'value',
            scale: true,
            axisLine: { show: false },
            axisLabel: { color: colors.textMuted },
            splitLine: { lineStyle: { color: colors.line } }
        },
        dataZoom: [
            {
                type: 'slider',
                show: true,
                xAxisIndex: [0],
                start: 0,
                end: 100,
                bottom: 10,
                height: 30,
                handleStyle: { color: colors.primary },
                textStyle: { color: colors.textMuted }
            },
            { type: 'inside', xAxisIndex: [0] }
        ],
        series: [
            {
                name: 'Sell Price',
                type: 'line',
                showSymbol: false,
                data: [],
                itemStyle: { color: colors.green },
                lineStyle: { width: 2 }
            },
            {
                name: 'Buy Price',
                type: 'line',
                showSymbol: false,
                data: [],
                itemStyle: { color: colors.blue },
                lineStyle: { width: 2 }
            }
        ]
    };

    myChart.setOption(option);
    window.addEventListener('resize', myChart.resize);
}

async function changeMode(mode, btn) {
    if (currentMode === mode) return;

    currentMode = mode;
    document.querySelectorAll('.presets button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    dataSell = [];
    dataBuy = [];
    myChart.setOption({ series: [{ data: [] }, { data: [] }] });

    if(mode === 'live') {
        await loadBuffer();
    } else {
        try {
            const res = await fetch(`/api/history/${ITEM_ID}?interval=${mode}`);
            const data = await res.json();
            updateStaticData(data);
        } catch (e) {
        }
    }
}

async function fetchByDate() {
    const date = document.getElementById('dateFilter').value;
    if(!date) return;
    currentMode = 'history';
    document.querySelectorAll('.presets button').forEach(b => b.classList.remove('active'));
    try {
        const res = await fetch(`/api/history/${ITEM_ID}?date=${date}`);
        updateStaticData(await res.json());
    } catch (e) {
    }
}

function updateStaticData(data) {
    if(!data) return;

    dataSell = data
        .filter(d => d.sell > 0)
        .map(d => [d.timestamp, d.sell]);

    dataBuy = data
        .filter(d => d.buy > 0)
        .map(d => [d.timestamp, d.buy]);

    myChart.setOption({
        series: [
            { data: dataSell },
            { data: dataBuy }
        ],
        dataZoom: [{ start: 0, end: 100 }]
    });
}

async function loadBuffer() {
    try {
        const res = await fetch(`/api/history/${ITEM_ID}?interval=live_buffer`);
        updateStaticData(await res.json());
    } catch (e) {
        console.error("Erro in buffer", e);
    }
}

function connectWS() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/realtime/${ITEM_ID}`);

    const MAX_ZEROS = 5;
    let zeroTracker = { sell: 0, buy: 0 };

    ws.onmessage = (event) => {
        const res = JSON.parse(event.data);

        if (res.type === "snapshot" || res.type === "price_update") {
            const d = res.data || res;

            let rawSell = d.current_sell_price || 0;
            let rawBuy = d.current_buy_price || 0;

            if (rawSell === 0) {
                zeroTracker.sell++;
            } else {
                zeroTracker.sell = 0;
            }

            if (rawBuy === 0) {
                zeroTracker.buy++;
            } else {
                zeroTracker.buy = 0;
            }

            const currentSell = (rawSell === 0 && zeroTracker.sell < MAX_ZEROS) ? 0 : rawSell;
            const currentBuy = (rawBuy === 0 && zeroTracker.buy < MAX_ZEROS) ? 0 : rawBuy;

            const SellPriceElement = document.getElementById('currentSellPriceDisplay');
            if (SellPriceElement) {
                SellPriceElement.innerText = currentSell.toLocaleString() + " gp";
                SellPriceElement.className = 'price-card text-green';
            }

            const BuyPriceElement = document.getElementById('currentBuyPriceDisplay');
            if (BuyPriceElement) {
                BuyPriceElement.innerText = currentBuy.toLocaleString() + " gp";
                BuyPriceElement.className = 'price-card text-red';
            }

            if (d.buy_limit) document.getElementById('statLimit').innerText = d.buy_limit.toLocaleString();
            if (d.avg_sell_24h) document.getElementById('statAvg').innerText = Math.round(d.avg_sell_24h).toLocaleString() + " gp";
            if (d.value) document.getElementById('statValue').innerText = Math.max(0, d.value).toLocaleString() + " gp";

            if (d.highalch) {
                const val = Math.max(0, d.highalch).toLocaleString() + " gp";
                document.getElementById('statHighTooltip').innerText = val;
            }

            if (d.lowalch) {
                const val = Math.max(0, d.lowalch).toLocaleString() + " gp";
                document.getElementById('statLowTooltip').innerText = val;
            }

            const taxRate = 0.02;
            const maxTax = 5000000;
            let taxValue = Math.min((currentSell > 50 ? Math.floor(currentSell * taxRate) : 0), maxTax);
            const margin = currentSell - taxValue - currentBuy;

            const taxElement = document.getElementById('Tax');
            if (taxElement) {
                taxElement.innerText = taxValue.toLocaleString() + " gp" + (currentSell > 50 ? " (2%)" : " (0%)");
                taxElement.className = 'tooltip-value ' + (taxValue > margin ? 'text-red' : 'text-green');
            }

            const marginElement = document.getElementById('Margin');
            if (marginElement) {
                marginElement.innerText = (margin > 0 ? "+" : "") + margin.toLocaleString() + " gp";
                marginElement.className = margin >= 0 ? 'text-green' : 'text-red';
            }

            if (d.value && currentBuy && d.buy_limit) {
                const itemValue = Math.max(0, d.value);
                const profitPerItem = itemValue - currentBuy;
                const totalStoreFlip = profitPerItem * d.buy_limit;
                const roi = ((profitPerItem / currentBuy) * 100).toFixed(2);

                const elProfitItem = document.getElementById('tooltipProfitItem');
                const elTotalProfit = document.getElementById('tooltipTotalProfit');
                const elRoi = document.getElementById('tooltipROI');

                if (elProfitItem) {
                    elProfitItem.innerText = `${profitPerItem.toLocaleString()} gp`;
                    elProfitItem.className = profitPerItem >= 0 ? 'text-green' : 'text-red';
                }
                if (elTotalProfit) {
                    elTotalProfit.innerText = `${totalStoreFlip.toLocaleString()} gp`;
                    elTotalProfit.className = totalStoreFlip >= 0 ? 'text-green' : 'text-red';
                }
                if (elRoi) {
                    elRoi.innerText = `${roi}%`;
                    elRoi.className = profitPerItem >= 0 ? 'text-green' : 'text-red';
                }
            }

            const buyLimit = d.buy_limit || parseInt(document.getElementById('statLimit').innerText.replace(/,/g, '')) || 0;
            if (currentSell > 0 && currentBuy > 0) {
                const profit = (currentSell - taxValue - currentBuy) * buyLimit;
                const profitElement = document.getElementById('Profit');
                if (profitElement) {
                    profitElement.innerText = (profit > 0 ? "+" : "") + profit.toLocaleString() + " gp";
                    profitElement.className = profit >= 0 ? 'text-green' : 'text-red';
                }
            }

            if (currentMode === 'live') {
                const ts = d.timestamp ? new Date(d.timestamp).getTime() : new Date().getTime();

                if (rawSell > 0 || zeroTracker.sell >= MAX_ZEROS) {
                    dataSell.push([ts, rawSell]);
                }

                if (rawBuy > 0 || zeroTracker.buy >= MAX_ZEROS) {
                    dataBuy.push([ts, rawBuy]);
                }

                if (dataSell.length > 2000) dataSell.shift();
                if (dataBuy.length > 2000) dataBuy.shift();
                myChart.setOption({ series: [{ data: dataSell }, { data: dataBuy }] });
            }

            if (d.name) {
                document.title = `${d.name} | Price OSRS`;
                const wikiUrl = `https://oldschool.runescape.wiki/w/Special:Lookup?type=item&id=${ITEM_ID}`;
                const nameElement = document.getElementById('nameText');
                nameElement.innerHTML = `<a href="${wikiUrl}" target="_blank" rel="noopener noreferrer" class="item-link">${d.name}</a>`;

                const iconUrl = `https://oldschool.runescape.wiki/images/${d.name.replace(/ /g, '_')}.png`;
                const itemIcon = document.getElementById('itemIcon');
                itemIcon.src = iconUrl;
                itemIcon.style.display = 'inline-block';
                itemIcon.style.cursor = 'pointer';
                itemIcon.onclick = () => window.open(wikiUrl, '_blank');

                document.getElementById('favicon').href = iconUrl;
            }
        }
    };


    ws.onclose = () => {
        setTimeout(connectWS, 3000);
    };
}

initChart();
loadBuffer().then(() => connectWS());
