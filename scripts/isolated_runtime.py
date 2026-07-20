import re
import socket
import subprocess
import time

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


ISOLATED_DATABASE_NAME = re.compile(
    r"(?:integration_credentials|variant_collection)_smoke_[0-9a-f]{32}"
)


def _validate_database_name(database_name: str) -> None:
    if not ISOLATED_DATABASE_NAME.fullmatch(database_name):
        raise ValueError("Unsafe isolated smoke database name.")


def build_isolated_database_url(admin_database_url: str, database_name: str) -> str:
    _validate_database_name(database_name)
    url = make_url(admin_database_url)
    if not url.drivername.startswith("postgresql"):
        raise ValueError("Isolated smoke requires PostgreSQL.")
    return url.set(database=database_name).render_as_string(hide_password=False)


def create_isolated_database(admin_database_url: str, database_name: str) -> None:
    _validate_database_name(database_name)
    engine = create_engine(admin_database_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    finally:
        engine.dispose()


def drop_isolated_database(admin_database_url: str, database_name: str) -> None:
    _validate_database_name(database_name)
    engine = create_engine(admin_database_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
    finally:
        engine.dispose()


def available_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_backend(api_url: str, process: subprocess.Popen, timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Isolated smoke backend exited before startup.")
        try:
            if httpx.get(f"{api_url}/health", timeout=1).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.25)
    raise TimeoutError("Isolated smoke backend did not become healthy.")


def stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
