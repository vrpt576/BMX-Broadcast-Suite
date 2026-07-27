import logging
from pathlib import Path
from connector.services.logging_service import configure_logging, recent_logs

def test_logging_writes_file_and_recent_buffer(tmp_path: Path):
    path = configure_logging("INFO", tmp_path, 2)
    logging.getLogger("bbs.test").warning("track test warning")
    for handler in logging.getLogger().handlers:
        handler.flush()
    assert path.exists()
    assert "track test warning" in path.read_text()
    assert any(x["message"] == "track test warning" for x in recent_logs(search="track test"))
