from govcheck.api.openapi_check import REQUIRED_OPERATIONS
from govcheck.main import app


def test_openapi_contains_the_versioned_public_contract() -> None:
    schema = app.openapi()

    assert all(method in schema["paths"][path] for path, method in REQUIRED_OPERATIONS)
    descriptions = " ".join(
        operation.get("description", "")
        for path in schema["paths"].values()
        for operation in path.values()
        if isinstance(operation, dict)
    ).casefold()
    assert "pdf" in descriptions
    assert "model" in descriptions
    assert "external" in descriptions
    finding_category = schema["components"]["schemas"]["FindingResponse"]["properties"][
        "category"
    ]
    assert set(finding_category["enum"]) == {
        "deadline",
        "document",
        "value",
        "criterion",
        "sanction",
        "obligation",
    }
