from typing import Union, List

from fastapi import FastAPI
from fastapi.params import Body
from pydantic import BaseModel

app = FastAPI()

# Declare body types using Python types
class Item(BaseModel):
    id: int
    name: str
    price: float
    is_offer: Union[bool, None] = None

class ItemList(BaseModel):
    items: List[Item]

@app.get("/")
def root():
    return {"Hello:" "World"}

@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"Error": "Item does not exist"}

@app.post("/create-items/")
def create_item(payload: dict = Body(...)):
    # mock create
    print(payload)
    return {"message": "Successfully created items"}

@app.put("/items/{item_id}")
def update_item(item_id: int, item: Item):
    return {"item_name": item.name, "item_price": item.price, "item_id": item_id}

# Logs related API (CRUD)
# GET
#  Return all or filtered logs
@app.get("/logs")
def search_log(q: Union[str, None] = None):
    return {"Hello: World"}

#  Return logs by id
@app.get("/logs/{id}")
def search_log_id(id: int):
    return {"Hello: World"}

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
@app.post("/logs")
def create():
    return {"Hello: World"}

# Create entries in bulk (with tenant ID)
@app.post("/logs/bulk")
def create_bulk():
    return {"Hello: World"}

# Create new tenant (admin only)
@app.post("/tenants")
def create_tenant():
    return {"Hello: World"}

# DELETE
# delete old logs (tenant-scoped)
@app.delete("logs/cleanup")
def delete_logs():
    # should not have return statement
    return {"Hello: World"}

# WS
# real-time log streaming **
@app.websocket("/logs/stream")
def log_stream():
    # What should it return?
    return {"Hello: World"}
