import importlib
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Fresh store, snapshot and inbox with the two SAMPLE PDFs; mock reader."""
    import make_fixtures
    inbox = tmp_path / "inbox"
    make_fixtures.write(inbox)
    monkeypatch.setenv("REGSTUDIO_INBOX", str(inbox))
    monkeypatch.setenv("REGSTUDIO_STORE", str(tmp_path / "store"))
    monkeypatch.setenv("REGSTUDIO_SNAPSHOT", str(tmp_path / "snapshot"))
    monkeypatch.setenv("REGSTUDIO_PREVIEW", str(tmp_path / "preview"))
    monkeypatch.setenv("REGSTUDIO_READER", "mock")
    import regstudio.config as config
    importlib.reload(config)
    for mod in list(sys.modules):
        if mod.startswith("regstudio.") and mod != "regstudio.config":
            importlib.reload(sys.modules[mod])
    from regstudio import db
    config.ensure_dirs()
    db.init()
    return tmp_path
