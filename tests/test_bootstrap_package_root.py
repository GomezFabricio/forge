"""Tests for _resolve_package_root() in forge.bootstrap (D10 fix).

Three scenarios:
  1. Editable / repo layout — real environment; config/ exists under repo root.
  2. Wheel / non-editable layout — simulated with a tmp dir that has
     share/forge/config/; sysconfig lookup is monkeypatched.
  3. Neither candidate exists — fallback behaviour (repo-relative, no raise).
"""


# ---------------------------------------------------------------------------
# Test 1: Editable / repo layout (real environment)
# ---------------------------------------------------------------------------

class TestRepoLayout:
    def test_resolves_to_repo_root_in_editable_install(self):
        """In the current editable install, PACKAGE_ROOT must point to the
        repo root that actually contains config/."""
        from forge.bootstrap import PACKAGE_ROOT

        # Config directory must exist under the resolved root
        assert (PACKAGE_ROOT / "config").exists(), (
            f"PACKAGE_ROOT={PACKAGE_ROOT} does not contain config/ — "
            "resolution is broken for the editable layout"
        )

    def test_package_root_is_absolute(self):
        from forge.bootstrap import PACKAGE_ROOT
        assert PACKAGE_ROOT.is_absolute()

    def test_copy_config_templates_finds_source(self, tmp_path):
        """copy_config_templates() must not raise for a fresh project root."""
        from forge.bootstrap import copy_config_templates
        # Should run without FileNotFoundError (source config/ exists)
        result = copy_config_templates(tmp_path)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Test 2: Wheel / non-editable layout (simulated)
# ---------------------------------------------------------------------------

class TestWheelLayout:
    def test_falls_back_to_sysconfig_data_dir(self, tmp_path, monkeypatch):
        """When __file__ is inside site-packages (no config/ sibling), the
        resolver must pick up the share/forge layout from sysconfig data dir."""
        import sysconfig as _sysconfig

        from forge import bootstrap as _bs

        # Simulate site-packages: no config/ next to forge/
        fake_site_packages = tmp_path / "lib" / "site-packages"
        fake_forge_pkg = fake_site_packages / "forge"
        fake_forge_pkg.mkdir(parents=True)
        fake_bootstrap = fake_forge_pkg / "bootstrap.py"
        fake_bootstrap.write_text("", encoding="utf-8")
        # Importantly: do NOT create fake_site_packages / "config" — it must be absent.

        # Simulate wheel data dir with share/forge/config/
        fake_data_dir = tmp_path / "data"
        share_config = fake_data_dir / "share" / "forge" / "config"
        share_config.mkdir(parents=True)
        (share_config / "modulos-transversales.yaml").write_text("# stub", encoding="utf-8")

        # Patch __file__ and sysconfig
        monkeypatch.setattr(_bs, "__file__", str(fake_bootstrap), raising=False)
        original_get_path = _sysconfig.get_path

        def fake_get_path(name, *a, **kw):
            if name == "data":
                return str(fake_data_dir)
            return original_get_path(name, *a, **kw)

        monkeypatch.setattr(_sysconfig, "get_path", fake_get_path)

        result = _bs._resolve_package_root()
        expected = fake_data_dir / "share" / "forge"
        assert result == expected, (
            f"Expected wheel root {expected}, got {result}"
        )

    def test_wheel_root_has_config(self, tmp_path, monkeypatch):
        """After resolution in wheel layout, config/ is reachable."""
        import sysconfig as _sysconfig

        from forge import bootstrap as _bs

        fake_site_packages = tmp_path / "lib" / "site-packages" / "forge"
        fake_site_packages.mkdir(parents=True)
        fake_bootstrap = fake_site_packages / "bootstrap.py"
        fake_bootstrap.write_text("", encoding="utf-8")

        fake_data_dir = tmp_path / "data"
        share_config = fake_data_dir / "share" / "forge" / "config"
        share_config.mkdir(parents=True)

        monkeypatch.setattr(_bs, "__file__", str(fake_bootstrap), raising=False)
        original = _sysconfig.get_path

        def fake_get_path(name, *a, **kw):
            return str(fake_data_dir) if name == "data" else original(name, *a, **kw)

        monkeypatch.setattr(_sysconfig, "get_path", fake_get_path)

        root = _bs._resolve_package_root()
        assert (root / "config").exists()


# ---------------------------------------------------------------------------
# Test 3: Neither candidate exists — fallback behaviour
# ---------------------------------------------------------------------------

class TestNeitherExists:
    def test_fallback_does_not_raise(self, tmp_path, monkeypatch):
        """When neither candidate has config/, _resolve_package_root() returns
        the repo-relative candidate without raising.  Errors surface later when
        a consumer actually tries to open a missing file."""
        import sysconfig as _sysconfig

        from forge import bootstrap as _bs

        # Fake site-packages with NO config/ anywhere
        fake_forge_pkg = tmp_path / "site-packages" / "forge"
        fake_forge_pkg.mkdir(parents=True)
        fake_bootstrap = fake_forge_pkg / "bootstrap.py"
        fake_bootstrap.write_text("", encoding="utf-8")

        # sysconfig returns a data dir that also has no share/forge/config/
        fake_data_dir = tmp_path / "data"
        fake_data_dir.mkdir(parents=True)

        monkeypatch.setattr(_bs, "__file__", str(fake_bootstrap), raising=False)
        original = _sysconfig.get_path

        def fake_get_path(name, *a, **kw):
            return str(fake_data_dir) if name == "data" else original(name, *a, **kw)

        monkeypatch.setattr(_sysconfig, "get_path", fake_get_path)

        # Must NOT raise — fallback to repo-relative candidate
        result = _bs._resolve_package_root()
        # The fallback is parent.parent of fake_bootstrap = fake_forge_pkg.parent.parent = tmp_path
        expected_fallback = fake_bootstrap.resolve().parent.parent
        assert result == expected_fallback

    def test_import_does_not_raise(self):
        """Importing forge.bootstrap in the real environment must never raise,
        even if internal paths were wrong — the module-level resolution is safe."""
        import forge.bootstrap  # noqa: F401 — just verify import succeeds
