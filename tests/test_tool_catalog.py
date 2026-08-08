import importlib.util
import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_catalog():
    return json.loads((ROOT / "data/tools.json").read_text(encoding="utf-8"))


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_openclaw_manifest_matches_catalog():
    catalog = load_catalog()
    expected = [
        item["name"] for item in catalog["tools"] if "openclaw" in item["hosts"]
    ]
    manifest = json.loads(
        (ROOT / "openclaw-plugin/openclaw.plugin.json").read_text(encoding="utf-8")
    )
    assert manifest["contracts"]["tools"] == expected


def test_hermes_handlers_match_catalog():
    catalog = load_catalog()
    expected = {
        item["name"] for item in catalog["tools"] if "hermes" in item["hosts"]
    }
    tree = ast.parse(
        (ROOT / ".hermes/plugins/adjacent/tools.py").read_text(encoding="utf-8")
    )
    registry = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AnnAssign)
        and getattr(node.target, "id", None) == "TOOL_HANDLERS"
    )
    actual = {
        key.value
        for key in ast.walk(registry.value)
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }
    assert actual == expected


def test_validator_uses_catalog_tools():
    catalog = load_catalog()
    expected = {
        item["name"] for item in catalog["tools"] if "openclaw" in item["hosts"]
    }
    validator = load_module(
        ROOT / "scripts/validate-plugin-packages.py", "plugin_validator"
    )
    assert validator.expected_openclaw_tools() == expected
