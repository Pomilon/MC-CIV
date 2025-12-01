from pydantic import BaseModel, Field
from typing import List, Literal, Union

class BroadcastEvent(BaseModel):
    action: Literal["BROADCAST"] = "BROADCAST"
    message: str = Field(..., description="The message to display to all players.")

class SpawnEvent(BaseModel):
    action: Literal["SPAWN"] = "SPAWN"
    entity_type: str = Field(..., description="The entity ID to spawn (e.g., zombie, pig).")
    location: str = Field("random", description="'random' or coordinates 'x y z'")

class WeatherEvent(BaseModel):
    action: Literal["WEATHER"] = "WEATHER"
    type: Literal["clear", "rain", "thunder"] = "clear"

class WaitEvent(BaseModel):
    action: Literal["WAIT"] = "WAIT"
    reason: str = Field(..., description="Why the narrator is waiting.")

# Union
NarratorAction = Union[BroadcastEvent, SpawnEvent, WeatherEvent, WaitEvent]
