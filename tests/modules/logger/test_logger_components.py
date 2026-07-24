from pathlib import Path

from src.modules.logger.logger import Logger


def test_file_logger_writes_entries(tmp_path: Path):
    log_file = tmp_path / "app.log"
    logger = Logger(str(log_file))

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
    assert "[WARN]" in content
    assert "[ERROR]" in content
    assert "[CRIT]" in content
    assert "[DEBUG]" in content
    assert "[GET]" in content
    assert "[POST]" in content
    assert "[DELETE]" in content


def test_logger_works_without_a_file():
    logger = Logger()

    logger.info("a")
    logger.log("b")
    logger.warn("c")
    logger.error("d")
    logger.crit("e")
    logger.debug("f")
    logger.get("/g")
    logger.post("/h")
    logger.delete("/i")
