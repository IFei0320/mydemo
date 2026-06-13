    $(document).ready(function () {
        let map = null;
        let BMap = window.BMap;
        let markers = [];
        let polylines = [];

        function initMap() {
            if (!BMap) {
                console.error('百度地图API未加载');
                return false;
            }
            try {
                map = new BMap.Map('map');
                const point = new BMap.Point(116.404, 39.915);
                map.centerAndZoom(point, 11);
                map.enableScrollWheelZoom(true);
                map.addControl(new BMap.NavigationControl());
                map.addControl(new BMap.ScaleControl());
                map.addControl(new BMap.OverviewMapControl());
                map.addControl(new BMap.MapTypeControl());
                console.log('百度地图初始化成功');
                return true;
            } catch (error) {
                console.error('地图初始化失败:', error);
                showError('地图初始化失败: ' + error.message);
                return false;
            }
        }

        function showError(message) {
            $('#errorMessage').text(message);
            $('#errorContainer').show();
            $('html, body').animate({
                scrollTop: $('#errorContainer').offset().top - 100
            }, 500);
        }

        function hideError() {
            $('#errorContainer').hide();
        }

        function showLoading() {
            $('#loadingContainer').show();
            $('html, body').animate({
                scrollTop: $('#loadingContainer').offset().top - 100
            }, 500);
        }

        function hideLoading() {
            $('#loadingContainer').hide();
        }

        function showResult(done) {
            $('#resultContainer').fadeIn(500, function () {
                $('html, body').animate({
                    scrollTop: $('#resultContainer').offset().top - 50
                }, 300);
                setTimeout(function () {
                    if (typeof done === 'function') {
                        done();
                    }
                }, 80);
            });
        }

        function bindMapAfterResultVisible(mapSpots) {
            if (!BMap) {
                showError('百度地图 API 未加载');
                return;
            }
            if (!map) {
                if (!initMap()) {
                    showError('地图初始化失败');
                    return;
                }
            }
            try { map.checkResize(); } catch (e) {}
            markDatasetSpots(mapSpots || []);
            try { map.checkResize(); } catch (e) {}
            if (window.requestAnimationFrame) {
                requestAnimationFrame(function () {
                    try { map.checkResize(); } catch (e) {}
                });
            }
        }

        function hideResult() {
            $('#resultContainer').hide();
        }

        function escapeHtml(s) {
            if (s === null || s === undefined) return '';
            return String(s)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;');
        }

        function renderOverview(overview, mapSpotCount) {
            overview = overview || {};
            $('#citySummary').text(overview.city_summary || '（暂无概况）');

            const wList = $('#whatToSeeList');
            wList.empty();
            (overview.what_to_see || []).forEach(function (line) {
                wList.append($('<li></li>').text(line));
            });
            if (!wList.children().length) {
                wList.append($('<li style="border-left-color: #a0aec0; color: #a0aec0;">暂无要点，可重试或微调城市名。</li>'));
            }

            const wo = $('#watchoutsList');
            wo.empty();
            (overview.watchouts || []).forEach(function (line) {
                wo.append($('<li class="warning"></li>').text(line));
            });
            if (!wo.children().length) {
                wo.append($('<li class="warning" style="border-left-color: #a0aec0; color: #a0aec0;">暂无单独条目，可查看概况段落。</li>'));
            }

            const regBox = $('#regionsBox');
            regBox.empty();
            (overview.regions || []).forEach(function (r) {
                const title = escapeHtml(r.title || '');
                const blurb = escapeHtml(r.blurb || '');
                regBox.append(
                    $('<div class="region-card"></div>').html(
                        '<strong>' + title + '</strong><p>' + blurb + '</p>'
                    )
                );
            });
            if (!(overview.regions || []).length) {
                regBox.append($('<p style="color: #a0aec0; font-size: 13px;">暂无片区主题提示。</p>'));  
            }

            if (overview.parse_note) {
                $('#parseNoteBox').show().text(overview.parse_note);
            } else {
                $('#parseNoteBox').hide().empty();
            }

            const hi = (overview.what_to_see || []).length;
            const wc = (overview.watchouts || []).length;
            $('#highlightCount').text(hi);
            $('#watchoutCount').text(wc);
            $('#mapSpotCount').text(typeof mapSpotCount === 'number' ? mapSpotCount : '-');
        }

        function clearMap() {
            if (map) {
                map.clearOverlays();
                markers = [];
                polylines = [];
            }
        }

        function markDatasetSpots(spots) {
            $('#mapEmptyHint').hide();
            if (!map || !BMap) {
                console.error('地图未初始化');
                return;
            }
            try { map.checkResize(); } catch (e) {}
            clearMap();
            const points = [];
            const list = spots || [];

            list.forEach(function (item) {
                const lon = item.longitude;
                const lat = item.latitude;
                if (lon == null || lat == null || isNaN(lon) || isNaN(lat)) return;
                const point = new BMap.Point(lon, lat);
                points.push(point);
                const marker = new BMap.Marker(point);
                map.addOverlay(marker);
                markers.push(marker);
 // --- 构建弹窗内容（利用数据库的其他字段） ---
                const name = escapeHtml(item.name || '景点');
                const area = escapeHtml(item.area || '');
                const rating = escapeHtml(item.rating || '');
                const price = escapeHtml(item.price_hint || '');
                const infoHtml =
                    '<div style="min-width:240px;padding:10px;font-size:13px;">' +
                    '<div style="font-weight:bold;color:#1a73e8;margin-bottom:6px;">' + name + '</div>' +
                    (area ? '<div>区域：' + area + '</div>' : '') +
                    (rating ? '<div>评分：' + rating + '</div>' : '') +
                    (price ? '<div>票价参考：' + price + '</div>' : '') +
                    '<div style="color:#888;font-size:11px;margin-top:6px;">景点信息</div>' +
                    '</div>';
                const infoWindow = new BMap.InfoWindow(infoHtml, {    //创建一个 InfoWindow（弹窗对象）
                    width: 280,
                    title: '景点',
                    enableMessage: false
                });
                marker.addEventListener('click', function () {  // 绑定事件：当用户点击标记点时，打开这个弹窗
                    map.openInfoWindow(infoWindow, point);
                });
            });

            if (points.length === 0) {
                $('#mapEmptyHint').show();
                return;
            }
            try {
                map.checkResize();
                const viewport = map.getViewport(points);     // 计算一个能容纳所有点的最佳视图范围 (Viewport)
                const zoom = Math.min(viewport.zoom - 1, 16);
                map.centerAndZoom(viewport.center, zoom);
                setTimeout(function () { try { map.checkResize(); } catch (e) {} }, 100);
            } catch (err) {
                console.warn('viewport', err);
                map.centerAndZoom(points[0], 13);
            }
        }

        $('#travelForm').on('submit', function (e) {
            e.preventDefault();

            const city = $('#city').val().trim();
            const season = $('#season').val();
            const days = $('#days').val();
            const budget = $('#budget').val();

            if (!city) {
                showError('请填写目的地城市');
                return;
            }
            if (!season) {
                showError('请选择旅行季节');
                return;
            }

            hideError();
            hideResult();
            showLoading();

            $('#submitBtn').prop('disabled', true).html('<i class="fas fa-spinner fa-spin mr-2"></i>生成中...');

            const requestData = {
                city: city,
                season: season,
                days: days,
                budget: budget || 0
            };

            $.ajax({
                url: window.travelRouteConfig.urls.generate,
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify(requestData),
                success: function (response) {
                    if (response.code === 200 && response.data) {
                        const d = response.data;
                        renderOverview(d.overview, d.map_spot_count);
                        showResult(function () {
                            bindMapAfterResultVisible(d.map_spots);
                        });
                    } else {
                        showError(response.message || '生成失败');
                    }
                },
                error: function (xhr, status, error) {
                    console.error('API请求失败:', error);
                    showError('网络错误，请重试: ' + error);
                },
                complete: function () {
                    hideLoading();
                    $('#submitBtn').prop('disabled', false).html('<i class="fas fa-paper-plane mr-2"></i>生成目的地速览');
                }
            });
        });
    });