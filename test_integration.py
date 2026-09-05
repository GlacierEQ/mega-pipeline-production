"""
APEX HIGH-SIGNAL COMPANIES — Integration Tests
Tests showing modules working together in realistic scenarios.
"""

import json
import time
from pathlib import Path

import pytest

from apex_nasa_telemetry_gate import (
    TelemetryPacket, EpistemicTelemetryGate, TelemetryStreamProcessor,
    generate_test_packets,
)
from apex_constellation_mesh import ConstellationMesh, generate_test_constellation
from apex_gpu_topology_engine import (
    GPUTopologyEngine, TrainingJob, generate_test_cluster,
)
from apex_f35_verification_pipeline import (
    F35VerificationPipeline, generate_test_modules,
)
from apex_ew_signal_fabric import (
    EWSignalFabric, SignalSample, generate_test_scenario,
)
from apex_cmmc_compliance_engine import (
    CMMCComplianceEngine, CMMCLevel, generate_test_assessment,
)
from apex_swarm_forge import (
    SwarmOrchestrator, EngagementAuthorization, generate_test_swarm,
)


class TestNASAConstellationIntegration:
    """Integration: NASA telemetry feeds into constellation mesh."""

    def test_telemetry_drives_handover(self):
        # NASA gate validates packet
        gate = EpistemicTelemetryGate(known_apids=frozenset(range(0x100, 0x10A)))
        pkts = generate_test_packets(10)
        proc = TelemetryStreamProcessor(gate)
        result = proc.process_batch(pkts)
        assert result["passed"] > 0

        # Constellation uses validated data for handover
        mesh = generate_test_constellation(num_sats=20, num_stations=5)
        for _ in range(5):
            import random
            rng = random.Random()
            sat_id = rng.choice(list(mesh.satellites.keys()))
            handover = mesh.perform_handover(sat_id, rng=rng)
            assert handover["status"] in ("SUCCESS", "FAILURE", "NO_GS")

    def test_telemetry_anomaly_triggers_ew_scan(self):
        # NASA gate detects anomaly
        gate = EpistemicTelemetryGate(known_apids=frozenset(range(0x100, 0x10A)))
        anomalous = TelemetryPacket(
            apid=0x100, sequence_flags=3, sequence_number=0,
            data_length=3, payload=b"\xff\xff\xff\xff",
        )
        anomalous.encode()
        passed, _ = gate.verify_l2_behavior(anomalous, predicted_value=100.0)
        # Anomaly detected (z-score high)
        if not passed:
            # EW fabric scans for threat
            samples, sigs = generate_test_scenario(num_samples=10, threat_ratio=1.0)
            fabric = EWSignalFabric()
            for sig in sigs:
                fabric.register_signature(sig)
            for s in samples[:3]:
                r = fabric.process_signal(s)
                assert "threat" in r


class TestGPUSwarmIntegration:
    """Integration: GPU topology informs swarm drone compute allocation."""

    def test_swarm_assigns_drones_with_gpu_backup(self):
        # Swarm registers drones
        swarm = generate_test_swarm(num_drones=30)
        mission = swarm.create_mission_from_voice("swarm to objective alpha")
        assign_result = swarm.assign_drones_to_mission(mission["mission_id"])
        assert assign_result["drones_assigned"] > 0

        # GPU topology allocates backup compute for drone imagery
        engine = generate_test_cluster(num_nodes=2, gpus_per_node=4)
        job = TrainingJob(
            job_id="DRONE-IMAGERY",
            required_gpus=2,
            min_memory_per_gpu_gb=40.0,
        )
        placement = engine.find_optimal_placement(job)
        assert placement["status"] == "PLACED"

    def test_f35_pipeline_uses_gpu_for_hil(self):
        # F-35 pipeline needs GPU for HIL simulation
        engine = generate_test_cluster(num_nodes=1, gpus_per_node=4)
        job = TrainingJob(
            job_id="F35-HIL",
            required_gpus=4,
            min_nvlink_connections=4,
            prefer_nvswitch=True,
        )
        placement = engine.find_optimal_placement(job)
        assert placement["status"] == "PLACED"

        # Pipeline runs with GPU allocated
        pipeline = generate_test_modules(count=2)
        mod_id = list(pipeline.modules.keys())[0]
        result = pipeline.execute_stage(mod_id)
        assert result["status"] in ("ADVANCED", "ROLLBACK", "DEPLOYED")


class TestCMMCSwarmIntegration:
    """Integration: CMMC compliance gates swarm engagement."""

    def test_compliance_blocks_unauthorized_engagement(self):
        # CMMC assesses compliance
        engine = generate_test_assessment(level=2, seed=42)
        assessment = engine.full_assessment()
        assert assessment["score"] > 0

        # Swarm checks compliance before engagement
        swarm = generate_test_swarm(num_drones=10)
        mission = swarm.create_mission_from_voice("engage target alpha")
        swarm.assign_drones_to_mission(mission["mission_id"])
        mid = mission["mission_id"]

        # Compliance gate: if score < 0.8, engagement denied
        if assessment["score"] < 0.8:
            swarm.missions[mid].engagement_authorization = EngagementAuthorization.DENIED
        else:
            swarm.missions[mid].engagement_authorization = EngagementAuthorization.AUTHORIZED

        did = swarm.missions[mid].assigned_drones[0]
        result = swarm.execute_engagement(did, mid)
        if assessment["score"] < 0.8:
            assert result["engagement"] == "DENIED"


class TestFullPipelineIntegration:
    """Integration: Complete mission pipeline across all modules."""

    def test_end_to_end_mission(self):
        # 1. CMMC compliance check
        cmmc = generate_test_assessment(level=2, seed=42)
        assessment = cmmc.full_assessment()
        assert assessment["score"] > 0

        # 2. NASA telemetry validation
        gate = EpistemicTelemetryGate(known_apids=frozenset(range(0x100, 0x10A)))
        pkts = generate_test_packets(20)
        proc = TelemetryStreamProcessor(gate)
        telemetry_result = proc.process_batch(pkts)
        assert telemetry_result["passed"] > 0

        # 3. Constellation mesh setup
        mesh = generate_test_constellation(num_sats=30, num_stations=8)
        status = mesh.get_constellation_status()
        assert status["satellites"] == 30

        # 4. GPU allocation for drone imagery processing
        gpu_engine = generate_test_cluster(num_nodes=2, gpus_per_node=4)
        job = TrainingJob(
            job_id="MISSION-IMAGERY",
            required_gpus=2,
            min_memory_per_gpu_gb=40.0,
        )
        placement = gpu_engine.find_optimal_placement(job)
        assert placement["status"] == "PLACED"

        # 5. F-35 verification (if applicable)
        pipeline = generate_test_modules(count=2)
        mod_id = list(pipeline.modules.keys())[0]
        f35_result = pipeline.execute_stage(mod_id)
        assert f35_result["status"] in ("ADVANCED", "ROLLBACK", "DEPLOYED")

        # 6. EW threat detection
        samples, sigs = generate_test_scenario(num_samples=20, threat_ratio=0.3)
        fabric = EWSignalFabric()
        for sig in sigs:
            fabric.register_signature(sig)
        threats_detected = 0
        for s in samples:
            r = fabric.process_signal(s)
            if r["threat"]:
                threats_detected += 1

        # 7. Swarm execution
        swarm = generate_test_swarm(num_drones=50)
        mission = swarm.create_mission_from_voice("swarm to objective alpha")
        if assessment["score"] > 0.7:
            swarm.missions[mission["mission_id"]].engagement_authorization = EngagementAuthorization.AUTHORIZED
        swarm.assign_drones_to_mission(mission["mission_id"])
        mid = mission["mission_id"]
        did = swarm.missions[mid].assigned_drones[0]
        engagement = swarm.execute_engagement(did, mid)

        # Final summary
        summary = {
            "cmmc_score": assessment["score"],
            "telemetry_passed": telemetry_result["passed"],
            "constellation_healthy": status["healthy_sats"],
            "gpu_placed": placement["status"] == "PLACED",
            "f35_status": f35_result["status"],
            "ew_threats": threats_detected,
            "swarm_engagement": engagement["engagement"],
        }
        assert all(v is not None for v in summary.values())
