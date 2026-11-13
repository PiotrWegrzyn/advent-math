from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.pool import StaticPool


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        options = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in url or url == "sqlite://":
            options["poolclass"] = StaticPool
        return create_engine(url, **options)
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)


ADDED_COLUMNS = {"task_variants": {"image": "TEXT"}}


def add_missing_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table, columns in ADDED_COLUMNS.items():
            if not inspector.has_table(table):
                continue
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, sql_type in columns.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}"))
