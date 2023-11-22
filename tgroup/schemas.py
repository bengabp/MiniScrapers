from pydantic import BaseModel
from typing import Dict, List, Optional, Union

Nullable = Union[str, None]


class Member(BaseModel):
	username: Nullable
	firstname: Nullable
	lastname: Nullable
	phone_number: Nullable
	uid: Union[int, None]
	
class Client(BaseModel):
	phone_number: str
	name: str
	api_hash: str
	api_id: int
	
	