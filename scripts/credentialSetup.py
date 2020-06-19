""""
Do not check this file in after updating
"""



streaming3Turbine = # paste over the Streams instance credential below, keeping the assigment. 
{
    "apikey": " overwrite region ",
    "iam_apikey_description": " overwrite region ",
    "iam_apikey_name": " overwrite region ",
    "iam_role_crn": " overwrite region ",
    "iam_serviceid_crn": " overwrite region ",
    "v2_rest_url":" overwrite region "
}




# When pasting - note the """ surrounding the paste region. 
## paste over the Event Streams credential below, keeping the assignment and surrounding """  
magsEventStream = """
{
  "api_key": " overwrite region ",
  "apikey": " overwrite region ",
  "iam_apikey_description": " overwrite region ",
  "iam_apikey_name": " overwrite region ",
  "iam_role_crn": " overwrite region ",
  "iam_serviceid_crn": " overwrite region ",
  "instance_id": " overwrite region ",
  "kafka_admin_url": " overwrite region ",
  "kafka_brokers_sasl": [
    " overwrite region ",
    " overwrite region ",
    " overwrite region ",
    " overwrite region ",
    " overwrite region ",
    " overwrite region "
  ],
  "kafka_http_url":" overwrite region ",
  "password": " overwrite region ",
  "user": "token"
}
"""


vcap_conf = {'streaming-analytics':
    [
        {
            'name': "Streaming3Turbine",
            'credentials': streaming3Turbine}
    ]
}
