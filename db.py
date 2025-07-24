import time
import os
from typing import Union
import psycopg
from psycopg.rows import dict_row
from psycopg.connection import Connection, Cursor

IS_TEST = os.getenv("TESTING") == "1"

conn: Union[Connection, None] = None
curr: Union[Cursor, None] = None

while True:
    try:
        #   Change later to remove hardcode connection (env variables)
        conn = psycopg.connect(conninfo="host=localhost dbname=fastapi user=postgres password=password",
                               row_factory=dict_row)
        curr = conn.cursor()
        print("Database connection was successful")
        break
    except Exception as error:
        print("Connection to database failed")
        print("Error: ", error)
        time.sleep(3)

def commit():
    if IS_TEST:
        print("⚠️ Running in TESTING mode — DB commits are disabled!")
    if not IS_TEST:
        conn.commit()