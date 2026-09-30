# NCR Voyix Incident Management Integration — Summary

**Source documents:**
- `NCR Voyix Standard Restaurant Incident Management Web Services Technical Doc V1.1.pdf`
- `Sample Messages for Restaurant Incident Management Interface.pdf`
- `NCR Voyix Restaurant Standard Mapping Doc.xlsx`

---

## What NCR Voyix provides

NCR Voyix operates an **Incident Management system** (backed by ServiceNow) for restaurant equipment faults. When a device issue is raised, NCR dispatches engineers, ships parts, and tracks the ticket through to resolution.

The integration is **bi-directional REST JSON over HTTPS**:

| Direction | Who calls who | What it does |
|---|---|---|
| **Inbound (us → NCR)** | We POST to the NCR ESB endpoint | Open a ticket, add a remark, close a ticket |
| **Outbound (NCR → us)** | NCR POSTs to our API Gateway endpoint | Send us status updates as the ticket progresses |

---

## Authentication — 2-Factor Mutual Auth (both factors **mandatory**)

| Factor | What it is | Our responsibility |
|---|---|---|
| **1 — WS-Security credentials** | `USERID` + `Password` sent in the JSON `Header` block of every request | Store in AWS Secrets Manager; inject at runtime |
| **2 — mTLS client certificate** | Our Lambda presents a commercial SSL cert on every HTTPS connection to NCR | Purchase from Symantec/GoDaddy/Thawte/Comodo/GeoTrust; separate certs for CERT and PROD |

**Certificate rules** (from NCR spec p.4–5):
- Must be a **commercial cert** from one of the five approved CAs — self-signed not accepted
- `CN` in the certificate must include and match the customer name (McDonald's UK)
- Must not be expired or revoked (OCSP or reachable CRL required)
- Separate certs for CERT (test/QA) and PROD environments
- Password minimum **24 characters**, rotated annually

> If either factor cannot be met, NCR must raise an internal security exception — adds time to the project.

---

## Environments

| Environment | Purpose | Endpoint |
|---|---|---|
| **CERT** | Development & testing (QA) | Provided by NCR during onboarding |
| **PROD** | Live production | Provided by NCR when CERT testing is signed off |

Endpoints are not in any public documentation — NCR provides them separately during onboarding along with the USERID/Password credentials.

---

## Operations we call (Inbound — us → NCR)

### 1. CreateRequest — Open a new ticket

**POST** to the NCR ESB endpoint. Response is **synchronous** — NCR returns the `NCRTicketID` immediately.

**Request fields:**

| Field | Required | Max length | Notes |
|---|---|---|---|
| `Header.TransactionID` | Y | — | UUID we generate per call |
| `Header.USERID` | Y | — | Fixed value from NCR onboarding |
| `Header.SourceSystem` | Y | — | Our source system name (confirm with NCR) |
| `Header.TimeStamp` | N | — | ISO-8601 UTC |
| `CreateServiceRequest.CountryCode` | Y | 2 | `"GB"` |
| `CreateServiceRequest.CustomerTicketID` | Y | — | Our `alert_id` — used to link callbacks back to us |
| `CreateServiceRequest.RequestType` | Y | — | `HW` (hardware) or `SW` (software) |
| `CreateServiceRequest.Priority` | Y | — | `1`=Critical, `2`=Urgent, `3`=Normal, `4`=Low |
| `CreateServiceRequest.Summary` | Y | 100 bytes | Brief description |
| `CreateServiceRequest.Description` | N | 4000 bytes | Full description |
| `CreateServiceRequest.MCN` | N | — | McDonald's UK master customer number |
| `CreateServiceRequest.Category` | N | 100 bytes | Maps to NCR category (confirm valid values) |
| `CreateServiceRequest.SubCategory` | N | 100 bytes | Maps to NCR subcategory |
| `CreateServiceRequest.Site.SiteNumber` | Y | 30 | Restaurant number |
| `CreateServiceRequest.Remark.Text` | N | 4000 bytes | Optional opening remark |
| `Caller.*` | N | — | Contact details (FirstName, LastName, PhoneNumber, EmailAddress) |

**Sample request:**
```json
{
  "Header": {
    "TransactionID": "1650389319426",
    "USERID": "USERID",
    "SourceSystem": "CUSTOMERAPP",
    "TimeStamp": "2022-04-19T17:28:39.425Z"
  },
  "CreateServiceRequest": {
    "CountryCode": "GB",
    "CustomerTicketID": "0122352",
    "RequestType": "HW",
    "Priority": 2,
    "Summary": "POS terminal offline at restaurant 1234",
    "Description": "POS terminal has been unreachable for 45 minutes.",
    "MCN": "<mcdonalds-uk-mcn>",
    "Category": "Hardware",
    "Subcategory": "Cash Drawer",
    "Site": { "SiteNumber": "1234" },
    "Remark": { "Text": "Detected by Snowfall proactive alerting" }
  }
}
```

**Response (synchronous):**
```json
{
  "Header": {
    "TransactionID": "1650389319426",
    "Status": "SUCCESS",
    "SourceSystem": "SOUP",
    "TimeStamp": "2024-02-07T00:19:29.390-05:00",
    "Fault": { "FaultDescription": null, "FaultCode": null }
  },
  "NCRIncidentUpdate": { "NCRTicketID": "01956911" }
}
```

> `NCRIncidentUpdate.NCRTicketID` is returned **immediately in the sync response** — store this as `ncr_servicenow_ticket_id` in DynamoDB.

---

### 2. UpdateRequest — Add a remark to an existing ticket

Used to add a note to an open ticket (e.g. alert condition changed).

**Request fields:**

| Field | Required | Notes |
|---|---|---|
| `Header.TransactionID` | Y | New UUID per call |
| `Header.USERID` | Y | Fixed NCR credential |
| `Header.SourceSystem` | Y | Our source system name |
| `Header.TimeStamp` | N | ISO-8601 UTC |
| `UpdateServiceRequest.TicketID` | Y | NCR's `NCRTicketID` from the CreateResponse |
| `UpdateServiceRequest.CountryCode` | Y | `"GB"` |
| `UpdateServiceRequest.Remark.Text` | Y | Max 4000 bytes |

**Sample request:**
```json
{
  "Header": {
    "TransactionID": "0010236C17132818",
    "USERID": "USERID",
    "SourceSystem": "CUSTOMERAPP"
  },
  "UpdateServiceRequest": {
    "TicketID": "01956894",
    "CountryCode": "GB",
    "Remark": { "Text": "Alert condition has changed — device partially recovered." }
  }
}
```

**Response:** Same structure as CreateResponse (`Header.Status` = `SUCCESS` / `FAILED`). Note: UpdateResponse is **asynchronous** — NCR does not return it immediately.

---

### 3. ResolveRequest — Close a ticket

Used when the Snowfall alert auto-resolves. **Ticket must be in Customer Queue** for this to succeed (confirm valid queue names with NCR during onboarding).

**Request fields:**

| Field | Required | Notes |
|---|---|---|
| `Header.*` | Y | Same as above |
| `UpdateServiceRequest.TicketID` | Y | NCR ticket ID |
| `UpdateServiceRequest.CountryCode` | Y | `"GB"` |
| `UpdateServiceRequest.ResolutionCategory` | Y | Resolution category (confirm valid values with NCR) |
| `UpdateServiceRequest.ResolutionNotes` | Y | Max 4000 bytes |

**Sample request:**
```json
{
  "Header": {
    "TransactionID": "1650389311127",
    "USERID": "USERID",
    "SourceSystem": "CUSTOMERAPP",
    "TimeStamp": "2022-04-19T17:28:39.425Z"
  },
  "UpdateServiceRequest": {
    "TicketID": "01957030",
    "CountryCode": "GB",
    "ResolutionCategory": "Auto-resolved",
    "ResolutionNotes": "Alert condition cleared — no further action required."
  }
}
```

---

## Operations NCR calls us (Outbound — NCR → us)

We must host an HTTP endpoint (our API Gateway `POST /ncr-servicenow-callback`) that NCR calls for two purposes:

### 4. IncidentUpdate — Status callbacks

NCR sends updates as the ticket progresses through their workflow. We must respond with an ACK **within 5 seconds**.

**Ticket status lifecycle (from Excel mapping doc):**

| Status | Meaning |
|---|---|
| `New` | Ticket just opened |
| `Assigned` | Assigned to an NCR technician |
| `In Progress` | Work in progress |
| `Open - New` | Open, awaiting action |
| `Open Part Ordered` | Part ordered, waiting for delivery |
| `Open Tech Dispatched` | Technician en route |
| `Open On Site` | Technician on site |
| `Closed Template Complete` | Ticket closed successfully |
| `Closed Cancelled` | Ticket cancelled |
| `Pending` | On hold |

**Fields populated by status** (from Excel `IncidentUpdate-FromNCRVoyix` sheet — "X" = present in that status):

| Field | New/Assigned/InProgress | Open-New onwards | Tech Dispatched+ | On Site+ | Closed |
|---|---|---|---|---|---|
| `CustomerTicketID` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `TicketID` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `Priority` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `TicketStatus` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `Summary` / `Description` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `SiteNumber` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `CaseID` (Dispatch #) | — | ✓ | ✓ | ✓ | ✓ |
| `CaseStatus` | — | ✓ | ✓ | ✓ | ✓ |
| `PartETA` | — | ✓ | ✓ | ✓ | ✓ |
| `TechETA` | — | — | ✓ | ✓ | ✓ |
| `TechArrival` | — | — | — | ✓ | ✓ |
| `PartArrival` | — | — | — | ✓ | ✓ |
| `CompleteDate` | — | — | — | — | ✓ |
| `ShipDate` / `OutboundTracking` / `OutboundSN` | — | — | — | — | ✓ |
| `ReturnMailerTrackingNumber` | — | — | — | — | ✓ (Template Complete only) |
| `RMAID` | — | ✓ | ✓ | ✓ | ✓ |

**Sample callback from NCR:**
```json
{
  "IncidentUpdateRequestMessage": {
    "Header": {
      "TransactionID": "234574463356",
      "USERID": "USERID",
      "SourceSystem": "SALESFORCE",
      "TimeStamp": "02-MAR-2021 11:32:26.697-05:00"
    },
    "IncidentUpdate": {
      "CustomerTicketID": "02978861",
      "TicketID": "02956861",
      "Priority": "P1 - Critical",
      "TicketStatus": "Open Tech Dispatched",
      "TechETA": "2024-01-24 11:00:00",
      "CaseID": "59446702",
      "CaseStatus": "Open Tech Dispatched"
    }
  }
}
```

**Our ACK response (must reply within 5 seconds):**
```json
{ "result": "success", "message": "<our_alert_id>" }
```
Or on error:
```json
{ "errorCode": "<code>", "message": "<description>" }
```

---

### 5. IncidentUpdate 2-Way Create — NCR-initiated ticket

NCR's service desk can **manually raise a ticket** in their system (e.g. a field engineer spotted a fault). NCR sends an `IncidentUpdate` callback with `CustomerTicketID` = `null` or `""`.

We must:
1. Detect `CustomerTicketID` is null/empty
2. Create a new DynamoDB record with the NCR `TicketID`
3. Return our new ticket number in the ACK

**Sample 2-Way Create callback:**
```json
{
  "IncidentUpdateRequestMessage": {
    "Header": { "TransactionID": "234574463356", "USERID": "USERID", "SourceSystem": "SALESFORCE" },
    "IncidentUpdate": {
      "CustomerTicketID": "",
      "TicketID": "02956861",
      "Priority": "P1 - Critical",
      "Summary": "Hardware - Battery Backup - Store 12345",
      "Description": "Our battery backup is beeping over and over",
      "SiteNumber": "12345",
      "TicketStatus": "New"
    }
  }
}
```

---

## Error handling

NCR returns errors in the `Header.Fault` block of any response:

```json
{
  "Header": {
    "Status": "FAILED",
    "Fault": {
      "FaultCode": "<error-code>",
      "FaultDescription": "<human-readable-description>"
    }
  }
}
```

Two fault types:
- **Business Faults** — returned from NCR dispatch systems (e.g. unknown `SiteNumber`, invalid ticket ID)
- **Technical Faults** — middleware or connectivity failures

NCR behaviour on failures:
- NCR will **retry** on system failures (both NCR-side and our side)
- NCR account team is notified by email on NCR system failures (optional)
- Customer tickets are updated with NCR system exception notes

Valid error codes are listed in the `ErrorMessages` sheet of the mapping doc (to be confirmed during onboarding).

---

## Items to confirm during NCR onboarding

| Item | Notes |
|---|---|
| `MCN` | McDonald's UK master customer number |
| `SourceSystem` | The string NCR expects in `Header.SourceSystem` (e.g. `MCDONALDS_UK`) |
| Restaurant → `SiteNumber` format | E.g. `"1234"` — confirm zero-padding etc. |
| `RequestType` values | `HW` / `SW` confirmed in spec |
| Valid `Category` / `SubCategory` values | Not in spec — confirmed in mapping session |
| Valid `ResolutionCategory` values for ResolveRequest | Not in spec — confirmed in mapping session |
| Queue name for ResolveRequest | Ticket must be in "Customer Queue" — confirm exact name |
| CERT endpoint URL and credentials | Provided by NCR |
| PROD endpoint URL and credentials | Provided by NCR after CERT sign-off |
| CN name format for mTLS certificate | Must match customer name — confirm exact format |
| Callback auth method | Basic Auth or Client Certificate (confirmed 15 Apr 2026 — both options available) |
| 24×7 support procedure | NCR requires documented and accepted support procedures before go-live |
