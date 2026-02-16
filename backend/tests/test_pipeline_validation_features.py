"""
Tests para extensiones de incidencias y score del pipeline.
"""

try:
    from backend.models.validation_result import RouteIssue, IssueType
    from backend.services.optimization_pipeline_service import (
        PipelineConfig,
        calculate_pipeline_candidate_score,
    )
    from backend.websocket.schedule_validation_ws import ScheduleValidationWebSocket
except ImportError:
    from models.validation_result import RouteIssue, IssueType
    from services.optimization_pipeline_service import (
        PipelineConfig,
        calculate_pipeline_candidate_score,
    )
    from websocket.schedule_validation_ws import ScheduleValidationWebSocket


def test_route_issue_supports_operational_context_fields():
    issue = RouteIssue(
        route_a="R1",
        route_b="R2",
        issue_type=IssueType.INSUFFICIENT_TIME,
        message="Faltan minutos para la conexión",
        suggestion="Reasignar o ajustar horario",
        severity="error",
        time_available=12.0,
        travel_time=18.0,
        buffer_minutes=-6.0,
        day="L",
        bus_id="B001",
    )

    data = issue.dict()
    assert data["time_available"] == 12.0
    assert data["travel_time"] == 18.0
    assert data["buffer_minutes"] == -6.0
    assert data["day"] == "L"
    assert data["bus_id"] == "B001"


def test_pipeline_score_prioritizes_viability_before_bus_count():
    # Candidato A: menos errores pero 1 bus inviable
    score_a = calculate_pipeline_candidate_score({
        "infeasible_buses": 1,
        "error_issues": 0,
        "total_buses": 28,
        "avg_efficiency": 80,
    })

    # Candidato B: sin buses inviables, aunque con más errores y un bus más
    score_b = calculate_pipeline_candidate_score({
        "infeasible_buses": 0,
        "error_issues": 4,
        "total_buses": 29,
        "avg_efficiency": 70,
    })

    assert score_b < score_a


def test_validate_all_summary_aggregation_counts_severities():
    day_reports = [
        {"summary": {"total_buses": 3, "feasible_buses": 2, "buses_with_issues": 1}},
        {"summary": {"total_buses": 2, "feasible_buses": 1, "buses_with_issues": 1}},
    ]
    incidents = [
        {"severity": "error"},
        {"severity": "warning"},
        {"severity": "error"},
        {"severity": "info"},
    ]

    summary = ScheduleValidationWebSocket._build_summary(day_reports, incidents)
    assert summary["total_buses"] == 5
    assert summary["feasible_buses"] == 3
    assert summary["buses_with_issues"] == 2
    assert summary["incidents_total"] == 4
    assert summary["incidents_error"] == 2
    assert summary["incidents_warning"] == 1
    assert summary["incidents_info"] == 1


def test_pipeline_config_parses_use_ml_assignment_flag():
    cfg = PipelineConfig.from_dict({"use_ml_assignment": False})
    assert cfg.use_ml_assignment is False
