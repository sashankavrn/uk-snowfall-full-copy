"""
NCR Voyix - CreateServiceRequest TEST SCRIPT
Cert environment: osbcert-ha.ncrvoyix.com

Auth: HTTP Basic Auth (confirmed by NCR — no mTLS cert required)

To run:
  $env:NCR_USERNAME = "MA230518"
  $env:NCR_PASSWORD = "..."
  .venv\\Scripts\\python.exe "Localfiles\\scripts and py\\ncr_create_service_request_test.py"
"""
import os
import requests
from requests.auth import HTTPBasicAuth

URL = "https://osbcert-ha.ncrvoyix.com/ext/CSDI/HSRStandardSyncRestReq/ServiceRequest/CreateServiceRequest"

# Credentials — set via environment variables
USERNAME = os.environ.get("NCR_USERNAME", "MA230518")
PASSWORD = os.environ.get("NCR_PASSWORD", "")

BODY = """<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                 xmlns:ser="http://service.ncr.com">
   <soapenv:Header/>
   <soapenv:Body>
       <ser:CreateServiceRequestMessage>
           <Header>
               <TransactionID>123456789001</TransactionID>
               <USERID>MA230518</USERID>
               <SourceSystem>CUSTOMERAPP</SourceSystem>
               <TimeStamp>2026-04-19T10:00:00</TimeStamp>
           </Header>
           <CreateServiceRequest>
               <CountryCode>GB</CountryCode>
               <ServiceRequest>
                   <CustomerTicketID>TEST12345</CustomerTicketID>
                   <Type>MAIN</Type>
                   <Priority>2</Priority>
                   <Summary>POS device issue</Summary>
                   <Description>POS not working</Description>
                   <Caller>
                       <FirstName>Test</FirstName>
                       <LastName>User</LastName>
                       <EmailAddress>test@example.com</EmailAddress>
                       <PhoneNumber>
                           <AreaCode>123</AreaCode>
                           <PhoneNumber>4567890</PhoneNumber>
                       </PhoneNumber>
                   </Caller>
                   <Site>
                       <SiteShortName>STORE123</SiteShortName>
                   </Site>
                   <CI>
                       <AssetID>ASSET123</AssetID>
                   </CI>
                   <ATMCustomerMetrics>
                       <SSDGCustomer>1</SSDGCustomer>
                       <NCRMCN>123456</NCRMCN>
                   </ATMCustomerMetrics>
                   <Remarks>
                       <Remark>
                           <Text>Test request from Python</Text>
                           <Type>General</Type>
                       </Remark>
                   </Remarks>
               </ServiceRequest>
           </CreateServiceRequest>
       </ser:CreateServiceRequestMessage>
   </soapenv:Body>
</soapenv:Envelope>"""

headers = {
    "Content-Type": "text/xml; charset=utf-8",
}

print(f"POST {URL}")
print(f"Auth: {USERNAME} / ***")

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

response = requests.post(
    URL,
    auth=HTTPBasicAuth(USERNAME, PASSWORD),
    headers=headers,
    data=BODY.encode("utf-8"),
    timeout=30,
    verify=False,  # NCR cert env uses private CA — disable for local testing only
)

print(f"\nStatus: {response.status_code}")
print(f"Response:\n{response.text}")
