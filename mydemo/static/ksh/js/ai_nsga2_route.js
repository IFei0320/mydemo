const sliderPairs = [
    ["priceSensitivity", "priceVal"],
    ["distanceSensitivity", "distanceVal"],
    ["hotnessPreference", "hotnessVal"],
    ["ratingPreference", "ratingVal"],
];
sliderPairs.forEach(([sliderId, labelId]) => {
    const slider = document.getElementById(sliderId);
    const label = document.getElementById(labelId);
    slider.addEventListener("input", () => label.innerText = slider.value);
});

let mapInstance = null;
let geocoder = null;
let latestHtmlReport = "";
let currentRequestToken = "";
let latestSelectedData = null;
function ensureMap() {
    if (!mapInstance && window.BMap) {
        mapInstance = new BMap.Map("routeMap");
        mapInstance.centerAndZoom(new BMap.Point(116.404, 39.915), 11);
        mapInstance.enableScrollWheelZoom(true);
        geocoder = new BMap.Geocoder();
    }
    return mapInstance;
}

function dayColor(dayNo) {
    const palette = ["#ff4d4f", "#1890ff", "#52c41a", "#faad14", "#722ed1", "#13c2c2"];
    return palette[(dayNo - 1) % palette.length];
}

function isValidChinaCoord(lon, lat) {
    return lon >= 73 && lon <= 136 && lat >= 3 && lat <= 54;
}

function renderMap(route, selectedCity) {
    const map = ensureMap();
    if (!map) return;
    map.clearOverlays();
    const grouped = {};
    const points = [];

    let visibleIndex = 0;
    route.forEach((item, index) => {
        const lon = parseFloat(item.longitude);
        const lat = parseFloat(item.latitude);
        if (!Number.isFinite(lon) || !Number.isFinite(lat) || !isValidChinaCoord(lon, lat)) {
            return;
        }
        visibleIndex = index + 1;
        const dayMatch = (item.visit_time || "").match(/第(\d+)天/);
        const dayNo = dayMatch ? parseInt(dayMatch[1], 10) : 1;
        const point = new BMap.Point(lon, lat);
        points.push(point);
        if (!grouped[dayNo]) grouped[dayNo] = [];
        grouped[dayNo].push(point);

        const marker = new BMap.Marker(point);
        const label = new BMap.Label(`${visibleIndex}`, {offset: new BMap.Size(20, -10)});
        label.setStyle({
            color: "#fff",
            backgroundColor: dayColor(dayNo),
            border: "none",
            borderRadius: "10px",
            padding: "2px 6px"
        });
        marker.setLabel(label);
        const info = new BMap.InfoWindow(`<b>${item.name}</b><br/>${item.visit_time}<br/>${item.features}<br/>预计：${item.estimated_cost}<br/>坐标：${lat}, ${lon}`);
        marker.addEventListener("click", () => map.openInfoWindow(info, point));
        map.addOverlay(marker);
    });

    Object.keys(grouped).forEach(dayKey => {
        const line = new BMap.Polyline(grouped[dayKey], {
            strokeColor: dayColor(parseInt(dayKey, 10)),
            strokeWeight: 5,
            strokeOpacity: 0.75,
        });
        map.addOverlay(line);

        const dayPoints = grouped[dayKey];
        for (let i = 0; i < dayPoints.length - 1; i++) {
            const startPoint = dayPoints[i];
            const endPoint = dayPoints[i + 1];
            const angle = Math.atan2(endPoint.lat - startPoint.lat, endPoint.lng - startPoint.lng) * 180 / Math.PI;
            const midPoint = new BMap.Point(
                (startPoint.lng + endPoint.lng) / 2,
                (startPoint.lat + endPoint.lat) / 2
            );
            const arrowLabel = new BMap.Label("➤", { offset: new BMap.Size(-8, -8), position: midPoint });
            arrowLabel.setStyle({
                color: dayColor(parseInt(dayKey, 10)),
                border: "none",
                background: "rgba(255,255,255,0.9)",
                borderRadius: "50%",
                width: "18px",
                height: "18px",
                lineHeight: "18px",
                textAlign: "center",
                fontWeight: "bold",
                transform: `rotate(${angle}deg)`,
            });
            map.addOverlay(arrowLabel);
        }
    });

    if (points.length > 0) {
        map.setViewport(points);
    } else if (geocoder && selectedCity) {
        geocoder.getPoint(selectedCity, function(point) {
            if (point) {
                map.centerAndZoom(point, 11);
            }
        }, selectedCity);
    }
}

function renderTable(route) {
    const tbody = $("#routeBody");
    tbody.empty();
    route.forEach((row, i) => {
        tbody.append(`
            <tr>
                <td><span class="table-rank">${i + 1}</span></td>
                <td>
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <div style="width: 32px; height: 32px; border-radius: 8px; background: linear-gradient(135deg, #4c6ef5, #748ffc); display: flex; align-items: center; justify-content: center; color: white; font-size: 13px;">
                            <i class="fas fa-map-marker-alt"></i>
                        </div>
                        <span style="font-weight: 700; color: #1a202c;">${row.name}</span>
                    </div>
                </td>
                <td><span class="plan-badge badge-blue"><i class="far fa-clock mr-1"></i>${row.visit_time}</span></td>
                <td><span class="plan-badge badge-green">${row.features}</span></td>
                <td><span style="color: #e53e3e; font-weight: 700;">${row.estimated_cost}</span></td>
                <td><small style="color: #a0aec0;"><i class="fas fa-crosshairs mr-1"></i>${row.latitude}, ${row.longitude}</small></td>
            </tr>
        `);
    });
}

function renderKnowledgeCards(cards) {
    const root = $("#knowledgeList");
    root.empty();
    if (!cards || !cards.length) {
        root.append(`
            <div style="text-align: center; padding: 40px; color: #a0aec0;">
                <i class="fas fa-inbox" style="font-size: 36px; margin-bottom: 12px; opacity: 0.5;"></i>
                <p>未命中本地知识卡，将以通用建议为主。</p>
            </div>
        `);
        $("#knowledgeCount").text("0");
        return;
    }
    $("#knowledgeCount").text(cards.length);
    cards.forEach((card, idx) => {
        const pitfalls = (card.pitfalls || []).join("；");
        root.append(`
            <div class="knowledge-card">
                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
                    <span style="width: 24px; height: 24px; border-radius: 50%; background: linear-gradient(135deg, #feca57, #ff9f43); color: white; font-size: 12px; font-weight: 700; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">${idx + 1}</span>
                    <h6 style="margin: 0; font-weight: 700; color: #1a202c;">${card.spot_name}</h6>
                </div>
                <div class="knowledge-grid">
                    <div>
                        <small><i class="fas fa-sun mr-1" style="color: #feca57;"></i>最佳时段</small>
                        <p>${card.best_time || "-"}</p>
                    </div>
                    <div>
                        <small><i class="fas fa-ticket-alt mr-1" style="color: #6bb3d9;"></i>预约提示</small>
                        <p>${card.booking_tip || "-"}</p>
                    </div>
                    <div>
                        <small><i class="fas fa-bus mr-1" style="color: #5dbea3;"></i>交通提示</small>
                        <p>${card.transport_tip || "-"}</p>
                    </div>
                    <div>
                        <small><i class="fas fa-exclamation-triangle mr-1" style="color: #e07a7a;"></i>避坑点</small>
                        <p>${pitfalls || "-"}</p>
                    </div>
                </div>
            </div>
        `);
    });
}

function sanitizeHtmlForPreview(rawHtml) {
    if (!rawHtml) return "";
    let cleaned = rawHtml.replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, "");
    if (!/<!doctype html>/i.test(cleaned)) {
        cleaned = `<!doctype html><html><head><meta charset="utf-8"><title>AI报告</title><base target="_blank"><base target="_blank">
</head><body>${cleaned}</body></html>`;
    }
    return cleaned;
}

function openHtmlReport(htmlText) {
    const safeHtml = sanitizeHtmlForPreview(htmlText);
    if (!safeHtml) return;
    const win = window.open("", "_blank");
    if (!win) return;
    win.document.open();
    win.document.write(safeHtml);
    win.document.close();
}

function downloadHtmlReport(htmlText, city) {
    const safeHtml = sanitizeHtmlForPreview(htmlText);
    if (!safeHtml) return;
    const blob = new Blob([safeHtml], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${city || "travel"}_ai_report.html`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

$("#previewHtmlReportBtn").on("click", function () {
    openHtmlReport(latestHtmlReport);
});

$("#downloadHtmlReportBtn").on("click", function () {
    const city = $("#city").val().trim() || "travel";
    downloadHtmlReport(latestHtmlReport, city);
});

var toastTimer = null;
function showToast(msg, type) {
    var $t = $('#toastMsg');
    clearTimeout(toastTimer);
    $t.removeClass('show error success').text(msg).addClass(type + ' show');
    toastTimer = setTimeout(function() {
        $t.removeClass('show');
    }, 2800);
}

$("#exportDidaBtn").on("click", function () {
    if (!latestSelectedData) {
        $("#errorText").text("请先选择方案并生成结果");
        $("#error").show();
        return;
    }
    const now = new Date();
    const defaultStr = new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    $("#didaDepartureInput").val(defaultStr);
    $("#didaModalMask").fadeIn(120);
});

function closeDidaModal() {
    $("#didaModalMask").fadeOut(120);
}

$("#closeDidaModalBtn, #cancelDidaBtn").on("click", closeDidaModal);

$("#confirmDidaBtn").on("click", function () {
    const departure = ($("#didaDepartureInput").val() || "").trim();
    if (!departure) {
        showToast("请先选择出发时间", "error");
        return;
    }
    closeDidaModal();

    $("#loading").html(`
        <div class="d-flex align-items-center">
            <div class="spinner-border spinner-border-sm text-white mr-3" role="status"></div>
            <span><i class="fas fa-cloud-upload-alt mr-2"></i>正在写入滴答清单...</span>
        </div>
    `).show();

    $.ajax({
        url: window.nsga2RouteConfig.urls.exportDida,
        type: "POST",
        contentType: "application/json",
        data: JSON.stringify({
            departure_time: departure.trim(),
            city: latestSelectedData.city || $("#city").val().trim(),
            style: latestSelectedData.style || "",
            route: latestSelectedData.route || [],
            knowledge_cards: latestSelectedData.knowledge_cards || []
        }),
        headers: { "X-CSRFToken": window.nsga2RouteConfig.csrfToken },
        success: function (res) {
            $("#loading").hide();
            console.log("DIDA RESPONSE:", JSON.stringify(res));
            if (res.code !== 200) {
                showToast(res.message || "写入滴答失败", "error");
                return;
            }
            const data = res.data || {};
            const created = data.created_count || 0;
            const failed = data.failed_count || 0;
            console.log("DIDA: created=" + created + " failed=" + failed);
            if (created > 0) {
                showToast(`已写入滴答清单：成功 ${created} 个任务` + (failed > 0 ? `，${failed} 个失败` : ""), "success");
            } else {
                showToast("写入失败，请稍后重试", "error");
            }
        },
        error: function (xhr) {
            $("#loading").hide();
            console.log("DIDA ERROR:", xhr.status, xhr.responseText);
            showToast("请求失败，请稍后重试", "error");
        }
    });
});

function metricValue(v, digit=2) {
    return Number(v || 0).toFixed(digit);
}

function renderRecent(recentPlans) {
    const list = $("#recentList");
    list.empty();
    if (!recentPlans || !recentPlans.length) {
        list.append('<p style="color: #a0aec0; width: 100%;"><i class="fas fa-inbox mr-2"></i>暂无历史记录</p>');
        return;
    }
    recentPlans.forEach(item => {
        const tag = $('<span class="recent-tag" title="点击加载此方案参数"></span>');
        tag.html(`<i class="fas fa-history mr-1"></i>${item.city} · ${item.season} · ${item.days}天 · 预算${item.budget}`);
        tag.data("plan", item);
        tag.on("click", function() {
            const p = $(this).data("plan");
            fillFormFromPlan(p);
            const preview = p.options_preview;
            if (preview && preview.length > 0) {
                currentRequestToken = p.token;
                renderTop3(preview);
                $("#top3Panel").show();
                $("#resultPanel").hide();
                showToast(`已恢复：${p.city} · ${p.season} · ${p.days}天`, "success");
            } else {
                $("#top3Panel").hide();
                $("#resultPanel").hide();
                showToast("参数已填回，请点击\"生成路线方案\"重新计算", "success");
            }
        });

        function fillFormFromPlan(p) {
            $("#city").val(p.city || "");
            $("#season").val(p.season || "spring");
            $("#days").val(p.days || 3);
            $("#budget").val(p.budget || 2000);
            if (p.price_sensitivity !== undefined) {
                $("#priceSensitivity").val(p.price_sensitivity);
                $("#priceVal").text(p.price_sensitivity);
                $("#distanceSensitivity").val(p.distance_sensitivity);
                $("#distanceVal").text(p.distance_sensitivity);
                $("#hotnessPreference").val(p.hotness_preference);
                $("#hotnessVal").text(p.hotness_preference);
                $("#ratingPreference").val(p.rating_preference);
                $("#ratingVal").text(p.rating_preference);
            }
            $("#resultPanel").hide();
            $("#top3Panel").hide();
        }
        list.append(tag);
    });
}

function renderTop3(options) {
    const container = $("#top3Options");
    container.empty();
    const gradients = [
        { header: "linear-gradient(135deg, #8b7fd4, #6b5b95)", text: "#8b7fd4", btn: "#8b7fd4" },
        { header: "linear-gradient(135deg, #5dbea3, #3d9970)", text: "#5dbea3", btn: "#5dbea3" },
        { header: "linear-gradient(135deg, #6bb3d9, #2980b9)", text: "#6bb3d9", btn: "#6bb3d9" }
    ];
    options.forEach((option, idx) => {
        const g = gradients[idx % 3];
        const m = option.metrics || {};
        const e = option.explain || {};
        const card = `
            <div class="plan-card">
                <div class="plan-card-header" style="background: ${g.header};">
                    <span class="rank-num">${idx + 1}</span>
                    <div>
                        <h6 style="margin: 0; font-weight: 700;">${option.title}</h6>
                        <small style="opacity: 0.8;">${option.style}</small>
                    </div>
                </div>
                <div class="plan-card-body">
                    <div style="margin-bottom: 12px; padding: 10px; border-radius: 10px; background: rgba(0,0,0,0.03);">
                        <small style="color: #a0aec0;">优势</small>
                        <p style="margin: 4px 0 0; font-weight: 700; color: #1a202c; font-size: 14px;">${option.advantage || "-"}</p>
                    </div>
                    <div class="plan-metric">
                        <small>门票合计</small>
                        <span style="color: #e53e3e;">${metricValue(m.cost)} 元</span>
                    </div>
                    <div class="plan-metric">
                        <small>预算剩余</small>
                        <span style="color: ${(option.remaining || 0) < 0 ? '#e53e3e' : '#38a169'};">${metricValue(option.remaining || 0)} 元</span>
                    </div>
                    <div class="plan-metric">
                        <small>总路程</small>
                        <span style="color: #6bb3d9;">${metricValue(m.distance)} km</span>
                    </div>
                    <div class="plan-metric">
                        <small>平均评分</small>
                        <span style="color: #feca57;">${metricValue(m.rating)}</span>
                    </div>
                    <div class="plan-metric">
                        <small>平均热度</small>
                        <span style="color: #8b7fd4;">${metricValue(m.hotness)}</span>
                    </div>
                    <div class="plan-metric">
                        <small>预算利用率</small>
                        <span class="plan-badge badge-blue">${metricValue(e.budget_usage_pct,1)}%</span>
                    </div>
                    <div class="plan-metric">
                        <small>偏好匹配度</small>
                        <span class="plan-badge badge-green">${metricValue(e.preference_match_pct,1)}%</span>
                    </div>
                    <button class="glass-btn glass-btn-primary select-plan-btn" data-option-id="${option.option_id}" style="width: 100%; margin-top: 12px;">
                        <i class="fas fa-check-circle mr-1"></i>选择此方案并生成地图/AI报告
                    </button>
                </div>
            </div>`;
        container.append(card);
    });
}

function renderSelectedPlan(data, payload) {
    latestSelectedData = data || null;
    const feas = data.feasibility || {};
    const tier = data.tier || "M";
    $("#usedDays").text(data.used_days);
    $("#paretoSize").text(data.pareto_size);
    $("#ticketCost").text(metricValue(data.ticket_cost) + " 元");
    $("#totalDistance").text(metricValue(data.metrics.distance));
    $("#budgetRemaining").text("+" + metricValue(data.total_estimate - data.ticket_cost) + " 元（食宿交通）");
    $("#feasibilityLabel").text("[" + tier + "档] " + (feas.label || "-"))
        .removeClass("badge-red badge-orange badge-green")
        .addClass(feas.css_class || "badge-gray");
    $("#feasibilityDetail").text(
        "全程预估约" + metricValue(data.total_estimate) + "元（门票" + metricValue(data.ticket_cost) + " + 食宿交通" + metricValue(data.total_living) + "）" +
        (feas.gap < 0 ? "，超出门票预算" + Math.abs(feas.gap) + "元" : feas.gap > 0 ? "，门票预算内可覆盖" : "")
    );
    $("#selectedAdvantage").text(data.advantage || "-");
    $("#budgetUsagePct").text(metricValue((data.explain || {}).budget_usage_pct, 1) + "%");
    $("#prefMatchPct").text(metricValue((data.explain || {}).preference_match_pct, 1) + "%");
    $("#aiSummary").text((data.ai_summary || "暂无 AI 攻略").replace(/\*/g, ""));
    const kb = data.knowledge_breakdown || {};
    const useWiki = !!kb.use_wiki_knowledge;
    $("#wikiModeBadge")
        .text(useWiki ? "网络攻略: 开" : "网络攻略: 关")
        .removeClass("badge-gray badge-green")
        .addClass(useWiki ? "badge-green" : "badge-gray");
    $("#jsonHitBadge").text("基础贴士 " + metricValue(kb.json_count || 0));
    $("#wikiHitBadge").text("补充贴士 " + metricValue(kb.wiki_count || 0));
    latestHtmlReport = data.ai_html_report || "";
    $("#previewHtmlReportBtn").prop("disabled", !latestHtmlReport);
    $("#downloadHtmlReportBtn").prop("disabled", !latestHtmlReport);
    $("#exportDidaBtn").prop("disabled", !(data.route && data.route.length));
    renderTable(data.route || []);
    renderKnowledgeCards(data.knowledge_cards || []);
    $("#resultPanel").show();
    setTimeout(() => renderMap(data.route || [], data.city || payload.city), 80);
}

$(document).on("click", ".select-plan-btn", function () {
    const optionId = parseInt($(this).data("option-id"), 10);
    if (!currentRequestToken || !optionId) {
        $("#errorText").text("方案标识失效，请重新生成");
        $("#error").show();
        return;
    }
    $("#error").hide();
    $("#loading").html(`
        <div class="d-flex align-items-center">
            <div class="spinner-border spinner-border-sm text-white mr-3" role="status"></div>
            <span><i class="fas fa-cog fa-spin mr-2"></i>正在生成地图与详细攻略，请稍候...</span>
        </div>
    `).show();
    $.ajax({
        url: window.nsga2RouteConfig.urls.select,
        type: "POST",
        contentType: "application/json",
        data: JSON.stringify({
            request_token: currentRequestToken,
            option_id: optionId,
            use_wiki_knowledge: $("#useWikiKnowledge").is(":checked")
        }),
        headers: { "X-CSRFToken": window.nsga2RouteConfig.csrfToken },
        success: function (res) {
            $("#loading").hide();
            if (res.code !== 200) {
                $("#errorText").text(res.message || "方案确认失败");
                $("#error").show();
                return;
            }
            renderSelectedPlan(res.data || {}, { city: $("#city").val().trim() });
        },
        error: function (xhr) {
            $("#loading").hide();
            $("#errorText").text("请求失败：" + (xhr.responseText || xhr.statusText));
            $("#error").show();
        }
    });
});

$("#generateBtn").on("click", function () {
    $("#error").hide();
    $("#resultPanel").hide();
    $("#top3Panel").hide();
    $("#recentPanel").hide();
    $("#loading").html(`
        <div class="d-flex align-items-center">
            <div class="spinner-border spinner-border-sm text-white mr-3" role="status"></div>
            <span><i class="fas fa-cog fa-spin mr-2"></i>正在生成路线方案，请稍候...</span>
        </div>
    `).show();
    latestHtmlReport = "";
    currentRequestToken = "";
    latestSelectedData = null;
    $("#previewHtmlReportBtn").prop("disabled", true);
    $("#downloadHtmlReportBtn").prop("disabled", true);
    $("#exportDidaBtn").prop("disabled", true);

    const payload = {
        city: $("#city").val().trim(),
        season: $("#season").val(),
        budget: parseFloat($("#budget").val() || "0"),
        days: parseInt($("#days").val() || "1", 10),
        price_sensitivity: parseInt($("#priceSensitivity").val(), 10),
        distance_sensitivity: parseInt($("#distanceSensitivity").val(), 10),
        hotness_preference: parseInt($("#hotnessPreference").val(), 10),
        rating_preference: parseInt($("#ratingPreference").val(), 10),
    };

    $.ajax({
        url: window.nsga2RouteConfig.urls.generate,
        type: "POST",
        contentType: "application/json",
        data: JSON.stringify(payload),
        headers: { "X-CSRFToken": window.nsga2RouteConfig.csrfToken },
        success: function (res) {
            $("#loading").hide();
            if (res.code !== 200) {
                $("#errorText").text(res.message || "生成失败");
                $("#error").show();
                return;
            }
            const data = res.data;
            currentRequestToken = data.request_token || "";
            renderTop3(data.options || []);
            renderRecent(data.recent_plans || []);
            $("#top3Panel").show();
            $("#recentPanel").show();
        },
        error: function (xhr) {
            $("#loading").hide();
            $("#errorText").text("请求失败：" + (xhr.responseText || xhr.statusText));
            $("#error").show();
        }
    });
});

// 页面加载时获取缓存列表
$(function() {
    if (window.nsga2RouteConfig && window.nsga2RouteConfig.urls.recentPlans) {
        $.getJSON({
            url: window.nsga2RouteConfig.urls.recentPlans,
            success: function(res) {
                if (res.code === 200 && res.data && res.data.recent_plans && res.data.recent_plans.length > 0) {
                    renderRecent(res.data.recent_plans);
                    $("#recentPanel").show();
                }
            }
        });
    }
});