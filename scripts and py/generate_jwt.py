import base64
import json
import hmac
import hashlib

def base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")

def generate_jwt(secret: str, payload: dict) -> str:
    # Header
    header = {
        "alg": "HS256",
        "typ": "JWT"
    }

    # Encode header & payload
    header_encoded = base64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_encoded = base64url_encode(json.dumps(payload, separators=(",", ":")).encode())

    unsigned_token = f"{header_encoded}.{payload_encoded}"

    # Signature
    signature = hmac.new(
        secret.encode(),
        unsigned_token.encode(),
        hashlib.sha256
    ).digest()

    signature_encoded = base64url_encode(signature)

    # Final JWT
    return f"{unsigned_token}.{signature_encoded}"


if __name__ == "__main__":
    secret = "Snowfall@2026"

    payload = {
        "sub": "thousandeyes-webhook",
        "iss": "te",
        "role": "webhook"
        # No "exp" → never expires
    }

    token = generate_jwt(secret, payload)
    print("\nGenerated JWT:\n")
    print(token)