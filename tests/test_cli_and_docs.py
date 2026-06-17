from pathlib import Path
import shutil

from code_rpa.cli import main


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def copy_project(tmp_path: Path) -> Path:
    target = tmp_path / "project"
    shutil.copytree(
        PROJECT_ROOT,
        target,
        ignore=shutil.ignore_patterns(".git", ".venv", ".pytest_cache", "__pycache__", "*.pyc"),
    )
    return target


def test_cli_skill_list_shows_web_report_export(capsys):
    exit_code = main(["--project-root", str(PROJECT_ROOT), "skill", "list"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "web_report_export" in captured.out


def test_cli_skill_create_generates_standard_skill_files(tmp_path):
    project = copy_project(tmp_path)

    exit_code = main(["--project-root", str(project), "skill", "create", "invoice_export"])

    skill_dir = project / "example_skills" / "invoice_export"
    assert exit_code == 0
    assert (skill_dir / "skill.yaml").exists()
    assert (skill_dir / "selectors.yaml").exists()
    assert (skill_dir / "repair_policy.yaml").exists()
    assert (skill_dir / "main.py").exists()
    assert (skill_dir / "tests" / "test_skill.py").exists()
    assert 'id: "invoice_export"' in (skill_dir / "skill.yaml").read_text(encoding="utf-8")
    assert "python" in (skill_dir / "repair_policy.yaml").read_text(encoding="utf-8")


def test_repo_skill_files_exist():
    skill_root = PROJECT_ROOT / ".agents" / "skills" / "self-healing-rpa-engineer"

    assert (skill_root / "SKILL.md").exists()
    assert (skill_root / "references" / "architecture.md").exists()
    assert (skill_root / "references" / "rpa-skill-spec.md").exists()
    assert (skill_root / "references" / "patch-json-spec.md").exists()
    assert (skill_root / "references" / "repair-pipeline.md").exists()
    assert (skill_root / "assets" / "skill.yaml.template").exists()
    assert (skill_root / "assets" / "selectors.yaml.template").exists()
    assert (skill_root / "assets" / "repair_policy.yaml.template").exists()


def test_readme_contains_key_sections():
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    required_phrases = [
        "Self-Healing Code RPA Framework",
        "What This Is Not",
        "Architecture",
        "MVP Scope",
        "Install",
        "Run Demo",
        "Run Tests",
        "repair_request.json",
        "patch.json",
        "Sandbox Testing",
        "Versions And Rollback",
        "Create A New RPA Skill",
        "Safety Boundaries",
    ]
    for phrase in required_phrases:
        assert phrase in readme

