#!/usr/bin/python
import requests
import re
import json
import argparse
import StringIO
import requests.packages.urllib3
from collections import OrderedDict
import datetime
import pandas

requests.packages.urllib3.disable_warnings()
#import httplib as http_client
#http_client.HTTPConnection.debuglevel = 1
__version__ = '0.0.1'

class Avi_Connect(object):
    def __init__(self, host='127.0.0.1', username='admin', password=None, tenant='*', avi_api_version='17.2.10', verify=False, output_dir=None, input_json=None):
        self.host = host
        self.username = username
        self.password = password
        self.output_dir = output_dir
        self.base_url = 'https://' + host
        self.avi_api_version = avi_api_version
        self.tenant = tenant
        self.session = requests.session()
        self.session.verify = False
        self.login()
        self.api_configuration_export = self._get('/api/configuration/export', params={'include_name': True, 'uuid_refs': True, 'passphrase': password})

    def login(self):
        login_data = {'username': self.username, 'password': self.password}
        r = self._post('/login', data=login_data)
        if r and 'AVI_API_VERSION' in r.headers.keys():
            self.session.headers.update({'X-Avi-Version': self.avi_api_version})
            self.session.headers.update({'X-Avi-Tenant':
            self.tenant})
        else:
            raise Exception('Failed authenticating as %s:%s with host %s' % (
                self.username, self.password, self.host))

    def _get(self, uri, params=None):
        url = self._url(uri)
        return self._request('get', url, params=params)

    def _post(self, uri, params=None, data=None):
        url = self._url(uri)
        return self._request('post', url, params=params, data=data)

    def _url(self, uri):
        return self.base_url + uri

    def _write(self, path, data):
        try:
            with open(path, 'w') as fh:
                json.dump(data, fh, indent=2)
        except Exception as e:
            print e.message

    def _request(self, method, url, params=None, data=None):
        _method = getattr(self.session, method)
        r = _method(url, params=params, data=data)
        try:
            r.raise_for_status()
        except Exception as e:
            print e.message
            return None
        try:
            data = r.json()
            m = re.match(self.base_url + '/(.*)', url)
            path = self.host + '-' + m.group(1).replace('/', '-') + '.json'
            # TODO Enable write below
            self._write(path, data)
        except ValueError:
            pass
        return r

class Avi_Report():
    def __init__(self,configuration_export):
        with open(configuration_export) as configuration:
            self.configuration_export = json.load(configuration)

        # VirtualService
        VIRTUALSERVICE_JSON_FIELDS = ['name', 'services', 'cloud_ref', 'application_profile_ref',
                                    'network_profile_ref', 'se_group_ref', 'pool_ref', 'http_policies', 'network_security_policy_ref']
        POOL_JSON_FIELDS = ['name', 'default_server_port',
                            'health_monitor_refs', 'application_persistence_profile_ref']

        self.virtualservice_table = self.obj_table('VirtualService', VIRTUALSERVICE_JSON_FIELDS)
        self.pool_table = self.obj_table('Pool', POOL_JSON_FIELDS)

        report = { 'VirtualService': self.virtualservice_table, 'Pool': self.pool_table }

        report_name = 'avi_migration_report-' + datetime.datetime.now().strftime("%Y%m%d-%H%M%S" + ".xlsx")
        self.write_report(report_name, report)


    def obj_table(self, obj_type, obj_json_fields):
        obj_table = []
        for obj in self.configuration_export[obj_type]:
            obj_table_dict = OrderedDict()
            for column_name in obj_json_fields:
                try:
                    if '_ref' in column_name:
                      table_column_name = re.sub('_ref','', column_name)
                      row_value = obj[column_name].split('#')[1]
                    else:
                      table_column_name = column_name
                      row_value = str(obj[column_name])
                    obj_table_dict[table_column_name] = row_value
                except:
                    pass
            obj_table.append(obj_table_dict)
        return obj_table

    def write_report(self, name, report):
        writer = pandas.ExcelWriter(name, engine='xlsxwriter')
        for obj_type in report.keys():
            df = pandas.DataFrame(report[obj_type])
            df.to_excel(writer, sheet_name=obj_type)
        writer.save()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--controller', default='127.0.0.1')
    parser.add_argument('-u', '--username', default='admin')
    parser.add_argument('-p', '--password', default=None)
    parser.add_argument('-o', '--output', default=".")
    parser.add_argument('-v', '--api-version', default='17.2.10')
    parser.add_argument('-t', '--tenant', default='*')
    parser.add_argument('-i', '--input', default=None,
                        help='')
    args = parser.parse_args()
    if args.input:
      migration_report = Avi_Report(args.input)
    else:
      Avi_Connect(host=args.controller, username=args.username, password=args.password,
                  output_dir=args.output, input_json=args.input, tenant=args.tenant, avi_api_version=args.api_version)
      migration_report = Avi_Report(args.controller+'-api-configuration-export.json')
