/**
 * DockPulse 2.0 - Frontend Application Controller
 * Handles real-time system/container telemetry, dynamic Chart.js graphing,
 * Multi-condition Anomaly Detection, Linear Trend Forecasting, AI Workload Recommendations,
 * Kubernetes HPA Scaling Advisory, Event Streaming, Container Lifecycle Actions, and Modal Dialogs.
 */

// Global Application State
let pollIntervalTime = 2000; // Defaults to 2 seconds
let pollIntervalId = null;
let selectedContainerId = null; // Tracks active container details view (null = Overview Mode)
let activeEventSeverity = "ALL";
let cachedIntelligence = null;
let cachedK8sPlan = null;
let currentRuntime = "Docker";

// HTML escaping helper to prevent rendering errors and XSS
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// Host/Cluster Overview Chart Instances
let hostResourceChart = null;
let scalingHistoryChart = null;
let workloadDistributionChart = null;
let currentCpuWarningThreshold = 70.0;
let currentCpuCriticalThreshold = 85.0;

// Container-Specific Detail Chart Instances
let containerCpuChart = null;
let containerMemoryChart = null;

// DOM Elements
const timeDisplay = document.getElementById("time-display");
const pollIntervalSelector = document.getElementById("poll-interval");
const dockerOfflineOverlay = document.getElementById("docker-offline-overlay");
const dockerRetryBtn = document.getElementById("btn-docker-retry");

// Navigation tabs & Workspaces
const navOverviewBtn = document.getElementById("nav-overview-btn");
const logoBackHome = document.getElementById("logo-back-home");
const overviewWorkspace = document.getElementById("overview-workspace-view");
const containerDetailWorkspace = document.getElementById("container-detail-workspace-view");
const btnDetailBack = document.getElementById("btn-detail-back");
const sidebarContainerList = document.getElementById("sidebar-container-list");

// Breadcrumb Elements
const breadcrumbSec = document.getElementById("breadcrumb-sec");
const breadcrumbActive = document.getElementById("breadcrumb-active");

// Host/Overview Cards DOM
const cpuValueEl = document.getElementById("cpu-value");
const cpuBarEl = document.getElementById("cpu-bar");
const cpuSubEl = document.getElementById("cpu-sub");
const ramValueEl = document.getElementById("ram-value");
const ramBarEl = document.getElementById("ram-bar");
const ramSubEl = document.getElementById("ram-sub");
const totalContainersValEl = document.getElementById("total-containers-val");
const runningContainersCardVal = document.getElementById("running-containers-card-val");
const runningCountBadge = document.getElementById("running-count-badge");
const overviewContainerTableBody = document.getElementById("overview-container-table-body");

// DockPulse 2.0 Intelligence Elements DOM
const clusterConditionBadge = document.getElementById("cluster-condition-badge");
const clusterConditionText = document.getElementById("cluster-condition-text");
const intelStatusPill = document.getElementById("intel-status-pill");
const intelStatusText = document.getElementById("intel-status-text");
const anomalyCountBadge = document.getElementById("anomaly-count-badge");
const intelIssuesList = document.getElementById("intel-issues-list");

// Trend Analysis DOM
const trendDirectionBadge = document.getElementById("trend-direction-badge");
const trendDirectionText = document.getElementById("trend-direction-text");
const trendIcon = document.getElementById("trend-icon");
const trendSlopeText = document.getElementById("trend-slope-text");
const trendPredictionText = document.getElementById("trend-prediction-text");

// Workload Scaling DOM
const scalingActionBadge = document.getElementById("scaling-action-badge");
const scalingCurrRep = document.getElementById("scaling-curr-rep");
const scalingRecRep = document.getElementById("scaling-rec-rep");
const scalingReasonText = document.getElementById("scaling-reason-text");
const btnOpenK8sModal = document.getElementById("btn-open-k8s-modal");

// AI Recommendations DOM
const aiRecommendationsList = document.getElementById("ai-recommendations-list");

// Event Stream DOM
const eventsStreamList = document.getElementById("events-stream-list");
const eventsCountLabel = document.getElementById("events-count-label");
const eventsFilterGroup = document.getElementById("events-filter-group");

// Container Details Cards DOM
const detailContainerName = document.getElementById("detail-container-name");
const detailContainerImage = document.getElementById("detail-container-image");
const detailContainerStatusBadge = document.getElementById("detail-container-status-badge");
const detailContainerStatusText = document.getElementById("detail-container-status-text");
const detailContainerRestarts = document.getElementById("detail-container-restarts");
const detailActionsGroup = document.getElementById("detail-actions-group");

const detailCpuVal = document.getElementById("detail-cpu-val");
const detailCpuBar = document.getElementById("detail-cpu-bar");
const detailRamVal = document.getElementById("detail-ram-val");
const detailRamBar = document.getElementById("detail-ram-bar");
const detailRamPct = document.getElementById("detail-ram-pct");
const detailNetworkVal = document.getElementById("detail-network-val");
const detailUptimeVal = document.getElementById("detail-uptime-val");

// Modals DOM
const configModal = document.getElementById("config-modal");
const btnOpenConfigModal = document.getElementById("btn-open-config-modal");
const btnCloseConfigModal = document.getElementById("btn-close-config-modal");
const btnCancelConfig = document.getElementById("btn-cancel-config");
const formConfig = document.getElementById("form-config");
const btnSidebarThresholds = document.getElementById("btn-sidebar-thresholds");

const k8sScaleModal = document.getElementById("k8s-scale-modal");
const btnCloseK8sModal = document.getElementById("btn-close-k8s-modal");
const btnCancelK8s = document.getElementById("btn-cancel-k8s");
const btnApplyK8sScale = document.getElementById("btn-apply-k8s-scale");
const btnSidebarK8s = document.getElementById("btn-sidebar-k8s");
const k8sModalCurrent = document.getElementById("k8s-modal-current");
const k8sModalTarget = document.getElementById("k8s-modal-target");
const k8sCmdDisplay = document.getElementById("k8s-cmd-display");

const toastContainer = document.getElementById("toast-container");


// =============================================================================
// 1. FLOATING TOAST NOTIFICATION SYSTEM
// =============================================================================
function showToast(message, type = "info") {
    if (!toastContainer) return;
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    
    let icon = "fa-circle-info";
    if (type === "success") icon = "fa-circle-check";
    if (type === "error") icon = "fa-triangle-exclamation";
    
    toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${message}</span>`;
    toastContainer.appendChild(toast);
    
    // Animate in
    setTimeout(() => toast.classList.add("show"), 10);
    
    // Auto dismiss after 4 seconds
    setTimeout(() => {
        toast.classList.remove("show");
        setTimeout(() => toast.remove(), 350);
    }, 4000);
}


// =============================================================================
// 2. INITIALIZE REAL-TIME CLOCK IN TOP HEADER
// =============================================================================
function startLiveClock() {
    setInterval(() => {
        const now = new Date();
        const timeString = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
        if (timeDisplay) {
            timeDisplay.innerHTML = `<i class="fa-regular fa-clock"></i> ${timeString}`;
        }
    }, 1000);
}


// =============================================================================
// 3. INITIALIZE CHARTS (Host & Containers targets)
// =============================================================================
function initializeCharts() {
    // A. HOST CPU & WORKLOAD OBSERVABILITY CHART
    const hostLineCtx = document.getElementById("resourceLineChart")?.getContext("2d");
    if (hostLineCtx) {
        const cpuGrad = hostLineCtx.createLinearGradient(0, 0, 0, 250);
        cpuGrad.addColorStop(0, "rgba(0, 210, 255, 0.28)");
        cpuGrad.addColorStop(1, "rgba(0, 210, 255, 0.01)");
        
        const ramGrad = hostLineCtx.createLinearGradient(0, 0, 0, 250);
        ramGrad.addColorStop(0, "rgba(255, 87, 127, 0.20)");
        ramGrad.addColorStop(1, "rgba(255, 87, 127, 0.0)");

        hostResourceChart = new Chart(hostLineCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Host CPU (%)',
                        borderColor: '#00d2ff',
                        backgroundColor: cpuGrad,
                        borderWidth: 2.2,
                        pointRadius: 2.5,
                        pointHoverRadius: 6,
                        pointBackgroundColor: (ctx) => {
                            const val = ctx.raw;
                            if (val >= currentCpuCriticalThreshold) return '#ef4444';
                            if (val >= currentCpuWarningThreshold) return '#f59e0b';
                            return '#00d2ff';
                        },
                        pointBorderColor: (ctx) => {
                            const val = ctx.raw;
                            if (val >= currentCpuWarningThreshold) return '#ffffff';
                            return '#00d2ff';
                        },
                        fill: true,
                        tension: 0.25,
                        data: []
                    },
                    {
                        label: 'Host RAM (%)',
                        borderColor: '#ff577f',
                        backgroundColor: ramGrad,
                        borderWidth: 1.8,
                        pointRadius: 1.5,
                        pointHoverRadius: 5,
                        fill: true,
                        tension: 0.25,
                        data: []
                    },
                    {
                        label: 'CPU Warning Threshold',
                        borderColor: 'rgba(245, 158, 11, 0.88)',
                        borderWidth: 1.8,
                        borderDash: [6, 4],
                        pointRadius: 0,
                        pointHoverRadius: 0,
                        fill: false,
                        tension: 0,
                        data: []
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(17, 18, 23, 0.95)',
                        borderColor: 'rgba(255, 255, 255, 0.1)',
                        borderWidth: 1,
                        padding: 10,
                        callbacks: {
                            label: (ctx) => {
                                const dsLabel = ctx.dataset.label || '';
                                const val = ctx.raw;
                                if (ctx.datasetIndex === 2) {
                                    return `${dsLabel}: ${val}% (Configured Limit)`;
                                }
                                if (ctx.datasetIndex === 0 && val >= currentCpuWarningThreshold) {
                                    return `Host CPU: ${val.toFixed(1)}% ⚠️ Exceeds Warning Limit`;
                                }
                                return `${dsLabel}: ${typeof val === 'number' ? val.toFixed(1) : val}%`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.03)' },
                        ticks: { color: '#9fa2a5', font: { size: 9 }, maxTicksLimit: 6 }
                    },
                    y: {
                        min: 0,
                        suggestedMax: 100,
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: {
                            color: '#9fa2a5',
                            font: { size: 9 },
                            callback: (v) => `${v}%`
                        }
                    }
                }
            }
        });
    }

    // B. SCALING & REPLICA HISTORY CHART (Replaces Disk Utilization)
    const scalingCtx = document.getElementById("scalingHistoryChart")?.getContext("2d");
    if (scalingCtx) {
        const repGrad = scalingCtx.createLinearGradient(0, 0, 0, 250);
        repGrad.addColorStop(0, "rgba(168, 85, 247, 0.28)");
        repGrad.addColorStop(1, "rgba(168, 85, 247, 0.01)");

        scalingHistoryChart = new Chart(scalingCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Active Replicas',
                        borderColor: '#a855f7',
                        backgroundColor: repGrad,
                        borderWidth: 2.5,
                        stepped: 'before',
                        pointRadius: 3,
                        pointHoverRadius: 6,
                        fill: true,
                        data: []
                    },
                    {
                        label: 'HPA Target Replicas',
                        borderColor: '#00d2ff',
                        borderWidth: 1.8,
                        borderDash: [5, 4],
                        stepped: 'before',
                        pointRadius: 2,
                        pointHoverRadius: 5,
                        fill: false,
                        data: []
                    },
                    {
                        label: 'Running Containers',
                        borderColor: '#22c55e',
                        borderWidth: 1.5,
                        pointRadius: 2,
                        pointHoverRadius: 5,
                        fill: false,
                        tension: 0.1,
                        data: []
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(17, 18, 23, 0.95)',
                        borderColor: 'rgba(255, 255, 255, 0.1)',
                        borderWidth: 1,
                        padding: 10,
                        callbacks: {
                            label: (ctx) => `${ctx.dataset.label}: ${ctx.raw} units`
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.03)' },
                        ticks: { color: '#9fa2a5', font: { size: 9 }, maxTicksLimit: 6 }
                    },
                    y: {
                        min: 0,
                        suggestedMax: 4,
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: {
                            color: '#9fa2a5',
                            font: { size: 9 },
                            stepSize: 1,
                            precision: 0
                        }
                    }
                }
            }
        });
    }

    // C. WORKLOAD DISTRIBUTION CHART (Per-container/pod balancing)
    const distCtx = document.getElementById("workloadDistributionChart")?.getContext("2d");
    if (distCtx) {
        workloadDistributionChart = new Chart(distCtx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    label: 'Workload CPU (%)',
                    data: [],
                    backgroundColor: [],
                    borderColor: 'rgba(255, 255, 255, 0.15)',
                    borderWidth: 1,
                    borderRadius: 4,
                    barThickness: 16,
                    maxBarThickness: 22
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(17, 18, 23, 0.95)',
                        borderColor: 'rgba(255, 255, 255, 0.1)',
                        borderWidth: 1,
                        padding: 10,
                        callbacks: {
                            label: (ctx) => `CPU Allocation: ${Number(ctx.raw).toFixed(1)}%`
                        }
                    }
                },
                scales: {
                    x: {
                        min: 0,
                        suggestedMax: 15,
                        grid: { color: 'rgba(255, 255, 255, 0.04)' },
                        ticks: {
                            color: '#9fa2a5',
                            font: { size: 9 },
                            callback: (v) => `${v}%`
                        }
                    },
                    y: {
                        grid: { display: false },
                        ticks: {
                            color: '#eceded',
                            font: { size: 10, family: 'Inter' }
                        }
                    }
                }
            }
        });
    }

    // B. CONTAINER-SPECIFIC CHARTS
    const containerCpuCtx = document.getElementById("containerCpuChart")?.getContext("2d");
    if (containerCpuCtx) {
        const containerCpuGrad = containerCpuCtx.createLinearGradient(0, 0, 0, 220);
        containerCpuGrad.addColorStop(0, "rgba(0, 210, 255, 0.2)");
        containerCpuGrad.addColorStop(1, "rgba(0, 210, 255, 0.0)");

        containerCpuChart = new Chart(containerCpuCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Container CPU (%)',
                    borderColor: '#00d2ff',
                    backgroundColor: containerCpuGrad,
                    borderWidth: 2,
                    pointRadius: 1,
                    fill: true,
                    tension: 0.3,
                    data: []
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { color: 'rgba(255, 255, 255, 0.03)' }, ticks: { color: '#9fa2a5', font: { size: 9 } } },
                    y: { min: 0, max: 100, grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#9fa2a5', font: { size: 9 } } }
                }
            }
        });
    }

    const containerMemoryCtx = document.getElementById("containerMemoryChart")?.getContext("2d");
    if (containerMemoryCtx) {
        const containerMemoryGrad = containerMemoryCtx.createLinearGradient(0, 0, 0, 220);
        containerMemoryGrad.addColorStop(0, "rgba(255, 87, 127, 0.2)");
        containerMemoryGrad.addColorStop(1, "rgba(255, 87, 127, 0.0)");

        containerMemoryChart = new Chart(containerMemoryCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Memory Used (MB)',
                    borderColor: '#ff577f',
                    backgroundColor: containerMemoryGrad,
                    borderWidth: 2,
                    pointRadius: 1,
                    fill: true,
                    tension: 0.3,
                    data: []
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { color: 'rgba(255, 255, 255, 0.03)' }, ticks: { color: '#9fa2a5', font: { size: 9 } } },
                    y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#9fa2a5', font: { size: 9 } } }
                }
            }
        });
    }
}


// =============================================================================
// 4. UPDATE HOST DASHBOARD TELEMETRY
// =============================================================================
function updateHostDashboard(data, isInitialLoad = false) {
    if (!data || !data.latest) return;

    // CPU Card
    if (cpuValueEl) cpuValueEl.innerText = `${data.latest.cpu_percentage.toFixed(1)}%`;
    if (cpuBarEl) cpuBarEl.style.width = `${Math.min(100, data.latest.cpu_percentage)}%`;
    
    // RAM Card
    if (ramValueEl) ramValueEl.innerText = `${data.latest.ram_percentage.toFixed(1)}%`;
    if (ramBarEl) ramBarEl.style.width = `${Math.min(100, data.latest.ram_percentage)}%`;
    if (ramSubEl) ramSubEl.innerText = `Used: ${data.latest.ram_used_gb} GB / ${data.latest.ram_total_gb} GB`;

    // Update configured thresholds if supplied in system metrics
    if (data.thresholds) {
        currentCpuWarningThreshold = data.thresholds.cpu_warning !== undefined ? data.thresholds.cpu_warning : currentCpuWarningThreshold;
        currentCpuCriticalThreshold = data.thresholds.cpu_critical !== undefined ? data.thresholds.cpu_critical : currentCpuCriticalThreshold;
    } else if (data.latest && data.latest.cpu_warning !== undefined) {
        currentCpuWarningThreshold = data.latest.cpu_warning;
        currentCpuCriticalThreshold = data.latest.cpu_critical || 85.0;
    }
    const legendThreshEl = document.getElementById("legend-cpu-thresh");
    if (legendThreshEl) legendThreshEl.innerText = `${currentCpuWarningThreshold}%`;

    // 1. UPDATE CPU & WORKLOAD OBSERVABILITY CHART
    if (hostResourceChart) {
        if (isInitialLoad && Array.isArray(data.history)) {
            const labels = [];
            const cpuPoints = [];
            const ramPoints = [];
            const threshPoints = [];
            data.history.forEach(point => {
                labels.push(point.timestamp);
                cpuPoints.push(point.cpu_percentage);
                ramPoints.push(point.ram_percentage);
                threshPoints.push(currentCpuWarningThreshold);
            });
            hostResourceChart.data.labels = labels;
            hostResourceChart.data.datasets[0].data = cpuPoints;
            hostResourceChart.data.datasets[1].data = ramPoints;
            if (hostResourceChart.data.datasets[2]) {
                hostResourceChart.data.datasets[2].data = threshPoints;
            }
            hostResourceChart.update();
        } else {
            hostResourceChart.data.labels.push(data.latest.timestamp);
            hostResourceChart.data.datasets[0].data.push(data.latest.cpu_percentage);
            hostResourceChart.data.datasets[1].data.push(data.latest.ram_percentage);
            if (hostResourceChart.data.datasets[2]) {
                hostResourceChart.data.datasets[2].data.push(currentCpuWarningThreshold);
            }
            
            if (hostResourceChart.data.labels.length > 50) {
                hostResourceChart.data.labels.shift();
                hostResourceChart.data.datasets[0].data.shift();
                hostResourceChart.data.datasets[1].data.shift();
                if (hostResourceChart.data.datasets[2]) {
                    hostResourceChart.data.datasets[2].data.shift();
                }
            }
            hostResourceChart.update();
        }
    }

    // 2. UPDATE SCALING & REPLICA HISTORY CHART
    if (scalingHistoryChart) {
        if (isInitialLoad && Array.isArray(data.history)) {
            const labels = [];
            const repPoints = [];
            const recPoints = [];
            const conPoints = [];
            data.history.forEach(point => {
                labels.push(point.timestamp);
                repPoints.push(point.replicas !== undefined ? point.replicas : 1);
                recPoints.push(point.recommended_replicas !== undefined ? point.recommended_replicas : (point.replicas || 1));
                conPoints.push(point.running_containers !== undefined ? point.running_containers : 1);
            });
            scalingHistoryChart.data.labels = labels;
            scalingHistoryChart.data.datasets[0].data = repPoints;
            scalingHistoryChart.data.datasets[1].data = recPoints;
            scalingHistoryChart.data.datasets[2].data = conPoints;

            const allVals = [...repPoints, ...recPoints, ...conPoints];
            const maxVal = Math.max(...allVals, 3);
            scalingHistoryChart.options.scales.y.suggestedMax = maxVal + 1;
            scalingHistoryChart.update();
        } else if (scalingHistoryChart.data.datasets[0]) {
            const curRep = data.latest.replicas !== undefined ? data.latest.replicas : 1;
            const recRep = data.latest.recommended_replicas !== undefined ? data.latest.recommended_replicas : curRep;
            const conCnt = data.latest.running_containers !== undefined ? data.latest.running_containers : 1;

            scalingHistoryChart.data.labels.push(data.latest.timestamp);
            scalingHistoryChart.data.datasets[0].data.push(curRep);
            scalingHistoryChart.data.datasets[1].data.push(recRep);
            scalingHistoryChart.data.datasets[2].data.push(conCnt);
            
            if (scalingHistoryChart.data.labels.length > 50) {
                scalingHistoryChart.data.labels.shift();
                scalingHistoryChart.data.datasets[0].data.shift();
                scalingHistoryChart.data.datasets[1].data.shift();
                scalingHistoryChart.data.datasets[2].data.shift();
            }

            const allVals = [
                ...scalingHistoryChart.data.datasets[0].data,
                ...scalingHistoryChart.data.datasets[1].data,
                ...scalingHistoryChart.data.datasets[2].data
            ];
            const maxVal = Math.max(...allVals, 3);
            scalingHistoryChart.options.scales.y.suggestedMax = maxVal + 1;
            scalingHistoryChart.update();
        }
    }
}

// =============================================================================
// 4B. UPDATE WORKLOAD DISTRIBUTION UI
// =============================================================================
async function fetchWorkloadDistribution() {
    if (!workloadDistributionChart) return;
    try {
        const res = await fetch('/api/workload-distribution');
        if (res.ok) {
            const data = await res.json();
            updateWorkloadDistribution(data.workloads || []);
        }
    } catch (err) {
        console.warn("Failed to fetch workload distribution:", err);
    }
}

function updateWorkloadDistribution(workloads) {
    if (!workloadDistributionChart) return;
    const balanceStatusEl = document.getElementById("workload-balance-status");

    if (!Array.isArray(workloads) || workloads.length === 0) {
        workloadDistributionChart.data.labels = ['No Active Workloads'];
        workloadDistributionChart.data.datasets[0].data = [0];
        workloadDistributionChart.data.datasets[0].backgroundColor = ['rgba(255, 255, 255, 0.08)'];
        workloadDistributionChart.update();
        if (balanceStatusEl) {
            balanceStatusEl.className = "legend-badge";
            balanceStatusEl.innerHTML = `<i class="fa-solid fa-circle-pause"></i> Idle`;
        }
        return;
    }

    const labels = [];
    const cpuValues = [];
    const bgColors = [];
    const palette = [
        '#00d2ff', // Cyan
        '#a855f7', // Purple
        '#10b981', // Emerald
        '#f59e0b', // Amber
        '#ec4899', // Pink
        '#38bdf8', // Sky
        '#8b5cf6'  // Violet
    ];

    workloads.forEach((w, idx) => {
        let name = w.name || `workload-${idx + 1}`;
        if (name.length > 22) {
            name = name.substring(0, 10) + '..' + name.substring(name.length - 8);
        }
        labels.push(name);
        const cpu = typeof w.cpu_percentage === 'number' ? Math.max(0, w.cpu_percentage) : 0.0;
        cpuValues.push(cpu);
        bgColors.push(palette[idx % palette.length]);
    });

    workloadDistributionChart.data.labels = labels;
    workloadDistributionChart.data.datasets[0].data = cpuValues;
    workloadDistributionChart.data.datasets[0].backgroundColor = bgColors;

    const maxCpu = Math.max(...cpuValues, 10);
    workloadDistributionChart.options.scales.x.suggestedMax = Math.ceil(maxCpu * 1.25);
    workloadDistributionChart.update();

    if (balanceStatusEl) {
        if (workloads.length >= 2) {
            const spread = Math.max(...cpuValues) - Math.min(...cpuValues);
            if (spread <= 15) {
                balanceStatusEl.className = "legend-badge";
                balanceStatusEl.innerHTML = `<i class="fa-solid fa-check"></i> Balanced`;
            } else {
                balanceStatusEl.className = "legend-badge imbalanced";
                balanceStatusEl.innerHTML = `<i class="fa-solid fa-scale-unbalanced"></i> Skewed (+${spread.toFixed(1)}%)`;
            }
        } else {
            balanceStatusEl.className = "legend-badge";
            balanceStatusEl.innerHTML = `<i class="fa-solid fa-cube"></i> Single Node`;
        }
    }
}


// =============================================================================
// 5. DOCKPULSE 2.0: UPDATE INTELLIGENCE & WORKLOAD MANAGEMENT UI
// =============================================================================
function updateIntelligenceUI(data) {
    if (!data) return;
    cachedIntelligence = data;

    const status = data.status || "NORMAL";
    const hostAnalysis = data.host_analysis || {};
    const contAnalysis = data.container_analysis || {};
    const trend = data.trend || {};
    const scaling = data.scaling_decision || {};
    const recommendations = data.recommendations || [];

    // 1. Cluster Condition Badge in Top Header
    if (clusterConditionBadge && clusterConditionText) {
        clusterConditionBadge.className = `cluster-condition-badge condition-${status.toLowerCase()}`;
        clusterConditionText.innerText = status;
    }

    // 2. Intelligence Section Status Pill
    if (intelStatusPill && intelStatusText) {
        intelStatusPill.className = `status-pill status-pill-${status.toLowerCase()}`;
        intelStatusText.innerText = status;
    }

    // 3. Anomaly & Condition Monitor
    const allIssues = [...(hostAnalysis.issues || []), ...(contAnalysis.issues || [])];
    if (anomalyCountBadge) {
        anomalyCountBadge.innerText = `${allIssues.length} Issue${allIssues.length === 1 ? '' : 's'}`;
    }

    if (intelIssuesList) {
        if (allIssues.length === 0) {
            intelIssuesList.innerHTML = `
                <li class="nominal-item">
                    <i class="fa-solid fa-circle-check"></i>
                    <span>No active threshold breaches or crash loops detected. Microservices operating nominally.</span>
                </li>
            `;
        } else {
            let html = '';
            allIssues.forEach(issue => {
                html += `
                    <li class="anomaly-item">
                        <i class="fa-solid fa-triangle-exclamation"></i>
                        <span>${issue}</span>
                    </li>
                `;
            });
            intelIssuesList.innerHTML = html;
        }
    }

    // 4. Predictive Trend Analysis
    const direction = trend.direction || "STABLE";
    const slope = trend.slope_per_min || 0.0;
    
    if (trendDirectionBadge && trendDirectionText && trendIcon) {
        trendDirectionBadge.className = `trend-badge trend-${direction.toLowerCase()}`;
        trendDirectionText.innerText = direction;
        
        if (direction === "UPWARD") {
            trendIcon.className = "fa-solid fa-arrow-trend-up";
        } else if (direction === "DOWNWARD") {
            trendIcon.className = "fa-solid fa-arrow-trend-down";
        } else {
            trendIcon.className = "fa-solid fa-minus";
        }
    }

    if (trendSlopeText) {
        const sign = slope > 0 ? "+" : "";
        trendSlopeText.innerText = `${sign}${slope.toFixed(1)}% / min`;
    }

    if (trendPredictionText) {
        trendPredictionText.innerText = trend.prediction || trend.description || "Trajectory is stable. No imminent threshold breach projected.";
    }

    // 5. Workload Scaling Decision
    const action = scaling.action || "KEEP CURRENT CAPACITY";
    const currRep = scaling.current_replicas || 2;
    const recRep = scaling.recommended_replicas || 2;

    if (scalingActionBadge) {
        if (action === "SCALE UP") {
            scalingActionBadge.className = "scaling-pill scale-up";
            scalingActionBadge.innerText = "SCALE UP";
        } else if (action === "SCALE DOWN") {
            scalingActionBadge.className = "scaling-pill scale-down";
            scalingActionBadge.innerText = "SCALE DOWN";
        } else {
            scalingActionBadge.className = "scaling-pill scale-keep";
            scalingActionBadge.innerText = "KEEP CAPACITY";
        }
    }

    if (scalingCurrRep) scalingCurrRep.innerText = currRep;
    if (scalingRecRep) scalingRecRep.innerText = recRep;
    if (scalingReasonText) scalingReasonText.innerText = scaling.reason || "Workload capacity is balanced.";

    // Sync Kubernetes Scale Modal preview fields
    if (k8sModalCurrent) k8sModalCurrent.innerText = currRep;
    if (k8sModalTarget) k8sModalTarget.innerText = recRep;
    if (k8sCmdDisplay) {
        k8sCmdDisplay.innerText = `kubectl scale deployment dockpulse-deployment --replicas=${recRep}`;
    }

    // 6. AI Recommendations
    if (aiRecommendationsList) {
        if (recommendations.length === 0) {
            aiRecommendationsList.innerHTML = `
                <div class="rec-item priority-info">
                    <div class="rec-header">
                        <span class="rec-tag">STATUS</span>
                        <span class="rec-priority">NOMINAL</span>
                    </div>
                    <p class="rec-text">All monitored microservices operating within normal bounds.</p>
                </div>
            `;
        } else {
            let html = '';
            recommendations.forEach(r => {
                const priorityClass = `priority-${(r.priority || 'info').toLowerCase()}`;
                html += `
                    <div class="rec-item ${priorityClass}">
                        <div class="rec-header">
                            <span class="rec-tag">${r.type || 'ADVICE'}</span>
                            <span class="rec-priority">${r.priority || 'INFO'}</span>
                        </div>
                        <p class="rec-text">${r.text}</p>
                    </div>
                `;
            });
            aiRecommendationsList.innerHTML = html;
        }
    }
}


// =============================================================================
// 6. DOCKPULSE 2.0: FETCH & RENDER LIVE EVENTS STREAM
// =============================================================================
async function fetchEvents() {
    try {
        let url = '/api/events?limit=30';
        if (activeEventSeverity !== 'ALL') {
            url += `&severity=${activeEventSeverity}`;
        }
        const res = await fetch(url);
        if (!res.ok) return;
        const data = await res.json();
        const events = data.events || [];

        if (eventsCountLabel) {
            eventsCountLabel.innerText = `${events.length} event${events.length === 1 ? '' : 's'}`;
        }

        if (eventsStreamList) {
            if (events.length === 0) {
                eventsStreamList.innerHTML = `<div class="events-empty"><i class="fa-solid fa-inbox"></i> No events found for filter: ${activeEventSeverity}</div>`;
                return;
            }

            let html = '';
            events.forEach(evt => {
                const sev = (evt.severity || 'INFO').toUpperCase();
                let badgeClass = "sev-info";
                if (sev === "CRITICAL") badgeClass = "sev-critical";
                if (sev === "WARNING") badgeClass = "sev-warning";
                if (sev === "RECOMMENDATION") badgeClass = "sev-recommendation";

                html += `
                    <div class="event-item">
                        <span class="event-sev-badge ${badgeClass}">${sev}</span>
                        <span class="event-time">${evt.timestamp}</span>
                        <div class="event-content">
                            <span class="event-title">${evt.title}</span>
                            <span class="event-msg">${evt.message}</span>
                        </div>
                        <span class="event-source">${evt.source}</span>
                    </div>
                `;
            });
            eventsStreamList.innerHTML = html;
        }
    } catch (err) {
        console.error("Failed to fetch event feed:", err);
    }
}


// =============================================================================
// 7. CONTAINER MANAGEMENT ACTIONS (START, STOP, RESTART)
// =============================================================================
async function containerAction(containerId, action, event) {
    if (event) {
        event.stopPropagation();
    }
    if (!containerId || !action) return;

    const btn = event ? event.currentTarget : null;
    const originalText = btn ? btn.innerHTML : "";
    if (btn) {
        btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i>`;
        btn.disabled = true;
    }

    try {
        const response = await fetch(`/api/container/${containerId}/action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action })
        });
        const result = await response.json();

        if (!response.ok) {
            showToast(result.error || `Failed to ${action} container`, "error");
        } else {
            showToast(result.message || `Container ${action}ed successfully`, "success");
            // Refresh telemetry and container list immediately
            performPollTick(false);
            fetchEvents();
        }
    } catch (err) {
        showToast(`Action failed: ${err.message}`, "error");
    } finally {
        if (btn) {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    }
}


// =============================================================================
// 7B. DUAL RUNTIME & KUBERNETES TOPOLOGY
// =============================================================================
async function fetchRuntimeInfo() {
    try {
        const res = await fetch('/api/runtime');
        if (res.ok) {
            const data = await res.json();
            currentRuntime = data.runtime || "Docker";

            const badge = document.getElementById("runtime-mode-badge");
            const icon = document.getElementById("runtime-mode-icon");
            const text = document.getElementById("runtime-mode-text");
            const topoSec = document.getElementById("k8s-topology-section");
            const topoBadge = document.getElementById("k8s-topology-badge");
            const sidebarNodeName = document.querySelector(".node-name");

            if (badge && text) {
                if (data.docker_available && data.kubernetes_available) {
                    text.innerText = `Runtime: ${currentRuntime} (Dual Active)`;
                } else {
                    text.innerText = `Runtime: ${currentRuntime}`;
                }

                if (currentRuntime === "Kubernetes") {
                    badge.className = "runtime-mode-badge runtime-k8s";
                    if (icon) icon.className = "fa-solid fa-dharmachakra";
                    if (sidebarNodeName) sidebarNodeName.innerText = "k8s-cluster";
                } else {
                    badge.className = "runtime-mode-badge";
                    if (icon) icon.className = "fa-brands fa-docker";
                    if (sidebarNodeName) sidebarNodeName.innerText = "docker-desktop";
                }
            }

            // Both monitoring sources remain available independently without hiding each other
            if (topoSec) {
                if (data.kubernetes_available) {
                    topoSec.style.display = "block";
                    if (topoBadge) {
                        topoBadge.className = "status-badge k8s-badge";
                        topoBadge.innerText = "Kubernetes API Active";
                    }
                } else {
                    if (topoBadge) {
                        topoBadge.className = "status-badge stopped";
                        topoBadge.innerText = "Kubernetes API Offline";
                    }
                    if (currentRuntime === "Kubernetes") {
                        topoSec.style.display = "block";
                    }
                }
            }
        }
    } catch (err) {
        console.warn("Failed to fetch runtime mode:", err);
    }
}

async function fetchK8sTopology() {
    const depCountEl = document.getElementById("k8s-deployments-count");
    const svcCountEl = document.getElementById("k8s-services-count");
    const podCountEl = document.getElementById("k8s-pods-count");
    const depTbody = document.getElementById("k8s-deployments-tbody");
    const svcTbody = document.getElementById("k8s-services-tbody");
    const podTbody = document.getElementById("k8s-pods-tbody");

    try {
        const res = await fetch('/api/workloads');
        if (!res.ok) {
            const errText = `HTTP ${res.status}: ${res.statusText || 'Failed to load topology'}`;
            if (depTbody) depTbody.innerHTML = `<tr><td colspan="5" class="loading-state" style="color: #ef4444;"><i class="fa-solid fa-triangle-exclamation"></i> Error loading deployments (${escapeHtml(errText)})</td></tr>`;
            if (svcTbody) svcTbody.innerHTML = `<tr><td colspan="4" class="loading-state" style="color: #ef4444;"><i class="fa-solid fa-triangle-exclamation"></i> Error loading services (${escapeHtml(errText)})</td></tr>`;
            if (podTbody) podTbody.innerHTML = `<tr><td colspan="5" class="loading-state" style="color: #ef4444;"><i class="fa-solid fa-triangle-exclamation"></i> Error loading pods (${escapeHtml(errText)})</td></tr>`;
            return;
        }

        const data = await res.json();
        const deployments = data.deployments || [];
        const services = data.services || [];
        const pods = data.pods || [];

        if (depCountEl) depCountEl.innerText = `${deployments.length} Deployment${deployments.length === 1 ? '' : 's'}`;
        if (svcCountEl) svcCountEl.innerText = `${services.length} Service${services.length === 1 ? '' : 's'}`;
        if (podCountEl) podCountEl.innerText = `${pods.length} Pod${pods.length === 1 ? '' : 's'}`;

        if (depTbody) {
            if (deployments.length === 0) {
                depTbody.innerHTML = `<tr><td colspan="5" class="loading-state"><i class="fa-solid fa-circle-info"></i> No active deployments</td></tr>`;
            } else {
                depTbody.innerHTML = deployments.map(d => `
                    <tr>
                        <td><strong>${escapeHtml(d.name)}</strong></td>
                        <td>${d.desired_replicas !== undefined ? d.desired_replicas : 0}</td>
                        <td>${d.current_replicas !== undefined ? d.current_replicas : 0}</td>
                        <td><span class="badge-status ${(d.ready_replicas || 0) >= (d.desired_replicas || 1) ? 'running' : 'stopped'}">${d.ready_replicas || 0}</span></td>
                        <td>${d.available_replicas !== undefined ? d.available_replicas : 0}</td>
                    </tr>
                `).join('');
            }
        }

        if (svcTbody) {
            if (services.length === 0) {
                svcTbody.innerHTML = `<tr><td colspan="4" class="loading-state"><i class="fa-solid fa-circle-info"></i> No services found</td></tr>`;
            } else {
                svcTbody.innerHTML = services.map(s => `
                    <tr>
                        <td><strong>${escapeHtml(s.name)}</strong></td>
                        <td>${escapeHtml(s.type || 'ClusterIP')}</td>
                        <td>${escapeHtml(s.cluster_ip || 'None')}</td>
                        <td><code>${escapeHtml(s.ports || 'N/A')}</code></td>
                    </tr>
                `).join('');
            }
        }

        if (podTbody) {
            if (pods.length === 0) {
                podTbody.innerHTML = `<tr><td colspan="5" class="loading-state"><i class="fa-solid fa-circle-info"></i> No pods found</td></tr>`;
            } else {
                podTbody.innerHTML = pods.map(p => {
                    const statusClass = (p.status || '').toLowerCase() === 'running' ? 'running' : 'stopped';
                    return `
                        <tr>
                            <td><strong>${escapeHtml(p.name)}</strong></td>
                            <td>${escapeHtml(p.ready || '1/1')}</td>
                            <td><span class="restarts-pill ${(p.restart_count || 0) > 0 ? 'restarts-warn' : ''}">${p.restart_count || 0}</span></td>
                            <td><span class="badge-status ${statusClass}"><span class="blink-dot"></span>${escapeHtml(p.status || p.phase || 'Unknown')}</span></td>
                            <td><code>${escapeHtml(p.pod_ip || p.node_name || 'N/A')}</code></td>
                        </tr>
                    `;
                }).join('');
            }
        }
    } catch (err) {
        console.warn("Failed to fetch K8s topology:", err);
        if (depTbody) depTbody.innerHTML = `<tr><td colspan="5" class="loading-state" style="color: #ef4444;"><i class="fa-solid fa-triangle-exclamation"></i> Failed to connect: ${escapeHtml(err.message)}</td></tr>`;
        if (svcTbody) svcTbody.innerHTML = `<tr><td colspan="4" class="loading-state" style="color: #ef4444;"><i class="fa-solid fa-triangle-exclamation"></i> Failed to connect: ${escapeHtml(err.message)}</td></tr>`;
        if (podTbody) podTbody.innerHTML = `<tr><td colspan="5" class="loading-state" style="color: #ef4444;"><i class="fa-solid fa-triangle-exclamation"></i> Failed to connect: ${escapeHtml(err.message)}</td></tr>`;
    }
}


// =============================================================================
// 8. LOAD SIDEBAR CONTAINERS & OVERVIEW TABLE WITH HEALTH & ACTIONS
// =============================================================================
async function fetchContainersList() {
    try {
        const response = await fetch('/api/containers');
        
        if (!response.ok) {
            if (response.status === 503) {
                if (currentRuntime !== "Kubernetes") {
                    showDockerOfflineOverlay();
                }
                return;
            }
            throw new Error(`Response failed with status: ${response.status}`);
        }
        
        const containers = await response.json();
        hideDockerOfflineOverlay();
        
        const totalCount = containers.length;
        const runningCount = containers.filter(c => c.status === 'running').length;
        const stoppedCount = totalCount - runningCount;
        
        if (runningCountBadge) runningCountBadge.innerText = `Running: ${runningCount}`;
        if (totalContainersValEl) totalContainersValEl.innerText = totalCount;
        if (runningContainersCardVal) runningContainersCardVal.innerText = runningCount;

        const sidebarRunningCount = document.getElementById("sidebar-running-count");
        const sidebarStoppedCount = document.getElementById("sidebar-stopped-count");
        if (sidebarRunningCount) sidebarRunningCount.innerText = runningCount;
        if (sidebarStoppedCount) sidebarStoppedCount.innerText = stoppedCount;

        // A. Sidebar List
        if (containers.length === 0) {
            sidebarContainerList.innerHTML = `
                <li class="container-list-empty">
                    <i class="fa-solid fa-circle-info"></i> No containers found
                </li>
            `;
        } else {
            let sidebarHtml = '';
            containers.forEach(c => {
                const isActive = selectedContainerId === c.id ? 'class="active"' : '';
                let dotClass = 'status-dot-red';
                if (c.status === 'running') {
                    dotClass = 'status-dot-green';
                } else if (c.status === 'restarting' || c.status === 'paused' || c.status === 'created') {
                    dotClass = 'status-dot-yellow';
                }

                sidebarHtml += `
                    <li id="sidebar-c-${c.id}" ${isActive}>
                        <a href="#" onclick="selectContainer('${c.id}')" title="Status: ${c.status} | Restarts: ${c.restart_count || 0}">
                            <span class="sidebar-status-dot ${dotClass}"></span>
                            <span>${c.name}</span>
                        </a>
                    </li>
                `;
            });
            sidebarContainerList.innerHTML = sidebarHtml;
        }

        // B. Overview Table Body
        if (selectedContainerId === null && overviewContainerTableBody) {
            if (containers.length === 0) {
                overviewContainerTableBody.innerHTML = `
                    <tr>
                        <td colspan="7" class="loading-state">
                            <i class="fa-solid fa-circle-question"></i> No Docker containers detected on Desktop Engine.
                        </td>
                    </tr>
                `;
            } else {
                let tableHtml = '';
                containers.forEach(c => {
                    const statusClass = c.status === 'running' ? 'running' : 'stopped';
                    const restarts = c.restart_count || 0;
                    
                    // Restarts pill style
                    let restartsClass = "restarts-pill";
                    if (restarts >= 3) restartsClass += " restarts-crit";
                    else if (restarts > 0) restartsClass += " restarts-warn";

                    // Health condition evaluation
                    let healthClass = "health-normal";
                    let healthText = "NORMAL";
                    if (c.status !== "running" || restarts >= 3) {
                        healthClass = "health-critical";
                        healthText = "CRITICAL";
                    } else if (restarts > 0) {
                        healthClass = "health-warning";
                        healthText = "WARNING";
                    }

                    // Start/Stop action toggle button
                    let toggleActionBtn = '';
                    if (c.status === 'running') {
                        toggleActionBtn = `
                            <button class="btn-table-act btn-act-stop" onclick="containerAction('${c.id}', 'stop', event)" title="Stop Container">
                                <i class="fa-solid fa-stop"></i> Stop
                            </button>
                        `;
                    } else {
                        toggleActionBtn = `
                            <button class="btn-table-act btn-act-start" onclick="containerAction('${c.id}', 'start', event)" title="Start Container">
                                <i class="fa-solid fa-play"></i> Start
                            </button>
                        `;
                    }

                    tableHtml += `
                        <tr id="row-c-${c.id}">
                            <td style="font-family: monospace; color: var(--accent-cpu); font-weight: 600;">${c.id}</td>
                            <td class="container-name">${c.name}</td>
                            <td><span class="image-name">${c.image}</span></td>
                            <td><span class="${restartsClass}">${restarts}</span></td>
                            <td>
                                <span class="badge-status ${statusClass}">
                                    <span class="blink-dot"></span>
                                    ${c.status}
                                </span>
                            </td>
                            <td>
                                <span class="health-badge ${healthClass}">
                                    <i class="fa-solid fa-circle"></i> ${healthText}
                                </span>
                            </td>
                            <td>
                                <div class="btn-action-group">
                                    <button class="btn-table-act btn-act-inspect" onclick="selectContainer('${c.id}')" title="Inspect Metrics">
                                        <i class="fa-solid fa-chart-line"></i> Inspect
                                    </button>
                                    <button class="btn-table-act btn-act-restart" onclick="containerAction('${c.id}', 'restart', event)" title="Restart Container">
                                        <i class="fa-solid fa-arrows-rotate"></i> Restart
                                    </button>
                                    ${toggleActionBtn}
                                </div>
                            </td>
                        </tr>
                    `;
                });
                overviewContainerTableBody.innerHTML = tableHtml;
            }
        }
        
    } catch (err) {
        console.error("Failed to retrieve container list:", err);
        if (currentRuntime !== "Kubernetes") {
            showDockerOfflineOverlay();
        }
    }
}


// =============================================================================
// 9. SELECT A CONTAINER TO MONITOR (DETAIL VIEW)
// =============================================================================
function selectContainer(containerId) {
    if (!containerId) return;
    
    selectedContainerId = containerId;
    
    if (containerCpuChart) {
        containerCpuChart.data.labels = [];
        containerCpuChart.data.datasets[0].data = [];
        containerCpuChart.update();
    }
    
    if (containerMemoryChart) {
        containerMemoryChart.data.labels = [];
        containerMemoryChart.data.datasets[0].data = [];
        containerMemoryChart.update();
    }

    if (navOverviewBtn) navOverviewBtn.classList.remove("active");
    if (overviewWorkspace) overviewWorkspace.classList.remove("active");
    if (containerDetailWorkspace) containerDetailWorkspace.classList.add("active");
    
    const sidebarItems = sidebarContainerList.querySelectorAll("li");
    sidebarItems.forEach(li => li.classList.remove("active"));
    const activeSidebarLi = document.getElementById(`sidebar-c-${containerId}`);
    if (activeSidebarLi) activeSidebarLi.classList.add("active");

    performPollTick(true);
}


// =============================================================================
// 10. RETURN TO OVERVIEW DASHBOARD
// =============================================================================
function backToOverview() {
    selectedContainerId = null;
    
    if (navOverviewBtn) navOverviewBtn.classList.add("active");
    if (containerDetailWorkspace) containerDetailWorkspace.classList.remove("active");
    if (overviewWorkspace) overviewWorkspace.classList.add("active");
    
    const sidebarItems = sidebarContainerList.querySelectorAll("li");
    sidebarItems.forEach(li => li.classList.remove("active"));

    if (breadcrumbSec) breadcrumbSec.innerText = "Infrastructure";
    if (breadcrumbActive) breadcrumbActive.innerText = "Cluster Overview";

    performPollTick(true);
}


// =============================================================================
// 11. UPDATE CONTAINER DETAILS VIEW
// =============================================================================
function updateContainerDetails(stats) {
    if (detailContainerName) detailContainerName.innerText = stats.name;
    if (detailContainerImage) detailContainerImage.innerText = stats.image || "unknown";
    if (detailContainerStatusText) detailContainerStatusText.innerText = stats.status;
    
    if (detailContainerStatusBadge) {
        detailContainerStatusBadge.className = stats.status === "running" ? "badge-status running" : "badge-status stopped";
    }

    if (detailContainerRestarts) {
        detailContainerRestarts.innerText = `Restarts: ${stats.restart_count || 0}`;
    }

    // Detail Action Buttons
    if (detailActionsGroup) {
        const isRunning = stats.status === "running";
        detailActionsGroup.innerHTML = `
            <button class="btn-table-act btn-act-restart" onclick="containerAction('${stats.id}', 'restart')">
                <i class="fa-solid fa-arrows-rotate"></i> Restart Container
            </button>
            <button class="btn-table-act ${isRunning ? 'btn-act-stop' : 'btn-act-start'}" onclick="containerAction('${stats.id}', '${isRunning ? 'stop' : 'start'}')">
                <i class="fa-solid ${isRunning ? 'fa-stop' : 'fa-play'}"></i> ${isRunning ? 'Stop' : 'Start'}
            </button>
        `;
    }

    // Metric values
    if (detailCpuVal) detailCpuVal.innerText = `${stats.cpu_percentage.toFixed(1)}%`;
    if (detailCpuBar) detailCpuBar.style.width = `${Math.min(100, stats.cpu_percentage)}%`;

    if (detailRamVal) detailRamVal.innerText = `${stats.memory_used_mb} MB / ${stats.memory_limit_mb} MB`;
    if (detailRamBar) detailRamBar.style.width = `${Math.min(100, stats.memory_percentage)}%`;
    if (detailRamPct) detailRamPct.innerText = `Usage Percentage: ${stats.memory_percentage.toFixed(1)}%`;

    if (detailNetworkVal) detailNetworkVal.innerText = stats.network_io;
    if (detailUptimeVal) detailUptimeVal.innerText = stats.uptime;

    if (breadcrumbSec) breadcrumbSec.innerText = "Containers";
    if (breadcrumbActive) breadcrumbActive.innerText = stats.name;

    const nowTimestamp = stats.timestamp;

    if (containerCpuChart) {
        containerCpuChart.data.labels.push(nowTimestamp);
        containerCpuChart.data.datasets[0].data.push(stats.cpu_percentage);
        if (containerCpuChart.data.labels.length > 25) {
            containerCpuChart.data.labels.shift();
            containerCpuChart.data.datasets[0].data.shift();
        }
        containerCpuChart.update();
    }

    if (containerMemoryChart) {
        containerMemoryChart.data.labels.push(nowTimestamp);
        containerMemoryChart.data.datasets[0].data.push(stats.memory_used_mb);
        if (containerMemoryChart.data.labels.length > 25) {
            containerMemoryChart.data.labels.shift();
            containerMemoryChart.data.datasets[0].data.shift();
        }
        containerMemoryChart.options.scales.y.max = stats.memory_limit_mb > 0 ? stats.memory_limit_mb : 512;
        containerMemoryChart.update();
    }
}


// =============================================================================
// 12. GENERAL POLL TICK EXECUTION ROUTINE
// =============================================================================
async function performPollTick(isInitialLoad = false) {
    await fetchRuntimeInfo();
    await fetchContainersList();
    fetchK8sTopology();
    
    if (currentRuntime !== "Kubernetes" && dockerOfflineOverlay && dockerOfflineOverlay.classList.contains("active")) {
        return;
    }
    
    try {
        // 1. Fetch Intelligence & Event Log
        const intelRes = await fetch('/api/intelligence');
        if (intelRes.ok) {
            const intelData = await intelRes.json();
            updateIntelligenceUI(intelData);
        }

        fetchEvents();

        // 2. Fetch Metrics (Overview or Detail)
        if (selectedContainerId === null) {
            const response = await fetch('/api/system-metrics');
            if (response.ok) {
                const data = await response.json();
                updateHostDashboard(data, isInitialLoad);
            }
            fetchWorkloadDistribution();
        } else {
            const response = await fetch(`/api/container/${selectedContainerId}`);
            if (!response.ok) {
                if (response.status === 503) {
                    showDockerOfflineOverlay();
                    return;
                }
                throw new Error(`Failed to fetch stats: ${response.status}`);
            }
            const stats = await response.json();
            if (stats.success === false) {
                backToOverview();
                return;
            }
            updateContainerDetails(stats);
        }
    } catch (err) {
        console.error("Poll tick error:", err);
    }
}


// =============================================================================
// 13. DOCKER OFFLINE WARNING MODAL
// =============================================================================
function showDockerOfflineOverlay() {
    if (dockerOfflineOverlay && !dockerOfflineOverlay.classList.contains("active")) {
        dockerOfflineOverlay.classList.add("active");
    }
}

function hideDockerOfflineOverlay() {
    if (dockerOfflineOverlay && dockerOfflineOverlay.classList.contains("active")) {
        dockerOfflineOverlay.classList.remove("active");
    }
}


// =============================================================================
// 14. POLLER SCHEDULING
// =============================================================================
function restartPollingTimer() {
    if (pollIntervalId) clearInterval(pollIntervalId);
    pollIntervalId = setInterval(() => {
        performPollTick(false);
    }, pollIntervalTime);
}


// =============================================================================
// 15. THRESHOLD CONFIGURATION MODAL HANDLERS
// =============================================================================
async function openConfigModal() {
    if (!configModal) return;
    try {
        const res = await fetch('/api/config');
        if (res.ok) {
            const data = await res.json();
            const cfg = data.config || {};
            document.getElementById("cfg-cpu-warn").value = cfg.cpu_warning || 70;
            document.getElementById("cfg-cpu-crit").value = cfg.cpu_critical || 85;
            document.getElementById("cfg-ram-warn").value = cfg.memory_warning || 75;
            document.getElementById("cfg-ram-crit").value = cfg.memory_critical || 90;
            document.getElementById("cfg-target-cpu").value = cfg.target_cpu_utilization || 70;
            document.getElementById("cfg-window-samples").value = cfg.window_samples || 6;
        }
    } catch (err) {
        console.error("Failed to load thresholds:", err);
    }
    configModal.classList.add("active");
}

function closeConfigModal() {
    if (configModal) configModal.classList.remove("active");
}

if (formConfig) {
    formConfig.addEventListener("submit", async (e) => {
        e.preventDefault();
        const payload = {
            cpu_warning: parseFloat(document.getElementById("cfg-cpu-warn").value),
            cpu_critical: parseFloat(document.getElementById("cfg-cpu-crit").value),
            memory_warning: parseFloat(document.getElementById("cfg-ram-warn").value),
            memory_critical: parseFloat(document.getElementById("cfg-ram-crit").value),
            target_cpu_utilization: parseFloat(document.getElementById("cfg-target-cpu").value),
            window_samples: parseInt(document.getElementById("cfg-window-samples").value)
        };

        try {
            const res = await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const result = await res.json();
            if (res.ok) {
                showToast("Operational thresholds updated successfully!", "success");
                closeConfigModal();
                performPollTick(false);
            } else {
                showToast(result.error || "Failed to update configuration", "error");
            }
        } catch (err) {
            showToast(`Update error: ${err.message}`, "error");
        }
    });
}


// =============================================================================
// 16. KUBERNETES SCALING MODAL HANDLERS
// =============================================================================
function updateK8sScaleCmdDisplay(target) {
    if (k8sCmdDisplay) {
        const depName = cachedIntelligence?.k8s_info?.name || 'dockpulse-deployment';
        k8sCmdDisplay.innerText = `kubectl scale deployment ${depName} --replicas=${target}`;
    }
}

async function openK8sModal() {
    if (!k8sScaleModal) return;
    const statusBox = document.getElementById("k8s-scale-status");
    if (statusBox) {
        statusBox.style.display = "none";
        statusBox.className = "k8s-scale-status";
        statusBox.innerHTML = "";
    }

    try {
        const res = await fetch('/api/k8s/scale');
        if (res.ok) {
            const data = await res.json();
            const deployment = data.deployment || {};
            const currentReps = deployment.replicas || 1;
            if (k8sModalCurrent) k8sModalCurrent.innerText = currentReps;
            
            // Set target from cached scaling recommendation if available, or default
            const recRep = cachedIntelligence?.scaling_decision?.recommended_replicas || (currentReps === 1 ? 2 : 1);
            if (k8sModalTarget) k8sModalTarget.innerText = recRep;
            updateK8sScaleCmdDisplay(recRep);
        }
    } catch (err) {
        console.error("Failed to load K8s info:", err);
    }
    k8sScaleModal.classList.add("active");
}

function closeK8sModal() {
    if (k8sScaleModal) k8sScaleModal.classList.remove("active");
}

// Stepper Inc/Dec listeners
const btnScaleInc = document.getElementById("btn-scale-inc");
const btnScaleDec = document.getElementById("btn-scale-dec");

if (btnScaleInc) {
    btnScaleInc.addEventListener("click", () => {
        let curr = parseInt(k8sModalTarget.innerText || "1");
        if (curr < 10) {
            curr += 1;
            k8sModalTarget.innerText = curr;
            updateK8sScaleCmdDisplay(curr);
        }
    });
}

if (btnScaleDec) {
    btnScaleDec.addEventListener("click", () => {
        let curr = parseInt(k8sModalTarget.innerText || "2");
        if (curr > 1) {
            curr -= 1;
            k8sModalTarget.innerText = curr;
            updateK8sScaleCmdDisplay(curr);
        }
    });
}

if (btnApplyK8sScale) {
    btnApplyK8sScale.addEventListener("click", async () => {
        const targetReplicas = parseInt(k8sModalTarget.innerText || "2");
        const statusBox = document.getElementById("k8s-scale-status");

        btnApplyK8sScale.disabled = true;
        btnApplyK8sScale.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Reconciling Cluster...`;

        if (statusBox) {
            statusBox.style.display = "block";
            statusBox.className = "k8s-scale-status status-loading";
            statusBox.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Dispatching scale to Kubernetes API and waiting for Pod readiness...`;
        }

        try {
            const res = await fetch('/api/k8s/scale', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target_replicas: targetReplicas, apply: true })
            });
            const result = await res.json();

            if (res.ok && result.success) {
                const msg = result.message || `Scaled to ${targetReplicas} replicas.`;
                if (statusBox) {
                    statusBox.className = "k8s-scale-status status-success";
                    statusBox.innerHTML = `<i class="fa-solid fa-circle-check"></i> ${escapeHtml(msg)}`;
                }
                showToast(msg, "success");
                await performPollTick(false);
                setTimeout(() => {
                    closeK8sModal();
                }, 1600);
            } else {
                const errMsg = result.error || result.message || "Kubernetes scale failed";
                if (statusBox) {
                    statusBox.className = "k8s-scale-status status-error";
                    statusBox.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> ${escapeHtml(errMsg)}`;
                }
                showToast(errMsg, "error");
            }
        } catch (err) {
            if (statusBox) {
                statusBox.className = "k8s-scale-status status-error";
                statusBox.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> Network error: ${escapeHtml(err.message)}`;
            }
            showToast(`Scale error: ${err.message}`, "error");
        } finally {
            btnApplyK8sScale.disabled = false;
            btnApplyK8sScale.innerHTML = `<i class="fa-solid fa-cloud-arrow-up"></i> Apply Scaling Plan`;
        }
    });
}


// =============================================================================
// 17. APPLICATION INITIALIZATION ON DOM READY
// =============================================================================
document.addEventListener("DOMContentLoaded", () => {
    startLiveClock();
    
    // View navigation buttons
    if (navOverviewBtn) {
        navOverviewBtn.addEventListener("click", (e) => {
            e.preventDefault();
            backToOverview();
        });
    }
    if (logoBackHome) logoBackHome.addEventListener("click", backToOverview);
    if (btnDetailBack) btnDetailBack.addEventListener("click", backToOverview);
    
    if (dockerRetryBtn) {
        dockerRetryBtn.addEventListener("click", () => {
            performPollTick(true);
        });
    }

    // Modal triggers
    if (btnOpenConfigModal) btnOpenConfigModal.addEventListener("click", openConfigModal);
    if (btnSidebarThresholds) {
        btnSidebarThresholds.addEventListener("click", (e) => {
            e.preventDefault();
            openConfigModal();
        });
    }
    if (btnCloseConfigModal) btnCloseConfigModal.addEventListener("click", closeConfigModal);
    if (btnCancelConfig) btnCancelConfig.addEventListener("click", closeConfigModal);

    if (btnOpenK8sModal) btnOpenK8sModal.addEventListener("click", openK8sModal);
    if (btnSidebarK8s) {
        btnSidebarK8s.addEventListener("click", (e) => {
            e.preventDefault();
            openK8sModal();
        });
    }
    if (btnCloseK8sModal) btnCloseK8sModal.addEventListener("click", closeK8sModal);
    if (btnCancelK8s) btnCancelK8s.addEventListener("click", closeK8sModal);

    // Event log filter buttons
    if (eventsFilterGroup) {
        const filterBtns = eventsFilterGroup.querySelectorAll(".filter-btn");
        filterBtns.forEach(btn => {
            btn.addEventListener("click", () => {
                filterBtns.forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                activeEventSeverity = btn.getAttribute("data-severity") || "ALL";
                fetchEvents();
            });
        });
    }

    // Initialize Chart contexts
    initializeCharts();
    
    // Export container selection and action handlers to global window scope for inline onclicks
    window.selectContainer = selectContainer;
    window.containerAction = containerAction;

    // Trigger initial poll and start recurring loop
    performPollTick(true);
    restartPollingTimer();
    
    // Poll interval dropdown changes
    if (pollIntervalSelector) {
        pollIntervalSelector.addEventListener("change", (e) => {
            pollIntervalTime = parseInt(e.target.value);
            restartPollingTimer();
        });
    }
});
