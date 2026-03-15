import json
import jwt
import boto3
import os

# AWS clients
secretsmanager = boto3.client("secretsmanager")

# JWT settings
JWT_ALGORITHM = "HS256"

# Your existing secret name and key
SECRET_NAME = "uk-snowfall-service-agent"
SECRET_KEY = "uk-snowfall-service-agent-key"


def get_jwt_secret():
    """
    Fetch JWT secret from Secrets Manager.
    """
    response = secretsmanager.get_secret_value(SecretId=SECRET_NAME)
    secret_dict = json.loads(response["SecretString"])
    return secret_dict[SECRET_KEY]


def generate_policy(principal_id, effect, resource):
    """
    Build IAM policy for API Gateway custom authorizer.
    """
    return {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": resource
                }
            ]
        }
    }


def lambda_handler(event, context):
    print("Event:", event)

    try:
        # -----------------------------------------
        # 1. Extract Authorization header
        # -----------------------------------------
        auth_header = event.get("authorizationToken", "")

        if not auth_header.startswith("Bearer "):
            print("Missing or invalid Authorization header")
            return {"isAuthorized": False}

        token = auth_header.replace("Bearer ", "").strip()

        # -----------------------------------------
        # 2. Decode JWT using secret
        # -----------------------------------------
        jwt_secret = get_jwt_secret()

        decoded = jwt.decode(
            token,
            jwt_secret,
            algorithms=[JWT_ALGORITHM]
        )

        print("Decoded JWT:", decoded)

        # -----------------------------------------
        # 3. No claim validation needed
        # -----------------------------------------
        # ThousandEyes does not send machine name or custom claims.
        # If token is valid, allow the request.

        # -----------------------------------------
        # 4. Return Allow policy
        # -----------------------------------------
        return generate_policy(
            principal_id="thousandeyes",
            effect="Allow",
            resource=event["methodArn"]
        )

    except jwt.ExpiredSignatureError:
        print("JWT expired")
        return {"isAuthorized": False}

    except jwt.InvalidTokenError as e:
        print("Invalid JWT:", str(e))
        return {"isAuthorized": False}

    except Exception as e:
        print("Authorizer error:", str(e))
        return {"isAuthorized": False}
