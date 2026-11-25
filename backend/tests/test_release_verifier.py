"""Release verifier root selection, including its shallow container mount."""

from pathlib import Path

import pytest

from scripts.ci import verify_release as verifier


@pytest.fixture
def recorded_checks(monkeypatch):
    calls = []
    monkeypatch.setattr(verifier.sys, "path", list(verifier.sys.path))
    monkeypatch.setattr(verifier, "verify_python", lambda: calls.append(("python",)))
    for name in ("verify_hashes", "verify_source", "verify_image", "verify_models"):
        monkeypatch.setattr(
            verifier, name,
            lambda root, name=name: calls.append((name, root)),
        )
    monkeypatch.setattr(
        verifier, "verify_dependencies",
        lambda root, development: calls.append(("verify_dependencies", root, development)),
    )
    return calls


def test_container_mount_explicit_root_runs_image_runtime_and_model_checks(
    monkeypatch, tmp_path, recorded_checks,
):
    monkeypatch.setattr(verifier, "__file__", "/ci/verify_release.py")

    assert verifier.main([
        "--root", str(tmp_path), "--image", "--runtime", "--models",
    ]) == 0
    root = tmp_path.resolve()
    assert recorded_checks == [
        ("python",),
        ("verify_hashes", root),
        ("verify_image", root),
        ("verify_dependencies", root, False),
        ("verify_models", root),
        ("verify_hashes", root),
    ]


def test_container_mount_without_root_fails_explicitly(
    monkeypatch, recorded_checks, capsys,
):
    monkeypatch.setattr(verifier, "__file__", "/ci/verify_release.py")

    assert verifier.main(["--image", "--runtime", "--models"]) == 1
    error = capsys.readouterr().err
    assert "Specify --root" in error
    assert "IndexError" not in error
    assert recorded_checks == []


def test_repository_location_keeps_its_default_root(recorded_checks):
    root = Path(verifier.__file__).resolve().parent.parent.parent

    assert verifier.main(["--source"]) == 0
    assert recorded_checks == [
        ("python",),
        ("verify_hashes", root),
        ("verify_source", root),
        ("verify_hashes", root),
    ]


def test_explicit_relative_root_is_resolved_from_cwd(
    monkeypatch, tmp_path, recorded_checks,
):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(verifier, "__file__", "/ci/verify_release.py")

    assert verifier.main(["--root", "runtime"]) == 0
    assert recorded_checks == [
        ("python",),
        ("verify_hashes", runtime.resolve()),
        ("verify_hashes", runtime.resolve()),
    ]


@pytest.mark.parametrize("existing_file", [False, True])
def test_invalid_explicit_root_fails_before_checks(
    monkeypatch, tmp_path, recorded_checks, capsys, existing_file,
):
    root = tmp_path / "invalid-root"
    if existing_file:
        root.write_text("fictional test data", encoding="utf-8")
    monkeypatch.setattr(verifier, "__file__", "/ci/verify_release.py")

    assert verifier.main(["--root", str(root)]) == 1
    assert "existing directory" in capsys.readouterr().err
    assert recorded_checks == []


def test_container_mount_help_does_not_resolve_a_default_root(monkeypatch, capsys):
    monkeypatch.setattr(verifier, "__file__", "/ci/verify_release.py")

    with pytest.raises(SystemExit) as exit_status:
        verifier.main(["--help"])
    assert exit_status.value.code == 0
    assert "--root" in capsys.readouterr().out
