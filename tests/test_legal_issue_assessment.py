import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "legal_issue_assessment.py"
spec = importlib.util.spec_from_file_location("legal_issue_assessment", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def test_preserves_operator_assessment_and_routes_missing_assessment_to_recovery():
    result = module.build_matrix(
        [
            {
                "issue_id": "ISSUE-1",
                "issue": "Potentially material condition",
                "operator_assessment": "This is my assessment exactly.",
                "source_ref": "chat://operator-span-1",
                "fact_pointers": ["FACT-1"],
            },
            {
                "issue_id": "ISSUE-2",
                "issue": "Another issue without an Operator assessment yet",
            },
        ]
    )

    assert result["rows"][0]["my_assessment"] == "This is my assessment exactly."
    assert result["rows"][0]["operator_assessment_source"] == "chat://operator-span-1"
    assert result["rows"][0]["fact_pointers"] == ["FACT-1"]
    assert result["assessment_recovery_targets"] == ["ISSUE-2"]
    assert result["analysis_separation"] == "assistant_or_agent_analysis_is_separate"
    assert result["storage_model"] == "view_over_stable_objects_not_duplicate_fact_store"
