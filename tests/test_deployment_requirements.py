import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUIREMENTS = os.path.join(ROOT, "requirements.txt")


def _declared_requirements():
    with open(REQUIREMENTS, encoding="utf-8") as handle:
        return {
            line.split(";", 1)[0].split("[", 1)[0].strip().lower()
            for line in handle
            if line.strip() and not line.lstrip().startswith("#")
        }


def _application_sources():
    paths = [
        "main.py",
        "memory_system.py",
        "pdf_analyzer.py",
        "product_research.py",
        "tracing.py",
    ]
    services_dir = os.path.join(ROOT, "services")
    paths.extend(
        os.path.join("services", name)
        for name in os.listdir(services_dir)
        if name.endswith(".py")
    )
    return paths


def test_unused_google_generativeai_sdk_is_not_deployed():
    assert "google-generativeai" not in _declared_requirements()


def test_application_does_not_import_google_generativeai_sdk():
    for relative_path in _application_sources():
        with open(os.path.join(ROOT, relative_path), encoding="utf-8") as handle:
            source = handle.read()
        assert "google.generativeai" not in source, relative_path
        assert "googleapiclient" not in source, relative_path
