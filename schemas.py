from datetime import datetime
from pydantic import BaseModel, EmailStr
from typing import Union, Dict, Any, Optional
from uuid import UUID

# Declare class using Python types
class Log(BaseModel):
    id: Optional[UUID] = None
    tenant_id: UUID
    user_id: UUID
    session_id: str
    ip_address: str
    user_agent: str
    action_type: str
    resource_type: str
    resource_id: str
    severity: str
    before_state: Optional[Dict[str, Any]] = None
    after_state: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

class Tenant(BaseModel):
    id: Union[UUID, None] = None
    name: str
    status: str
    created_at: Optional[datetime] = None

class User(BaseModel):
    tenant_id: UUID
    email: EmailStr
    full_name: str
    role: str