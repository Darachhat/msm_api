from typing   import Generic, Optional, TypeVar
from pydantic import BaseModel, ConfigDict, Field
from ulid     import ULID

DataType = TypeVar("DataType")


def get_ulid() -> str:
    """Generate a ULID trace identifier."""
    return str(ULID())


class Base(BaseModel):
    """Base Pydantic model with common configuration."""

    model_config = ConfigDict(
        from_attributes   = True
        , use_enum_values = True
    )


class IResponseBase(BaseModel, Generic[DataType]):
    trace_id : str                = Field(default_factory = get_ulid)
    status   : int                = 1
    message  : str                = "Success"
    data     : Optional[DataType] = None
