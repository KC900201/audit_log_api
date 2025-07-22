import time
import psycopg
from psycopg.rows import dict_row

conn = None
curr = None

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
