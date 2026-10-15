"""
DockPulse 2.0 - Intelligent Container Observability & Workload Management Platform
Connected to local Docker Desktop using official Python Docker SDK.
Integrates:
- Real-Time System & Container Telemetry
- Prometheus Metrics Exporter
- Multi-Condition Anomaly Detection
- Statistical Linear Trend Forecasting
- AI-Style Workload Recommendation Engine
- Kubernetes Horizontal Workload Balancing & Autoscaling Bridge
"""

import time
import threading
from datetime import datetime
import json
import urllib.parse
import urllib.request
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import psutil
import docker
from flask import Flask, jsonify, render_template, request
from prometheus_client import CollectorRegistry, Gauge, generate_latest, CONTENT_TYPE_LATEST

from runtime_providers import runtime_manager
from intelligence import (
    ThresholdConfig,
    EventLogManager,
    AnomalyDetector,
    RecommendationEngine,
    WorkloadScaler,
    KubernetesBridge
)

app = Flask(__name__)


PROMETHEUS_URL = "http://prometheus:9090"


def get_pod_cpu_usage(pod_uid, cpu_request_cores=0.25):
    """
    Returns actual pod CPU utilization as a percentage of its CPU request.
    Returns None when Prometheus has no usable metric for this pod.
    """
    if not pod_uid:
        return None

    try:
        uid_pattern = pod_uid.replace("-", "_")
        promql = (
            'sum(rate(container_cpu_usage_seconds_total'
            '{id=~".*pod' + uid_pattern +
            '.*cri-containerd.*scope"}[1m]))'
        )

        query_url = (
            f"{PROMETHEUS_URL}/api/v1/query?"
            + urllib.parse.urlencode({"query": promql})
        )

        req = urllib.request.Request(
            query_url,
            headers={"Accept": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))

        if payload.get("status") != "success":
            return None

        results = payload.get("data", {}).get("result", [])
        if not results:
            return None

        cpu_cores = sum(
            max(0.0, float(item["value"][1]))
            for item in results
        )

        if cpu_request_cores <= 0:
            return None

        return round((cpu_cores / cpu_request_cores) * 100, 2)

    except Exception as exc:
        app.logger.debug("Pod CPU metric unavailable: %s", exc)
        return None

# ==============================================================================
# PROMETHEUS METRICS CONFIGURATION
# ==============================================================================
prometheus_registry = CollectorRegistry()

# Define host Gauges
host_cpu_gauge = Gauge('dockpulse_host_cpu_percentage', 'Host CPU utilization percentage', registry=prometheus_registry)
host_ram_gauge = Gauge('dockpulse_host_memory_percentage', 'Host RAM utilization percentage', registry=prometheus_registry)
host_disk_gauge = Gauge('dockpulse_host_disk_percentage', 'Host Disk utilization percentage', registry=prometheus_registry)
containers_total_gauge = Gauge('dockpulse_containers_total', 'Total number of containers registered', registry=prometheus_registry)
containers_running_gauge = Gauge('dockpulse_containers_running', 'Number of currently running containers', registry=prometheus_registry)

# Define container Gauges (Docker Mode)
container_cpu_gauge = Gauge('dockpulse_container_cpu_percentage', 'Container CPU usage percentage', ['container_name', 'container_id'], registry=prometheus_registry)
container_memory_used_gauge = Gauge('dockpulse_container_memory_used_bytes', 'Container memory usage in bytes', ['container_name', 'container_id'], registry=prometheus_registry)
container_memory_limit_gauge = Gauge('dockpulse_container_memory_limit_bytes', 'Container memory limit in bytes', ['container_name', 'container_id'], registry=prometheus_registry)
container_status_gauge = Gauge('dockpulse_container_status', 'Container status (1=running, 0=stopped/exited)', ['container_name', 'container_id', 'status'], registry=prometheus_registry)

# Define Kubernetes Gauges (Kubernetes Mode)
k8s_pods_total_gauge = Gauge('dockpulse_k8s_pods_total', 'Total number of Kubernetes pods', registry=prometheus_registry)
k8s_pods_running_gauge = Gauge('dockpulse_k8s_pods_running', 'Number of running Kubernetes pods', registry=prometheus_registry)
k8s_deployments_total_gauge = Gauge('dockpulse_k8s_deployments_total', 'Total number of Kubernetes deployments', registry=prometheus_registry)
k8s_deployment_replicas_gauge = Gauge('dockpulse_k8s_deployment_replicas', 'Kubernetes deployment replicas', ['deployment_name', 'state'], registry=prometheus_registry)


# ==============================================================================
# GLOBAL METRICS STORE & INTELLIGENCE MANAGERS
# ==============================================================================
METRIC_HISTORY_LIMIT = 50
host_metrics_history = deque(maxlen=METRIC_HISTORY_LIMIT)
history_lock = threading.Lock()

# Initialize DockPulse 2.0 Intelligence Core
threshold_config = ThresholdConfig()
event_manager = EventLogManager(maxlen=100)
anomaly_detector = AnomalyDetector(threshold_config, event_manager)
recommendation_engine = RecommendationEngine(threshold_config, event_manager)
workload_scaler = WorkloadScaler(threshold_config)
k8s_bridge = KubernetesBridge(manifest_path="k8s/deployment.yaml", k8s_provider=runtime_manager.get_k8s_provider())

# Startup Event Log
event_manager.add_event(
    severity="INFO",
    title="DockPulse 2.0 Engine Online",
    message=f"Intelligent Observability initialized in {runtime_manager.detect_runtime()} runtime mode.",
    source="System"
)


def get_docker_client():
    """
    Attempts to connect to the local Docker Desktop daemon dynamically.
    Returns a client instance if successful, or None if the Docker daemon is offline.
    """
    try:
        client = docker.from_env()
        client.ping()  # Forces a connection verify check
        return client
    except Exception:
        return None


def get_formatted_uptime(seconds):
    """Converts seconds into a human-readable days, hours, minutes format."""
    if seconds <= 0:
        return "0m"
    
    days = int(seconds // (24 * 3600))
    seconds %= (24 * 3600)
    hours = int(seconds // 3600)
    seconds %= 3600
    minutes = int(seconds // 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    
    return " ".join(parts)


def host_metric_collector():
    """
    Background worker that collects host system metrics (CPU, RAM, Disk) every 2 seconds.
    Maintains rolling time-series deque for dashboard and statistical trend models.
    """
    print("Starting background host metric collector thread (DockPulse 2.0)...")
    while True:
        try:
            # 1. System CPU percentage
            cpu_pct = psutil.cpu_percent(interval=None)
            
            # 2. System RAM metrics
            ram = psutil.virtual_memory()
            ram_pct = ram.percent
            ram_used_gb = round(ram.used / (1024 ** 3), 2)
            ram_total_gb = round(ram.total / (1024 ** 3), 2)
            
            # 3. System Disk metrics
            disk = psutil.disk_usage('/')
            disk_pct = disk.percent
            disk_used_gb = round(disk.used / (1024 ** 3), 2)
            disk_total_gb = round(disk.total / (1024 ** 3), 2)
            disk_free_gb = round(disk.free / (1024 ** 3), 2)
            
            # 4. System Uptime & Process counts
            boot_time = psutil.boot_time()
            uptime_sec = time.time() - boot_time
            uptime_str = get_formatted_uptime(uptime_sec)
            
            processes_count = len(psutil.pids())
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            # 5. Workload Replicas & Scaling State Telemetry
            current_replicas = 2
            desired_replicas = 2
            running_workloads = 0
            avg_pod_cpu = None
            try:
                docker_prov = runtime_manager.get_docker_provider()
                if docker_prov.is_available():
                    running_workloads = docker_prov.get_summary().get("running_workloads", 0)

                k_info = k8s_bridge.get_deployment_info()
                current_replicas = k_info.get("replicas", 2)
                desired_replicas = k_info.get("replicas", 2)

                # Sample Pod CPU for HPA scaling telemetry (never confuse with host CPU)
                k8s_prov = runtime_manager.get_k8s_provider()
                if k8s_prov.is_available():
                    pod_cpus = []
                    for pod in k8s_prov.get_workloads().get("pods", []):
                        if pod.get("name", "").startswith("dockpulse-deployment"):
                            u = get_pod_cpu_usage(pod.get("pod_uid"))
                            if u is not None:
                                pod_cpus.append(u)
                    if pod_cpus:
                        avg_pod_cpu = round(sum(pod_cpus) / len(pod_cpus), 2)
            except Exception:
                pass

            scale_eval = workload_scaler.evaluate(
                current_cpu=avg_pod_cpu,
                current_replicas=current_replicas,
                metric_source="Pod CPU (Prometheus/cAdvisor)" if avg_pod_cpu is not None else "Pod Telemetry Awaiting"
            )
            recommended_reps = scale_eval.get("recommended_replicas", current_replicas)
            scaling_act = scale_eval.get("action", "KEEP CURRENT CAPACITY")
            
            payload = {
                "timestamp": timestamp,
                "cpu_percentage": cpu_pct,
                "ram_percentage": ram_pct,
                "ram_used_gb": ram_used_gb,
                "ram_total_gb": ram_total_gb,
                "disk_percentage": disk_pct,
                "disk_used_gb": disk_used_gb,
                "disk_total_gb": disk_total_gb,
                "disk_free_gb": disk_free_gb,
                "uptime": uptime_str,
                "processes_count": processes_count,
                "replicas": current_replicas,
                "desired_replicas": desired_replicas,
                "recommended_replicas": recommended_reps,
                "running_containers": running_workloads or current_replicas,
                "scaling_action": scaling_act,
                "cpu_warning": threshold_config.cpu_warning,
                "cpu_critical": threshold_config.cpu_critical
            }
            
            with history_lock:
                host_metrics_history.append(payload)
            
        except Exception as e:
            print(f"Error collecting host metrics: {e}")
            
        time.sleep(2)


# Start background collector thread
collector_thread = threading.Thread(target=host_metric_collector, daemon=True)
collector_thread.start()


# Workload Distribution Cache & Collector
workload_distribution_cache = []
workload_dist_lock = threading.Lock()

def workload_distribution_collector():
    """
    Background worker that collects per-container/pod CPU & memory utilization
    every 2.5 seconds and updates the workload distribution cache.
    """
    print("Starting background workload distribution collector thread (DockPulse 2.0)...")

    while True:
        try:
            active_runtime = runtime_manager.detect_runtime()
            dist_results = []

            if active_runtime == "Kubernetes":
                k8s_prov = runtime_manager.get_k8s_provider()

                if k8s_prov.is_available():
                    workloads = k8s_prov.get_workloads()
                    pods = workloads.get("pods", [])

                    running_pods = [
                        pod for pod in pods
                        if pod.get("state") == "running"
                        or pod.get("phase") == "Running"
                    ]

                    for idx, pod in enumerate(running_pods):
                        pod_name = pod.get("name", f"pod-{idx + 1}")
                        cpu_percentage = get_pod_cpu_usage(
                            pod.get("pod_uid"),
                            cpu_request_cores=0.25
                        )

                        dist_results.append({
                            "id": pod.get("id", pod_name[:12]),
                            "name": pod_name,
                            "cpu_percentage": cpu_percentage,
                            "status": pod.get("status", "running"),
                            "kind": "pod",
                            "node": pod.get("node_name", "desktop-control-plane")
                        })

            else:
                docker_provider = runtime_manager.get_docker_provider()

                if docker_provider.is_available():
                    client = docker_provider._get_client()

                    if client:
                        running_containers = [
                            container
                            for container in client.containers.list()
                            if container.status == "running"
                        ]

                        def sample_container(container):
                            try:
                                stats = container.stats(stream=False)
                                cpu_stats = stats.get("cpu_stats", {})
                                precpu_stats = stats.get("precpu_stats", {})

                                cpu_delta = (
                                    cpu_stats.get("cpu_usage", {}).get("total_usage", 0)
                                    - precpu_stats.get("cpu_usage", {}).get("total_usage", 0)
                                )
                                system_delta = (
                                    cpu_stats.get("system_cpu_usage", 0)
                                    - precpu_stats.get("system_cpu_usage", 0)
                                )
                                online_cpus = cpu_stats.get("online_cpus", 1) or 1

                                cpu_pct = (
                                    round((cpu_delta / system_delta) * online_cpus * 100.0, 2)
                                    if system_delta > 0 and cpu_delta > 0
                                    else 0.0
                                )
                                memory_mb = round(
                                    stats.get("memory_stats", {}).get("usage", 0)
                                    / (1024 * 1024),
                                    1
                                )

                                container_cpu_gauge.labels(
                                    container_name=container.name,
                                    container_id=container.short_id
                                ).set(cpu_pct)

                                return {
                                    "id": container.short_id,
                                    "name": container.name,
                                    "cpu_percentage": cpu_pct,
                                    "memory_mb": memory_mb,
                                    "status": container.status,
                                    "kind": "container"
                                }

                            except Exception as exc:
                                app.logger.debug(
                                    "Container sampling failed for %s: %s",
                                    getattr(container, "name", "unknown"),
                                    exc
                                )
                                return None

                        with ThreadPoolExecutor(max_workers=6) as executor:
                            sampled = list(
                                executor.map(sample_container, running_containers)
                            )

                        dist_results = [
                            result for result in sampled
                            if result is not None
                        ]

            with workload_dist_lock:
                workload_distribution_cache.clear()
                workload_distribution_cache.extend(dist_results)

        except Exception:
            app.logger.exception("Workload distribution collector failed")

        time.sleep(2.5)


dist_thread = threading.Thread(target=workload_distribution_collector, daemon=True)
dist_thread.start()


# ==============================================================================
# WEB DASHBOARD & TELEMETRY ROUTES
# ==============================================================================

@app.route("/")
def index():
    """Serves the DockPulse 2.0 dynamic observability console."""
    return render_template("index.html")


@app.route("/api/system-metrics")
def get_system_metrics():
    """
    API Endpoint returning latest host/node metrics and rolling history array.
    """
    with history_lock:
        history_list = list(host_metrics_history)
        
    if not history_list:
        boot_time = psutil.boot_time()
        uptime_sec = time.time() - boot_time
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        fallback = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "cpu_percentage": 0.0,
            "ram_percentage": ram.percent,
            "ram_used_gb": round(ram.used / (1024 ** 3), 2),
            "ram_total_gb": round(ram.total / (1024 ** 3), 2),
            "disk_percentage": disk.percent,
            "disk_used_gb": round(disk.used / (1024 ** 3), 2),
            "disk_total_gb": round(disk.total / (1024 ** 3), 2),
            "disk_free_gb": round(disk.free / (1024 ** 3), 2),
            "uptime": get_formatted_uptime(uptime_sec),
            "processes_count": len(psutil.pids()),
            "replicas": 1,
            "desired_replicas": 1,
            "recommended_replicas": 1,
            "running_containers": 1,
            "scaling_action": "KEEP CURRENT CAPACITY",
            "cpu_warning": threshold_config.cpu_warning,
            "cpu_critical": threshold_config.cpu_critical
        }
        return jsonify({"latest": fallback, "history": [fallback], "thresholds": threshold_config.to_dict()})

    return jsonify({
        "latest": history_list[-1],
        "history": history_list,
        "thresholds": threshold_config.to_dict()
    })


@app.route("/api/workload-distribution")
def get_workload_distribution():
    """
    API Endpoint returning CPU & resource allocation distribution across active
    containers or Kubernetes pods to demonstrate horizontal workload balancing.
    """
    with workload_dist_lock:
        data = list(workload_distribution_cache)
    
    if not data:
        try:
            provider = runtime_manager.get_active_provider()
            workloads = provider.get_workloads()
            items = workloads.get("containers", [])
            data = [
                {
                    "id": item.get("id", "c-0"),
                    "name": item.get("name", "workload"),
                    "cpu_percentage": 0.0,
                    "status": item.get("status", "running"),
                    "kind": item.get("kind", "container")
                }
                for item in items if item.get("status") == "running"
            ]
        except Exception:
            data = []

    return jsonify({
        "success": True,
        "runtime": runtime_manager.detect_runtime(),
        "workloads": data,
        "count": len(data),
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })


@app.route("/api/runtime", methods=["GET", "POST"])
def get_runtime():
    """
    API Endpoint returning detected runtime mode ('Docker' or 'Kubernetes')
    and infrastructure connectivity diagnostics.
    POST allows dynamically selecting the active runtime ('docker' or 'kubernetes').
    """
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        target_mode = payload.get("runtime", "") or payload.get("mode", "")
        if runtime_manager.set_runtime(target_mode):
            event_manager.add_event(
                severity="INFO",
                title="Runtime Mode Changed",
                message=f"Operator switched active runtime mode to: {runtime_manager.detect_runtime()}",
                source="Runtime"
            )
    return jsonify(runtime_manager.get_runtime_info())


@app.route("/api/workloads")
def get_workloads():
    """
    API Endpoint returning full workload topology:
    Docker containers, and Kubernetes pods, deployments, services.
    Neither runtime hides the other.
    """
    docker_prov = runtime_manager.get_docker_provider()
    k8s_prov = runtime_manager.get_k8s_provider()

    docker_data = docker_prov.get_workloads() if docker_prov.is_available() else {"containers": []}
    k8s_data = k8s_prov.get_workloads() if k8s_prov.is_available() else {"pods": [], "deployments": [], "services": []}

    containers = docker_data.get("containers", [])
    pods = k8s_data.get("pods", [])
    deployments = k8s_data.get("deployments", [])
    services = k8s_data.get("services", [])

    return jsonify({
        "success": True,
        "runtime": runtime_manager.detect_runtime(),
        "docker_available": docker_prov.is_available(),
        "kubernetes_available": k8s_prov.is_available(),
        "containers": containers,
        "pods": pods,
        "deployments": deployments,
        "services": services,
        "summary": {
            "total_containers": len(containers),
            "running_containers": sum(1 for c in containers if c.get("status") == "running"),
            "total_pods": len(pods),
            "running_pods": sum(1 for p in pods if p.get("state") == "running" or p.get("phase") == "Running"),
            "total_deployments": len(deployments),
            "total_services": len(services)
        }
    })


@app.route("/api/containers")
def get_containers():
    """
    API Endpoint returning registered Docker containers.
    Never mixes Kubernetes pods into the Docker container list.
    """
    docker_prov = runtime_manager.get_docker_provider()
    if not docker_prov.is_available():
        return jsonify({
            "success": False,
            "error": "Docker Engine / Daemon not detected"
        }), 503

    workloads = docker_prov.get_workloads()
    data = workloads.get("containers", [])
    return jsonify(data)


@app.route("/api/container/<container_id>")
def get_container_stats(container_id):
    """
    API Endpoint returning detailed live resource telemetry for a specific container or Pod.
    Checks Docker containers first; falls back to Kubernetes Pods.
    """
    docker_prov = runtime_manager.get_docker_provider()
    if docker_prov.is_available():
        stats = docker_prov.get_workload_detail(container_id)
        if stats.get("success") is not False:
            return jsonify(stats)

    k8s_prov = runtime_manager.get_k8s_provider()
    if k8s_prov.is_available():
        stats = k8s_prov.get_workload_detail(container_id)
        if stats.get("success") is not False:
            return jsonify(stats)

    return jsonify({"success": False, "error": f"Workload '{container_id}' not found"}), 404


# ==============================================================================
# DOCKPULSE 2.0: WORKLOAD LIFECYCLE ACTIONS
# ==============================================================================

@app.route("/api/container/<container_id>/action", methods=["POST"])
def container_action(container_id):
    """
    Executes container/workload lifecycle actions.
    Docker: start, stop, restart with self-preservation safety guard.
    Kubernetes: restart/delete pod (ReplicaSet auto-heals).
    """
    payload = request.get_json(silent=True) or {}
    action = payload.get("action", "").lower().strip()

    docker_prov = runtime_manager.get_docker_provider()
    if docker_prov.is_available():
        res = docker_prov.execute_workload_action(container_id, action)
        if res.get("success"):
            event_manager.add_event(
                severity="INFO",
                title="Docker Action Executed",
                message=res.get("message", f"Action '{action}' executed."),
                source=res.get("container_name", container_id)
            )
            return jsonify(res)
        elif "Safety Guard" in res.get("error", ""):
            return jsonify(res), 403

    k8s_prov = runtime_manager.get_k8s_provider()
    if k8s_prov.is_available():
        res = k8s_prov.execute_workload_action(container_id, action)
        if res.get("success"):
            event_manager.add_event(
                severity="INFO",
                title="Kubernetes Action Executed",
                message=res.get("message", f"Action '{action}' executed."),
                source=res.get("container_name", container_id)
            )
            return jsonify(res)

    return jsonify({"success": False, "error": f"Unable to execute '{action}' on workload '{container_id}'"}), 400


# ==============================================================================
# DOCKPULSE 2.0: INTELLIGENCE, ANOMALY DETECTION & RECOMMENDATION ROUTES
# ==============================================================================

@app.route("/api/intelligence")
def get_intelligence():
    """
    Core DockPulse 2.0 endpoint:
    Aggregates Host & Workload telemetry, runs multi-condition anomaly detection,
    computes linear regression trends, generates AI workload recommendations,
    and calculates horizontal replica autoscaling recommendations.
    """
    # 1. Fetch Host History
    with history_lock:
        history_list = list(host_metrics_history)
        
    host_analysis = anomaly_detector.analyze_host(history_list)
    
    # 2. Fetch Workload Data via Active Provider
    provider = runtime_manager.get_active_provider()
    workload_items = []
    if provider.is_available():
        try:
            workloads = provider.get_workloads()
            workload_items = workloads.get("containers", [])
        except Exception as e:
            app.logger.warning(f"Failed to fetch workloads for intelligence: {e}")

    container_analysis = anomaly_detector.analyze_containers(workload_items)

    # 3. Overall Condition (Worst of Host and Workloads)
    condition_rank = {"NORMAL": 1, "WARNING": 2, "CRITICAL": 3}
    host_rank = condition_rank.get(host_analysis["status"], 1)
    cont_rank = condition_rank.get(container_analysis["status"], 1)
    
    overall_status = "CRITICAL" if max(host_rank, cont_rank) == 3 else ("WARNING" if max(host_rank, cont_rank) == 2 else "NORMAL")

    # 4. Kubernetes Bridge & Workload Autoscaling
    k8s_info = k8s_bridge.get_deployment_info()
    current_k8s_replicas = k8s_info.get("replicas", 2)
    
    # Calculate pod CPU from actual Prometheus / cAdvisor pod metrics (never confuse with host CPU)
    avg_pod_cpu = None
    k8s_prov = runtime_manager.get_k8s_provider()
    if k8s_prov.is_available():
        pod_cpus = []
        for pod in k8s_prov.get_workloads().get("pods", []):
            if pod.get("name", "").startswith("dockpulse-deployment"):
                u = get_pod_cpu_usage(pod.get("pod_uid"))
                if u is not None:
                    pod_cpus.append(u)
        if pod_cpus:
            avg_pod_cpu = round(sum(pod_cpus) / len(pod_cpus), 2)

    metric_src = "Pod CPU (Prometheus/cAdvisor)" if avg_pod_cpu is not None else "Pod Telemetry Awaiting"
    scaling_decision = workload_scaler.evaluate(
        current_cpu=avg_pod_cpu,
        current_replicas=current_k8s_replicas,
        metric_source=metric_src
    )

    # 5. Synthesize Actionable AI Recommendations
    recommendations = recommendation_engine.generate_recommendations(
        host_analysis=host_analysis,
        container_analysis=container_analysis,
        scaling_decision=scaling_decision
    )

    return jsonify({
        "runtime": provider.get_runtime_name(),
        "status": overall_status,
        "condition": "Critical Alert" if overall_status == "CRITICAL" else ("Warning" if overall_status == "WARNING" else "Healthy"),
        "host_analysis": host_analysis,
        "container_analysis": container_analysis,
        "trend": host_analysis.get("trend", {}),
        "scaling_decision": scaling_decision,
        "recommendations": recommendations,
        "k8s_info": k8s_info,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })


@app.route("/api/events")
def get_events():
    """
    Returns rolling in-memory event and alert history.
    Query parameters:
    - limit: max events to return (default: 30)
    - severity: filter by 'CRITICAL', 'WARNING', 'INFO', 'RECOMMENDATION'
    """
    limit = request.args.get("limit", default=30, type=int)
    severity = request.args.get("severity", default=None, type=str)
    events = event_manager.get_events(limit=limit, severity=severity)
    return jsonify({
        "total": len(events),
        "events": events
    })


@app.route("/api/config", methods=["GET", "POST"])
def handle_config():
    """
    GET: Returns current threshold configuration.
    POST: Updates warning/critical thresholds and window durations.
    """
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        threshold_config.update(payload)
        event_manager.add_event(
            severity="INFO",
            title="Thresholds Updated",
            message=f"Operator tuned thresholds: CPU Warn={threshold_config.cpu_warning}%, CPU Crit={threshold_config.cpu_critical}%, Window={threshold_config.window_samples} samples",
            source="Config"
        )
        return jsonify({
            "success": True,
            "message": "Operational thresholds updated successfully.",
            "config": threshold_config.to_dict()
        })

    return jsonify({
        "config": threshold_config.to_dict()
    })


@app.route("/api/k8s/scale", methods=["GET", "POST"])
def k8s_scale():
    """
    GET: Returns current deployment status and scale command plan.
    POST: Accepts {"target_replicas": N, "apply": true/false}.
          When apply=true:
          - If live Kubernetes cluster is available: calls Kubernetes API to patch deployment
            replicas, waits for reconciliation, and verifies actual pod readiness before returning.
          - If cluster offline: updates k8s/deployment.yaml manifest for GitOps tracking.
    """
    deployment_name = "dockpulse-deployment"
    k8s_prov = runtime_manager.get_k8s_provider()

    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        target_replicas = int(payload.get("target_replicas", 2))
        apply_action = bool(payload.get("apply", False))

        plan = k8s_bridge.generate_scale_plan(target_replicas)

        if apply_action:
            # 1. LIVE KUBERNETES API SCALING
            if k8s_prov.is_available():
                result = k8s_prov.scale_workload(
                    deployment_name=deployment_name,
                    target_replicas=target_replicas,
                    wait_timeout=25
                )

                if result.get("success"):
                    # Synchronize local YAML manifest file
                    k8s_bridge.update_manifest_replicas(target_replicas)
                    event_manager.add_event(
                        severity="INFO",
                        title="Kubernetes Scale Applied",
                        message=result.get("message", f"Scaled {deployment_name} to {target_replicas} replicas."),
                        source="K8sScaler"
                    )
                    return jsonify({
                        "success": True,
                        "message": result.get("message"),
                        "plan": plan,
                        "verification": result
                    })
                else:
                    event_manager.add_event(
                        severity="CRITICAL",
                        title="Kubernetes Scale Failed",
                        message=result.get("error", "Scale API call failed"),
                        source="K8sScaler"
                    )
                    return jsonify({
                        "success": False,
                        "error": result.get("error"),
                        "plan": plan
                    }), 500
            else:
                # 2. Manifest-only fallback when live cluster API is not reached
                success, msg = k8s_bridge.update_manifest_replicas(target_replicas)
                if success:
                    event_manager.add_event(
                        severity="INFO",
                        title="Kubernetes Manifest Updated",
                        message=f"Updated k8s/deployment.yaml to {target_replicas} replicas (Live cluster offline).",
                        source="K8sScaler"
                    )
                return jsonify({
                    "success": success,
                    "message": msg,
                    "plan": plan
                })

        return jsonify({
            "success": True,
            "message": "Dry-run scaling command generated.",
            "plan": plan
        })

    # GET request
    info = k8s_bridge.get_deployment_info()
    return jsonify({
        "deployment": info,
        "dry_run_command": f"kubectl scale deployment {info.get('name', deployment_name)} --replicas={info.get('replicas', 1)}"
    })


# ==============================================================================
# PROMETHEUS SCRAPE EXPORTER ENDPOINT
# ==============================================================================

@app.route("/metrics")
def metrics():
    """
    Prometheus metrics scraping endpoint.
    Exposes host metrics and active runtime telemetry in Prometheus exposition format.
    """
    # 1. Gather Host Metrics (always collected)
    try:
        cpu_pct = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        host_cpu_gauge.set(cpu_pct)
        host_ram_gauge.set(ram.percent)
        host_disk_gauge.set(disk.percent)
    except Exception as e:
        app.logger.error(f"Error collecting host metrics for Prometheus: {e}")

    # 2. Gather Docker Metrics independently
    docker_prov = runtime_manager.get_docker_provider()
    if docker_prov.is_available():
        try:
            workloads = docker_prov.get_workloads()
            all_containers = workloads.get("containers", [])
            containers_total_gauge.set(len(all_containers))

            container_status_gauge.clear()
            running_count = 0

            for c in all_containers:
                c_name = c.get("name", "unknown")
                c_id = c.get("id", "unknown")
                status = c.get("status", "unknown")
                is_running = 1 if status == "running" else 0

                if is_running:
                    running_count += 1

                container_status_gauge.labels(
                    container_name=c_name,
                    container_id=c_id,
                    status=status
                ).set(is_running)

            containers_running_gauge.set(running_count)

        except Exception as e:
            app.logger.error(
                f"Error collecting Docker metrics for Prometheus: {e}"
            )

    # 3. Gather Kubernetes Metrics independently
    k8s_prov = runtime_manager.get_k8s_provider()
    if k8s_prov.is_available():
        try:
            workloads = k8s_prov.get_workloads()
            pods = workloads.get("pods", [])
            deployments = workloads.get("deployments", [])

            k8s_pods_total_gauge.set(len(pods))

            running_pods = sum(
                1 for p in pods
                if p.get("state") == "running"
                or p.get("phase") == "Running"
            )
            k8s_pods_running_gauge.set(running_pods)
            k8s_deployments_total_gauge.set(len(deployments))

            k8s_deployment_replicas_gauge.clear()

            for dep in deployments:
                d_name = dep.get("name", "unknown")

                k8s_deployment_replicas_gauge.labels(
                    deployment_name=d_name, state="desired"
                ).set(dep.get("desired_replicas", 0))

                k8s_deployment_replicas_gauge.labels(
                    deployment_name=d_name, state="ready"
                ).set(dep.get("ready_replicas", 0))

                k8s_deployment_replicas_gauge.labels(
                    deployment_name=d_name, state="available"
                ).set(dep.get("available_replicas", 0))

        except Exception as e:
            app.logger.error(
                f"Error collecting Kubernetes metrics for Prometheus: {e}"
            )
    return generate_latest(prometheus_registry), 200, {'Content-Type': CONTENT_TYPE_LATEST}
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
