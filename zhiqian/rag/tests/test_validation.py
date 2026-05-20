from app.pipelines.validation import (
    generate_validation_script,
    validate_request_payload,
)


def test_validate_request_payload_ok():
    errors = validate_request_payload({
        "task_id": 1,
        "suggestions": [{"category": "SQL_REWRITE", "target": "x.y"}],
    })
    assert errors == []


def test_validate_request_payload_fail():
    errors = validate_request_payload({
        "task_id": "oops",
        "suggestions": [],
    })
    assert any("task_id" in e for e in errors)
    assert any("suggestions" in e for e in errors)


def test_generate_validation_script_sql_rewrite():
    scripts = generate_validation_script(
        task_id=42,
        suggestions=[{
            "category": "SQL_REWRITE",
            "target": "com.demo.UserMapper.xml#listActive",
            "risk_level": "LOW",
            "confidence": 0.94,
            "unified_diff": "--- a\n+++ b\n@@\n-IFNULL\n+COALESCE",
        }],
    )
    assert len(scripts) == 1
    s = scripts[0]
    assert "Task ID  : 42" in s["content"]
    assert "COALESCE" in s["content"]
    assert s["file_path"] == "validation/task-42/01-sql_rewrite.sql"


def test_generate_validation_script_dependency():
    scripts = generate_validation_script(
        task_id=7,
        suggestions=[{
            "category": "DEPENDENCY",
            "target": "pom.xml#mysql-connector-java",
            "risk_level": "LOW",
            "confidence": 0.92,
        }],
    )
    s = scripts[0]
    assert "opengauss-jdbc" in s["content"]
    assert s["file_path"].endswith(".sql")
