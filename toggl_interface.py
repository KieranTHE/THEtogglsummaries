import requests
import json
import logging
import base64
import sys
import pandas as pd
import datetime
import time
import math
from ftplib import FTP
from pathlib import Path

#set logging
logging.basicConfig(level=logging.DEBUG)

#read secrets
with open('secrets.json') as secrets_file:
  secrets = json.load(secrets_file)
logging.debug(secrets['toggl_api_key'])

#read log
with open('log.json') as log_file:
  logged = json.load(log_file)

#header and param details for api requests
string_api = secrets['toggl_api_key'] + ':' + "api_token"

headers = {
    'Authorization' : 'Basic '+ base64.b64encode(string_api.encode('ascii')).decode("utf-8"),
}

#Account details
# params={
#     'user_agent':secrets['email'],
#     'workspace_id':secrets['workspace_id']
#     }
# url='https://www.toggl.com/api/v8/me'
# response=requests.get(url,headers=headers)
# if response.status_code!=200:
#     logging.error(response.text)
#     quit()

# response=response.json()
# logging.debug(response)
# email=response['data']['email']
# logging.debug(email)

#reports
#date of most recent friday
logging.debug(logged['last_run'])
first_saturday = datetime.datetime.fromisoformat(logged['last_run'])
#first_saturday = datetime.datetime.fromisoformat("2020-10-10T00:00:00+10:00")

end_fortnight = first_saturday + datetime.timedelta(days=13)
end_fortnight = end_fortnight.replace(tzinfo=None)

today = datetime.datetime.now() - datetime.timedelta(days=1)
today = today.replace(tzinfo=None)

logging.debug(today)

leap = end_fortnight

while leap < today :    
    end_fortnight = leap
    leap = end_fortnight + datetime.timedelta(days=14)

    start_date = end_fortnight - datetime.timedelta(days=13)

    start_string=start_date.strftime("%Y-%m-%d")
    end_string=end_fortnight.strftime("%Y-%m-%d")

    logging.debug(start_string)

    url='https://toggl.com/reports/api/v2/details'

    params = {
        'user_agent':secrets['email'],
        'workspace_id':secrets['workspace_id'],
        'since': start_string,
        'until' : end_string,
    }

    response=requests.get(url,headers=headers,params=params)
    if response.status_code!=200:
        logging.error(response.text)
        quit()

    response=response.json()
    #logging.debug(response)
    response_df = pd.json_normalize(response['data'])

    if response['total_count'] > response['per_page']:
        page = 1
        while page <= math.floor(response['total_count']/response['per_page']):
            params['page'] = page + 1
            response2=requests.get(url,headers=headers,params=params)
            if response2.status_code!=200:
                logging.error(response2.text)
                quit()
            response2=response2.json()
            response_df = response_df.append(pd.json_normalize(response2['data']))
            page = page + 1

    response_df.rename(
        columns={
            'client':'CLIENT',
            'project':'PROJECT',
            'dur':'HOURS',
            'description':'DESCRIPTION',
            'start':'START'
            }, 
        inplace=True)
    #logging.debug(response_df)
    grouped_df = response_df.groupby(by=['CLIENT','PROJECT','START','DESCRIPTION'])['HOURS'].sum()
    result_df = grouped_df.div(3600000).round(decimals=2)
    result_df = result_df.reset_index()
    result_df=result_df.reindex(columns=['CLIENT','PROJECT','DESCRIPTION','START','HOURS'])

    logging.debug(result_df)

    for client in result_df['CLIENT'].unique():
        client_df = result_df[result_df['CLIENT'] == client]
        csv_string = start_date.strftime("%Y%m%d") + '-' + end_fortnight.strftime("%Y%m%d") + '_' + client + '.csv'
        client_df.to_csv(secrets['store_location'] + csv_string, index=False)
        if secrets['ftp'] == "True":
            file_path = secrets['store_location'] + csv_string
            with FTP(secrets['ftp_address'], secrets['ftp_username'], secrets['ftp_password']) as ftp, open(file_path, 'rb') as file:
                ftp.cwd(secrets['ftp_store'])
                ftp.storbinary(f'STOR {csv_string}', file)

    #update log
    logged['last_run'] = (end_fortnight + datetime.timedelta(days=1)).isoformat()
    with open("log.json", "w") as jsonFile:
        json.dump(logged, jsonFile)

    time.sleep(2)