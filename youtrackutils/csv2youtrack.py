#! /usr/bin/env python

import sys

if sys.version_info >= (3, 0):
    print("\nThe script doesn't support python 3. Please use python 2.7+\n")
    sys.exit(1)

import os
import getopt
import re
import calendar
import time
import json
import datetime
from youtrackutils import csvClient
import youtrackutils.csvClient.youtrackMapping
from youtrackutils.csvClient.client import Client
from youtrack.youtrackImporter import *
from youtrack import User, Comment
from youtrack.connection import Connection


csvClient.FIELD_TYPES.update(youtrack.EXISTING_FIELD_TYPES)


def usage():
    print("""
Usage:
    %s [OPTIONS] issues_file yt_url [yt_login] [yt_password]

    issues_file    Issues csv file
    mapping_file   Field mapping file (json) for csv file
    yt_url         YouTrack base URL
    yt_user        YouTrack user
    yt_password    YouTrack user's password
    
      To run the script you need to provide a mapping file that contains
    information on how to map columns from your csv file to fields in YouTrack.
    Otherwise a default mapping will be used but it won't match your needs in
    99.9 percents of cases.
      To generate sample mapping file from your csv file run the script with
    -g option. It will read columns from your csv file and build sample file.
    Then you'll be able to modify it to feet your needs and re-run the script. 

Options:
    -h,  Show this help and exit
    -g,  Generate mapping file based on columns in csv file
    -m MAPPING_FILE,
         Path to mapping file that maps columns from csv to YouTrack fields  
    -c COMMENTS_FILE,
         Import comments from the file
    -a ATTACHMENTS_FILE,
         Import attachments from the file
    -t TOKEN_FILE,
         Import permanent token from the file

""" % os.path.basename(sys.argv[0]))


def main():
    try:
        params = {}
        opts, args = getopt.getopt(sys.argv[1:], 'hgm:c:a:t:')
        for opt, val in opts:
            if opt == '-h':
                usage()
                sys.exit(0)
            elif opt == '-g':
                params['generate_mapping'] = True
            elif opt == '-m':
                check_file_and_save(val, params, 'mapping_file')
            elif opt == '-c':
                check_file_and_save(val, params, 'comments_file')
            elif opt == '-a':
                check_file_and_save(val, params, 'attachments_file')
            elif opt == '-t':
                check_file_and_save(val, params, 'token_file')

        if params.get('generate_mapping', False):
            params['issues_file'] = args[0]
        elif 'token_file' in params:
            (params['issues_file'],
             params['target_url']) = args
        else:
            (params['issues_file'],
             params['target_url'],
             params['login'],
             params['password']) = args
    except getopt.GetoptError as e:
        print(e)
        usage()
        sys.exit(1)
    except (ValueError, KeyError):
        print("Bad arguments")
        usage()
        sys.exit(1)

    if params.get('generate_mapping', False):
        generate_mapping_file(
            params['issues_file'], params.get('mapping_file'))
    else:
        update_mapping(params['mapping_file'])
        csv2youtrack(params)


def check_file_and_save(filename, params, key):
    try:
        params[key] = os.path.abspath(filename)
    except (OSError, IOError) as e:
        print("Data file is not accessible: ")
        print(filename)
        raise e


def generate_mapping_file(issues_csv_filename, mapping_filename=None):
    if not mapping_filename:
        mapping_filename = os.path.splitext(issues_csv_filename)[0] + '.json'
    if os.path.isfile(mapping_filename):
        print("Mapping file won't be generated because the file already exists")
        print(mapping_filename)
        sys.exit(1)
    source = Client(issues_csv_filename)
    mapping_data = dict(
        __delete_me__="See more info about mapping file here: " +
                      "https://www.jetbrains.com/help/youtrack/standalone/" +
                      "Import-from-CSV-File.html#build-mapping-file",
        field_names={
            f: "put_youtrack_field_name_here" for f in source.get_header()},
        field_types=dict(
            youtrack_field_name1="field_type1",
            youtrack_field_name2="field_type2",
            youtrack_field_nameN="field_typeN"),
        csv_field_delimiter=',',
        csv_value_delimiter=',',
        date_format_string='%Y-%m-%d %H:%M:%S'
    )
    try:
        with open(mapping_filename, 'w') as f:
            json.dump(mapping_data, f, sort_keys=True, indent=4)
        print("Mapping file has written to " + mapping_filename)
    except (IOError, OSError) as e:
        print "Failed to write mapping file"
        print(mapping_filename)
        raise e


def update_mapping(mapping_filename):
    try:
        with open(mapping_filename, 'r') as f:
            mapping_data = json.load(f)
            if 'csv_field_delimiter' in mapping_data:
                csvClient.CSV_DELIMITER = mapping_data['csv_field_delimiter']
            if 'csv_value_delimiter' in mapping_data:
                csvClient.VALUE_DELIMITER = mapping_data['csv_value_delimiter']
            if 'date_format_string' in mapping_data:
                csvClient.DATE_FORMAT_STRING = mapping_data['date_format_string']
            csvClient.FIELD_NAMES = mapping_data['field_names']
            csvClient.FIELD_TYPES = mapping_data['field_types']
    except (OSError, IOError) as e:
        print("Failed to read mapping file")
        raise e
    except KeyError as e:
        print("Bad mapping file")
        raise e


def get_project(issue):
    for key, value in csvClient.FIELD_NAMES.items():
        if value == "project":
            return re.sub(r'\W+', "", issue[key])


def csv2youtrack(params):
    source = dict()
    for s in ('issues', 'comments', 'attachments', 'links'):
        if params.get(s + '_file'):
            source[s] = Client(params[s + '_file'])
    if source:
        token = None
        if params.get('token_file', ''):
            try:
                with open(params['token_file'], 'r') as f:
                    token = f.read()
            except IOError as e:
                print("Cannot load token from file")
                raise e
        if token:
            target = Connection(params['target_url'], token=token)
        else:
            target = Connection(
                params['target_url'], params['login'], params['password'])

        config = CsvYouTrackImportConfig(csvClient.FIELD_NAMES,
                                         csvClient.FIELD_TYPES)
        importer = CsvYouTrackImporter(source, target, config)
        importer.import_csv()
    else:
        print("Nothing to import.")


class CsvYouTrackImporter(YouTrackImporter):
    def __init__(self, source, target, import_config):
        super(CsvYouTrackImporter, self).__init__(source['issues'],
                                                  target,
                                                  import_config)
        self._after = 0
        self._comments = dict()
        self._attachments = dict()
        if 'comments' in source:
            for c in source['comments'].get_rows():
                issue_id = '%s-%s' % (c[0], c[1])
                if issue_id not in self._comments:
                    self._comments[issue_id] = []
                self._comments[issue_id].append(c[2:])
        if 'attachments' in source:
            for a in source['attachments'].get_rows():
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
            result.created = self._import_config.to_unix_date(comment[1])
            result.text = comment[2]
            return result

    def get_field_value(self, field_name, field_type, value):
        if (field_name == self._import_config.get_project_name_key()) or (
        field_name == self._import_config.get_project_id_key()):
            return None
        if field_type == u'date':
            return self._import_config.to_unix_date(value)
        if re.match(r'^\s*(enum|version|build|ownedfield|user|group)\[\*\]s*$',
                    field_type, re.IGNORECASE):
            delim = getattr(csvClient,
                            'VALUE_DELIMITER',
                            csvClient.CSV_DELIMITER)
            values = re.split(re.escape(delim), value)
            if len(values) > 1:
                value = values
        return super(CsvYouTrackImporter, self).get_field_value(field_name,
                                                                field_type,
                                                                value)

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
        idf = self._import_config.get_key_for_field_name(u'numberInProject')
        match_result = number_regex.search(issue[idf])
        return match_result.group()

    def _get_yt_issue_id(self, issue):
        number_in_project = self._get_issue_id(issue)
        pf = self._import_config.get_key_for_field_name(
                self._import_config.get_project_id_key()
        )
        project_id = issue[pf]
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
            created = self._import_config.to_unix_date(attach[1])
            name = os.path.basename(attach[2])
            content = open(attach[2], 'rb')
            self._target.importAttachment(
                issue_id, name, content, author, None, None, created, '')

    def _get_custom_field_names(self):
        project_name_key = self._import_config.get_key_for_field_name(
            self._import_config.get_project_name_key())
        project_id_key = self._import_config.get_key_for_field_name(
            self._import_config.get_project_id_key())
        return [key for key in self._source.get_header()
                if (key not in [project_name_key, project_id_key])]

    def _get_projects(self):
        result = {}
        for issue in self._source.get_issues():
            project_id, project_name = self._import_config.get_project(issue)
            if project_id not in result:
                result[project_id] = project_name
        return result

    def _get_custom_fields_for_projects(self, project_ids):
        fields = [self._import_config.get_field_info(field_name)
                  for field_name in self._get_custom_field_names()]
        return [f for f in fields if f is not None]


class CsvYouTrackImportConfig(YouTrackImportConfig):
    def __init__(self, name_mapping, type_mapping, value_mapping=None):
        super(CsvYouTrackImportConfig, self).__init__(name_mapping,
                                                      type_mapping,
                                                      value_mapping)

    @staticmethod
    def to_unix_date(date):
        if csvClient.DATE_FORMAT_STRING[-2:] == "%z":
            dt = datetime.datetime.strptime(
                date[:-6],
                csvClient.DATE_FORMAT_STRING[:-2].rstrip())
        else:
            dt = datetime.datetime.strptime(
                date, csvClient.DATE_FORMAT_STRING)
        return str(calendar.timegm(dt.timetuple()) * 1000)

    @staticmethod
    def get_project_id_key():
        return u'project_id'

    @staticmethod
    def get_project_name_key():
        return u'project_name'

    def get_project(self, issue):
        project_name_key = self.get_key_for_field_name(
            self.get_project_name_key())
        project_id_key = self.get_key_for_field_name(self.get_project_id_key())
        if project_name_key not in issue:
            print(u"ERROR: issue doesn't contain a project_name key called '%s'"
                  % project_name_key)
            print(u"issue: ")
            print(issue)
            raise Exception("Bad csv file")
        if project_id_key not in issue:
            print(u"ERROR: issue doesn't contain a project_id key called '%s'"
                  % project_id_key)
            print(u"issue: ")
            print(issue)
            raise Exception("Bad csv file")
        project_name = issue[project_name_key]
        project_id = issue.get(project_id_key, re.sub(r'\W+', "", project_name))
        return project_id, project_name

    def get_field_info(self, field_name):
        result = {AUTO_ATTACHED: self._get_default_auto_attached(),
                  NAME: self._name_mapping.get(field_name, field_name),
                  TYPE: None}
        if result[NAME] in self._type_mapping:
            result[TYPE] = self._type_mapping[result[NAME]]
        elif result[NAME] in youtrack.EXISTING_FIELD_TYPES:
            result[TYPE] = youtrack.EXISTING_FIELD_TYPES[result[NAME]]
        result[POLICY] = self._get_default_bundle_policy()
        return result


if __name__ == "__main__":
    main()
