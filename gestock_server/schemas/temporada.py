from pydantic import BaseModel

class TemporadasGetResponse(BaseModel):
    temporadas: list[str]