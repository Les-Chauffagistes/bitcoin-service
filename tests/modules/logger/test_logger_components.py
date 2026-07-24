from pathlib import Path

from src.modules.logger.consoleLogger import ConsoleLogger
from src.modules.logger.fileLogger import FileLogger
from src.modules.logger.logger import Logger


def test_file_logger_writes_entries(tmp_path: Path):
    log_file = tmp_path / "app.log"
    logger = FileLogger(str(log_file))

    logger.info("hello")
    logger.warn("warn")
    logger.error("err")
    logger.crit("crit")
    logger.debug("dbg")
    logger.get("/health")
    logger.post("/v1")
    logger.delete("/v1")

    content = log_file.read_text()
    assert "[INFO]" in content
    assert "[WARNING]" in content
    assert "[ERROR]" in content
    assert "[CRITICAL]" in content
    assert "[DEBUG]" in content
    assert "[GET]" in content
    assert "[POST]" in content
    assert "[DELETE]" in content


def test_console_logger_line_operations():
    console = ConsoleLogger()
    line = console.info("started")

    line.add_text("ok")
    line.edit_print()
    line.set_text("reset")
    line.info()
    line.warn()
    line.crit()
    line.debug()
    line.get()
    line.post()

    assert console.curent_line >= 1
    assert len(console._line_data) >= 1


def test_logger_delegates_to_console_and_optional_file(tmp_path: Path):
    with_file = Logger(str(tmp_path / "delegated.log"))
    without_file = Logger()

    assert with_file.info("a") is not None
    assert with_file.log("b") is not None
    assert with_file.warn("c") is not None
    assert with_file.error("d") is not None
    assert with_file.crit("e") is not None
    assert with_file.debug("f") is not None
    assert with_file.get("/g") is not None
    assert with_file.post("/h") is not None
    assert with_file.delete("/i") is not None

    assert without_file.info("a") is not None
    assert without_file.log("b") is not None
    assert without_file.warn("c") is not None
    assert without_file.error("d") is not None
    assert without_file.crit("e") is not None
    assert without_file.debug("f") is not None
    assert without_file.get("/g") is not None
    assert without_file.post("/h") is not None
    assert without_file.delete("/i") is not None
