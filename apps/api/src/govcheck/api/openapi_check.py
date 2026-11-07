from govcheck.main import app

REQUIRED_OPERATIONS = {
    ("/api/v1/documents", "post"),
    ("/api/v1/documents/{document_id}", "get"),
    ("/api/v1/documents/{document_id}/events", "get"),
    ("/api/v1/documents/{document_id}/analysis", "post"),
    ("/api/v1/documents/{document_id}/chat", "post"),
    ("/api/v1/documents/{document_id}/findings", "get"),
    ("/api/v1/documents/{document_id}/report", "get"),
    ("/health", "get"),
    ("/ready", "get"),
}


def main() -> None:
    schema = app.openapi()
    missing = [
        f"{method.upper()} {path}"
        for path, method in sorted(REQUIRED_OPERATIONS)
        if method not in schema["paths"].get(path, {})
    ]
    if missing:
        raise RuntimeError(f"OpenAPI is missing operations: {', '.join(missing)}")
    print(f"openapi_operations={len(REQUIRED_OPERATIONS)}")


if __name__ == "__main__":
    main()
