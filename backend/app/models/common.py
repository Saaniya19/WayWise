
from pydantic import BaseModel, ConfigDict, Field

class Location(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    name: str | None = None
    placeId: str | None = None
