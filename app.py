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

app = Flask(__name__)

# Thread-safe global store for host system metrics history (last 20 data points)
# Deque automatically drops the oldest item when it exceeds maxlen.
METRIC_HISTORY_LIMIT = 20
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
