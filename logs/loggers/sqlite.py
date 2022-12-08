import logging
import sqlite3


class SqliteHandler(logging.StreamHandler):
    def __init__(self, conn: sqlite3.Connection, table: str) -> None:
        super().__init__()
        self.conn = conn
        self.table = table
        self.log = logging.getLogger(__name__)

    def emit(self, record: logging.LogRecord) -> None:
        # record can be formatted with a custom formatter here
        # or parsed into a more meaningful type
        # e.g. on certain types of events we might want
        # additional formatting (say, json) or a stacktrace
        msg = self.format(record)
        table = self.table
        try:
            with self.conn:
                self.conn.execute(
                    f"insert into {table}(level, time, msg) values (?, ?, ?)",
                    (record.levelname, record.asctime, msg),
                )
        except sqlite3.IntegrityError as e:
            self.log.error(msg=f"{e}")


class SqliteLogHandler(logging.StreamHandler):
    def __init__(self, conn: sqlite3.Connection, table: str, sender: str) -> None:
        super().__init__()
        self.conn = conn
        self.table = table
        self.sender = sender
        # default logger for unprocessable entries
        self.log = logging.getLogger(__name__)

    def emit(self, record: logging.LogRecord) -> None:
        # record can be formatted with a custom formatter here
        # or parsed into a more meaningful type
        # e.g. on certain types of events we might want
        # additional formatting (say, json) or a stacktrace
        msg = self.format(record)
        table = self.table
        try:
            with self.conn:
                self.conn.execute(
                    f"insert into {table}(level, time, msg, sender) values (?, ?, ?, ?)",
                    (record.levelname, record.asctime, msg, self.sender),
                )
        except sqlite3.IntegrityError as e:
            self.log.error(msg=f"{e}")
