import logging
import os
import sqlite3
from time import sleep
import click
from loggers.sqlite import SqliteHandler


def do_work():
    # note that the logger name
    log = logging.getLogger("app")
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
    with open("db/create.sql", "r") as f:
        query = f.read()
    with db:
        if drop:
            db.execute(f"DROP TABLE IF EXISTS {table}")
            log.debug("dropped table")
        query = query.format(table=table)
        log.debug(f"query: {query}")
        db.execute(query)

    # craete custom handler for this logger
    # note that unlike usual __name__ argument, logger
    # has its unique id (app in this case)
    db_logger = SqliteHandler(db, table=table)
    db_logger.setLevel(logging.INFO)
    log.addHandler(db_logger)

    # make some log calls
    do_work()


if __name__ == "__main__":
    main()
