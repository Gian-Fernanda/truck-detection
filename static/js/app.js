/**
 * CY Vehicle Monitoring Dashboard - Client Logic
 */

document.addEventListener("DOMContentLoaded", () => {
    // --- Elements ---
    const valFps = document.getElementById("val-fps");
    const valRes = document.getElementById("val-res");
    const kpiActive = document.getElementById("kpi-active");
    const kpiTotalIn = document.getElementById("kpi-total-in");
    const kpiTotalOut = document.getElementById("kpi-total-out");
    const kpiAvgStay = document.getElementById("kpi-avg-stay");
    
    const logsContainer = document.getElementById("logs-container");
    const truckTableBody = document.getElementById("truck-table-body");
    const searchTruckInput = document.getElementById("search-truck");
    
    const videoFeed = document.getElementById("video-feed");
    const videoWrapper = document.getElementById("video-wrapper");
    const btnFullscreen = document.getElementById("btn-fullscreen");
    
    // Zone Drawing Elements
    const btnDrawZone = document.getElementById("btn-draw-zone");
    const zoneToolbar = document.getElementById("zone-toolbar");
    const zoneCanvas = document.getElementById("zone-canvas");
    const pointsCounter = document.getElementById("points-counter");
    const btnZoneReset = document.getElementById("btn-zone-reset");
    const btnZoneCancel = document.getElementById("btn-zone-cancel");
    const btnZoneSave = document.getElementById("btn-zone-save");
    
    let isDrawingZone = false;
    let zonePoints = [];
    let currentVehiclesList = [];
    let occupancyChart = null;

    // --- 1. Inisialisasi Chart.js ---
    function initChart() {
        const ctx = document.getElementById("occupancyChart").getContext("2d");
        
        // Gradient fill for sleek aesthetic
        const gradient = ctx.createLinearGradient(0, 0, 0, 180);
        gradient.addColorStop(0, "rgba(6, 182, 212, 0.4)");
        gradient.addColorStop(1, "rgba(6, 182, 212, 0.0)");

        occupancyChart = new Chart(ctx, {
            type: "line",
            data: {
                labels: [],
                datasets: [{
                    label: "Truk Aktif di CY",
                    data: [],
                    borderColor: "#06b6d4",
                    backgroundColor: gradient,
                    borderWidth: 2.5,
                    fill: true,
                    tension: 0.35,
                    pointRadius: 3,
                    pointHoverRadius: 6,
                    pointBackgroundColor: "#06b6d4",
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: "rgba(15, 23, 42, 0.9)",
                        titleColor: "#94a3b8",
                        bodyColor: "#ffffff",
                        borderColor: "rgba(255, 255, 255, 0.1)",
                        borderWidth: 1,
                        padding: 8,
                        displayColors: false,
                    }
                },
                scales: {
                    x: {
                        grid: { color: "rgba(255, 255, 255, 0.05)" },
                        ticks: { color: "#64748b", font: { size: 10 } }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: "rgba(255, 255, 255, 0.05)" },
                        ticks: { color: "#64748b", stepSize: 1, font: { size: 10 } }
                    }
                }
            }
        });
    }

    // --- 2. Polling API Telemetry (/api/stats) ---
    async function fetchTelemetry() {
        try {
            const response = await fetch("/api/stats");
            if (!response.ok) return;
            const data = await response.json();

            // Update KPI
            kpiActive.textContent = data.active_count || 0;
            kpiTotalIn.textContent = data.total_entered || 0;
            kpiTotalOut.textContent = data.total_exited || 0;
            kpiAvgStay.textContent = data.avg_stay_minutes !== undefined ? data.avg_stay_minutes.toFixed(1) : "0.0";

            // Update Meta Badges
            valFps.textContent = data.fps !== undefined ? data.fps.toFixed(1) : "0.0";
            valRes.textContent = data.resolution || "--x--";

            // Update Logs
            renderLogs(data.logs || []);

            // Update Vehicle Table
            currentVehiclesList = data.vehicles || [];
            renderTable(currentVehiclesList);

            // Update Chart
            if (data.occupancy_history && occupancyChart) {
                const labels = data.occupancy_history.map(item => item.time);
                const values = data.occupancy_history.map(item => item.occupancy);
                occupancyChart.data.labels = labels;
                occupancyChart.data.datasets[0].data = values;
                occupancyChart.update("none"); // update without animation jank
            }
        } catch (err) {
            console.error("Telemetry fetch error:", err);
        }
    }

    // --- 3. Render Live Logs ---
    function renderLogs(logs) {
        if (!logs || logs.length === 0) {
            logsContainer.innerHTML = '<div class="empty-state">Menunggu aktivitas kendaraan...</div>';
            return;
        }

        logsContainer.innerHTML = logs.map(log => {
            const isMasuk = log.includes("MASUK");
            const badgeClass = isMasuk ? "masuk" : "keluar";
            const badgeText = isMasuk ? "MASUK" : "KELUAR";

            // Extract time like [12.5s] or text
            const timeMatch = log.match(/\[(.*?)\]/);
            const timeStr = timeMatch ? timeMatch[1] : "";
            const cleanText = log.replace(/\[.*?\]\s*(MASUK|KELUAR)\s*/, "");

            return `
                <div class="log-item">
                    <div class="log-left">
                        <span class="log-badge ${badgeClass}">${badgeText}</span>
                        <span class="log-text">${cleanText}</span>
                    </div>
                    <span class="log-time">${timeStr}</span>
                </div>
            `;
        }).join("");
    }

    // --- 4. Render Table with Search Filter ---
    function renderTable(vehicles) {
        const query = (searchTruckInput.value || "").toLowerCase();
        const filtered = vehicles.filter(v => 
            `truk #${v.id}`.toLowerCase().includes(query) ||
            v.type.toLowerCase().includes(query) ||
            v.status.toLowerCase().includes(query)
        );

        if (filtered.length === 0) {
            truckTableBody.innerHTML = '<tr><td colspan="5" class="empty-table-cell">Tidak ada data kendaraan ditemukan.</td></tr>';
            return;
        }

        truckTableBody.innerHTML = filtered.map(v => {
            const statusClass = v.is_active ? "active" : "exited";
            const statusText = v.is_active ? "● Aktif di CY" : "Sudah Keluar";
            return `
                <tr>
                    <td><strong>#${v.id}</strong></td>
                    <td>${v.type}</td>
                    <td>${v.entry_time.toFixed(1)}s</td>
                    <td>${v.duration_min.toFixed(1)} mnt</td>
                    <td><span class="status-tag ${statusClass}">${statusText}</span></td>
                </tr>
            `;
        }).join("");
    }

    searchTruckInput.addEventListener("input", () => renderTable(currentVehiclesList));

    // --- 5. Interactive Zone Drawing on Canvas ---
    function resizeCanvas() {
        const rect = videoFeed.getBoundingClientRect();
        zoneCanvas.width = rect.width;
        zoneCanvas.height = rect.height;
    }

    window.addEventListener("resize", resizeCanvas);

    btnDrawZone.addEventListener("click", () => {
        isDrawingZone = true;
        zonePoints = [];
        resizeCanvas();
        zoneCanvas.classList.add("active-drawing");
        zoneToolbar.classList.add("show");
        pointsCounter.textContent = "0 Titik";
        drawZoneOnCanvas();
    });

    zoneCanvas.addEventListener("click", (e) => {
        if (!isDrawingZone) return;
        const rect = zoneCanvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        // Map canvas coordinates to video resolution
        const scaleX = 1920 / rect.width; // standard ref or normalized
        const scaleY = 1080 / rect.height;

        zonePoints.push({
            canvasX: x,
            canvasY: y,
            realX: Math.round(x * scaleX),
            realY: Math.round(y * scaleY),
        });

        pointsCounter.textContent = `${zonePoints.length} Titik`;
        drawZoneOnCanvas();
    });

    function drawZoneOnCanvas() {
        const ctx = zoneCanvas.getContext("2d");
        ctx.clearRect(0, 0, zoneCanvas.width, zoneCanvas.height);

        if (zonePoints.length === 0) return;

        ctx.strokeStyle = "#06b6d4";
        ctx.fillStyle = "rgba(6, 182, 212, 0.25)";
        ctx.lineWidth = 2;

        ctx.beginPath();
        ctx.moveTo(zonePoints[0].canvasX, zonePoints[0].canvasY);
        for (let i = 1; i < zonePoints.length; i++) {
            ctx.lineTo(zonePoints[i].canvasX, zonePoints[i].canvasY);
        }

        if (zonePoints.length >= 3) {
            ctx.closePath();
            ctx.fill();
        }
        ctx.stroke();

        // Draw points dots
        for (const pt of zonePoints) {
            ctx.fillStyle = "#ffffff";
            ctx.beginPath();
            ctx.arc(pt.canvasX, pt.canvasY, 4, 0, Math.PI * 2);
            ctx.fill();
        }
    }

    btnZoneReset.addEventListener("click", () => {
        zonePoints = [];
        pointsCounter.textContent = "0 Titik";
        drawZoneOnCanvas();
    });

    btnZoneCancel.addEventListener("click", () => {
        isDrawingZone = false;
        zoneCanvas.classList.remove("active-drawing");
        zoneToolbar.classList.remove("show");
        const ctx = zoneCanvas.getContext("2d");
        ctx.clearRect(0, 0, zoneCanvas.width, zoneCanvas.height);
    });

    btnZoneSave.addEventListener("click", async () => {
        if (zonePoints.length < 3) {
            alert("Harap tentukan minimal 3 titik batas untuk zona CY.");
            return;
        }

        const rawPoints = zonePoints.map(pt => [pt.realX, pt.realY]);
        try {
            const res = await fetch("/api/zone", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ points: rawPoints })
            });
            const result = await res.json();
            if (result.success) {
                btnZoneCancel.click();
            } else {
                alert("Gagal menyimpan zona: " + result.message);
            }
        } catch (e) {
            alert("Error menyimpan zona: " + e.message);
        }
    });

    // --- 6. Fullscreen Video ---
    btnFullscreen.addEventListener("click", () => {
        if (!document.fullscreenElement) {
            videoWrapper.requestFullscreen().catch(err => alert("Fullscreen error: " + err.message));
        } else {
            document.exitFullscreen();
        }
    });

    // --- 7. Start App ---
    initChart();
    fetchTelemetry();
    setInterval(fetchTelemetry, 1000);
});

function handleStreamError() {
    console.warn("Video stream disconnected. Retrying...");
    setTimeout(() => {
        const stream = document.getElementById("video-feed");
        if (stream) stream.src = "/video_feed?t=" + new Date().getTime();
    }, 2000);
}
