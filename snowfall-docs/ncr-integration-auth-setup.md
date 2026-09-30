# NCR ServiceDesk Integration – Authentication & Architecture Q&A Document

**Project**: McDonald's UK Snowfall Data Pipeline  
**Integration**: AWS Lambda → NCR Service Desk SOAP API  
**NCR Doc Reference**: NCR Service Desk Web Services Technical Doc v3.2 (June 2021)  
**Prepared by**: McDonald's UK Engineering Team  
**Date**: April 2026

---

## Overview

The McDonald's UK Snowfall platform runs proactive monitoring Lambdas in AWS. When an alert is
triggered (e.g. a device issue detected at a restaurant), the system needs to automatically raise
an incident ticket in the NCR Service Desk system.

This document describes the proposed authentication model and open questions that need to be
resolved with the NCR onboarding team before implementation can proceed.

---

## System Components

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  AWS (eu-central-1)                                                         │
│                                                                             │
│  EventBridge (scheduled)                                                    │
│       │                                                                     │
│       ▼                                                                     │
│  snowfall-proactive-alerts Lambda                                           │
│       │                                                                     │
│       │  HTTPS POST (SOAP 1.1)                                              │
│       │  ┌─ WS-Security header (USERID + Password)                         │
│       │  └─ mTLS client certificate                                         │
│       │                                                                     │
│       ▼                                                                     │
│  NCR Enterprise Service Bus (ESB) ──► NCR Service Desk                     │
│                                                                             │
│  ◄──────── NCRIncidentUpdate callback (async, NCR-initiated)                │
│       │                                                                     │
│       ▼                                                                     │
│  API Gateway (REST HTTPS :443)                                              │
│       │                                                                     │
│       ▼                                                                     │
│  snowfall-ncr-callback Lambda                                               │
│       │                                                                     │
│       ▼                                                                     │
│  DynamoDB (proactive_alerts_table)                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Authentication Model (per NCR v3.2 spec)

NCR requires **2-Factor Authentication** for all inbound calls:

### Factor 1 – WS-Security SOAP Header (Username/Password)

Every SOAP request must include a `<wsse:Security>` block in the SOAP envelope header:

```xml
<soapenv:Header>
  <wsse:Security
    xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
    <wsse:UsernameToken>
      <wsse:Username>USERID_FROM_NCR</wsse:Username>
      <wsse:Password
        Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd#PasswordText">
        PASSWORD_FROM_NCR
      </wsse:Password>
    </wsse:UsernameToken>
  </wsse:Security>
</soapenv:Header>
```

- USERID and Password are provisioned by the NCR integration team (NCA/SOUP domain account)
- Password minimum length: 24 characters
- Password must be rotated **annually**, aligned with SSL certificate renewal
- One unique account per business process / per country

**How we store this in AWS:**
```
AWS Secrets Manager secret: "ncr/credentials"
{
  "userid":   "SOUP_USERID_HERE",
  "password": "SOUP_PASSWORD_HERE"
}
```

---

### Factor 2 – SSL Mutual TLS (mTLS) Client Certificate

Every HTTPS connection from Lambda to NCR must present a **client certificate** so NCR can
authenticate the caller at the TLS layer.

**Certificate requirements (per NCR spec):**
- Must be a **commercial certificate** from one of: DigiCert, GoDaddy, Thawte, Comodo, GeoTrust
- URL must be HTTPS
- CN name must include and match the customer name (McDonald's UK)
- Must **not** be expired
- Must **not** be revoked (CRL reachable, or OCSP used as fallback)
- **Separate certificates required** for CERT (test) and PROD environments

**How we store this in AWS:**
```
AWS Secrets Manager secret: "ncr/client-cert-{env}"   → full PEM certificate string
AWS Secrets Manager secret: "ncr/client-key-{env}"    → PEM private key string
```

**How Lambda uses the certificate:**

Lambda writes the PEM strings to `/tmp` (ephemeral, never persisted outside the execution
environment) at cold start, then passes them to the `requests` library:

```python
import requests, tempfile, os, boto3, json

_cert_path = None
_key_path  = None

def _load_mtls_certs():
    global _cert_path, _key_path
    if _cert_path and os.path.exists(_cert_path):
        return  # reuse on warm invocation

    sm = boto3.client("secretsmanager")
    cert_pem = sm.get_secret_value(SecretId="ncr/client-cert-prod")["SecretString"]
    key_pem  = sm.get_secret_value(SecretId="ncr/client-key-prod")["SecretString"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pem", dir="/tmp") as f:
        f.write(cert_pem.encode())
        _cert_path = f.name

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pem", dir="/tmp") as f:
        f.write(key_pem.encode())
        _key_path = f.name

def call_ncr_soap(soap_body: str, endpoint_url: str) -> str:
    _load_mtls_certs()
    response = requests.post(
        endpoint_url,
        data=soap_body.encode("utf-8"),
        headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": '""'},
        cert=(_cert_path, _key_path),  # <-- mTLS client cert
        verify=True,                    # <-- validates NCR server cert
        timeout=30,
    )
    response.raise_for_status()
    return response.text
```

---

## Network / Connectivity

| Direction | From | To | Port | Auth |
|---|---|---|---|---|
| Inbound to NCR | AWS Lambda (VPC or public) | NCR ESB endpoint | 443 (HTTPS) | mTLS + WS-Security header |
| Outbound from NCR | NCR ESB | Our API Gateway | 443 (HTTPS) | **Basic auth (username/password) OR client certificate** — confirmed in meeting 15 Apr 2026 |

**Note from NCR spec:**
> NCR preferred port for sending outbound responses is **443**. If a different port is used,
> NCR must submit a Firewall Rule change request to NCR global security — this adds time.

Our callback endpoint uses AWS API Gateway on port 443 by default — no firewall change needed.

---

## NCR Environments

| Environment | Purpose | URL |
|---|---|---|
| CERT | Development / QA / testing | *To be provided by NCR* |
| PROD | Live production | *To be provided by NCR* |

Each environment requires its own:
- Separate SOAP endpoint URL
- Separate SSL client certificate (NCR explicitly does NOT recommend sharing certs across environments)
- Separate SOUP domain account credentials

---

## SOAP Operation Used

For raising an incident we use `createServiceRequest`.

**Key fields we send:**

| Field | Source in our system |
|---|---|
| `TransactionID` | UUID generated per alert (idempotency key) |
| `USERID` | From Secrets Manager |
| `SourceSystem` | To be confirmed with NCR |
| `CountryCode` | `GB` |
| `CustomerTicketID` | Our `alert_id` (stored in DynamoDB) |
| `Type` (CallType) | From rule config (e.g. `HELPDESK`, `MAIN`) |
| `Priority` | From rule config (1=Critical, 2=Urgent, 3=Normal) |
| `Summary` | Alert rule name + message |
| `Description` | Alert details + script results (max 4000 chars) |
| `Site.SiteShortName` | Restaurant number |
| `CI.AssetID` | Device ID |
| `ATMCustomerMetrics.NCRMCN` | McDonald's UK NCR master customer number |
| `ATMCustomerMetrics.SSDGCustomer` | `0` (false) unless confirmed otherwise |

**What we get back (synchronous ACK):**

| Field | Description |
|---|---|
| `TransactionID` | Echoes our GUID |
| `Status` | `SUCCESS` or `FAILURE` |
| `FaultCode` / `FaultDescription` | Only present on failure |

⚠️ **The NCR ticket ID (`INCxxxxxxx`) is NOT returned in the create ACK.**
It arrives asynchronously via the outbound `NCRIncidentUpdate` callback.

---

## Outbound Callback from NCR

NCR will call our API Gateway endpoint when the ticket status changes.

**Our endpoint (to give to NCR):**
```
https://<api-gateway-id>.execute-api.eu-central-1.amazonaws.com/prod/ncr-callback
```

NCR sends `NCRIncidentUpdate` containing:
- `CustomerTicketID` — our original alert_id, used to look up the DynamoDB record
- `NCRTicketID` — the `INCxxxxxxx` number we need to store back
- `NCRTicketStatus` — OPEN / ASSIGNED / DISPATCHED / WORK IN PROGRESS / COMPLETED / CANCELLED

Our callback Lambda responds with `NCRIncidentUpdateResponseMessage` (ACK) within 5 seconds.

---

## DynamoDB Record (proactive_alerts_table)

Fields added for NCR integration:

| Attribute | Set when | Value example |
|---|---|---|
| `ncr_transaction_id` | On `createServiceRequest` | `"3f2a1b...` (our GUID) |
| `ncr_create_status` | On `createServiceRequest` ACK | `"SUCCESS"` / `"FAILED"` |
| `ncr_ticket_id` | When NCR callback arrives | `"INC0012345"` |
| `ncr_ticket_status` | When NCR callback arrives | `"ASSIGNED"` |

---

## IAM Permissions Required

The proactive-alerts Lambda execution role needs:

```json
{
  "Effect": "Allow",
  "Action": "secretsmanager:GetSecretValue",
  "Resource": [
    "arn:aws:secretsmanager:eu-central-1:*:secret:ncr/credentials*",
    "arn:aws:secretsmanager:eu-central-1:*:secret:ncr/client-cert*",
    "arn:aws:secretsmanager:eu-central-1:*:secret:ncr/client-key*"
  ]
}
```

---

## Open Questions for NCR Onboarding Team

### Authentication & Credentials
1. What is the `USERID` and initial `Password` for the CERT environment SOUP account?
2. What is the `USERID` and initial `Password` for the PROD environment SOUP account?
3. What `SourceSystem` value should we send to identify our system in the SOAP header?
4. Should the WS-Security password be sent as `PasswordText` or `PasswordDigest`?

### Certificates (mTLS)
5. Do we generate the client certificate ourselves and send the CSR to NCR, or does NCR issue it?
6. If we generate it: what CN name format is expected? (e.g. `mcdonalds-uk`, `MCD-UK`, etc.)
7. Where do we submit the certificate for registration in the NCR system?
8. Do we need separate certificates for CERT and PROD? (NCR spec says yes — confirming)

### Endpoints
9. What is the CERT endpoint URL for `createServiceRequest`?
10. What is the PROD endpoint URL for `createServiceRequest`?
11. Is the NCR server certificate issued by a standard trusted CA (so Lambda's default `certifi` bundle works), or do we need to add a custom CA?

### Customer Mapping
12. What is the `NCRMCN` value for McDonald's UK?
13. What is the `SSDGCustomer` value for McDonald's UK (true/false)?
14. Does the restaurant number (e.g. `1234`) map directly to `SiteShortName` in NCR's system?
15. What `AssetID` format does NCR expect for restaurant devices?

### Outbound Callback
16. ~~What authentication does NCR use when calling our callback endpoint?~~ ✅ **Confirmed 15 Apr 2026: NCR supports Basic auth (username/password) or client certificate. We will choose one — decision pending.** See meeting notes below.
17. Does NCR support IP whitelisting for the outbound callback calls? If so, what are the NCR NAT/egress IPs?
18. Does NCR need to register our callback endpoint URL before starting to send updates?

### Error Codes
19. Can NCR provide the full list of `FaultCode` values returned on failures?

---

## What We Need to Provide to NCR

| Item | Description |
|---|---|
| Our callback endpoint URL | `https://<apigw>.execute-api.eu-central-1.amazonaws.com/prod/ncr-callback` |
| Client certificate (CSR or PEM) | For CERT environment first, then PROD |
| Our outbound static IP (if needed) | AWS Lambda in VPC with NAT Gateway gives fixed IP |
| `SourceSystem` identifier | To be agreed |

---

## Meeting Notes

### 15 April 2026 — NCR Onboarding Call

- **Callback authentication**: NCR confirmed two supported options for authenticating their outbound `IncidentUpdate` calls to our API Gateway:
  1. **Basic Auth** — NCR sends a static username and password in the HTTP `Authorization` header.
  2. **Client Certificate** — NCR presents a client certificate when calling our endpoint (mTLS on our side).
- **Decision required**: We need to decide which option to implement and confirm with NCR. Current preference is **Basic Auth** as it is simpler to validate at API Gateway level (AWS API Gateway does not natively terminate mTLS for inbound connections without a Lambda authorizer or NLB).
- **Action**: Agree the chosen auth method with NCR and obtain the credentials (if Basic) or their certificate (if cert-based) before building the callback API Gateway.

---

## Implementation Statusí

| Component | Status |
|---|---|
| Proactive-alerts Lambda (alerts, email, scripts) | ✅ Done |
| NCR `create_ncr_ticket()` function | ⏳ Pending credentials |
| `ncr/credentials` Secrets Manager secret | ⏳ Pending NCR provisioning |
| `ncr/client-cert` + `ncr/client-key` secrets | ⏳ Pending certificate process |
| `snowfall-ncr-callback` Lambda | ⏳ Ready to build |
| API Gateway for NCR callback | ⏳ Ready to build |
| DynamoDB schema NCR fields | ⏳ Ready to add |
| Terraform for new resources | ⏳ Ready to write |
