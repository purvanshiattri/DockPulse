# DockPulse 2.0 | Intelligent Container Observability & Workload Management Platform

DockPulse 2.0 is an intelligent container observability, anomaly detection, predictive analytics, and workload balancing platform. Directly interfaced with the local Docker Desktop engine via the official Python Docker SDK, DockPulse transforms passive metrics monitoring into an active operational lifecycle:

$$\textbf{MONITOR} \longrightarrow \textbf{DETECT} \longrightarrow \textbf{ANALYZE} \longrightarrow \textbf{RECOMMEND} \longrightarrow \textbf{ACT}$$

Designed for modern DevOps practices and realistic single-machine demonstrations on Windows laptops with Docker Desktop, DockPulse 2.0 requires **zero external cloud infrastructure** and adds **zero heavy dependencies**.

---

## 🌟 What Changed in DockPulse 2.0?

| Capability | DockPulse 1.0 (Baseline) | DockPulse 2.0 (Intelligent Platform) |
| :--- | :--- | :--- |
| **Telemetry Scope** | Passive host & container stats | Intelligent resource tracking + restart counts + crash-loop detection |
| **Anomaly Detection** | None (manual observation required) | Automated rolling-window detection (`NORMAL`, `WARNING`, `CRITICAL`) |
| **Trend & Forecasting** | None | 1st-order linear regression slope ($\%/min$) & time-to-breach estimation |
| **Workload Advisory** | None | Context-aware AI recommendations based on observed metrics |
| **Workload Balancing** | None | Kubernetes HPA replica scaling calculation (`SCALE UP`, `SCALE DOWN`, `KEEP`) |
| **Alert History** | None | Live in-memory ring buffer event stream with severity filters |
| **Threshold Tuning** | Hardcoded | Configurable via REST API and dynamic interactive UI modal |
| **Container Actions** | Inspect only | Full lifecycle actions: `start`, `stop`, `restart` with self-preservation safety |
| **Kubernetes Bridge** | Static YAML files | Manifest parser, dry-run `kubectl scale` generator, and manifest updater |

---

## 🏗️ Architectural Design & Telemetry Flow

```
                                    +------------------------------------------------+
                                    |          Local Docker Desktop Engine           |
                                    |     [Containers, Memory, CPU, Net I/O, cgroups] |
                                    +-----------------------+------------------------+
                                                            |
                                                (Named Pipe / docker.sock)
                                                            v
+-------------------------------------------------------------------------------------------------------------------+
|                                        DockPulse 2.0 Flask Backend Service                                        |
|                                                                                                                   |
|  [Background Host Collector]        [Container Stats Parser]        [Thread-safe History Ring Buffers]            |
|               |                                |                                   |                              |
|               +--------------------------------+-----------------------------------+                              |
|                                                |                                                                  |
|                                                v                                                                  |
|  +-------------------------------------------------------------------------------------------------------------+  |
|  |                                  DOCKPULSE 2.0 INTELLIGENCE ENGINE (intelligence.py)                        |  |
|  |                                                                                                             |  |
|  |  1. Anomaly Detector       --> Sustained CPU/RAM breaches, sudden spikes (+25%), crash loop checks          |  |
|  |  2. Trend Analyzer         --> Least-squares regression slope (m %/min), estimated breach forecast         |  |
|  |  3. Workload Scaler        --> Kubernetes HPA formula: ceil[current * (current_util / target_util)]         |  |
|  |  4. Recommendation Engine  --> Actionable operational directives derived from active telemetry rules        |  |
|  |  5. Event Log Manager      --> In-memory rolling ring buffer (deque) capturing timestamped alerts           |  |
|  |  6. Kubernetes Bridge      --> Deployment manifest parser, kubectl scale plan, and safe updater            |  |
|  +-------------------------------------------------------------------------------------------------------------+  |
|                                                |                                                                  |
|               +--------------------------------+--------------------------------+                                 |
|               |                                |                                |                                 |
|               v                                v                                v                                 |
|      /api/intelligence                   /api/events                     /api/container/:id/action                |
|      /api/system-metrics                 /api/config                     /metrics (Prometheus Exporter)           |
+---------------+--------------------------------+--------------------------------+---------------------------------+
                |                                |                                |
    (Async Poll | every 2s)                      | (Scrape 5s)                    | (Scrape 5s)
                v                                v                                v
+---------------+------------------------+ +-----+------------------------+ +-----+----------------------------------+
|      DockPulse 2.0 Dark UI Console     | |   Prometheus Time-Series DB  | |        cAdvisor Container Advisor      |
|  - Anomaly Status (NORMAL/WARN/CRIT)   | |   - Scrapes :5000/metrics    | |        - Port 8089:8080                |
|  - Trend Slopes & Predictive Horizons  | |   - TSDB Storage             | |        - Raw kernel cgroups telemetry  |
|  - Kubernetes Workload Scaling Card    | +------------------------------+ +----------------------------------------+
|  - AI Recommendation Feed              |
|  - Live Alerts Stream & Filters        |
|  - Container Lifecycle Controls        |
|  - Runtime Threshold Config Modal      |
+----------------------------------------+
```

---

## 🧠 Core Intelligence Modules & Mathematical Algorithms

### 1. Multi-Condition Anomaly Detection Engine
Evaluates telemetry across rolling time windows ($W$ samples, default 6 samples = 12 seconds):
- **Sustained High CPU**: Triggers `WARNING` if $\overline{\text{CPU}}_W \ge \text{threshold}_{\text{warn}}$ (default 70%), and `CRITICAL` if $\overline{\text{CPU}}_W \ge \text{threshold}_{\text{crit}}$ (default 85%).
- **Sustained Memory Saturation**: Triggers `WARNING` if $\overline{\text{RAM}}_W \ge 75\%$, and `CRITICAL` if $\ge 90\%$.
- **Resource Spike Detection**: Identifies abrupt transients if $\max(\text{CPU}_W) - \min(\text{CPU}_W) \ge 25\%$.
- **Container Health & Crash Loops**: Inspects container exit states and restart counts. If `restart_count >= 3`, promotes status to `CRITICAL` (crash loop alert).

### 2. Statistical Linear Trend Analysis (First-Order Regression)
DockPulse 2.0 computes the rate of change without requiring bulky external machine learning packages using least-squares linear regression over recent data points $(x_i, y_i)$:

$$m = \frac{N \sum x_i y_i - \sum x_i \sum y_i}{N \sum x_i^2 - \left(\sum x_i\right)^2}$$

- **Slope Interpretation**: $m$ is scaled to $\%/\text{min}$.
  - $m > +1.5\%/\text{min} \implies \textbf{UPWARD}$
  - $m < -1.5\%/\text{min} \implies \textbf{DOWNWARD}$
  - $|m| \le 1.5\%/\text{min} \implies \textbf{STABLE}$
- **Predictive Horizon Estimation**:
  $$\text{Time to Breach (mins)} = \frac{\text{Threshold}_{\text{crit}} - \text{Current Value}}{m}$$

### 3. Kubernetes Workload Balancing & Horizontal Scaling Engine
Modeled after the official Kubernetes Horizontal Pod Autoscaler (HPA) algorithm:

$$\text{Desired Replicas} = \max\left(\text{MinReplicas}, \min\left(\text{MaxReplicas}, \left\lceil \text{CurrentReplicas} \times \frac{\text{CurrentMetric}}{\text{TargetMetric}} \right\rceil \right)\right)$$

- If $\text{Current CPU} \ge \text{Warning Threshold}$ and $\text{Desired} > \text{Current} \implies \textbf{SCALE UP}$
- If $\text{Current CPU} < 30\%$ and $\text{Current} > \text{MinReplicas} \implies \textbf{SCALE DOWN}$
- Otherwise $\implies \textbf{KEEP CURRENT CAPACITY}$

### 4. AI-Style Workload Recommendation Engine
Synthesizes anomaly states, trend velocity, and container lifecycles into prioritized actionable directives:
- *"Consider scaling workload from 2 → 3 replicas to alleviate sustained load."*
- *"Pre-emptive action: CPU trend is accelerating (+4.2%/min). Monitor background batch jobs or prepare additional replica pods."*
- *"High memory: Investigate memory-heavy workload for memory leaks or increase container memory allocation."*
- *"Repeated container restarts: Inspect application health, exit codes, logs (`docker logs`), and restart policy."*

---

## 🛠️ File Structure

```
c:\DevOpsProj\
│
├── app.py                     # Flask server, SDK connector, REST endpoints, metrics exporter
├── intelligence.py            # DockPulse 2.0 Core: AnomalyDetector, TrendAnalyzer, WorkloadScaler, EventLogManager
├── requirements.txt           # Minimal dependencies (Flask, psutil, docker, prometheus-client)
├── Dockerfile                 # Multi-stage container definition
├── docker-compose.yml         # Observability stack: dockpulse + cadvisor + prometheus
├── prometheus.yml             # Prometheus scraping rules
├── Jenkinsfile                # Declarative CI/CD pipeline
├── tests/
│   └── test_intelligence.py   # Unit test suite verifying math, trends, and scaling logic
├── k8s/
│   ├── deployment.yaml        # Kubernetes Deployment (replicas, limits, probes)
│   └── service.yaml           # Kubernetes NodePort Service (Port 32000)
├── static/
│   ├── style.css              # Dark DevOps console styling, modals, badges, cards, and feeds
│   └── script.js              # Real-time controller, dual Chart.js lines, intelligence polling, action handlers
├── templates/
│   └── index.html             # Single-page dynamic dashboard featuring Intelligence Hub & Event Feed
├── PROJECT_REPORT.md          # Comprehensive academic project report
└── README.md                  # This document!
```

---

## 🚀 Setup & Execution Guide

### Option A: Local Bare-Metal Execution (Recommended for Fast Local Development)
**Prerequisites**: Python 3.10+ and Docker Desktop running.

1. **Activate virtual environment or install dependencies**:
   ```powershell
   cd C:\DevOpsProj
   pip install -r requirements.txt
   ```

2. **Run Unit Tests to verify intelligence calculations**:
   ```powershell
   python -m unittest tests/test_intelligence.py
   ```

3. **Launch DockPulse 2.0**:
   ```powershell
   python app.py
   ```

4. **Access the Dashboard**:
   Open **`http://localhost:5000`** in your browser.

---

### Option B: Docker Compose Observability Stack (Full Production Simulation)
**Prerequisites**: Docker Desktop running.

1. **Build and start all services in detached mode**:
   ```powershell
   docker-compose up -d --build
   ```

2. **Verify running containers**:
   ```powershell
   docker-compose ps
   ```

3. **Access Services**:
   - **DockPulse 2.0 Dashboard**: `http://localhost:5000`
   - **Prometheus TSDB**: `http://localhost:9090`
   - **cAdvisor Web UI**: `http://localhost:8089`

---

## 🧪 Step-by-Step Viva & Demo Walkthrough Guide

Use this script during college project presentations to demonstrate every feature of DockPulse 2.0:

### Demo 1: Intelligent Resource Monitoring
1. Open `http://localhost:5000`.
2. Observe the **System Resource Cards** showing real-time Host CPU, RAM, and registered container nodes.
3. In the **Cluster Active Container Feed** table, point out the new **Restarts** count and **Health** condition column.
4. Click **Inspect** on any container to transition into the **Container Details View**, displaying isolated CPU and RAM Chart.js line charts.

### Demo 2: Anomaly Detection & Condition States
1. In the top navigation bar, show the **Cluster Condition Badge** (`NORMAL`, `WARNING`, `CRITICAL`).
2. Show the **Detected Anomalies** card in the Intelligence section.
3. Click the **Thresholds** button in the header. Lower the **CPU Warning Threshold** to `10%` and click **Save & Apply Thresholds**.
4. Observe the Cluster Condition change to `WARNING` with an active anomaly entry explaining that Host CPU utilization exceeds the threshold.

### Demo 3: Predictive Trend Analysis
1. In the Intelligence section, showcase the **Predictive Trend Analysis** card.
2. Note the **Trajectory Velocity** (e.g., `+0.4% / min`) and the **Direction Badge** (`STABLE`, `UPWARD`, or `DOWNWARD`).
3. Explain the regression slope formula: DockPulse evaluates whether resource growth velocity will lead to a threshold breach before failure occurs.

### Demo 4: AI-Style Workload Recommendation & Scaling Advisory
1. Inspect the **Workload Balancing Decision** card. Show the **Current Replicas** vs. **Recommended Replicas** and the recommended action (`SCALE UP`, `SCALE DOWN`, or `KEEP CURRENT CAPACITY`).
2. Point to the **AI Workload Recommendations** list, showing contextual advice tailored to observed metrics (e.g. CPU quota increases, replica scaling, memory leak investigation).

### Demo 5: Kubernetes Scaling Bridge
1. Click the **Review & Apply K8s Scaling** button.
2. An interactive modal displays the target replica count and the exact dry-run command:
   ```bash
   kubectl scale deployment dockpulse-deployment --replicas=3
   ```
3. Click **Apply Scaling Plan**. The application safely updates `k8s/deployment.yaml`, displays a success toast notification, and logs the action into the event feed.

### Demo 6: Container Lifecycle Actions & Safety Guard
1. In the Container table, find any test container and click **Restart** or **Stop**.
2. Notice the live action confirmation toast and real-time state change.
3. Attempt to stop the core `dockpulse-dashboard` service. The backend **Safety Guard** activates and returns a `403 Forbidden` error toast, demonstrating production-grade self-preservation.

### Demo 7: Live Alerts & Event Stream
1. Scroll down to the **Live Observability Alerts & Event Stream** panel.
2. Show historical timestamped entries labeled `[CRITICAL]`, `[WARNING]`, `[INFO]`, and `[RECOMMENDATION]`.
3. Click the filter buttons (`Critical`, `Warning`, `Recommendations`, `Info`) to demonstrate instant client-side event filtering.

---

## 📡 REST API Reference

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/api/system-metrics` | `GET` | Latest host/node metrics + 50-point rolling history |
| `/api/containers` | `GET` | List all containers with state and restart counts |
| `/api/container/<id>` | `GET` | Live telemetry for specific container (CPU, RAM, Net I/O, Uptime) |
| `/api/container/<id>/action` | `POST` | Execute `start`, `stop`, `restart` on container |
| `/api/intelligence` | `GET` | Aggregated anomaly states, trend slope, recommendations, and scaling plan |
| `/api/events` | `GET` | Rolling in-memory alert history (supports `?limit=N&severity=CRITICAL`) |
| `/api/config` | `GET/POST` | Read or update runtime warning/critical thresholds |
| `/api/k8s/scale` | `GET/POST` | Inspect deployment info, preview dry-run command, or apply replica scaling |
| `/metrics` | `GET` | Prometheus exposition endpoint for host and container gauges |

---

## 🎯 Viva & Technical Interview Cheat-Sheet

### Q1: How does DockPulse 2.0 calculate the trend slope without external ML libraries?
> **Answer:** It uses the least-squares linear regression formula on a sliding window of recent telemetry coordinates. By finding the line of best fit $y = mx + c$, it calculates the slope $m$ in $\%/\text{min}$, providing a lightweight, low-overhead projection of whether CPU or memory is rapidly trending towards a breach.

### Q2: What is the autoscaling algorithm used in DockPulse 2.0?
> **Answer:** It implements the standard Kubernetes Horizontal Pod Autoscaler (HPA) mathematical model:
> $$\text{Desired Replicas} = \left\lceil \text{Current Replicas} \times \frac{\text{Current Utilization}}{\text{Target Utilization}} \right\rceil$$
> Bound by minimum and maximum replica limits.

### Q3: Why is DockPulse 2.0 built without a persistent SQL/NoSQL database?
> **Answer:** For local developer observability and small cluster nodes, introducing an external database adds significant memory overhead, disk I/O, and setup complexity. DockPulse 2.0 uses thread-safe rolling queues (`collections.deque(maxlen=N)`) in Python memory, which provide $O(1)$ appends and zero chance of memory leaks.

### Q4: How does DockPulse prevent a user from accidentally stopping the monitoring dashboard?
> **Answer:** The `/api/container/<id>/action` route contains a backend safety guard checking container name and ID against protected infrastructure names (`dockpulse`, `dockpulse-dashboard`, `dockpulse-cadvisor`, `dockpulse-prometheus`). Any stop request targeting core infrastructure is rejected with `403 Forbidden`.
