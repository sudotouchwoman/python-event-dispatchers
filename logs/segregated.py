import logging
import os
import sqlite3
from time import sleep
import click
from loggers.sqlite import SqliteLogHandler


def logger_factory(
    name: str, table: str, conn: sqlite3.Connection
) -> logging.Logger:
    # returns logger instance configured with sqlite
    # connection
    log = logging.getLogger(name)
    if not log.hasHandlers():
        log.setLevel(logging.DEBUG)
        # log messages to the stderr, as usual
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            fmt="[%(asctime)s]::[%(name)s]::[%(threadName)s] - %(message)s",
            datefmt="%H:%M:%S",
        )
        console.setFormatter(formatter)
        log.addHandler(console)

        db_logger = SqliteLogHandler(conn, table=table, sender=name)
        db_logger.setLevel(logging.INFO)
        log.addHandler(db_logger)

    return log


def do_work(name: str):
    log = logging.getLogger(name)
    log.debug("will do work")
    log.info("start")
    sleep(4)
    log.debug("finished with work")
    log.warning("work done")
    sleep(1)
    log.error("error")


@click.command()
@click.option(
    "-t",
    "--table",
    default="test",
    help="Table to store logs in",
)
@click.option(
    "-d",
    "--drop",
    is_flag=True,
    default=False,
    help="Drop sqlite table if it already exists",
)
@click.option(
    "-f",
    "--file",
    default="db/test.db",
    help="Path to sqlite db file",
)
def main(table, drop, file):
    log = logging.getLogger("app")
    log.setLevel(logging.DEBUG)
    # log messages to the stderr, as usual
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        fmt="[%(asctime)s]::[%(name)s]::[%(threadName)s] - %(message)s",
        datefmt="%H:%M:%S",
    )
    console.setFormatter(formatter)
    log.addHandler(console)

    # create db file if nesessary
    if not os.path.isfile(file):
        with open(file, "x") as f:
            log.debug("made sure that db file exists")

    db_uri = f"file:{file}?mode=rw"
    log.debug(f"connecting to {db_uri}")
    db = sqlite3.connect(db_uri, uri=True)
    # create/drop table
    with open("db/create-with-sender.sql", "r") as f:
        query = f.read()
    with db:
        if drop:
            db.execute(f"DROP TABLE IF EXISTS {table}")
            log.debug("dropped table")
        query = query.format(table=table)
        log.debug(f"query: {query}")
        db.execute(query)

    for component in ("agent", "lift"):
        logger_factory(component, table, conn=db)

    # make some log calls
    for component in ("agent", "lift"):
        do_work(component)


if __name__ == "__main__":
    main()
