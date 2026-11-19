from typing   import Generic, Optional, TypeVar
from pydantic import BaseModel

DataType = TypeVar("DataType")


class IResponseBase(BaseModel, Generic[DataType]):
    status  : int                = 1
    message : str                = "Success"
    data    : Optional[DataType] = None
