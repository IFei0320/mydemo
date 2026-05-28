var chartDom = document.getElementById('part4');
var myChart = echarts.init(chartDom);

var rawData = window.part4Config.dataList;
var data = rawData.map(function (item) {
    return { name: String(item.name || '未知区域'), value: parseFloat(item.value) || 0 };
});
data.sort(function (a, b) { return b.value - a.value; });

var categories = data.map(function (d) { return d.name; });
var values = data.map(function (d) { return d.value; });
var total = values.reduce(function (a, b) { return a + b; }, 0) || 1;

var vmin = values.length ? Math.min.apply(null, values) : 0;
var vmax = values.length ? Math.max.apply(null, values) : 1;

function barColor(index, value) {
    var n = Math.max(categories.length, 1);
    var hue = Math.round((index / n) * 280 + 180);
    var t = vmax > vmin ? (value - vmin) / (vmax - vmin) : 0.5;
    var sat = Math.round(45 + t * 20);
    var light = Math.round(65 + t * 15);
    return 'hsl(' + hue + ',' + sat + '%,' + light + '%)';
}

function calculateStats(dataArr) {
    if (!dataArr.length) return;
    var totalAreas = dataArr.length;
    var totalSpots = dataArr.reduce(function (sum, item) { return sum + item.value; }, 0);
    var maxItem = dataArr.reduce(function (max, item) { return item.value > max.value ? item : max; }, dataArr[0]);
    $('#totalAreas').text(totalAreas + ' 个');
    $('#totalSpots').text(totalSpots.toLocaleString() + ' 个');
    $('#maxArea').text(maxItem ? maxItem.name : '-');
}

calculateStats(data);

var rowPx = 40;
var chartH = Math.min(1400, Math.max(480, 140 + categories.length * rowPx));
chartDom.style.height = chartH + 'px';

var option = {
    backgroundColor: 'transparent',
    title: {
        text: '各区域景点数量对比',
        subtext: '更新：' + new Date().toLocaleString(),
        left: 'center',
        top: 8,
        textStyle: { fontSize: 18, fontWeight: '600', color: '#4a4a6a' },
        subtextStyle: { fontSize: 12, color: '#8a8aae' }
    },
    tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        backgroundColor: 'rgba(255, 255, 255, 0.85)',
        borderColor: 'rgba(255, 255, 255, 0.5)',
        borderWidth: 1,
        textStyle: { color: '#4a4a6a' },
        extraCssText: 'backdrop-filter: blur(10px); box-shadow: 0 8px 32px rgba(31, 38, 135, 0.15); border-radius: 12px;',
        formatter: function (params) {
            var p = params[0];
            var pct = ((p.value / total) * 100).toFixed(1);
            return (
                '<div style="padding:10px 14px;min-width:180px;">' +
                '<div style="font-weight:600;color:#4a4a6a;margin-bottom:6px;font-size:15px;">' + p.name + '</div>' +
                '<div style="color:#6b6b8a;">景点数：<b style="color:#7B8CDE;">' + p.value + '</b> 条</div>' +
                '<div style="color:#6b6b8a;">占全部景点：<b style="color:#BB9AB1;">' + pct + '%</b></div>' +
                '</div>'
            );
        }
    },
    toolbox: {
        feature: {
            dataView: { show: true, readOnly: false, title: '数据视图', lang: ['数据视图', '关闭', '刷新'] },
            restore: { show: true, title: '还原' },
            saveAsImage: { show: true, title: '保存为图片' }
        },
        iconStyle: { borderColor: '#a0a0c0' },
        right: 16,
        top: 8
    },
    grid: { left: '3%', right: '5%', top: 72, bottom: 28, containLabel: true },
    xAxis: {
        type: 'value',
        name: '景点条数',
        nameTextStyle: { color: '#8a8aae', fontSize: 12 },
        splitLine: { lineStyle: { type: 'dashed', color: 'rgba(150,150,180,0.15)' } },
        axisLabel: { color: '#8a8aae' },
        axisLine: { lineStyle: { color: 'rgba(150,150,180,0.3)' } }
    },
    yAxis: {
        type: 'category',
        data: categories,
        inverse: true,
        axisLabel: { color: '#4a4a6a', fontSize: 12, width: 140, overflow: 'truncate', ellipsis: '…' },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: 'rgba(150,150,180,0.3)' } }
    },
    dataZoom: [
        { type: 'inside', yAxisIndex: 0, filterMode: 'none' }
    ],
    series: [
        {
            name: '景点数',
            type: 'bar',
            data: values.map(function (v, i) {
                return {
                    value: v,
                    itemStyle: {
                        color: barColor(i, v),
                        borderRadius: [0, 8, 8, 0],
                        shadowColor: 'rgba(0,0,0,0.06)',
                        shadowBlur: 6,
                        shadowOffsetY: 2
                    }
                };
            }),
            barMaxWidth: 26,
            label: {
                show: true,
                position: 'right',
                formatter: '{c}',
                color: '#6b6b8a',
                fontWeight: '500',
                fontSize: 12
            },
            emphasis: {
                itemStyle: {
                    shadowBlur: 14,
                    shadowColor: 'rgba(123,140,222,0.2)'
                }
            }
        }
    ]
};

if (data.length > 0) {
    myChart.setOption(option);
} else {
    $('#noDataAlert').removeClass('d-none');
    myChart.setOption({
        title: { text: '暂无数据', left: 'center', top: 'center', textStyle: { fontSize: 22, color: '#a0aec0', fontWeight: '500' } }
    });
}

function refreshChart() {
    $('#chartLoading').removeClass('d-none');
    myChart.showLoading({ text: '…', color: '#7B8CDE', maskColor: 'rgba(255,255,255,0.7)' });
    setTimeout(function () {
        myChart.hideLoading();
        $('#chartLoading').addClass('d-none');
        chartDom.style.height = chartH + 'px';
        myChart.resize();
    }, 400);
}

function downloadChart() {
    var url = myChart.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#ffffff' });
    var link = document.createElement('a');
    link.download = '各区域景点数量_' + new Date().toLocaleDateString() + '.png';
    link.href = url;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

window.addEventListener('resize', function () {
    myChart.resize();
});
