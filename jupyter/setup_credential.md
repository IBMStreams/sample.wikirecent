# Enable Cloud Submission

To enable Cloud submission setup a VCAP getting the credential from 
your streams instance running on the Cloud.

Create a credential.py file in the current directory with the following 
the pattern,


## Apikey for instance being submitted to...
```python
streaming3Turbine = {
    "apikey": "SZtizGEk0JUST_AN_EXAMPLECgIZb0xmO",
    "iam_apikey_description": "Auto generated apikey during resource-key operation for Instance - crn:v1:bluemix:public:streaming-analytics:us-south:a/309e3606a35c9fea12981876cd991b07:b11e1ab0-9570-44d0-950c-7b84b5abb817::",
    "iam_apikey_name": "auto-generated-apikey-JUST_AN_EXAMPLE-d2fdf7cedd75",
    "iam_role_crn": "crn:v1:bluemix:JUST_A_EXAMPLE:Manager",
    "iam_serviceid_crn": "crn:v1:bluemix:public:iam-identity::a/JUST_AN_EXAMPLE::serviceid:ServiceId-761f23f0-ec9f-4eba-9f97-7cee5b99d19f",
    "v2_rest_url": "https://streams-app-service.ng.bluemix.net/v2/streaming_analytics/b11e1ab0-JUST_AN_EXAMPLE-7b84b5abb817"
```

### VCAP mapping to instance...
```Python
vcap_conf = {'streaming-analytics': [{
                'name': "Streaming3Turbine",
                'credentials': streaming3Turbine}]
            }

```

### Notes:
- The notebooks will access the configuration.py file. 
- If you do not use the name 'Streaming3Turbine' you must find/replace
the string within the notebook.



