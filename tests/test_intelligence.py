"""
Unit Tests for DockPulse 2.0 Intelligence Engine
Tests:
- ThresholdConfig
- EventLogManager
- TrendAnalyzer (slope, direction, breach forecast)
- AnomalyDetector (sustained load, spikes, container states)
- WorkloadScaler (HPA algorithm, scale up, scale down, keep capacity)
- KubernetesBridge (manifest parsing, scale command generation)
"""

import unittest
from intelligence import (
    ThresholdConfig,
    EventLogManager,
    TrendAnalyzer,
    AnomalyDetector,
    RecommendationEngine,
    WorkloadScaler,
    KubernetesBridge
)


class TestTrendAnalyzer(unittest.TestCase):
    def test_stable_trend(self):
        vals = [20.0, 20.1, 20.0, 20.2, 20.1, 20.0]
        res = TrendAnalyzer.calculate_linear_trend(vals, interval_sec=2.0)
        self.assertEqual(res["direction"], "STABLE")

    def test_upward_trend(self):
        # Linearly increasing from 30 to 60 over 6 points (10 sec total -> +180%/min)
        vals = [30.0, 36.0, 42.0, 48.0, 54.0, 60.0]
        res = TrendAnalyzer.calculate_linear_trend(vals, interval_sec=2.0)
        self.assertEqual(res["direction"], "UPWARD")
        self.assertGreater(res["slope_per_min"], 10.0)

    def test_breach_prediction(self):
        # At 70%, slope is 5%/min, threshold is 85% -> 15 / 5 = 3.0 mins
        mins = TrendAnalyzer.estimate_breach_time(70.0, 5.0, 85.0)
        self.assertEqual(mins, 3.0)

        # Downward or zero slope should return None
        self.assertIsNone(TrendAnalyzer.estimate_breach_time(70.0, -2.0, 85.0))
        self.assertIsNone(TrendAnalyzer.estimate_breach_time(70.0, 0.2, 85.0))


class TestWorkloadScaler(unittest.TestCase):
    def setUp(self):
        self.cfg = ThresholdConfig()
        self.scaler = WorkloadScaler(self.cfg)

    def test_scale_up_under_high_load(self):
        # Current CPU 90% (exceeds warning 70%). Replicas = 2.
        # Ratio = 90 / 70 = 1.28 -> ceil(2 * 1.28) = ceil(2.57) = 3
        res = self.scaler.evaluate(current_cpu=90.0, current_replicas=2)
        self.assertEqual(res["action"], "SCALE UP")
        self.assertEqual(res["recommended_replicas"], 3)

    def test_keep_capacity_under_nominal_load(self):
        # Current CPU 55% (target is 70%). Replicas = 2.
        res = self.scaler.evaluate(current_cpu=55.0, current_replicas=2)
        self.assertEqual(res["action"], "KEEP CURRENT CAPACITY")
        self.assertEqual(res["recommended_replicas"], 2)

    def test_scale_down_under_low_load(self):
        # Current CPU 15% (< scale_down_threshold 30%). Replicas = 3.
        res = self.scaler.evaluate(current_cpu=15.0, current_replicas=3)
        self.assertEqual(res["action"], "SCALE DOWN")
        self.assertEqual(res["recommended_replicas"], 2)

    def test_unavailable_metric_keeps_capacity(self):
        # When Prometheus/cAdvisor pod CPU metrics are unavailable (None)
        res = self.scaler.evaluate(current_cpu=None, current_replicas=2, metric_source="Pod CPU")
        self.assertEqual(res["action"], "KEEP CURRENT CAPACITY")
        self.assertEqual(res["recommended_replicas"], 2)
        self.assertIn("unavailable", res["reason"].lower())

    def test_keep_ha_baseline_under_low_load(self):
        # Low workload CPU (e.g. 5%) must NOT scale down below the 2-replica HA baseline
        res = self.scaler.evaluate(current_cpu=5.0, current_replicas=2, metric_source="Pod CPU")
        self.assertEqual(res["action"], "KEEP CURRENT CAPACITY")
        self.assertEqual(res["recommended_replicas"], 2)


class TestAnomalyDetector(unittest.TestCase):
    def setUp(self):
        self.cfg = ThresholdConfig()
        self.event_mgr = EventLogManager()
        self.detector = AnomalyDetector(self.cfg, self.event_mgr)

    def test_normal_host(self):
        history = [
            {"cpu_percentage": 25.0, "ram_percentage": 40.0} for _ in range(10)
        ]
        res = self.detector.analyze_host(history)
        self.assertEqual(res["status"], "NORMAL")
        self.assertEqual(len(res["issues"]), 0)

    def test_critical_cpu_host(self):
        history = [
            {"cpu_percentage": 90.0, "ram_percentage": 40.0} for _ in range(10)
        ]
        res = self.detector.analyze_host(history)
        self.assertEqual(res["status"], "CRITICAL")
        self.assertTrue(any("CPU" in issue for issue in res["issues"]))

    def test_container_crash_loop(self):
        containers = [
            {"name": "web-service", "status": "running", "restart_count": 5}
        ]
        res = self.detector.analyze_containers(containers)
        self.assertEqual(res["status"], "CRITICAL")
        self.assertTrue(any("restart" in issue for issue in res["issues"]))

    def test_analyze_host_thresholds(self):
        history = [
            {"cpu_percentage": 25.0, "ram_percentage": 40.0} for _ in range(5)
        ]
        res = self.detector.analyze_host(history)
        self.assertIn("cpu_warning", res)
        self.assertIn("cpu_critical", res)
        self.assertEqual(res["cpu_warning"], self.cfg.cpu_warning)
        self.assertEqual(res["cpu_critical"], self.cfg.cpu_critical)


class TestKubernetesBridge(unittest.TestCase):
    def test_manifest_read(self):
        bridge = KubernetesBridge("k8s/deployment.yaml")
        info = bridge.get_deployment_info()
        self.assertTrue(info["available"])
        self.assertGreaterEqual(info["replicas"], 1)
        self.assertEqual(info["name"], "dockpulse-deployment")

    def test_generate_scale_plan(self):
        bridge = KubernetesBridge("k8s/deployment.yaml")
        plan = bridge.generate_scale_plan(3)
        self.assertEqual(plan["target_replicas"], 3)
        self.assertIn("--replicas=3", plan["kubectl_command"])


if __name__ == "__main__":
    unittest.main()
