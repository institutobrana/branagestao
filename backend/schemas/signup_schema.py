from pydantic import BaseModel


class SignupSchema(BaseModel):
    nome: str
    email: str
    senha: str