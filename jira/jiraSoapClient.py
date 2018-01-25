import SOAPpy
import SOAPpy.Types
import getpass
import datetime
import time

class JiraSoapClient:
    def __init__(self, url, login, password):
        self._soap = SOAPpy.WSDL.Proxy(url + '/rpc/soap/jirasoapservice-v2?wsdl')
        self._auth = self._soap.login(login, password)

    def get_issues(self, project_id, from_id, to_id):
        issues = []
        for i in range(from_id, to_id):
            issue_id = project_id + '-' + str(i)
            try:
                issue = self._soap.getIssue(self._auth, issue_id)
                issues.append(issue)
            except BaseException:
                print "Can't find issue wih id [ %s ]" % issue_id
                pass
        return issues

