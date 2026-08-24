from pydantic import BaseModel

class FamiliasGetResponse(BaseModel):
    familias: list[str]