# DockPulse | Real-Time Docker Container Monitoring Platform

DockPulse is a premium, lightweight, real-time Docker container monitoring dashboard connected directly to the local Docker Desktop engine on your machine. Built on a Flask backend, it uses the official Python Docker SDK to retrieve actual container resource footprints, and visualizes them on a modern dark-themed frontend with Chart.js.

If Docker Desktop is offline, DockPulse warns the user gracefully via a glassmorphic warning overlay and resumes live-updates automatically once the Docker daemon is booted up.

---

## 🏗️ Architectural Design & Metrics Flow

```
                      +------------------------------------------+
                      |        Local Docker Desktop Engine       |
                      |    [Containers, Memory, CPU, Net I/O]    |
                      +--------------------+---------------------+
                                           |
                                 (npipe / docker.sock)
                                           v
                      +--------------------+---------------------+
                      |      DockPulse Flask Backend App         |
                      |   - Port 5000                            |
                      |   - /api/containers (UI)                 |
                      |   - /metrics (Prometheus Exporter API)   |
                      +--------------------+---------------------+
                            |              |
                (HTTP Poll) |              | (Scrape Poll every 5s)
                            v              v
         +------------------+----+   +-----+---------------------+
         |   DockPulse UI        |   |    Prometheus TSDB        |
         |   - Port 5000         |   |    - Port 9090            |
         |   - Custom Observability| |    - /metrics target      |
         +-----------------------+   +-----+---------------------+
                                           |
                                           | (QL Queries / Pull)
                                           v
                                     +-----+---------------------+
                                     |    Grafana Dashboards     |
                                     |    - Port 3000                |
                                     |    - Pre-provisioned Panels   |
                                     +---------------------------+
```

### Key Highlights
1. **True Real-time SDK Integration**: No more simulated container metrics. DockPulse retrieves raw statistics directly from the Docker daemon socket/pipe, parsing metrics like delta CPU ratios, virtual ethernet network packages, and startup ISO dates.
2. **Self-Healing Connection Loop**: If DockPulse loses connection to Docker Desktop (or if the server is started while Docker is stopped), a prominent overlay warning is shown. The frontend runs a lightweight poll checking daemon status, automatically removing the block the moment Docker starts.
3. **Double Live Graphing**: When you select a container from the sidebar list, DockPulse resets the active graph contexts and plots isolated real-time lines plotting container CPU load (%) and memory usage (MB) side-by-side.
4. **Observability Integration**: DockPulse hosts a native `/metrics` exporter endpoint, exposing local host resources and real-time container metrics. Prometheus scrapes this data into a time-series database, and Grafana queries it to render historical graphs.

---

## 📊 Observability & Monitoring Ecosystem

### 1. Prometheus Scrape Configuration
Prometheus acts as the centralized time-series metrics collection and storage engine.
* **Scrape interval**: Configured to `5s` in `prometheus.yml` to match the real-time nature of container scaling.
* **Endpoint target**: Scrapes the `/metrics` endpoint exposed by the `dockpulse` Flask service inside the Docker Compose bridge network at `http://dockpulse:5000/metrics`.
* **Exported Metric Metrics**:
  * `dockpulse_host_cpu_percentage`: Current host CPU utilization.
  * `dockpulse_host_memory_percentage`: Current host virtual memory RAM usage.
  * `dockpulse_host_disk_percentage`: Host root disk utilization.
  * `dockpulse_containers_total`: Total registered container nodes (running + stopped).
  * `dockpulse_containers_running`: Count of active executing container nodes.
  * `dockpulse_container_cpu_percentage`: Real-time container CPU load (labeled by name/ID).
  * `dockpulse_container_memory_used_bytes`: Container RSS RAM allocation (cache subtracted).
  * `dockpulse_container_status`: State index (1 for running, 0 for stopped/exited).

### 2. Grafana Dashboard Provisioning
Grafana serves as the visualization and advanced analytics interface.
* **Automatic Datasource Setup**: Auto-provisions the local Prometheus container (`http://prometheus:9090`) as the default datasource.
* **Pre-configured Dashboards**: Auto-loads a custom DevOps dashboard containing CPU, RAM, and Disk Gauges, container lifecycle state timelines, and historical line graphs plotting individual container workloads over time.
* **Accessing the Stack**:
  * DockPulse Application: `http://localhost:5000`
  * Prometheus Dashboard: `http://localhost:9090`
  * Grafana Telemetry Panels: `http://localhost:3000` (Default credentials: `admin` / `admin`)

---

## 🛠️ File Structure

```
project/
│
├── app.py                # Python Flask server, SDK connector, stats parsers, REST APIs, metrics exporter
├── requirements.txt      # Python dependencies (Flask, psutil, docker, prometheus-client)
├── prometheus.yml        # Prometheus scrape configurations
├── static/
│   ├── style.css         # Outfitted dark mode styles, custom dynamic tables, and overlays
│   └── script.js         # Sidebar container updater, detail toggles, and dual Chart.js lines
├── templates/
│   └── index.html        # Main template featuring Overview vs Container detail workspaces
├── grafana/
│   └── provisioning/     # Auto-provisioned Grafana dashboards and Prometheus datasources
├── Dockerfile            # Container definition
├── docker-compose.yml    # Development stack (DockPulse + Prometheus + Grafana)
├── Jenkinsfile           # DevOps pipeline stages
├── k8s/
│   ├── deployment.yaml   # K8s Deployment descriptor
│   └── service.yaml      # K8s NodePort exposure Port 32000
└── README.md             # This document!
```

---

## 🚀 Setup & Execution Guide

### Local Execution (Prerequisites: Python 3.8+ & Docker Desktop Running)
1. **Ensure Docker Desktop is running**: Make sure the Docker engine is online on your machine.
2. **Setup virtual environment**:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Boot up Flask server**:
   ```bash
   python app.py
   ```
5. **Open Dashboard**: Go to **`http://localhost:5000`** in your browser.

### Docker Compose Execution (Full Observability Stack: DockPulse + Prometheus + Grafana)
1. **Ensure Docker Desktop is running**.
2. **Build and start all services in detached mode**:
   ```bash
   docker-compose up -d --build
   ```
3. **Verify the container stack statuses**:
   ```bash
   docker-compose ps
   ```
4. **Access the web interfaces**:
   * **DockPulse dashboard**: `http://localhost:5000`
   * **Prometheus API & status**: `http://localhost:9090`
   * **Grafana panels**: `http://localhost:3000` (Default credentials: username `admin` / password `admin`)

---

## 🎯 Viva & Technical Interview Cheat-Sheet

Be prepared to answer these containerization-specific questions during viva panels or engineering interviews:

### Q1: How does DockPulse calculate container CPU usage percentage from raw stats?
> **Answer:** Unlike host-wide CPU metrics, a container's CPU percentage is calculated by comparing changes in container-specific CPU ticks against total host system CPU ticks over a delta interval, scaled by the number of active CPU cores.
> The formula applied in `app.py` is:
> $$\text{CPU \%} = \frac{\Delta \text{ Container CPU Ticks}}{\Delta \text{ System CPU Ticks}} \times \text{Online CPUs} \times 100$$
> This matches the output generated by the native `docker stats` terminal command.

### Q2: How does the application connect to Docker Desktop on different Operating Systems?
> **Answer:** The Python Docker SDK wraps standard connection layers. By calling `docker.from_env()`, it checks environment flags and resolves connection sockets automatically:
> * **Windows**: Communicates over named pipes at `npipe:////./pipe/docker_engine`.
> * **Linux / macOS**: Connects to the standard Unix socket file at `unix://var/run/docker.sock`.

### Q3: Why does `app.py` subtract `cache` from the memory usage stats?
> **Answer:** In Linux cgroups, the memory stats reports `usage` which includes both resident memory (RSS) and active filesystem cache pages. If we report raw `usage`, the RAM reading will look artificially inflated because the OS caches files inside memory. Subtracting `cache` from `usage` yields the true active working set size, matching `docker stats`.

### Q4: How does DockPulse handle cases where Docker Desktop is offline?
> **Answer:** In `app.py`, connections to the daemon are wrapped in a try/except helper block. If the daemon ping fails, the API responds with a `503 Service Unavailable` status and a clear JSON error. The frontend (`script.js`) intercepts this response, halts graph polling to prevent thread locks, and displays a prominent warning overlay until the connection is restored.
