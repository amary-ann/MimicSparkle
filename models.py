from beanie import Document, Update, Save, SaveChanges, Replace, Insert, before_event
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone
from typing import List

def get_utc_now():
    return datetime.now(timezone.utc)

class BaseDocument(Document):
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)

    @before_event(Insert)
    def set_created_at(self) -> None:
        self.created_at = get_utc_now()

    @before_event(Update, Save, SaveChanges, Replace)
    def set_updated_at(self) -> None:
        self.updated_at = get_utc_now()


class MsgRequest(BaseModel):
    phone_number: str
    message: str
class Message(BaseDocument):
    message: str
    is_user: bool

class Beneficiary(BaseDocument):
    phone_number: str
    name: str
    account_number: str
    bank: str

    class Settings:
        name = "beneficiary"

    
class Session(BaseDocument):
    phone_number: str
    chats: List[Message] = []
    is_active: bool = True
    does_user_exist: bool = False
    chat_phase: str = 'default'
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    address: Optional[str] = None
    account_number: str = ""
    beneficiary: List[Beneficiary] = []
    is_transfer_initiated: bool = False
    is_account_balance_initiated: bool = False
    transfer_prompt_shown: bool = False
    recipient_type: Optional[str] = None    

    class Settings:
        name = "sessions"

class User(BaseDocument):
    phone_number: str
    first_name: str 
    last_name: str
    email: str
    address: str
    dob: str
    bvn : str 
    account_number: str
    account_link: Optional[str] = None
    is_account_active: bool = True
    
    class Settings:
        name = "user"

class Balance(BaseDocument):
    account_number:str
    balance:float=Field(default=0.0)

    class Settings:
        name = "balance"

class PinRequest(BaseModel):
    pin:str
    phone_number: str

class RegPinRequest(BaseModel):
    pin:str
    confirm_pin:str
    phone_number: str

class Pin(BaseDocument):
    pin: Optional[str] = None
    confirm_pin:str
    phone_number: str

class Request(BaseModel):
    phone_number: str
    message: Optional[str] = ""
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    num_media: Optional[int] = 0
    
class NotifyRequest(BaseModel):
    reference: Optional[str] = None
    narration: Optional[str] = None
    amount: float= Field(default=0.0)
    customerId: Optional[int] = None
    accountNumber:str
    originatorAccountNumber: str
    originatorAccountName: str
    originatorBank: str
    originatorNarration: Optional[str] = None
    isVirtualPayment: bool=False
    
@dataclass
class AppResponse:
    success: bool
    message: str
