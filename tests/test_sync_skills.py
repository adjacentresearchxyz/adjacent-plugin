import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_sync_module():
    path = ROOT / "scripts/sync-skills.py"
    spec = importlib.util.spec_from_file_location("sync_skills", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_fixture(tmp_path):
    canonical = tmp_path / "plugins/adjacent/skills/shared/SKILL.md"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("canonical\n", encoding="utf-8")
    for relative in (".factory/skills/shared", ".hermes/plugins/adjacent/skills/shared"):
        (tmp_path / relative).mkdir(parents=True)
    return tmp_path


def test_sync_writes_shared_mirrors(tmp_path):
    module = load_sync_module()
    root = make_fixture(tmp_path)

    assert module.sync_skills(root) == [
        ".factory/skills/shared/SKILL.md",
        ".hermes/plugins/adjacent/skills/shared/SKILL.md",
    ]
    source = (root / "plugins/adjacent/skills/shared/SKILL.md").read_bytes()
    assert (root / ".factory/skills/shared/SKILL.md").read_bytes() == source
    assert (root / ".hermes/plugins/adjacent/skills/shared/SKILL.md").read_bytes() == source
    assert module.sync_skills(root, check=True) == []


def test_check_detects_drift_without_writing(tmp_path):
    module = load_sync_module()
    root = make_fixture(tmp_path)
    module.sync_skills(root)
    mirror = root / ".factory/skills/shared/SKILL.md"
    mirror.write_text("drift\n", encoding="utf-8")

    assert module.sync_skills(root, check=True) == [".factory/skills/shared/SKILL.md"]
    assert mirror.read_text(encoding="utf-8") == "drift\n"
