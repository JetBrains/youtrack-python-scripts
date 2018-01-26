#! /usr/bin/env python

import sys

if sys.version_info >= (3, 0):
    print("\nThe script doesn't support python 3. Please use python 2.7+\n")
    sys.exit(1)

from youtrack.connection import Connection
from youtrack.youtrackImporter import YouTrackImporter, YouTrackImportConfig
from youtrack.youtrackImporter import AUTO_ATTACHED, NAME, TYPE, POLICY
from youtrack import User, Group, Comment
import youtrackutils.zendesk
from youtrackutils.zendesk.zendeskClient import ZendeskClient
import datetime
import calendar
import urllib2


__author__ = 'user'


def main():
    source_url, source_login, source_password, target_url, target_login, target_password, project_id = sys.argv[1:8]
    zendesk2youtrack(source_url, source_login, source_password, target_url, target_login, target_password, project_id)


def zendesk2youtrack(source_url, source_login, source_password, target_url, target_login, target_password, project_id):
    target = Connection(target_url, target_login, target_password)
    source = ZendeskClient(source_url, source_login, source_password)

    importer = ZendeskYouTrackImporter(source, target, ZendeskYouTrackImportConfig(
        youtrackutils.zendesk.NAMES, {}, {}))
    importer.do_import({project_id: project_id})


class ZendeskYouTrackImporter(YouTrackImporter):
    def __init__(self, source, target, import_config):
        super(ZendeskYouTrackImporter, self).__init__(source, target, import_config)

    def _get_fields_with_values(self, project_id):
        return []

    def _to_yt_issue(self, issue, project_id):
        yt_issue = super(ZendeskYouTrackImporter, self)._to_yt_issue(issue, project_id)
        for item in issue[u'custom_fields']:
            self.process_field(self._source.get_custom_field(str(item[u'id']))[u'title'], project_id, yt_issue, item[u'value'])
        return yt_issue

    def _to_yt_comment(self, comment):
        yt_comment = Comment()
        user = self._to_yt_user(comment[u'author_id'])
        self._import_user(user)
        yt_comment.author = user.login
        yt_comment.text = comment[u'body']
        yt_comment.created = self.to_unix_date(comment[u'created_at'])
        return yt_comment

    def _get_attachments(self, issue):
        result = []
        issue_id = self._get_issue_id(issue)
        for audit in self._source.get_ticket_audits(issue_id):
            created = audit[u'created_at']
            for event in audit[u'events']:
                attachments_key = u'attachments'
                if (attachments_key in event) and (len(event[attachments_key])):
                    user = self._to_yt_user(event["author_id"])
                    self._import_user(user)
                    for attachment in event[attachments_key]:
                        result.append(ZdAttachment(attachment[u"file_name"], self.to_unix_date(created), user.login, attachment[u"content_url"]))
        return result

    def _get_issues(self, project_id):
        return self._source.get_issues()

    def _get_comments(self, issue):
        result = []
        for audit in self._source.get_ticket_audits(self._get_issue_id(issue)):
            created = audit[u"created_at"]
            for event in audit[u'events']:
                if event[u'type'] == u"Comment":
                    event[u"created_at"] = created
                    result.append(event)
        return result[1:]

    def _get_custom_fields_for_projects(self, project_ids):
        fields = self._source.get_custom_fields()
        result = []
        for field in fields:
            yt_field = {NAME: self._import_config.get_field_name(field[u'title'])}
            yt_field[AUTO_ATTACHED] = True
            yt_field[TYPE] = self._import_config.get_field_type(yt_field[NAME], field[u'type'])
            if yt_field[TYPE] is not None:
                result.append(yt_field)
        return result

    def _get_issue_links(self, project_id, after, limit):
        return []

    def _to_yt_user(self, value):
        user = self._source.get_user(value)
        yt_groups = []
        for g in self._source.get_groups_for_user(value):
            ytg = Group()
            ytg.name = g
            yt_groups.append(ytg)
        yt_user = User()
        if user[u'email'] is None:
            yt_user.email = "example@example.com"
            yt_user.login = user[u'name'].replace(" ", "_")
        else:
            yt_user.email = user[u'email']
            yt_user.login = yt_user.email
        yt_user.fullName = user[u'name']
        yt_user.getGroups = lambda: yt_groups
        return yt_user

    def to_unix_date(self, date):
        dt = datetime.datetime.strptime(date, "%Y-%m-%dT%H:%M:%SZ")
        return str(calendar.timegm(dt.timetuple()) * 1000)


class ZendeskYouTrackImportConfig(YouTrackImportConfig):
    def __init__(self, name_mapping, type_mapping, value_mapping=None):
        super(ZendeskYouTrackImportConfig, self).__init__(name_mapping, type_mapping, value_mapping)

    def get_predefined_fields(self):
        return [
            {NAME: u'Type', TYPE: u'enum[1]', POLICY: '0'},
            {NAME: u'Priority', TYPE: u'enum[1]', POLICY: '0'},
            {NAME: u'State', TYPE: u'state[1]', POLICY: '0'},
            {NAME: u'Assignee', TYPE: u'user[1]', POLICY: '2'},
            {NAME: u'Due date', TYPE: u'date'},
            {NAME: u'Organization', TYPE: u'enum[1]', POLICY: '0'}
        ]

    def get_field_type(self, name, type):
        types = {u"text": u"string", u"checkbox": u"enum[*]", u"date": u"date", u"integer": u"integer",
                 u"decimal": u"float", u"regexp": u"string", u"tagger": u"enum[1]"}
        return types.get(type)


class ZdAttachment():
    def __init__(self, name, created, author_login, url):
        self.name = name
        self.created = created
        self.authorLogin = author_login
        self._url = url

    def getContent(self):
        f = urllib2.urlopen(urllib2.Request(self._url))
        return f


if __name__ == "__main__":
    main()
