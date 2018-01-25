import base64
import httplib2
import json
import os

from jira import JiraException

_debug = os.environ.get('DEBUG')


class JiraClient(object):

    def __init__(self, url, login, password):
        self._url = (url[:-1] if (url[-1] == '/') else url) + "/rest"
        self._headers = {}
        self._http = httplib2.Http(timeout=10, disable_ssl_certificate_validation=True)
        # self._http.add_credentials(login, password)
        self._login(login, password)

    def get_issue_link_types(self):
        response, content = self._get(self._rest_url() + '/issueLinkType')
        return content

    def get_project_by_id(self, key):
        response, content = self._get(self._rest_url() + "/project/" + key)
        return content

    def get_issues(self, project_key, from_id, to_id):
        issues = []
        for i in range(from_id, to_id + 1):
            issue = self.get_issue('%s-%d' % (project_key, i))
            if issue is not None:
                issues.append(issue)
        return issues

    def get_issue(self, issue_id):
        response, content = self._get(self._rest_url() + "/issue/" + issue_id)
        if response.status == 200:
            return content
        print "Can't get issue " + issue_id

    def get_worklog(self, issue_id):
        response, content = self._get(self._rest_url() + "/issue/" + issue_id + '/worklog')
        if response.status == 200:
            return content
        print "Can't get worklog for issue " + issue_id

    def _rest_url(self):
        return self._url + "/api/latest"

    def _post(self, url, body):
        headers = self._headers.copy()
        headers['Content-Type'] = 'application/json'
        json_body = json.dumps(body)
        headers['Content-Length'] = str(len(json_body))
        response, content = self._http.request(url, "POST", json_body, headers)
        if response.status != 200:
            raise JiraException(response)
        return response, json.loads(content)

    def _get(self, url):
        if _debug:
            print "DEBUG: _get %s" % url
        response, content = self._http.request(url, headers=self._headers.copy())
        if _debug:
            print "DEBUG: response: %d" % response.status
            print "DEBUG: content: %s" % content
        return response, json.loads(content)

    def _login(self, login, password):
        # response, content = self._post(self._url + "/auth/1/session", {"username": login, "password": password})
        # self._headers['JSESSIONID'] = content['session']['value']
        auth = base64.b64encode(login + ':' + password)
        self._headers['Authorization'] = 'Basic ' + auth
