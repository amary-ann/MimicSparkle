from pydantic import BaseModel, Field
from typing import List, Optional

class UserProfile(BaseModel):
    name:  Optional[str] = None

class Contact(BaseModel):
    profile: UserProfile = None
    wa_id:  Optional[str] = None

class Metadata(BaseModel):
    display_phone_number: str = ""
    phone_number_id: str = ""

class TextMessage(BaseModel):
    body: Optional[str] = None

class Message(BaseModel):
    from_: str = Field("", alias="from")
    id: str=""
    timestamp: Optional[str] = None
    type: str = ""
    type: str=""
    text: Optional[TextMessage] = None

    # class Config:
    #     fields = {"from_": "from"}

class Value(BaseModel):
    messaging_product: str = ""
    metadata: Metadata= None
    contacts: List[Contact]
    messages: Optional[List[Message]] = None
    statuses: Optional[List[dict]] = None

class Change(BaseModel):
    value: Optional[Value] = None
    field: Optional[str] = None

class Entry(BaseModel):
    id: Optional[str] = None
    changes: Optional[List[Change]] = None

class WhatsAppWebhook(BaseModel):
    object: Optional[str] = None
    entry: Optional[List[Entry]] = None

class MsgRequest(BaseModel):
    to: str
    message: str