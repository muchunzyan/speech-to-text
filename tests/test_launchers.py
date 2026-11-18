from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_windows_powershell_scripts_have_utf8_bom():
    for name in ("setup-windows.ps1", "start-windows.ps1"):
        content = (PROJECT_ROOT / "scripts" / name).read_bytes()
        assert content.startswith(b"\xef\xbb\xbf"), f"{name} must be UTF-8 with BOM"


def test_windows_batch_launcher_calls_powershell_entrypoint():
    content = (PROJECT_ROOT / "start-windows.bat").read_text(encoding="ascii")
    assert "-ExecutionPolicy Bypass" in content
    assert "scripts\\start-windows.ps1" in content


def test_macos_launcher_uses_python_311_setup():
    launcher = (PROJECT_ROOT / "start-macos.command").read_text(encoding="utf-8")
    setup = (PROJECT_ROOT / "scripts" / "setup-macos.sh").read_text(encoding="utf-8")
    assert "setup-macos.sh" in launcher
    assert "python3.11 -m venv" in setup
