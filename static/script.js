/**
 * DockPulse - Frontend Application Controller
 * Handles real-time system/container metric polling, dynamic Chart.js graphing,
 * Docker daemon availability overlay, sidebar listings, and responsive page views.
 */

// Global Application State
let pollIntervalTime = 2000; // Defaults to 2 seconds
let pollIntervalId = null;
let selectedContainerId = null; // Tracks active container details view (null = Overview Mode)

// Host/Cluster Overview Chart Instances
let hostResourceChart = null;
let hostDiskChart = null;

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
const ramValueEl = document.getElementById("ram-value");
const ramBarEl = document.getElementById("ram-bar");
const ramSubEl = document.getElementById("ram-sub");
const diskValueEl = document.getElementById("disk-value");
const diskBarEl = document.getElementById("disk-bar");
const diskSubEl = document.getElementById("disk-sub");
const procValueEl = document.getElementById("proc-value");
const uptimeValueEl = document.getElementById("uptime-value");
const runningCountBadge = document.getElementById("running-count-badge");
const runningContainersCardVal = document.getElementById("running-containers-card-val");
const overviewContainerTableBody = document.getElementById("overview-container-table-body");

// Container Details Cards DOM
const detailContainerName = document.getElementById("detail-container-name");
const detailContainerImage = document.getElementById("detail-container-image");
const detailContainerStatusBadge = document.getElementById("detail-container-status-badge");
const detailContainerStatusText = document.getElementById("detail-container-status-text");

const detailCpuVal = document.getElementById("detail-cpu-val");
const detailCpuBar = document.getElementById("detail-cpu-bar");
const detailRamVal = document.getElementById("detail-ram-val");
const detailRamBar = document.getElementById("detail-ram-bar");
const detailRamPct = document.getElementById("detail-ram-pct");
const detailNetworkVal = document.getElementById("detail-network-val");
const detailUptimeVal = document.getElementById("detail-uptime-val");


// 1. Initialize Real-Time Clock in Top Header
function startLiveClock() {
    setInterval(() => {
        const now = new Date();
        const timeString = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
        timeDisplay.innerHTML = `<i class="fa-regular fa-clock"></i> ${timeString}`;
    }, 1000);
}


// 2. Initialize Charts (Host & Containers targets)
function initializeCharts() {
    // ==========================================
    // A. HOST OVERVIEW CHARTS
    // ==========================================
    const hostLineCtx = document.getElementById("resourceLineChart").getContext("2d");
    const cpuGrad = hostLineCtx.createLinearGradient(0, 0, 0, 250);
    cpuGrad.addColorStop(0, "rgba(0, 210, 255, 0.25)");
    cpuGrad.addColorStop(1, "rgba(0, 210, 255, 0.0)");
    
    const ramGrad = hostLineCtx.createLinearGradient(0, 0, 0, 250);
    ramGrad.addColorStop(0, "rgba(255, 87, 127, 0.25)");
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
                    borderWidth: 2,
                    pointRadius: 1,
                    fill: true,
                    tension: 0.4,
                    data: []
                },
                {
                    label: 'Host RAM (%)',
                    borderColor: '#ff577f',
                    backgroundColor: ramGrad,
                    borderWidth: 2,
                    pointRadius: 1,
                    fill: true,
                    tension: 0.4,
                    data: []
                }
            ]
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

    const hostDiskCtx = document.getElementById("diskDoughnutChart").getContext("2d");
    hostDiskChart = new Chart(hostDiskCtx, {
        type: 'doughnut',
        data: {
            labels: ['Used (GB)', 'Free (GB)'],
            datasets: [{
                data: [0, 100],
                backgroundColor: ['#ffa000', 'rgba(255, 255, 255, 0.04)'],
                borderColor: '#181b1f',
                borderWidth: 3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '72%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#9fa2a5', boxWidth: 10, font: { size: 10, family: 'Inter' } }
                }
            }
        }
    });

    // ==========================================
    // B. CONTAINER-SPECIFIC LIVE CHARTS
    // ==========================================
    // Container CPU Usage History
    const containerCpuCtx = document.getElementById("containerCpuChart").getContext("2d");
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

    // Container Memory Usage History (MB)
    const containerMemoryCtx = document.getElementById("containerMemoryChart").getContext("2d");
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


// 3. Update Host Overview Dashboard UI
function updateHostDashboard(data, isInitialLoad = false) {
    // Update metric cards
    cpuValueEl.innerText = `${data.latest.cpu_percentage.toFixed(1)}%`;
    cpuBarEl.style.width = `${data.latest.cpu_percentage}%`;
    
    ramValueEl.innerText = `${data.latest.ram_percentage.toFixed(1)}%`;
    ramBarEl.style.width = `${data.latest.ram_percentage}%`;
    ramSubEl.innerText = `Used: ${data.latest.ram_used_gb} GB / ${data.latest.ram_total_gb} GB`;
    
    diskValueEl.innerText = `${data.latest.disk_percentage.toFixed(1)}%`;
    diskBarEl.style.width = `${data.latest.disk_percentage}%`;
    diskSubEl.innerText = `Available: ${data.latest.disk_free_gb} GB / ${data.latest.disk_total_gb} GB`;
    
    procValueEl.innerText = data.latest.processes_count;
    uptimeValueEl.innerText = data.latest.uptime;

    // Update Line Chart History
    if (isInitialLoad) {
        const labels = [];
        const cpuPoints = [];
        const ramPoints = [];
        data.history.forEach(point => {
            labels.push(point.timestamp);
            cpuPoints.push(point.cpu_percentage);
            ramPoints.push(point.ram_percentage);
        });
        hostResourceChart.data.labels = labels;
        hostResourceChart.data.datasets[0].data = cpuPoints;
        hostResourceChart.data.datasets[1].data = ramPoints;
        hostResourceChart.update();
    } else {
        hostResourceChart.data.labels.push(data.latest.timestamp);
        hostResourceChart.data.datasets[0].data.push(data.latest.cpu_percentage);
        hostResourceChart.data.datasets[1].data.push(data.latest.ram_percentage);
        
        if (hostResourceChart.data.labels.length > 20) {
            hostResourceChart.data.labels.shift();
            hostResourceChart.data.datasets[0].data.shift();
            hostResourceChart.data.datasets[1].data.shift();
        }
        hostResourceChart.update();
    }

    // Update Disk Doughnut
    hostDiskChart.data.datasets[0].data = [data.latest.disk_used_gb, data.latest.disk_free_gb];
    hostDiskChart.update();
}


// 4. Load Sidebar Dynamic Containers List
async function fetchContainersList() {
    try {
        const response = await fetch('/api/containers');
        
        // Handle Docker Offline gracefully
        if (!response.ok) {
            if (response.status === 503) {
                showDockerOfflineOverlay();
                return;
            }
            throw new Error(`Response failed with status: ${response.status}`);
        }
        
        const containers = await response.json();
        
        // Hide Docker offline overlay if it was visible
        hideDockerOfflineOverlay();
        
        // Calculate running vs stopped count from real container status fields
        const runningCount = containers.filter(c => c.status === 'running').length;
        const stoppedCount = containers.length - runningCount;
        
        // Update overview table badge and main summary card
        runningCountBadge.innerText = `Running: ${runningCount}`;
        runningContainersCardVal.innerText = runningCount;

        // Update the sidebar count indicator pills dynamically
        const sidebarRunningCount = document.getElementById("sidebar-running-count");
        const sidebarStoppedCount = document.getElementById("sidebar-stopped-count");
        if (sidebarRunningCount) sidebarRunningCount.innerText = runningCount;
        if (sidebarStoppedCount) sidebarStoppedCount.innerText = stoppedCount;

        // A. Build Monitored Containers Sidebar list
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
                
                // Docker container status-to-color indicator dot mapping:
                // Green = running
                // Red = exited or stopped
                // Yellow = restarting or paused or created
                let dotClass = 'status-dot-red';
                if (c.status === 'running') {
                    dotClass = 'status-dot-green';
                } else if (c.status === 'restarting' || c.status === 'paused' || c.status === 'created') {
                    dotClass = 'status-dot-yellow';
                } else {
                    dotClass = 'status-dot-red'; // exited, stopped, dead, etc.
                }

                sidebarHtml += `
                    <li id="sidebar-c-${c.id}" ${isActive}>
                        <a href="#" onclick="selectContainer('${c.id}')" title="Status: ${c.status}">
                            <span class="sidebar-status-dot ${dotClass}"></span>
                            <span>${c.name}</span>
                        </a>
                    </li>
                `;
            });
            sidebarContainerList.innerHTML = sidebarHtml;
        }

        // B. Build Overview Table body
        if (selectedContainerId === null) {
            if (containers.length === 0) {
                overviewContainerTableBody.innerHTML = `
                    <tr>
                        <td colspan="5" class="loading-state">
                            <i class="fa-solid fa-circle-question"></i> No Docker containers detected on Desktop Engine.
                        </td>
                    </tr>
                `;
            } else {
                let tableHtml = '';
                containers.forEach(c => {
                    const statusClass = c.status === 'running' ? 'running' : 'stopped';
                    tableHtml += `
                        <tr id="row-c-${c.id}">
                            <td style="font-family: monospace; color: var(--accent-cpu); font-weight: 600;">${c.id}</td>
                            <td class="container-name">${c.name}</td>
                            <td><span class="image-name">${c.image}</span></td>
                            <td>
                                <span class="badge-status ${statusClass}">
                                    <span class="blink-dot"></span>
                                    ${c.status}
                                </span>
                            </td>
                            <td>
                                <button class="btn-action btn-start" onclick="selectContainer('${c.id}')">
                                    <i class="fa-solid fa-magnifying-glass-chart"></i> Inspect metrics
                                </button>
                            </td>
                        </tr>
                    `;
                });
                overviewContainerTableBody.innerHTML = tableHtml;
            }
        }
        
    } catch (err) {
        console.error("Failed to retrieve active container list:", err);
        // Safely check offline state
        showDockerOfflineOverlay();
    }
}


// 5. Select a container to monitor (transitions view)
function selectContainer(containerId) {
    if (!containerId) return;
    
    // Set state
    selectedContainerId = containerId;
    
    // Reset container charts histories to prevent overlapping data
    containerCpuChart.data.labels = [];
    containerCpuChart.data.datasets[0].data = [];
    containerCpuChart.update();
    
    containerMemoryChart.data.labels = [];
    containerMemoryChart.data.datasets[0].data = [];
    containerMemoryChart.update();

    // visual toggles
    navOverviewBtn.classList.remove("active");
    overviewWorkspace.classList.remove("active");
    containerDetailWorkspace.classList.add("active");
    
    // Highlight sidebar entry
    const sidebarItems = sidebarContainerList.querySelectorAll("li");
    sidebarItems.forEach(li => li.classList.remove("active"));
    const activeSidebarLi = document.getElementById(`sidebar-c-${containerId}`);
    if (activeSidebarLi) {
        activeSidebarLi.classList.add("active");
    }

    // Trigger immediate poll update for container details
    performPollTick(true);
}


// 6. Return back to overview node dashboard
function backToOverview() {
    selectedContainerId = null;
    
    // UI selections
    navOverviewBtn.classList.add("active");
    containerDetailWorkspace.classList.remove("active");
    overviewWorkspace.classList.add("active");
    
    // Reset sidebar selection highlights
    const sidebarItems = sidebarContainerList.querySelectorAll("li");
    sidebarItems.forEach(li => li.classList.remove("active"));

    // Reset breadcrumbs
    breadcrumbSec.innerText = "Infrastructure";
    breadcrumbActive.innerText = "Cluster Overview";

    // Immediate tick refresh
    performPollTick(true);
}


// 7. Update Detailed Container View metrics
function updateContainerDetails(stats) {
    // Fill text components
    detailContainerName.innerText = stats.name;
    detailContainerImage.innerText = stats.image || "unknown";
    detailContainerStatusText.innerText = stats.status;
    
    // badge state
    if (stats.status === "running") {
        detailContainerStatusBadge.className = "badge-status running";
    } else {
        detailContainerStatusBadge.className = "badge-status stopped";
    }

    // Fill metric values
    detailCpuVal.innerText = `${stats.cpu_percentage.toFixed(1)}%`;
    detailCpuBar.style.width = `${stats.cpu_percentage}%`;

    detailRamVal.innerText = `${stats.memory_used_mb} MB / ${stats.memory_limit_mb} MB`;
    detailRamBar.style.width = `${stats.memory_percentage}%`;
    detailRamPct.innerText = `Usage Percentage: ${stats.memory_percentage.toFixed(1)}%`;

    detailNetworkVal.innerText = stats.network_io;
    detailUptimeVal.innerText = stats.uptime;

    // Update Breadcrumbs
    breadcrumbSec.innerText = "Containers";
    breadcrumbActive.innerText = stats.name;

    // Push coordinates to line charts
    const nowTimestamp = stats.timestamp;

    // CPU graph update
    containerCpuChart.data.labels.push(nowTimestamp);
    containerCpuChart.data.datasets[0].data.push(stats.cpu_percentage);
    if (containerCpuChart.data.labels.length > 20) {
        containerCpuChart.data.labels.shift();
        containerCpuChart.data.datasets[0].data.shift();
    }
    containerCpuChart.update();

    // Memory graph update
    containerMemoryChart.data.labels.push(nowTimestamp);
    containerMemoryChart.data.datasets[0].data.push(stats.memory_used_mb);
    if (containerMemoryChart.data.labels.length > 20) {
        containerMemoryChart.data.labels.shift();
        containerMemoryChart.data.datasets[0].data.shift();
    }
    // Update y-axis scale max dynamically based on limit
    containerMemoryChart.options.scales.y.max = stats.memory_limit_mb > 0 ? stats.memory_limit_mb : 512;
    containerMemoryChart.update();
}


// 8. General Poll Tick Execution Routine
async function performPollTick(isInitialLoad = false) {
    // 1. Always poll the running containers list to feed sidebar dynamically
    await fetchContainersList();
    
    // Exit early if Docker overlay is active (to prevent loop congestion)
    if (dockerOfflineOverlay.classList.contains("active")) {
        return;
    }
    
    try {
        if (selectedContainerId === null) {
            // A. Poll Host System stats
            const response = await fetch('/api/system-metrics');
            const data = await response.json();
            updateHostDashboard(data, isInitialLoad);
        } else {
            // B. Poll Selected Container stats
            const response = await fetch(`/api/container/${selectedContainerId}`);
            if (!response.ok) {
                if (response.status === 503) {
                    showDockerOfflineOverlay();
                    return;
                }
                throw new Error(`Failed to fetch stats: ${response.status}`);
            }
            const stats = await response.json();
            
            // Check if container was removed/stopped in background
            if (stats.success === false) {
                console.warn("Container not running, returning to overview...");
                backToOverview();
                return;
            }
            updateContainerDetails(stats);
        }
    } catch (err) {
        console.error("Failed to execute metrics polling tick:", err);
    }
}


// 9. Display offline warnings
function showDockerOfflineOverlay() {
    if (!dockerOfflineOverlay.classList.contains("active")) {
        dockerOfflineOverlay.classList.add("active");
    }
}

function hideDockerOfflineOverlay() {
    if (dockerOfflineOverlay.classList.contains("active")) {
        dockerOfflineOverlay.classList.remove("active");
    }
}


// 10. Poller Rescheduling Loop
function restartPollingTimer() {
    if (pollIntervalId) {
        clearInterval(pollIntervalId);
    }
    pollIntervalId = setInterval(() => {
        performPollTick(false);
    }, pollIntervalTime);
}


// 11. App Setup on DOM loaded
document.addEventListener("DOMContentLoaded", () => {
    // Start header clock
    startLiveClock();
    
    // Bind click events
    navOverviewBtn.addEventListener("click", (e) => {
        e.preventDefault();
        backToOverview();
    });
    
    logoBackHome.addEventListener("click", backToOverview);
    btnDetailBack.addEventListener("click", backToOverview);
    
    dockerRetryBtn.addEventListener("click", () => {
        performPollTick(true);
    });

    // Initialize Charts canvas context
    initializeCharts();
    
    // Bind click actions to window global context so inline actions in tables compile fine
    window.selectContainer = selectContainer;

    // Trigger initial seeding poller tick
    performPollTick(true);
    
    // Start loop poller
    restartPollingTimer();
    
    // Polling interval selector changes
    pollIntervalSelector.addEventListener("change", (e) => {
        pollIntervalTime = parseInt(e.target.value);
        restartPollingTimer();
    });
});
