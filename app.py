"""
DockPulse - Real-Time Docker Container Monitoring Platform
Connected to local Docker Desktop using official Python Docker SDK.
"""

import time
import threading
from datetime import datetime
from collections import deque
import psutil
import docker
from flask import Flask, jsonify, render_template, request
from prometheus_client import CollectorRegistry, Gauge, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

# Prometheus metrics configuration
# Use a custom CollectorRegistry to isolate our custom metrics and keep it lightweight.
prometheus_registry = CollectorRegistry()

# Define host Gauges
host_cpu_gauge = Gauge('dockpulse_host_cpu_percentage', 'Host CPU utilization percentage', registry=prometheus_registry)
host_ram_gauge = Gauge('dockpulse_host_memory_percentage', 'Host RAM utilization percentage', registry=prometheus_registry)
host_disk_gauge = Gauge('dockpulse_host_disk_percentage', 'Host Disk utilization percentage', registry=prometheus_registry)
containers_total_gauge = Gauge('dockpulse_containers_total', 'Total number of containers registered', registry=prometheus_registry)
containers_running_gauge = Gauge('dockpulse_containers_running', 'Number of currently running containers', registry=prometheus_registry)

# Define container Gauges
container_cpu_gauge = Gauge('dockpulse_container_cpu_percentage', 'Container CPU usage percentage', ['container_name', 'container_id'], registry=prometheus_registry)
container_memory_used_gauge = Gauge('dockpulse_container_memory_used_bytes', 'Container memory usage in bytes', ['container_name', 'container_id'], registry=prometheus_registry)
container_memory_limit_gauge = Gauge('dockpulse_container_memory_limit_bytes', 'Container memory limit in bytes', ['container_name', 'container_id'], registry=prometheus_registry)
container_status_gauge = Gauge('dockpulse_container_status', 'Container status (1=running, 0=stopped/exited)', ['container_name', 'container_id', 'status'], registry=prometheus_registry)


# Thread-safe global store for host system metrics history (last 50 data points)
# Deque automatically drops the oldest item when it exceeds maxlen.
# Store 30-50 data points to avoid memory bloat while seeding graphs smoothly.
METRIC_HISTORY_LIMIT = 50
host_metrics_history = deque(maxlen=METRIC_HISTORY_LIMIT)
history_lock = threading.Lock()


def get_docker_client():
    """
    Attempts to connect to the local Docker Desktop daemon dynamically.
    Returns a client instance if successful, or None if the Docker daemon is offline.
    This enables dynamic recovery when the user launches Docker Desktop after the server starts.
    """
    try:
        # standard docker environment checks (looks at pipe/sockets)
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
    This powers the main DockPulse Cluster Overview dashboard.
    
    --------------------------------------------------------------------------
    OBSERVABILITY TIME-SERIES & HISTORY ARRAYS DESIGN PRINCIPLE:
    1. WHY HISTORY ARRAYS ARE REQUIRED: Time-series line/area charts (like CPU & RAM history) 
       require a sequential series of chronological data points (X = timestamp, Y = value) 
       to plot connected vectors. A single snapshot metric is insufficient for history.
    2. WHY GRAPHS REMAIN EMPTY WITHOUT BACKEND HISTORY: When a user refreshes their browser, 
       any client-side JavaScript memory is wiped out. If the backend does not persist and 
       buffer historical coordinates, the chart will render completely blank on page load, 
       forcing the user to wait for multiple polling cycles to see a line begin to form.
    3. WHY ROLLING DEQUES ARE MEMORY EFFICIENT: Storing infinite logs in memory leads to OOM 
       crashes. Using a double-ended queue (collections.deque) with a strict 'maxlen=50' 
       enforces an upper memory boundary. Appending new points drops the oldest elements 
       automatically in O(1) time complexity, preventing memory leaks while keeping enough 
       history to pre-populate charts instantly.
    --------------------------------------------------------------------------
    """
    print("Starting background host metric collector thread...")
    while True:
        try:
            # 1. System CPU percentage (non-blocking call)
            cpu_pct = psutil.cpu_percent(interval=None)
            
            # 2. System RAM metrics (virtual memory)
            ram = psutil.virtual_memory()
            ram_pct = ram.percent
            ram_used_gb = round(ram.used / (1024 ** 3), 2)
            ram_total_gb = round(ram.total / (1024 ** 3), 2)
            
            # 3. System Disk metrics (root directory)
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
                "processes_count": processes_count
            }
            
            # Append to thread-safe host history queue
            with history_lock:
                host_metrics_history.append(payload)
            
        except Exception as e:
            print(f"Error collecting host metrics: {e}")
            
        time.sleep(2)


# Start the background host collector thread
collector_thread = threading.Thread(target=host_metric_collector, daemon=True)
collector_thread.start()


@app.route("/")
def index():
    """Serves the main DockPulse dynamic dashboard interface."""
    return render_template("index.html")


@app.route("/api/system-metrics")
def get_system_metrics():
    """
    API Endpoint returning latest host/node metrics.
    Used to drive the Cluster Overview dashboard when no specific container is chosen.
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
            "processes_count": len(psutil.pids())
        }
        return jsonify({"latest": fallback, "history": [fallback]})

    return jsonify({
        "latest": history_list[-1],
        "history": history_list
    })


@app.route("/api/containers")
def get_containers():
    """
    API Endpoint that queries Docker Desktop.
    Returns a clean JSON list of all active/running containers.
    If Docker Desktop is offline, returns a 503 warning status.
    """
    client = get_docker_client()
    if not client:
        return jsonify({"success": False, "error": "Docker Engine not detected"}), 503
        
    try:
        # Get all containers (running and stopped)
        all_containers = client.containers.list(all=True)
        data = []
        for c in all_containers:
            data.append({
                "id": c.short_id,
                "name": c.name,
                "status": c.status,
                "image": c.attrs.get('Config', {}).get('Image', '')
            })
        return jsonify(data)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/container/<container_id>")
def get_container_stats(container_id):
    """
    API Endpoint returning REAL metrics for a specific running container.
    Calculates CPU percent, RAM MB bounds, Net I/O, and exact Uptime.
    """
    client = get_docker_client()
    if not client:
        return jsonify({"success": False, "error": "Docker Engine not detected"}), 503
        
    try:
        # Retrieve target container
        container = client.containers.get(container_id)
        
        # If the container has stopped, return flat zeroed metrics safely
        if container.status != "running":
            return jsonify({
                "id": container.short_id,
                "name": container.name,
                "status": container.status,
                "cpu_percentage": 0.0,
                "memory_used_mb": 0.0,
                "memory_limit_mb": 0.0,
                "memory_percentage": 0.0,
                "network_io": "0 B / 0 B",
                "uptime": "stopped",
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })
            
        # Fetch statistics snapshot (non-streaming, blocks very briefly to gather stats)
        stats = container.stats(stream=False)
        
        # 1. Calculate CPU percentage usage (standard Docker delta formula)
        cpu_stats = stats.get('cpu_stats', {})
        precpu_stats = stats.get('precpu_stats', {})
        
        cpu_usage = cpu_stats.get('cpu_usage', {})
        precpu_usage = precpu_stats.get('cpu_usage', {})
        
        cpu_delta = cpu_usage.get('total_usage', 0) - precpu_usage.get('total_usage', 0)
        system_delta = cpu_stats.get('system_cpu_usage', 0) - precpu_stats.get('system_cpu_usage', 0)
        
        online_cpus = cpu_stats.get('online_cpus', len(cpu_usage.get('percpu_usage', [1])))
        if online_cpus == 0:
            online_cpus = 1
            
        if system_delta > 0 and cpu_delta > 0:
            cpu_percent = (cpu_delta / system_delta) * online_cpus * 100.0
            cpu_percent = round(cpu_percent, 2)
        else:
            cpu_percent = 0.0
            
        # 2. Calculate RAM memory stats
        memory_stats = stats.get('memory_stats', {})
        mem_usage = memory_stats.get('usage', 0)
        mem_limit = memory_stats.get('limit', 1)  # avoid division by zero
        
        # Subtract inactive cache pages for true active application RAM allocation (Docker default)
        cache = memory_stats.get('stats', {}).get('cache', 0)
        if mem_usage > cache:
            mem_usage -= cache
            
        mem_used_mb = round(mem_usage / (1024 * 1024), 2)
        mem_limit_mb = round(mem_limit / (1024 * 1024), 2)
        mem_percent = round((mem_usage / mem_limit) * 100.0, 2)
        
        # 3. Calculate Network I/O (combine stats across all virtual ethernet cards)
        networks = stats.get('networks', {})
        rx_bytes = 0
        tx_bytes = 0
        for interface, net_data in networks.items():
            rx_bytes += net_data.get('rx_bytes', 0)
            tx_bytes += net_data.get('tx_bytes', 0)
            
        def format_bytes(bytes_count):
            if bytes_count < 1024:
                return f"{bytes_count} B"
            elif bytes_count < 1024 * 1024:
                return f"{round(bytes_count / 1024, 2)} KB"
            else:
                return f"{round(bytes_count / (1024 * 1024), 2)} MB"
                
        network_io = f"{format_bytes(rx_bytes)} / {format_bytes(tx_bytes)}"
        
        # 4. Calculate precise uptime from State Start Time compared against UTC Clock
        started_at_str = container.attrs.get('State', {}).get('StartedAt', '')
        uptime_str = "unknown"
        if started_at_str:
            try:
                base_time_str = started_at_str[:19]
                started_dt = datetime.strptime(base_time_str, "%Y-%m-%dT%H:%M:%S")
                uptime_delta = datetime.utcnow() - started_dt
                uptime_seconds = int(uptime_delta.total_seconds())
                if uptime_seconds < 0:
                    uptime_seconds = 0
                uptime_str = get_formatted_uptime(uptime_seconds)
              
            except Exception:
                uptime_str = "unknown"
                
        return jsonify({
            "id": container.short_id,
            "name": container.name,
            "status": container.status,
            "cpu_percentage": cpu_percent,
            "memory_used_mb": mem_used_mb,
            "memory_limit_mb": mem_limit_mb,
            "memory_percentage": mem_percent,
            "network_io": network_io,
            "uptime": uptime_str,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
        
    except docker.errors.NotFound:
        return jsonify({"success": False, "error": f"Container {container_id} not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/metrics")
def metrics():
    """
    Prometheus metrics scraping endpoint.
    Dynamically fetches host resource utilization and container metrics 
    directly from Docker Engine SDK, exposing them in Prometheus exposition format.
    """
    # 1. Gather Host Metrics
    try:
        cpu_pct = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        host_cpu_gauge.set(cpu_pct)
        host_ram_gauge.set(ram.percent)
        host_disk_gauge.set(disk.percent)
    except Exception as e:
        app.logger.error(f"Error collecting host metrics for Prometheus: {e}")

    # 2. Gather Container Metrics
    client = get_docker_client()
    if client:
        try:
            all_containers = client.containers.list(all=True)
            containers_total_gauge.set(len(all_containers))
            
            # Clear container gauges to prevent stale data accumulation
            container_cpu_gauge.clear()
            container_memory_used_gauge.clear()
            container_memory_limit_gauge.clear()
            container_status_gauge.clear()
            
            running_count = 0
            for c in all_containers:
                c_name = c.name
                c_id = c.short_id
                status = c.status
                is_running = 1 if status == "running" else 0
                if is_running:
                    running_count += 1
                
                # Expose container status (running/stopped/etc.)
                container_status_gauge.labels(container_name=c_name, container_id=c_id, status=status).set(is_running)
            
            containers_running_gauge.set(running_count)
        except Exception as e:
            app.logger.error(f"Error collecting container metrics for Prometheus: {e}")
    else:
        # Docker Desktop engine is offline
        containers_total_gauge.set(0)
        containers_running_gauge.set(0)
        
    return generate_latest(prometheus_registry), 200, {'Content-Type': CONTENT_TYPE_LATEST}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
