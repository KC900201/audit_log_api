from typing import Union, List
from datetime import datetime

from fastapi import FastAPI, Response, status, HTTPException
from pydantic import BaseModel

app = FastAPI()

# Declare body types using Python types
class Log(BaseModel):
    id: Union[int, None] = None
    userId: int
    text: str
    level: str = "INFO"
    timeStamp: datetime

class ItemList(BaseModel):
    items: List[Log]

# Mock lists
item_list = [
    {"id": 1, "userId": 100100, "text": "Test string", "level": "ERROR", "timeStamp": datetime.now()},
    {"id": 2, "userId": 100101, "text": "Hello World", "level": "WARNING", "timeStamp": datetime.now()},
    {"id": 3, "userId": 100102, "name": "Hello KC", "level": "CRITICAL", "timeStamp": datetime.now()}
]


def find_log(id):
    for item in item_list:
        if item["id"] == id:
            return item
    return None

def find_index_log(id):
    for i, p in enumerate(item_list):
        if p["id"] == id:
            return i
    return None

@app.get("/")
def root():
    return {"Hello": "World"}

# Logs related API (CRUD)
# GET
#  Return all or filtered logs
@app.get("/logs/")
def search_log(q: Union[str, None] = None):
    if not item_list:
        return {"Error:" "Log list is empty"}

    return {"list": item_list}

#  Return logs by id
@app.get("/logs/{id}")
def search_log_id(id: int, response: Response):
    if not item_list:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Log list is empty")

    item = find_log(id)

    if not item:
        # trigger exception
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Log with id {id} does not exist")

    return {"item": item}

# Export logs (tenant-scoped) **
@app.get("/logs/export")
def export_log():
    return {"Hello: World"}

# Return log statistics (tenant-scoped) **
@app.get("/logs/stats")
def get_stats():
    return {"Hello: World"}

# List accessible tenant (admin only)
@app.get("/tenants")
def search_tenant():
    return {"Hello: World"}

# POST
# Create log entry (with tenant-ID)
@app.post("/logs/", status_code=status.HTTP_201_CREATED)
def create_log(log: Log):
    # mock create
    item_dict = log.model_dump()
    item_dict["id"] = len(item_list) + 1
    item_list.append(item_dict)
    return {"message": "Successfully created items"}

# Create entries in bulk (with tenant ID)
@app.post("/logs/bulk", status_code=status.HTTP_201_CREATED)
def create_bulk():
    return {"Hello: World"}

# Create new tenant (admin only)
@app.post("/tenants")
def create_tenant():
    return {"Hello: World"}

# PUT
@app.put("/logs/{id}", )
def update_log(id: int, log: Log):
    if not item_list:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log list is empty")

    index = find_index_log(id)

    if index is None:
        # trigger exception
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Log with id {id} does not exist")

    log_dict = log.model_dump()
    log_dict["id"] = id
    item_list[index] = log_dict

    return {"log": log_dict}

# DELETE
# delete old logs (tenant-scoped)
@app.delete("logs/cleanup")
def delete_logs():
    while len(item_list) > 0:
        item_list.pop()

    return {"message": "All logs are deleted"}

@app.delete("/logs/cleanup/{id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_item(id: int):
    item = find_log(id)
    if item:
        item_list.remove(item)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Log with id {id} does not exist")

# WS
# real-time log streaming **
@app.websocket("/logs/stream")
def log_stream():
    # What should it return?
    return {"Hello: World"}
