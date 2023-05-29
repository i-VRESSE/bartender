from datetime import datetime, timedelta
from typing import Annotated, Sequence
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from fastapi import Body, FastAPI
import jwt
from pydantic import BaseModel

app = FastAPI()


def load_key_pair():
    """Key pair loader.

    ```shell
    openssl genpkey -algorithm RSA -out private_key.pem -pkeyopt rsa_keygen_bits:2048
    openssl rsa -pubout -in private_key.pem -out public_key.pem
    ```

    Returns:
        _description_
    """
    with open("private_key.pem", "rb") as key_file:
        private_key = serialization.load_pem_private_key(
            key_file.read(),
            password=None,
            backend=default_backend(),
        )
    with open("public_key.pem", "rb") as key_file:
        public_key = serialization.load_pem_public_key(
            key_file.read(),
        )
    return private_key, public_key


private_key, public_key = load_key_pair()

# TODO add /.well-known/jwks.json endpoint
@app.get(".well-known/jwks.json")
async def root():
    # TODO find library to generate jwks
    return {
        "keys": [
            {
                "kty": "RSA",
                "alg": "RS256",
                "use": "sig",
                "n": public_key.public_numbers().n,
                "kid":
            }
        ]
    }


@app.get("/token")
def get_token(
    username: str = "someone",
):
    roles: Sequence[str] = ("expert", "guru")
    expire = datetime.utcnow() + timedelta(minutes=15)
    payload = {
        "sub": username,
        "exp": expire,
        "roles": roles,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


class Token(BaseModel):
    jwt: str


@app.post("/verify")
def verify_token(
    token: Token,
):
    return jwt.decode(token.jwt, public_key, algorithms=["RS256"])
