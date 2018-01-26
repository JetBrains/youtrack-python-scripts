#! /usr/bin/env python

import sys

if sys.version_info >= (3, 0):
    print("\nThe script doesn't support python 3. Please use python 2.7+\n")
    sys.exit(1)

import os
import re
import calendar
import time
import datetime
import youtrackutils.csvClient
from youtrackutils.csvClient.client import Client
import youtrackutils.csvClient.youtrackMapping
from youtrack.youtrackImporter import *

youtrackutils.csvClient.FIELD_TYPES.update(youtrack.EXISTING_FIELD_TYPES)
from youtrack import User, Comment
from youtrack.connection import Connection


def main():
    source_file, target_url, target_login, target_password = sys.argv[1:5]
    comments_file = None
    attachments_file = None
    if len(sys.argv) > 5:
        comments_file = sys.argv[5]
    if len(sys.argv) > 6:
        attachments_file = sys.argv[6]
    csv2youtrack(source_file, target_url, target_login, target_password, comments_file, attachments_file)


def get_project(issue):
    for key, value in youtrackutils.csvClient.FIELD_NAMES.items():
        if value == "project":
            return re.sub(r'\W+', "", issue[key])


def csv2youtrack(source_file, target_url, target_login, target_password, comments_file=None, attachments_file=None):
    target = Connection(target_url, target_login, target_password)
    source = Client(source_file)
    source_comments = None
    if comments_file:
        source_comments = Client(comments_file)

    source_attachments = None
    if attachments_file:
        source_attachments = Client(attachments_file)

    config = CsvYouTrackImportConfig(youtrackutils.csvClient.FIELD_NAMES, youtrackutils.csvClient.FIELD_TYPES)
    importer = CsvYouTrackImporter(source, target, config, source_comments, source_attachments)
    importer.import_csv()


class CsvYouTrackImporter(YouTrackImporter):
    def __init__(self, source, target, import_config, source_comments=None, source_attachments=None):
        super(CsvYouTrackImporter, self).__init__(source, target, import_config)
        self._after = 0
        self._comments = dict()
        self._attachments = dict()
        if source_comments:
            for c in source_comments.get_rows():
                issue_id = '%s-%s' % (c[0], c[1])
                if issue_id not in self._comments:
                    self._comments[issue_id] = []
                self._comments[issue_id].append(c[2:])
        if source_attachments:
            for a in source_attachments.get_rows():
                issue_id = '%s-%s' % (a[0], a[1])
                if issue_id not in self._attachments:
                    self._attachments[issue_id] = []
                self._attachments[issue_id].append(a[2:])

    def import_csv(self, new_projects_owner_login=u'root'):
        projects = self._get_projects()
        self._source.reset()
        self.do_import(projects, new_projects_owner_login)

    def _to_yt_comment(self, comment):
        if isinstance(comment, str) or isinstance(comment, unicode):
            result = Comment()
            result.author = u'guest'
            result.text = comment
            result.created = str(int(time.time() * 1000))
            return result
        if isinstance(comment, list):
            yt_user = self._to_yt_user(comment[0])
            self._import_user(yt_user)
            result = Comment()
            result.author = yt_user.login
            result.created = self._import_config._to_unix_date(comment[1])
            result.text = comment[2]
            return result

    def get_field_value(self, field_name, field_type, value):
        if (field_name == self._import_config.get_project_name_key()) or (
        field_name == self._import_config.get_project_id_key()):
            return None
        if field_type == u'date':
            return self._import_config._to_unix_date(value)
        if re.match(r'^\s*(enum|version|build|ownedfield|user|group)\[\*\]s*$', field_type, re.IGNORECASE):
            delim = getattr(youtrackutils.csvClient, 'VALUE_DELIMITER', csvClient.CSV_DELIMITER)
            values = re.split(re.escape(delim), value)
            if len(values) > 1:
                value = values
        return super(CsvYouTrackImporter, self).get_field_value(field_name, field_type, value)

    def _to_yt_user(self, value):
        users_mapping = dict()

        yt_user = User()
        user = value.split(';')
        yt_user.login = user[0].replace(' ', '_')
        if yt_user.login in users_mapping:
            user = users_mapping[yt_user.login]
            yt_user.login = user[0]
        try:
            yt_user.fullName = user[1] or yt_user.login
        except IndexError:
            yt_user.fullName = yt_user.login
        try:
            yt_user.email = user[2].strip() or yt_user.login + '@fake.com'
        except IndexError:
            yt_user.email = yt_user.login + '@fake.com'
        return yt_user


    def _get_issue_id(self, issue):
        number_regex = re.compile("\d+")
        match_result = number_regex.search(issue[self._import_config.get_key_for_field_name(u'numberInProject')])
        return match_result.group()

    def _get_yt_issue_id(self, issue):
        number_in_project = self._get_issue_id(issue)
        project_id = issue[self._import_config.get_key_for_field_name(self._import_config.get_project_id_key())]
        return '%s-%s' % (project_id, number_in_project)

    def _get_issues(self, project_id):
        issues = self._source.get_issues()
        for issue in issues:
            if self._import_config.get_project(issue)[0] == project_id:
                yield issue

    def _get_comments(self, issue):
        if self._comments:
            return self._comments.get(self._get_yt_issue_id(issue), [])
        return issue[self._import_config.get_key_for_field_name(u'comments')]

    def _get_attachments(self, issue):
        if self._attachments:
            return self._attachments.get(self._get_yt_issue_id(issue), [])
        return []

    def _import_attachments(self, issue_id, issue_attachments):
        for attach in issue_attachments:
            yt_user = self._to_yt_user(attach[0])
            self._import_user(yt_user)
            author = yt_user.login
            created = self._import_config._to_unix_date(attach[1])
            name = os.path.basename(attach[2])
            content = open(attach[2], 'rb')
            #group = attach[3]
            self._target.importAttachment(issue_id, name, content, author, None, None, created, '')

    def _get_custom_field_names(self, project_ids):
        project_name_key = self._import_config.get_key_for_field_name(self._import_config.get_project_name_key())
        project_id_key = self._import_config.get_key_for_field_name(self._import_config.get_project_id_key())
        return [key for key in self._source.get_header() if (key not in [project_name_key, project_id_key])]

    def _get_projects(self):
        result = {}
        for issue in self._source.get_issues():
            project_id, project_name = self._import_config.get_project(issue)
            if project_id not in result:
                result[project_id] = project_name
        return result

    def _get_custom_fields_for_projects(self, project_ids):
        result = [elem for elem in [self._import_config.get_field_info(field_name) for field_name in
                                   self._get_custom_field_names(project_ids)] if elem is not None]
        return result


class CsvYouTrackImportConfig(YouTrackImportConfig):
    def __init__(self, name_mapping, type_mapping, value_mapping=None):
        super(CsvYouTrackImportConfig, self).__init__(name_mapping, type_mapping, value_mapping)

    def _to_unix_date(self, date):
        if youtrackutils.csvClient.DATE_FORMAT_STRING[-2:] == "%z":
            dt = datetime.datetime.strptime(date[:-6], youtrackutils.csvClient.DATE_FORMAT_STRING[:-2].rstrip())
        else:
            dt = datetime.datetime.strptime(date, youtrackutils.csvClient.DATE_FORMAT_STRING)
        return str(calendar.timegm(dt.timetuple()) * 1000)

    def get_project_id_key(self):
        return u'project_id'

    def get_project_name_key(self):
        return u'project_name'

    def get_project(self, issue):
        project_name_key = self.get_key_for_field_name(self.get_project_name_key())
        project_id_key = self.get_key_for_field_name(self.get_project_id_key())
        if project_name_key not in issue:
            print(u'ERROR: issue does not contain a project_name key called "%s"' % project_name_key)
            print(u'issue: ')
            print(issue)
            raise Exception("Bad csv file")
        if project_id_key not in issue:
            print(u'ERROR: issue does not contain a project_id key called "%s"' % project_id_key)
            print(u'issue: ')
            print(issue)
            raise Exception("Bad csv file")
        project_name = issue[project_name_key]
        project_id = issue.get(project_id_key, re.sub(r'\W+', "", project_name))
        return project_id, project_name

    def get_field_info(self, field_name):
        result = {AUTO_ATTACHED: self._get_default_auto_attached(),
                  NAME: field_name if field_name not in self._name_mapping else self._name_mapping[field_name],
                  TYPE: None}
        if result[NAME] in self._type_mapping:
            result[TYPE] = self._type_mapping[result[NAME]]
        elif result[NAME] in youtrack.EXISTING_FIELD_TYPES:
            result[TYPE] = youtrack.EXISTING_FIELD_TYPES[result[NAME]]
        result[POLICY] = self._get_default_bundle_policy()
        return result

if __name__ == "__main__":
    main()
