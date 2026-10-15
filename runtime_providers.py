"""
DockPulse 2.0 - Runtime Provider Abstraction Layer
Dual-runtime provider architecture supporting:
1. Docker Mode: Docker Python SDK -> Docker Engine -> Docker Containers
2. Kubernetes Mode: Kubernetes Python Client -> Kubernetes API -> Pods, Deployments, Services
"""

import os
import time
from abc import ABC, abstractmethod
from datetime import datetime

# Optional imports handled gracefully
try:
    import docker
    DOCKER_AVAILABLE = True
except ImportError:
    docker = None
    DOCKER_AVAILABLE = False

try:
    import kubernetes
    from kubernetes import client as k8s_client, config as k8s_config
    KUBERNETES_AVAILABLE = True
except ImportError:
    kubernetes = None
    k8s_client = None
    k8s_config = None
    KUBERNETES_AVAILABLE = False


def format_uptime_seconds(seconds):
    """Converts seconds into human-readable uptime format."""
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


class BaseRuntimeProvider(ABC):
    """Abstract base class for DockPulse container and orchestrator runtimes."""

    @abstractmethod
    def get_runtime_name(self) -> str:
        """Returns runtime display name ('Docker' or 'Kubernetes')."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Checks if the underlying daemon/API is accessible."""
        pass

    @abstractmethod
    def get_workloads(self) -> dict:
        """Returns registered workloads (containers or pods/deployments/services)."""
        pass

    @abstractmethod
    def get_workload_detail(self, workload_id: str) -> dict:
        """Returns telemetry or inspection details for a specific workload unit."""
        pass

    @abstractmethod
    def execute_workload_action(self, workload_id: str, action: str) -> dict:
        """Executes lifecycle action (start, stop, restart, delete)."""
        pass

    @abstractmethod
    def scale_workload(self, deployment_name: str, target_replicas: int, wait_timeout: int = 30) -> dict:
        """Scales workload replicas and verifies active state."""
        pass

    @abstractmethod
    def get_scaling_status(self, deployment_name: str) -> dict:
        """Returns current replica counts and scaling status."""
        pass

    @abstractmethod
    def get_summary(self) -> dict:
        """Returns aggregate workload counters."""
        pass


class DockerProvider(BaseRuntimeProvider):
    """
    Docker Runtime Provider:
    Interfaces with Docker Desktop daemon via the official Python Docker SDK.
    """

    def __init__(self):
        self._client = None
        self._last_check_time = 0
        self._is_online = False

    def _get_client(self):
        """Lazily connects or reconnects to Docker Engine."""
        now = time.time()
        # Cache connection status for 3 seconds to avoid ping storm
        if self._client is not None and (now - self._last_check_time < 3):
            return self._client if self._is_online else None

        if not DOCKER_AVAILABLE:
            self._is_online = False
            return None

        try:
            client = docker.from_env()
            client.ping()
            self._client = client
            self._is_online = True
            self._last_check_time = now
            return self._client
        except Exception:
            self._is_online = False
            self._last_check_time = now
            return None

    def get_runtime_name(self) -> str:
        return "Docker"

    def is_available(self) -> bool:
        return self._get_client() is not None

    def get_workloads(self) -> dict:
        """Fetches registered containers from Docker Engine."""
        client = self._get_client()
        if not client:
            return {"containers": [], "pods": [], "deployments": [], "services": []}

        try:
            all_containers = client.containers.list(all=True)
            containers_list = []
            for c in all_containers:
                restart_count = c.attrs.get('RestartCount', 0)
                created_at = c.attrs.get('Created', '')
                state_status = c.attrs.get('State', {}).get('Status', c.status)
                containers_list.append({
                    "id": c.short_id,
                    "name": c.name,
                    "status": c.status,
                    "state": state_status,
                    "image": c.attrs.get('Config', {}).get('Image', ''),
                    "restart_count": restart_count,
                    "created_at": created_at,
                    "kind": "container"
                })

            return {
                "containers": containers_list,
                "pods": [],
                "deployments": [],
                "services": []
            }
        except Exception as e:
            return {"containers": [], "error": str(e)}

    def get_workload_detail(self, workload_id: str) -> dict:
        """Fetches real-time CPU, RAM, Network I/O metrics for a specific container."""
        client = self._get_client()
        if not client:
            return {"success": False, "error": "Docker Engine not detected"}

        try:
            container = client.containers.get(workload_id)
            restart_count = container.attrs.get('RestartCount', 0)

            if container.status != "running":
                return {
                    "id": container.short_id,
                    "name": container.name,
                    "status": container.status,
                    "cpu_percentage": 0.0,
                    "memory_used_mb": 0.0,
                    "memory_limit_mb": 0.0,
                    "memory_percentage": 0.0,
                    "network_io": "0 B / 0 B",
                    "uptime": "stopped",
                    "restart_count": restart_count,
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                }

            stats = container.stats(stream=False)
            cpu_stats = stats.get('cpu_stats', {})
            precpu_stats = stats.get('precpu_stats', {})
            cpu_usage = cpu_stats.get('cpu_usage', {})
            precpu_usage = precpu_stats.get('cpu_usage', {})

            cpu_delta = cpu_usage.get('total_usage', 0) - precpu_usage.get('total_usage', 0)
            system_delta = cpu_stats.get('system_cpu_usage', 0) - precpu_stats.get('system_cpu_usage', 0)
            online_cpus = cpu_stats.get('online_cpus', len(cpu_usage.get('percpu_usage', [1]))) or 1

            cpu_percent = 0.0
            if system_delta > 0 and cpu_delta > 0:
                cpu_percent = round((cpu_delta / system_delta) * online_cpus * 100.0, 2)

            memory_stats = stats.get('memory_stats', {})
            mem_usage = memory_stats.get('usage', 0)
            mem_limit = memory_stats.get('limit', 1)
            cache = memory_stats.get('stats', {}).get('cache', 0)
            if mem_usage > cache:
                mem_usage -= cache

            mem_used_mb = round(mem_usage / (1024 * 1024), 2)
            mem_limit_mb = round(mem_limit / (1024 * 1024), 2)
            mem_percent = round((mem_usage / mem_limit) * 100.0, 2) if mem_limit > 0 else 0.0

            networks = stats.get('networks', {})
            rx_bytes = sum(net.get('rx_bytes', 0) for net in networks.values())
            tx_bytes = sum(net.get('tx_bytes', 0) for net in networks.values())

            def fmt_bytes(b):
                if b < 1024:
                    return f"{b} B"
                elif b < 1024 * 1024:
                    return f"{round(b / 1024, 2)} KB"
                return f"{round(b / (1024 * 1024), 2)} MB"

            started_at_str = container.attrs.get('State', {}).get('StartedAt', '')
            uptime_str = "unknown"
            if started_at_str:
                try:
                    started_dt = datetime.strptime(started_at_str[:19], "%Y-%m-%dT%H:%M:%S")
                    delta = (datetime.utcnow() - started_dt).total_seconds()
                    uptime_str = format_uptime_seconds(max(0, delta))
                except Exception:
                    uptime_str = "unknown"

            return {
                "id": container.short_id,
                "name": container.name,
                "status": container.status,
                "cpu_percentage": cpu_percent,
                "memory_used_mb": mem_used_mb,
                "memory_limit_mb": mem_limit_mb,
                "memory_percentage": mem_percent,
                "network_io": f"{fmt_bytes(rx_bytes)} / {fmt_bytes(tx_bytes)}",
                "uptime": uptime_str,
                "restart_count": restart_count,
                "timestamp": datetime.now().strftime("%H:%M:%S")
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def execute_workload_action(self, workload_id: str, action: str) -> dict:
        """Executes start, stop, restart with safety guard."""
        client = self._get_client()
        if not client:
            return {"success": False, "error": "Docker Engine not detected"}

        try:
            container = client.containers.get(workload_id)
            c_name = container.name.lower()
            protected = ["dockpulse", "dockpulse-dashboard", "dockpulse-cadvisor", "dockpulse-prometheus"]

            if c_name in protected and action == "stop":
                return {
                    "success": False,
                    "error": "Safety Guard Activated: DockPulse core monitoring infrastructure cannot be stopped from its own dashboard."
                }

            if action == "start":
                container.start()
                msg = f"Container '{container.name}' started successfully."
            elif action == "stop":
                container.stop(timeout=5)
                msg = f"Container '{container.name}' stopped."
            elif action == "restart":
                container.restart(timeout=5)
                msg = f"Container '{container.name}' restarted successfully."
            else:
                return {"success": False, "error": f"Invalid action: {action}"}

            return {
                "success": True,
                "message": msg,
                "action": action,
                "container_id": container.short_id,
                "container_name": container.name
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def scale_workload(self, deployment_name: str, target_replicas: int, wait_timeout: int = 30) -> dict:
        """In Docker-only mode, horizontal scaling is done via docker compose scale."""
        return {
            "success": False,
            "error": "Docker standalone mode active. For live horizontal autoscaling, run in Kubernetes mode or use 'docker compose up --scale dockpulse=N'."
        }

    def get_scaling_status(self, deployment_name: str) -> dict:
        """Returns default replica info for Docker mode."""
        return {
            "name": deployment_name,
            "desired_replicas": 1,
            "current_replicas": 1,
            "ready_replicas": 1,
            "available_replicas": 1,
            "runtime": "Docker"
        }

    def get_summary(self) -> dict:
        workloads = self.get_workloads()
        containers = workloads.get("containers", [])
        total = len(containers)
        running = sum(1 for c in containers if c.get("status") == "running")
        return {
            "runtime": "Docker",
            "total_workloads": total,
            "running_workloads": running,
            "stopped_workloads": total - running
        }


class KubernetesProvider(BaseRuntimeProvider):
    """
    Kubernetes Runtime Provider:
    Interfaces with Kubernetes API via the official Python Kubernetes Client.
    Supports in-cluster ServiceAccount token or local kubeconfig.
    Provides Pod telemetry, Deployment tracking, Service discovery, and REAL Deployment Scaling.
    """

    def __init__(self):
        self._core_v1 = None
        self._apps_v1 = None
        self._namespace = "default"
        self._is_online = False
        self._last_check_time = 0
        self._init_client()

    def _init_client(self):
        """Attempts to load in-cluster config or local kubeconfig."""
        if not KUBERNETES_AVAILABLE:
            self._is_online = False
            return

        # 1. Determine namespace from in-cluster secret if present
        ns_path = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
        if os.path.exists(ns_path):
            try:
                with open(ns_path, "r") as f:
                    self._namespace = f.read().strip() or "default"
            except Exception:
                self._namespace = "default"
        else:
            self._namespace = os.environ.get("KUBERNETES_NAMESPACE", "default")

        # 2. Try in-cluster configuration first
        try:
            k8s_config.load_incluster_config()
            self._core_v1 = k8s_client.CoreV1Api()
            self._apps_v1 = k8s_client.AppsV1Api()
            self._is_online = True
            return
        except Exception:
            pass

        # 3. Fallback to local kubeconfig
        try:
            k8s_config.load_kube_config()
            self._core_v1 = k8s_client.CoreV1Api()
            self._apps_v1 = k8s_client.AppsV1Api()
            self._is_online = True
        except Exception:
            self._is_online = False

    def get_runtime_name(self) -> str:
        return "Kubernetes"

    def is_available(self) -> bool:
        if not self._is_online or self._core_v1 is None:
            self._init_client()
        if not self._is_online:
            return False

        now = time.time()
        if now - self._last_check_time < 3:
            return self._is_online

        try:
            # Lightweight health check
            self._core_v1.get_api_resources()
            self._is_online = True
            self._last_check_time = now
            return True
        except Exception:
            self._is_online = False
            self._last_check_time = now
            return False

    def get_workloads(self) -> dict:
        """Fetches real Pods, Deployments, and Services from Kubernetes API."""
        if not self.is_available():
            return {"containers": [], "pods": [], "deployments": [], "services": [], "error": "Kubernetes API unreachable"}

        pods_list = []
        deployments_list = []
        services_list = []

        # 1. Fetch Pods
        try:
            pods_resp = self._core_v1.list_namespaced_pod(namespace=self._namespace)
            for pod in pods_resp.items:
                p_name = pod.metadata.name
                phase = pod.status.phase or "Unknown"

                # Calculate restart count and ready containers
                total_c = len(pod.spec.containers)
                ready_c = 0
                restarts = 0
                image = pod.spec.containers[0].image if pod.spec.containers else ""

                if pod.status.container_statuses:
                    for cs in pod.status.container_statuses:
                        restarts += cs.restart_count
                        if cs.ready:
                            ready_c += 1

                created_at = pod.metadata.creation_timestamp.isoformat() if pod.metadata.creation_timestamp else ""

                pod_dict = {
                    "id": p_name[:12],
                    "pod_uid": pod.metadata.uid,
                    "name": p_name,
                    "namespace": pod.metadata.namespace,
                    "status": phase.lower() if ready_c == total_c and phase == "Running" else phase,
                    "state": phase.lower(),
                    "phase": phase,
                    "ready": f"{ready_c}/{total_c}",
                    "restart_count": restarts,
                    "image": image,
                    "pod_ip": pod.status.pod_ip or "Pending",
                    "node_name": pod.spec.node_name or "Pending",
                    "created_at": created_at,
                    "kind": "pod"
                }
                pods_list.append(pod_dict)
        except Exception as e:
            print(f"Error fetching pods: {e}")

        # 2. Fetch Deployments
        try:
            deps_resp = self._apps_v1.list_namespaced_deployment(namespace=self._namespace)
            for dep in deps_resp.items:
                d_name = dep.metadata.name
                desired = dep.spec.replicas or 0
                current = dep.status.replicas or 0
                ready = dep.status.ready_replicas or 0
                available = dep.status.available_replicas or 0
                img = dep.spec.template.spec.containers[0].image if dep.spec.template.spec.containers else ""

                deployments_list.append({
                    "name": d_name,
                    "namespace": dep.metadata.namespace,
                    "desired_replicas": desired,
                    "current_replicas": current,
                    "ready_replicas": ready,
                    "available_replicas": available,
                    "image": img,
                    "kind": "deployment"
                })
        except Exception as e:
            print(f"Error fetching deployments: {e}")

        # 3. Fetch Services
        try:
            svcs_resp = self._core_v1.list_namespaced_service(namespace=self._namespace)
            for svc in svcs_resp.items:
                s_name = svc.metadata.name
                s_type = svc.spec.type or "ClusterIP"
                cluster_ip = svc.spec.cluster_ip or "None"

                ports = []
                if svc.spec.ports:
                    for p in svc.spec.ports:
                        p_str = f"{p.port}"
                        if p.node_port:
                            p_str += f":{p.node_port}"
                        p_str += f"/{p.protocol}"
                        ports.append(p_str)

                services_list.append({
                    "name": s_name,
                    "namespace": svc.metadata.namespace,
                    "type": s_type,
                    "cluster_ip": cluster_ip,
                    "ports": ", ".join(ports),
                    "kind": "service"
                })
        except Exception as e:
            print(f"Error fetching services: {e}")

        return {
            "containers": [],  # Do not mix Kubernetes pods into Docker container list
            "pods": pods_list,
            "deployments": deployments_list,
            "services": services_list
        }

    def get_workload_detail(self, workload_id: str) -> dict:
        """Fetches detailed information for a specific Kubernetes Pod."""
        if not self.is_available():
            return {"success": False, "error": "Kubernetes API unreachable"}

        try:
            pods_resp = self._core_v1.list_namespaced_pod(namespace=self._namespace)
            target_pod = None
            for p in pods_resp.items:
                if p.metadata.name == workload_id or p.metadata.name.startswith(workload_id):
                    target_pod = p
                    break

            if not target_pod:
                return {"success": False, "error": f"Pod '{workload_id}' not found"}

            restarts = 0
            if target_pod.status.container_statuses:
                restarts = sum(cs.restart_count for cs in target_pod.status.container_statuses)

            # Calculate uptime from startTime
            uptime_str = "unknown"
            if target_pod.status.start_time:
                delta = (datetime.utcnow().timestamp() - target_pod.status.start_time.timestamp())
                uptime_str = format_uptime_seconds(max(0, delta))

            # Extract resource requests/limits from pod spec
            resources = {}
            if target_pod.spec.containers:
                c0 = target_pod.spec.containers[0]
                resources = {
                    "limits": c0.resources.limits if c0.resources else {},
                    "requests": c0.resources.requests if c0.resources else {}
                }

            return {
                "id": target_pod.metadata.name[:12],
                "name": target_pod.metadata.name,
                "namespace": target_pod.metadata.namespace,
                "status": target_pod.status.phase,
                "pod_ip": target_pod.status.pod_ip or "Pending",
                "node_name": target_pod.spec.node_name or "Pending",
                "restart_count": restarts,
                "uptime": uptime_str,
                "resources": resources,
                "cpu_percentage": 0.0,
                "memory_used_mb": 0.0,
                "memory_limit_mb": 512.0,
                "memory_percentage": 0.0,
                "network_io": "K8s CNI Interface",
                "timestamp": datetime.now().strftime("%H:%M:%S")
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def execute_workload_action(self, workload_id: str, action: str) -> dict:
        """Executes Pod lifecycle action (delete/restart pod so ReplicaSet recreates it)."""
        if not self.is_available():
            return {"success": False, "error": "Kubernetes API unreachable"}

        try:
            pods_resp = self._core_v1.list_namespaced_pod(namespace=self._namespace)
            target_pod_name = None
            for p in pods_resp.items:
                if p.metadata.name == workload_id or p.metadata.name.startswith(workload_id):
                    target_pod_name = p.metadata.name
                    break

            if not target_pod_name:
                return {"success": False, "error": f"Pod '{workload_id}' not found"}

            if action in ["restart", "delete", "stop"]:
                self._core_v1.delete_namespaced_pod(name=target_pod_name, namespace=self._namespace)
                msg = f"Pod '{target_pod_name}' deleted. Kubernetes ReplicaSet is reconciling and launching a fresh replacement Pod."
                return {
                    "success": True,
                    "message": msg,
                    "action": "pod_restarted",
                    "container_id": target_pod_name[:12],
                    "container_name": target_pod_name
                }

            return {"success": False, "error": f"Action '{action}' is not supported for Kubernetes Pods."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def scale_workload(self, deployment_name: str, target_replicas: int, wait_timeout: int = 30) -> dict:
        """
        REAL KUBERNETES SCALING:
        1. Calls Kubernetes AppsV1 API to patch the Deployment's scale.
        2. Polls Deployment status until actual pods match target replicas.
        3. Returns verified confirmation or explicit failure.
        """
        if not self.is_available():
            return {"success": False, "error": "Kubernetes API unreachable. Cannot scale deployment."}

        try:
            # 1. Read current deployment
            dep = self._apps_v1.read_namespaced_deployment(name=deployment_name, namespace=self._namespace)
            current_replicas = dep.spec.replicas

            if current_replicas == target_replicas:
                return {
                    "success": True,
                    "message": f"Deployment '{deployment_name}' is already at desired capacity of {target_replicas} replicas.",
                    "current_replicas": current_replicas,
                    "desired_replicas": target_replicas,
                    "ready_replicas": dep.status.ready_replicas or 0,
                    "available_replicas": dep.status.available_replicas or 0,
                    "verified": True
                }

            # 2. Actually patch Deployment replica count via Kubernetes API
            scale_body = {"spec": {"replicas": int(target_replicas)}}
            self._apps_v1.patch_namespaced_deployment_scale(
                name=deployment_name,
                namespace=self._namespace,
                body=scale_body
            )

            # 3. Verification Loop: Wait and poll until Kubernetes reconciles
            start_time = time.time()
            verified = False
            last_status = {}

            while (time.time() - start_time) < wait_timeout:
                time.sleep(1.5)
                check_dep = self._apps_v1.read_namespaced_deployment(name=deployment_name, namespace=self._namespace)
                spec_reps = check_dep.spec.replicas
                ready_reps = check_dep.status.ready_replicas or 0
                avail_reps = check_dep.status.available_replicas or 0
                status_reps = check_dep.status.replicas or 0

                last_status = {
                    "spec_replicas": spec_reps,
                    "status_replicas": status_reps,
                    "ready_replicas": ready_reps,
                    "available_replicas": avail_reps
                }

                # Condition for successful verification:
                # Target reached and ready replicas match target (or ready >= target for scale up, ready <= target for scale down)
                if spec_reps == target_replicas and ready_reps == target_replicas and avail_reps == target_replicas:
                    verified = True
                    break

            if verified:
                msg = f"Kubernetes Scale Verified: Deployment '{deployment_name}' scaled from {current_replicas} → {target_replicas} replicas. (All {target_replicas} Pods Ready & Available)."
                return {
                    "success": True,
                    "message": msg,
                    "current_replicas": current_replicas,
                    "target_replicas": target_replicas,
                    "verified": True,
                    "status": last_status
                }
            else:
                # If timeout occurred, check if spec took effect even if pods are still booting
                check_dep = self._apps_v1.read_namespaced_deployment(name=deployment_name, namespace=self._namespace)
                ready_reps = check_dep.status.ready_replicas or 0
                if check_dep.spec.replicas == target_replicas:
                    msg = f"Scale patched to {target_replicas} replicas. Reconciliation in progress ({ready_reps}/{target_replicas} ready within {wait_timeout}s timeout)."
                    return {
                        "success": True,
                        "message": msg,
                        "current_replicas": current_replicas,
                        "target_replicas": target_replicas,
                        "verified": False,
                        "status": last_status
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to patch deployment replicas. Current spec: {check_dep.spec.replicas}, expected: {target_replicas}"
                    }

        except Exception as e:
            return {"success": False, "error": f"Kubernetes API error: {str(e)}"}

    def get_scaling_status(self, deployment_name: str) -> dict:
        """Reads live replica metrics for deployment."""
        if not self.is_available():
            return {
                "name": deployment_name,
                "desired_replicas": 1,
                "current_replicas": 1,
                "ready_replicas": 1,
                "available_replicas": 1,
                "available": False
            }

        try:
            dep = self._apps_v1.read_namespaced_deployment(name=deployment_name, namespace=self._namespace)
            return {
                "name": deployment_name,
                "desired_replicas": dep.spec.replicas or 1,
                "current_replicas": dep.status.replicas or 0,
                "ready_replicas": dep.status.ready_replicas or 0,
                "available_replicas": dep.status.available_replicas or 0,
                "available": True,
                "runtime": "Kubernetes"
            }
        except Exception as e:
            return {
                "name": deployment_name,
                "desired_replicas": 1,
                "current_replicas": 1,
                "ready_replicas": 1,
                "available_replicas": 1,
                "available": False,
                "error": str(e)
            }

    def get_summary(self) -> dict:
        workloads = self.get_workloads()
        pods = workloads.get("pods", [])
        deps = workloads.get("deployments", [])
        svcs = workloads.get("services", [])
        running = sum(1 for p in pods if p.get("state") == "running" or p.get("phase") == "Running")

        return {
            "runtime": "Kubernetes",
            "total_workloads": len(pods),
            "running_workloads": running,
            "stopped_workloads": len(pods) - running,
            "total_deployments": len(deps),
            "total_services": len(svcs)
        }


class RuntimeManager:
    """
    Central Runtime Manager & Factory:
    Automatically identifies whether DockPulse is running under Docker Compose or Kubernetes,
    instantiates the appropriate provider, and handles graceful runtime queries.
    """

    def __init__(self):
        self._docker_provider = DockerProvider()
        self._k8s_provider = KubernetesProvider()
        self._forced_runtime = os.environ.get("DOCKPULSE_RUNTIME", "").strip().lower()

    def set_runtime(self, runtime_name: str) -> bool:
        """Allows dynamically selecting active runtime ('docker' or 'kubernetes')."""
        if runtime_name and runtime_name.lower() in ["docker", "kubernetes"]:
            self._forced_runtime = runtime_name.lower()
            return True
        elif runtime_name and runtime_name.lower() in ["auto", "reset", "default"]:
            self._forced_runtime = ""
            return True
        return False

    def detect_runtime(self) -> str:
        """
        Determines active runtime:
        1. Check explicit operator selection or DOCKPULSE_RUNTIME override.
        2. Detect in-cluster Kubernetes environment (KUBERNETES_SERVICE_HOST or serviceaccount token).
        3. Detect Docker Engine via socket connection (primary for compose deployment).
        4. Detect standalone Kubernetes cluster via kubeconfig if Docker is unavailable.
        5. Fallback to Docker.
        """
        if self._forced_runtime == "kubernetes":
            return "Kubernetes"
        if self._forced_runtime == "docker":
            return "Docker"

        # Check 1: In-cluster Kubernetes Pod indicators
        is_in_cluster = (
            os.environ.get("KUBERNETES_SERVICE_HOST") is not None or
            os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token")
        )
        if is_in_cluster and self._k8s_provider.is_available():
            return "Kubernetes"

        # Check 2: When running on Docker Engine (e.g. Docker Compose), select Docker as
        # primary container runtime while keeping Kubernetes monitoring fully available
        if self._docker_provider.is_available():
            return "Docker"

        # Check 3: If Docker is unavailable, fall back to Kubernetes
        if self._k8s_provider.is_available():
            return "Kubernetes"

        # Fallback
        return "Docker"

    def get_active_provider(self) -> BaseRuntimeProvider:
        """Returns the currently active BaseRuntimeProvider implementation."""
        runtime = self.detect_runtime()
        if runtime == "Kubernetes":
            return self._k8s_provider
        return self._docker_provider

    def get_k8s_provider(self) -> KubernetesProvider:
        """Returns the KubernetesProvider directly (for scaling or k8s bridge operations)."""
        return self._k8s_provider

    def get_docker_provider(self) -> DockerProvider:
        """Returns the DockerProvider directly."""
        return self._docker_provider

    def get_runtime_info(self) -> dict:
        """Returns runtime diagnostic state for UI badges and API consumers."""
        active_runtime = self.detect_runtime()
        provider = self.get_active_provider()
        is_online = provider.is_available()

        return {
            "runtime": active_runtime,
            "mode": active_runtime.lower(),
            "available": is_online,
            "docker_available": self._docker_provider.is_available(),
            "kubernetes_available": self._k8s_provider.is_available(),
            "in_cluster": os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token"),
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }


# Singleton instance for DockPulse 2.0 application
runtime_manager = RuntimeManager()
