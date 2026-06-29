from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PUBLIC_DOCS = (
    ROOT / "README.md",
    ROOT / "docs" / "README.md",
    ROOT / "docs" / "submission-report.md",
)
INTERNAL_REFERENCES = (
    "docs/.pdca-status.json",
    "docs/.bkit-memory.json",
    "docs/deployment/railway.md",
    "docs/release/",
    "docs/superpowers/",
    "work/tasks/",
    "private-admin-gap-audit",
    "first-release-checklist",
    "cross-tenant-constraint-plan",
    "rag-vector-evaluation-plan",
)


def test_public_docs_do_not_reference_internal_artifacts():
    combined_docs = "\n".join(
        path.read_text(encoding="utf-8") for path in PUBLIC_DOCS
    )

    for reference in INTERNAL_REFERENCES:
        assert reference not in combined_docs


def test_internal_status_files_are_not_public_docs():
    assert not (ROOT / "docs" / ".pdca-status.json").exists()
    assert not (ROOT / "docs" / "deployment" / "railway.md").exists()


def test_release_folder_is_not_used_for_public_docs():
    release_dir = ROOT / "docs" / "release"

    if release_dir.exists():
        assert not any(path.is_file() for path in release_dir.rglob("*"))
