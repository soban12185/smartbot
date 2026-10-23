"""Frontend regression tests for Service Finder.

The frontend has no browser test harness in this project, so the pure client
helpers are tested with Node's built-in test runner and the DOM wiring is
checked for the stale-response/error-state guards directly in main.js.
"""
import os
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_JS = os.path.join(ROOT, "static", "js", "main.js")
TEMPLATE = os.path.join(ROOT, "templates", "index.html")
NODE_TEST = os.path.join(ROOT, "tests", "frontend_service_finder.test.js")


def test_frontend_client_suite_runs_with_node():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    result = subprocess.run(
        [node, "--test", NODE_TEST],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (result.stdout + "\n" + result.stderr)


def test_main_js_guards_against_stale_service_responses():
    source = open(MAIN_JS, encoding="utf-8").read()
    assert "serviceSearchRequestId" in source
    assert "serviceSearchController.abort()" in source
    assert "client.isStaleResponse(requestId, serviceSearchRequestId)" in source
    assert "client.classifyServiceResponse(" in source
    assert "outcome.state === 'error' || outcome.state === 'empty'" in source


def test_template_loads_client_before_main_and_busts_cache():
    source = open(TEMPLATE, encoding="utf-8").read()
    client_index = source.index("service_finder_client.js")
    main_index = source.index("js/main.js")
    assert client_index < main_index
    assert "v='20261023'" in source
