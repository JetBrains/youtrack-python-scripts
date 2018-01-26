__author__ = 'user'
import httplib2
import json

class ZendeskClient:
    def __init__(self, url, login, password):
        self._http = httplib2.Http(disable_ssl_certificate_validation=True)
        self._url = url
        self._http.add_credentials(login, password)

    def _rest_url(self):
        return self._url + "/api/v2"

    def get_issues(self):
        iterator = PageIterator(self, "/tickets.json", u"tickets")
        for elem in iterator:
            org_id_key = u'organization_id'
            org_id = elem.get(org_id_key)
            if org_id is not None:
                elem[org_id_key] = self.get_organization(org_id)[u'name']
            yield elem

    def get_ticket_audits(self, ticket_id):
        return PageIterator(self, "/tickets/%s/audits.json" % ticket_id, u"audits")

    def get_custom_fields(self):
        response, content = self._get("/ticket_fields.json")
        if response.status == 200:
            return content[u'ticket_fields']

    def get_custom_field(self, id):
        response, content = self._get("/ticket_fields/%s.json" % id)
        if response.status == 200:
            return content["ticket_field"]
        else:
            return None


    def get_organization(self, id):
        response, content = self._get("/organizations/" + str(id) + ".json")
        if response.status == 200:
            return content[u'organization']


    def get_user(self, id):
        response, content = self._get("/users/" + str(id) + ".json")
        if response.status == 200:
            return content[u'user']

    def get_groups_for_user(self, id):
        iterator = PageIterator(self, "/users/" + str(id) + "/group_memberships.json", u"group_memberships")
        return [self.get_group(gm["group_id"])["name"] for gm in iterator]

    def get_group(self, id):
        response, content = self._get("/groups/" + str(id) + ".json")
        if response.status == 200:
            return content[u'group']


    def _get(self, url):
        response, content = self._http.request(self._rest_url() + url)
        return response, json.loads(content)

class PageIterator:
    def __init__(self, zd_client, url, entities_name):
        self._zd_client = zd_client
        self._url = url
        self._entities_name = entities_name
        self._current_page = 0
        self._values = []

    def __iter__(self):
        return self

    def next(self):
        if not len(self._values):
            self._current_page += 1
            response, content = self._zd_client._get(self._url + "?page=" + str(self._current_page) + "&limit=100")
            if response.status != 200:
                raise StopIteration
            self._values = content[self._entities_name]
            if not len(self._values):
                raise StopIteration
        return self._values.pop(0)
