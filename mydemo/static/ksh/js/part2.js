// Chart 1: Funnel Chart - 景区评论数排行
    var chartDom = document.getElementById('part2');
    var myChart = echarts.init(chartDom);
    var option;

    option = {
        backgroundColor: 'transparent',
        tooltip: {
            trigger: 'item',
            formatter: '{a} <br/>{b} : {c}%',
            backgroundColor: 'rgba(255, 255, 255, 0.85)',
            borderColor: 'rgba(255, 255, 255, 0.5)',
            borderWidth: 1,
            textStyle: { color: '#4a4a6a' },
            extraCssText: 'backdrop-filter: blur(10px); box-shadow: 0 8px 32px rgba(31, 38, 135, 0.15); border-radius: 12px;'
        },
        toolbox: {
            feature: {
                dataView: { readOnly: false, title: '数据视图', lang: ['数据视图', '关闭', '刷新'] },
                restore: { title: '还原' },
                saveAsImage: { title: '保存为图片', pixelRatio: 2 }
            },
            iconStyle: { borderColor: '#8a8aae' },
            right: 20,
            top: 20
        },
        legend: {
            data: window.part2Config.nameList,
            bottom: 20,
            textStyle: { fontSize: 12, color: '#6b6b8a' },
            itemGap: 20
        },
        series: [
            {
                name: '评论数',
                type: 'funnel',
                left: '5%',
                top: 60,
                bottom: 60,
                width: '60%',
                min: 0,
                max: 3000000,
                minSize: '0%',
                maxSize: '100%',
                sort: 'descending',
                gap: 3,
                label: {
                    show: true,
                    position: 'right',
                    formatter: '{b}  {c}',
                    fontSize: 13,
                    fontWeight: '500',
                    color: '#4a4a6a',
                    lineHeight: 20
                },
                labelLine: {
                    show: true,
                    length: 20,
                    length2: 30,
                    lineStyle: { width: 1.5, type: 'solid', color: 'rgba(150, 150, 180, 0.4)' }
                },
                itemStyle: {
                    borderColor: 'rgba(255,255,255,0.6)',
                    borderWidth: 2,
                    shadowBlur: 20,
                    shadowOffsetX: 0,
                    shadowOffsetY: 8,
                    shadowColor: 'rgba(0, 0, 0, 0.15)'
                },
                emphasis: {
                    label: { fontSize: 14, fontWeight: '600', color: '#7B8CDE' },
                    itemStyle: { shadowBlur: 30, shadowColor: 'rgba(0, 0, 0, 0.25)' }
                },
                data: window.part2Config.dataList,
                color: ['#7B8CDE', '#A0D2DB', '#F7C5CC', '#E8A0BF', '#9FB4CC', '#7EC8B8', '#F0D78C', '#BB9AB1', '#D4A5D9']
            }
        ]
    };

    option && myChart.setOption(option);
    window.addEventListener('resize', function() { myChart.resize(); });

$(document).ready(function () {
        var chartDom = document.getElementById('part4');
        var myChart = echarts.init(chartDom);

        loadChartData();

        $('#provinceFilter').change(function () {
            loadChartData();
        });

        function loadChartData() {
            var selectedCity = $('#provinceFilter').val();

            myChart.showLoading({
                text: '数据加载中...',
                color: '#7EC8B8',
                textColor: '#6b6b8a',
                maskColor: 'rgba(255, 255, 255, 0.6)',
                zlevel: 0
            });

            $.ajax({
                url: window.part2Config.urls.cityData,
                type: 'GET',
                data: {"city": selectedCity},
                dataType: 'json',
                success: function (response) {
                    myChart.hideLoading();
                    updateChart(response.data);
                },
                error: function (xhr, status, error) {
                    myChart.hideLoading();
                    alert("Error: " + error);
                }
            });
        }

        function updateChart(data) {
            option = {
                backgroundColor: 'transparent',
                tooltip: {
                    trigger: 'axis',
                    axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(0,0,0,0.03)' } },
                    backgroundColor: 'rgba(255, 255, 255, 0.85)',
                    borderColor: 'rgba(255, 255, 255, 0.5)',
                    borderWidth: 1,
                    textStyle: { color: '#4a4a6a' },
                    extraCssText: 'backdrop-filter: blur(10px); box-shadow: 0 8px 32px rgba(31, 38, 135, 0.15); border-radius: 12px;'
                },
                grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
                legend: {
                    data: ['热度评分'],
                    top: 20,
                    textStyle: { fontSize: 14, color: '#6b6b8a' }
                },
                xAxis: {
                    type: 'value',
                    boundaryGap: [0, 0.01],
                    axisLine: { lineStyle: { color: 'rgba(150, 150, 180, 0.3)' } },
                    axisLabel: { color: '#8a8aae' },
                    splitLine: { lineStyle: { color: 'rgba(150, 150, 180, 0.15)', type: 'dashed' } }
                },
                yAxis: {
                    type: 'category',
                    data: data.names,
                    axisLine: { lineStyle: { color: 'rgba(150, 150, 180, 0.3)' } },
                    axisLabel: { color: '#6b6b8a', fontSize: 12 },
                    axisTick: { alignWithLabel: true }
                },
                series: [
                    {
                        name: '热度评分',
                        type: 'bar',
                        data: data.values,
                        barWidth: '60%',
                        itemStyle: {
                            color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                                { offset: 0, color: '#A0D2DB' },
                                { offset: 0.5, color: '#7EC8B8' },
                                { offset: 1, color: '#7B8CDE' }
                            ]),
                            borderRadius: [0, 8, 8, 0],
                            shadowColor: 'rgba(123, 140, 222, 0.25)',
                            shadowBlur: 12,
                            shadowOffsetY: 4
                        },
                        emphasis: {
                            itemStyle: {
                                color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                                    { offset: 0, color: '#7EC8B8' },
                                    { offset: 0.7, color: '#7B8CDE' },
                                    { offset: 1, color: '#BB9AB1' }
                                ]),
                                shadowColor: 'rgba(123, 140, 222, 0.4)',
                                shadowBlur: 16
                            }
                        },
                        animationDuration: 1000,
                        animationEasing: 'elasticOut'
                    }
                ]
            };
            option && myChart.setOption(option, true);
        }

        window.addEventListener('resize', function() { myChart.resize(); });
    });
