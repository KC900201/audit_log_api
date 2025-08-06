import pytest
from db import conn

@pytest.fixture(scope="function", autouse=True)
def db_transaction():
    # Start a transaction
    with conn.transaction():
        yield
        # When context exits, rollback transaction if conn.commit() is not called
