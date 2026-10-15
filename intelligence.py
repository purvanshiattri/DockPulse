"""
DockPulse 2.0 - Intelligence & Workload Management Engine
Provides:
1. Configurable Threshold Management
2. Rolling In-Memory Event & Alert Bus
3. Lightweight Statistical Trend Analysis (Linear Regression / Rate of Change)
4. Multi-Condition Anomaly Detection (Sustained load, spikes, container health)
5. AI-Style Workload Recommendation Engine
6. Kubernetes Horizontal Workload Balancing / Autoscaler Model
"""

import time
import math
import re
import os
import threading
from datetime import datetime
from collections import deque


class ThresholdConfig:
    """Manages configurable operational thresholds and evaluation parameters."""
    def __init__(self):
        self.lock = threading.Lock()
        # System & Container CPU thresholds (%)
        self.cpu_warning = 70.0
        self.cpu_critical = 85.0
        
        # System & Container RAM thresholds (%)
        self.memory_warning = 75.0
        self.memory_critical = 90.0
        
        # Rate of change / Spike threshold (% delta in short window)
        self.spike_threshold = 25.0
        
        # Rolling window evaluation sample count
        self.window_samples = 6  # ~12 seconds with 2s polling
        
        # Autoscaling target CPU utilization (%)
        self.target_cpu_utilization = 70.0
        self.min_replicas = 2  # Baseline high-availability minimum (per k8s/deployment.yaml)
        self.max_replicas = 10
        self.scale_down_threshold = 30.0

    def to_dict(self):
        with self.lock:
            return {
                "cpu_warning": self.cpu_warning,
                "cpu_critical": self.cpu_critical,
                "memory_warning": self.memory_warning,
                "memory_critical": self.memory_critical,
                "spike_threshold": self.spike_threshold,
                "window_samples": self.window_samples,
                "target_cpu_utilization": self.target_cpu_utilization,
                "min_replicas": self.min_replicas,
                "max_replicas": self.max_replicas,
                "scale_down_threshold": self.scale_down_threshold
            }

    def update(self, data):
        with self.lock:
            if "cpu_warning" in data:
                self.cpu_warning = float(data["cpu_warning"])
            if "cpu_critical" in data:
                self.cpu_critical = float(data["cpu_critical"])
            if "memory_warning" in data:
                self.memory_warning = float(data["memory_warning"])
            if "memory_critical" in data:
                self.memory_critical = float(data["memory_critical"])
            if "spike_threshold" in data:
                self.spike_threshold = float(data["spike_threshold"])
            if "window_samples" in data:
                self.window_samples = max(3, min(30, int(data["window_samples"])))
            if "target_cpu_utilization" in data:
                self.target_cpu_utilization = float(data["target_cpu_utilization"])
            if "min_replicas" in data:
                self.min_replicas = max(1, int(data["min_replicas"]))
            if "max_replicas" in data:
                self.max_replicas = max(self.min_replicas, int(data["max_replicas"]))
            if "scale_down_threshold" in data:
                self.scale_down_threshold = float(data["scale_down_threshold"])


class EventLogManager:
    """Thread-safe rolling ring buffer for system, container, and AI recommendation events."""
    def __init__(self, maxlen=100):
        self.events = deque(maxlen=maxlen)
        self.lock = threading.Lock()
        self._last_event_keys = {}  # Throttle repetitive duplicate alerts

    def add_event(self, severity, title, message, source="system", throttle_seconds=10):
        """
        Adds an event if not identical to a recent event within throttle_seconds.
        Severity: 'CRITICAL', 'WARNING', 'INFO', 'RECOMMENDATION'
        """
        key = f"{severity}:{title}:{source}"
        now_ts = time.time()
        
        with self.lock:
            last_ts = self._last_event_keys.get(key, 0)
            if now_ts - last_ts < throttle_seconds:
                return  # Throttled duplicate

            self._last_event_keys[key] = now_ts
            event = {
                "id": f"evt-{int(now_ts * 1000)}",
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "severity": severity.upper(),
                "title": title,
                "message": message,
                "source": source
            }
            self.events.appendleft(event)

    def get_events(self, limit=50, severity=None):
        with self.lock:
            result = list(self.events)
        if severity:
            result = [e for e in result if e["severity"] == severity.upper()]
        return result[:limit]


class TrendAnalyzer:
    """
    Lightweight statistical trend analysis engine using first-order linear regression.
    Evaluates metric velocity (slope m in %/min) and estimates time to threshold breach.
    Does NOT require numpy or heavy ML libraries.
    """
    @staticmethod
    def calculate_linear_trend(values, interval_sec=2.0):
        """
        Calculates least-squares linear slope:
        y = mx + c
        Returns:
            slope_per_min: slope scaled to change per minute (%)
            direction: 'UPWARD', 'DOWNWARD', 'STABLE'
            r_squared: correlation coefficient strength [0, 1]
        """
        n = len(values)
        if n < 4:
            return {
                "slope_per_min": 0.0,
                "direction": "STABLE",
                "r_squared": 0.0,
                "description": "Insufficient history for trend calculation"
            }

        # x values in minutes (0, dt, 2*dt, ...)
        dt_min = interval_sec / 60.0
        x = [i * dt_min for i in range(n)]
        y = [float(v) for v in values]

        sum_x = sum(x)
        sum_y = sum(y)
        sum_xx = sum(xi * xi for xi in x)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))

        denominator = (n * sum_xx) - (sum_x * sum_x)
        if abs(denominator) < 1e-9:
            slope = 0.0
        else:
            slope = ((n * sum_xy) - (sum_x * sum_y)) / denominator

        # Mean and R^2 evaluation
        mean_y = sum_y / n
        ss_tot = sum((yi - mean_y) ** 2 for yi in y)
        intercept = (sum_y - slope * sum_x) / n
        ss_res = sum((yi - (slope * xi + intercept)) ** 2 for xi, yi in zip(x, y))

        r_squared = 0.0
        if ss_tot > 1e-6:
            r_squared = max(0.0, min(1.0, 1.0 - (ss_res / ss_tot)))

        # Categorize direction (threshold: +/- 1.5% per minute change)
        if slope > 1.5:
            direction = "UPWARD"
            description = f"Trending upward (+{slope:.1f}%/min)"
        elif slope < -1.5:
            direction = "DOWNWARD"
            description = f"Trending downward ({slope:.1f}%/min)"
        else:
            direction = "STABLE"
            description = "Metric trajectory is stable"

        return {
            "slope_per_min": round(slope, 2),
            "direction": direction,
            "r_squared": round(r_squared, 2),
            "description": description
        }

    @staticmethod
    def estimate_breach_time(current_val, slope_per_min, threshold):
        """
        Estimates minutes until threshold breach if current upward slope persists.
        Returns: estimated_minutes (int or float) or None if not approaching.
        """
        if slope_per_min <= 0.5:
            return None
        if current_val >= threshold:
            return 0  # Already breached

        diff = threshold - current_val
        mins = diff / slope_per_min
        if mins > 120:  # Beyond reasonable prediction horizon
            return None
        return round(mins, 1)


class AnomalyDetector:
    """
    Detects sustained threshold breaches, sudden resource spikes,
    and container health degradation.
    """
    def __init__(self, config: ThresholdConfig, event_mgr: EventLogManager):
        self.config = config
        self.event_mgr = event_mgr

    def analyze_host(self, history):
        """
        Analyzes host CPU & RAM rolling history.
        Returns:
            status: 'NORMAL', 'WARNING', 'CRITICAL'
            issues: list of detected issue strings
            trend: trend analysis dict for CPU
        """
        if not history:
            return {
                "status": "NORMAL",
                "condition": "Healthy",
                "issues": [],
                "trend": {"direction": "STABLE", "description": "Awaiting telemetry"}
            }

        cfg = self.config
        window_size = min(len(history), cfg.window_samples)
        recent_window = list(history)[-window_size:]
        
        cpu_vals = [p.get("cpu_percentage", 0.0) for p in recent_window]
        ram_vals = [p.get("ram_percentage", 0.0) for p in recent_window]
        
        latest_cpu = cpu_vals[-1]
        latest_ram = ram_vals[-1]
        avg_cpu = sum(cpu_vals) / len(cpu_vals)
        avg_ram = sum(ram_vals) / len(ram_vals)

        # Full history CPU values for trend regression
        all_cpu_vals = [p.get("cpu_percentage", 0.0) for p in history]
        trend_info = TrendAnalyzer.calculate_linear_trend(all_cpu_vals[-15:])

        issues = []
        status = "NORMAL"

        # 1. Critical sustained CPU
        if avg_cpu >= cfg.cpu_critical:
            status = "CRITICAL"
            issue_msg = f"Sustained high Host CPU utilization (Avg {avg_cpu:.1f}% >= {cfg.cpu_critical}%)"
            issues.append(issue_msg)
            self.event_mgr.add_event("CRITICAL", "High CPU Threshold Exceeded", issue_msg, "Host")
        elif avg_cpu >= cfg.cpu_warning:
            if status != "CRITICAL":
                status = "WARNING"
            issue_msg = f"Elevated Host CPU utilization (Avg {avg_cpu:.1f}% >= {cfg.cpu_warning}%)"
            issues.append(issue_msg)
            self.event_mgr.add_event("WARNING", "Host CPU Warning", issue_msg, "Host")

        # 2. Critical sustained RAM
        if avg_ram >= cfg.memory_critical:
            status = "CRITICAL"
            issue_msg = f"Sustained high Host RAM saturation (Avg {avg_ram:.1f}% >= {cfg.memory_critical}%)"
            issues.append(issue_msg)
            self.event_mgr.add_event("CRITICAL", "Memory Threshold Exceeded", issue_msg, "Host")
        elif avg_ram >= cfg.memory_warning:
            if status != "CRITICAL":
                status = "WARNING"
            issue_msg = f"Elevated Host RAM consumption (Avg {avg_ram:.1f}% >= {cfg.memory_warning}%)"
            issues.append(issue_msg)
            self.event_mgr.add_event("WARNING", "Host RAM Warning", issue_msg, "Host")

        # 3. Sudden resource spike detection (difference between min and max in window)
        if len(cpu_vals) >= 3:
            cpu_delta = max(cpu_vals) - min(cpu_vals)
            if cpu_delta >= cfg.spike_threshold:
                if status == "NORMAL":
                    status = "WARNING"
                spike_msg = f"Sudden Host CPU spike detected (jumped +{cpu_delta:.1f}% in recent window)"
                issues.append(spike_msg)
                self.event_mgr.add_event("WARNING", "CPU Spike Detected", spike_msg, "Host")

        # 4. Trend trajectory prediction
        if trend_info["direction"] == "UPWARD" and latest_cpu < cfg.cpu_critical:
            mins_to_crit = TrendAnalyzer.estimate_breach_time(latest_cpu, trend_info["slope_per_min"], cfg.cpu_critical)
            if mins_to_crit is not None:
                trend_msg = f"CPU trending upward (+{trend_info['slope_per_min']}%/min). High CPU condition likely in ~{mins_to_crit}m if trend continues."
                trend_info["prediction"] = trend_msg
                if status == "NORMAL" and mins_to_crit <= 10:
                    status = "WARNING"
                    issues.append(trend_msg)
                    self.event_mgr.add_event("WARNING", "Predicted Resource Exhaustion", trend_msg, "Predictor")

        return {
            "status": status,
            "condition": "Critical Alert" if status == "CRITICAL" else ("Warning" if status == "WARNING" else "Healthy"),
            "issues": issues,
            "trend": trend_info,
            "latest_cpu": round(latest_cpu, 1),
            "latest_ram": round(latest_ram, 1),
            "avg_cpu": round(avg_cpu, 1),
            "avg_ram": round(avg_ram, 1),
            "cpu_warning": cfg.cpu_warning,
            "cpu_critical": cfg.cpu_critical
        }

    def analyze_containers(self, containers_data):
        """
        Analyzes container health status, restart counts, and per-container metrics.
        Returns aggregate status and list of container issues.
        """
        issues = []
        worst_status = "NORMAL"

        for c in containers_data:
            c_name = c.get("name", "unknown")
            c_status = c.get("status", "unknown")
            restart_count = c.get("restart_count", 0)

            # Check stopped or restarting states
            if c_status in ["restarting", "dead"]:
                worst_status = "CRITICAL"
                msg = f"Container '{c_name}' is in unstable state: {c_status}"
                issues.append(msg)
                self.event_mgr.add_event("CRITICAL", "Unstable Container State", msg, c_name)
            elif c_status not in ["running", "created"]:
                if worst_status == "NORMAL":
                    worst_status = "WARNING"
                msg = f"Container '{c_name}' is {c_status}"
                issues.append(msg)

            # Check repeated restarts
            if restart_count >= 3:
                worst_status = "CRITICAL"
                msg = f"Container '{c_name}' has repeated restarts ({restart_count} times - possible crash loop)"
                issues.append(msg)
                self.event_mgr.add_event("CRITICAL", "Crash Loop Detected", msg, c_name)
            elif restart_count > 0:
                if worst_status == "NORMAL":
                    worst_status = "WARNING"
                msg = f"Container '{c_name}' restarted {restart_count} time(s)"
                issues.append(msg)
                self.event_mgr.add_event("INFO", "Container Restarted", msg, c_name)

        return {
            "status": worst_status,
            "issues": issues
        }


class RecommendationEngine:
    """
    AI-Style Recommendation Engine:
    Maps observed metrics, anomaly alerts, trend velocity, and container states
    into actionable operational suggestions.
    """
    def __init__(self, config: ThresholdConfig, event_mgr: EventLogManager):
        self.config = config
        self.event_mgr = event_mgr

    def generate_recommendations(self, host_analysis, container_analysis, scaling_decision):
        """
        Synthesizes all telemetry streams into prioritized recommendations.
        """
        recommendations = []
        cfg = self.config

        # 1. Scaling Action Recommendation
        if scaling_decision["action"] == "SCALE UP":
            rec = {
                "type": "SCALING",
                "priority": "HIGH",
                "text": f"Consider scaling workload from {scaling_decision['current_replicas']} → {scaling_decision['recommended_replicas']} replicas to alleviate sustained load. (Advisory only — operator approval required).",
                "reason": scaling_decision["reason"],
                "basis": scaling_decision.get("basis", "Rule-based HPA evaluation")
            }
            recommendations.append(rec)
            self.event_mgr.add_event("RECOMMENDATION", "Scale Up Advised", rec["text"], "Scaler")
        elif scaling_decision["action"] == "SCALE DOWN":
            rec = {
                "type": "SCALING",
                "priority": "LOW",
                "text": f"Workload load is low. Consider scaling down from {scaling_decision['current_replicas']} → {scaling_decision['recommended_replicas']} replicas to optimize resource allocation. (Advisory only — operator approval required).",
                "reason": scaling_decision["reason"],
                "basis": scaling_decision.get("basis", "Rule-based HPA evaluation")
            }
            recommendations.append(rec)

        # 2. Host CPU & Memory Sizing
        avg_cpu = host_analysis.get("avg_cpu", 0.0)
        avg_ram = host_analysis.get("avg_ram", 0.0)
        trend = host_analysis.get("trend", {})

        if avg_cpu >= cfg.cpu_critical:
            recommendations.append({
                "type": "RESOURCE",
                "priority": "HIGH",
                "text": "High CPU: Consider increasing container CPU quota limits or distributing workload across additional worker nodes.",
                "reason": f"Sustained CPU at {avg_cpu:.1f}% exceeds critical {cfg.cpu_critical}% limit."
            })
        elif trend.get("direction") == "UPWARD" and trend.get("slope_per_min", 0) > 3.0:
            recommendations.append({
                "type": "CAPACITY",
                "priority": "MEDIUM",
                "text": "Pre-emptive action: CPU trend is accelerating. Monitor background batch jobs or prepare additional replica pods.",
                "reason": f"CPU growth velocity at +{trend['slope_per_min']}%/min."
            })

        if avg_ram >= cfg.memory_critical:
            recommendations.append({
                "type": "MEMORY",
                "priority": "HIGH",
                "text": "High memory: Investigate memory-heavy workload for memory leaks or increase container memory allocation.",
                "reason": f"Sustained RAM at {avg_ram:.1f}% exceeds critical {cfg.memory_critical}% boundary."
            })

        # 3. Container-specific recommendations
        for issue in container_analysis.get("issues", []):
            if "restarts" in issue.lower() or "crash" in issue.lower():
                recommendations.append({
                    "type": "HEALTH",
                    "priority": "HIGH",
                    "text": "Repeated container restarts: Inspect application health, exit codes, logs (`docker logs`), and restart policy.",
                    "reason": issue
                })
            elif "stopped" in issue.lower() or "unstable" in issue.lower():
                recommendations.append({
                    "type": "LIFECYCLE",
                    "priority": "MEDIUM",
                    "text": "Check stopped service dependencies or run container inspection to ensure expected availability.",
                    "reason": issue
                })

        # 4. Default nominal recommendation if healthy
        if not recommendations:
            recommendations.append({
                "type": "STATUS",
                "priority": "INFO",
                "text": "All monitored services operating within nominal parameters. System health is optimal.",
                "reason": "Host and container resources remain below warning thresholds."
            })

        return recommendations


class WorkloadScaler:
    """
    Workload Balancing & Horizontal Autoscaling Recommendation Engine.
    Implements standard Kubernetes Horizontal Pod Autoscaler (HPA) algorithm:
    desiredReplicas = ceil[currentReplicas * (currentMetric / targetMetric)]
    """
    def __init__(self, config: ThresholdConfig):
        self.config = config

    def evaluate(self, current_cpu, current_replicas=2, metric_source="Pod CPU"):
        """
        Calculates recommended replicas and action using standard rule-based Kubernetes HPA algorithm.
        Does NOT use machine-learning. Explains the rule-based basis of each recommendation.
        Handles unavailable (None) or stale metrics without fabricating data.
        """
        cfg = self.config
        target = cfg.target_cpu_utilization
        min_reps = cfg.min_replicas
        max_reps = cfg.max_replicas

        if current_replicas <= 0:
            current_replicas = 2

        # 1. Handle unavailable or stale metrics explicitly
        if current_cpu is None:
            return {
                "action": "KEEP CURRENT CAPACITY",
                "current_replicas": current_replicas,
                "recommended_replicas": current_replicas,
                "target_utilization": target,
                "current_utilization": None,
                "metric_source": metric_source,
                "min_replicas": min_reps,
                "max_replicas": max_reps,
                "reason": f"Workload CPU metrics unavailable from monitoring stack ({metric_source}). Maintaining current capacity of {current_replicas} replicas.",
                "basis": "Rule-based evaluation: Scaling decisions require active workload telemetry."
            }

        # 2. Rule-based HPA formula: ceil[currentReplicas * (currentMetric / targetMetric)]
        ratio = current_cpu / target if target > 0 else 1.0
        calculated_replicas = math.ceil(current_replicas * ratio)
        recommended_replicas = max(min_reps, min(max_reps, calculated_replicas))

        # 3. Rule-based action evaluation
        if current_cpu >= cfg.cpu_warning and recommended_replicas > current_replicas:
            action = "SCALE UP"
            reason = f"Workload CPU ({current_cpu:.1f}%) exceeds warning threshold ({cfg.cpu_warning}%). Scaling up balances cluster load."
            basis = f"Rule-based HPA formula: ceil({current_replicas} * {current_cpu:.1f} / {target}) = {calculated_replicas} (Metric: {metric_source})."
        elif current_cpu < cfg.scale_down_threshold and current_replicas > min_reps:
            scale_down_target = max(min_reps, current_replicas - 1)
            recommended_replicas = scale_down_target
            action = "SCALE DOWN"
            reason = f"Workload CPU ({current_cpu:.1f}%) is low (< {cfg.scale_down_threshold}%). Conserving compute capacity while respecting minimum {min_reps} replicas."
            basis = f"Rule-based conservative scale-down: reduced by 1 to {recommended_replicas} (Metric: {metric_source})."
        else:
            action = "KEEP CURRENT CAPACITY"
            recommended_replicas = current_replicas
            if current_replicas == min_reps and current_cpu < cfg.scale_down_threshold:
                reason = f"Workload CPU ({current_cpu:.1f}%) is low, but deployment is already at high-availability baseline ({min_reps} replicas). Maintaining capacity."
            else:
                reason = f"Workload capacity is balanced (CPU: {current_cpu:.1f}%, Target: {target}%). Maintaining {current_replicas} replicas."
            basis = f"Rule-based HPA evaluation: Target utilization {target}%, HA Minimum {min_reps} replicas (Metric: {metric_source})."

        return {
            "action": action,
            "current_replicas": current_replicas,
            "recommended_replicas": recommended_replicas,
            "target_utilization": target,
            "current_utilization": round(current_cpu, 1),
            "min_replicas": min_reps,
            "max_replicas": max_reps,
            "metric_source": metric_source,
            "reason": reason,
            "basis": basis
        }


class KubernetesBridge:
    """
    Kubernetes Integration Layer:
    Reads deployment specifications from live Kubernetes API (when connected)
    or falls back to k8s/deployment.yaml manifest.
    Provides scale plans, live status, and manifest synchronization.
    """
    def __init__(self, manifest_path="k8s/deployment.yaml", k8s_provider=None):
        self.manifest_path = manifest_path
        self.k8s_provider = k8s_provider

    def get_deployment_info(self):
        """Reads replica count and metadata from live Kubernetes API or deployment.yaml."""
        # 1. Try Live Kubernetes Provider first
        if self.k8s_provider and self.k8s_provider.is_available():
            try:
                live_status = self.k8s_provider.get_scaling_status("dockpulse-deployment")
                if live_status.get("available"):
                    return {
                        "available": True,
                        "replicas": live_status.get("desired_replicas", 1),
                        "current_replicas": live_status.get("current_replicas", 1),
                        "ready_replicas": live_status.get("ready_replicas", 1),
                        "available_replicas": live_status.get("available_replicas", 1),
                        "name": live_status.get("name", "dockpulse-deployment"),
                        "runtime": "Kubernetes",
                        "manifest_path": self.manifest_path
                    }
            except Exception:
                pass

        # 2. Fallback to parsing local manifest file
        if not os.path.exists(self.manifest_path):
            return {
                "available": False,
                "replicas": 1,
                "name": "dockpulse-deployment",
                "manifest_path": self.manifest_path
            }

        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Regex parse replicas to avoid strict pyyaml dependency
            name_match = re.search(r"name:\s*([a-zA-Z0-9_\-]+)", content)
            replica_match = re.search(r"replicas:\s*(\d+)", content)
            
            name = name_match.group(1) if name_match else "dockpulse-deployment"
            replicas = int(replica_match.group(1)) if replica_match else 1

            return {
                "available": True,
                "replicas": replicas,
                "current_replicas": replicas,
                "ready_replicas": replicas,
                "available_replicas": replicas,
                "name": name,
                "manifest_path": self.manifest_path
            }
        except Exception as e:
            return {
                "available": False,
                "error": str(e),
                "replicas": 1,
                "name": "dockpulse-deployment"
            }

    def generate_scale_plan(self, target_replicas):
        """Generates dry-run kubectl command and manifest preview."""
        info = self.get_deployment_info()
        current = info.get("replicas", 2)
        name = info.get("name", "dockpulse-deployment")

        cmd = f"kubectl scale deployment {name} --replicas={target_replicas}"
        return {
            "current_replicas": current,
            "target_replicas": target_replicas,
            "deployment_name": name,
            "kubectl_command": cmd,
            "manifest_file": self.manifest_path,
            "status": "ready_for_execution"
        }

    def update_manifest_replicas(self, target_replicas):
        """Safely updates replicas in k8s/deployment.yaml."""
        if not os.path.exists(self.manifest_path):
            return False, f"Manifest {self.manifest_path} not found"

        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                content = f.read()

            new_content = re.sub(r"(replicas:\s*)(\d+)", rf"\g<1>{target_replicas}", content, count=1)
            with open(self.manifest_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return True, f"Updated {self.manifest_path} to {target_replicas} replicas."
        except Exception as e:
            return False, str(e)
