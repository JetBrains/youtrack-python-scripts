#! /usr/bin/env python

import sys

if sys.version_info >= (3, 0):
    print("\nThe script doesn't support python 3. Please use python 2.7+\n")
    sys.exit(1)

import os
import traceback
import re
import getopt
import calendar
import urllib2
import youtrackutils.redmine
import youtrack
import youtrack.connection
import time
from youtrack.importHelper import create_bundle_safe
from datetime import datetime
from dateutil import parser

sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
sys.stderr = sys.stdout

CHUNK_SIZE = 100


def usage():
    basename = os.path.basename(sys.argv[0])
    print("""
Usage:
    %s [-t] [-s] [-l] -a api_key r_url y_url y_user y_password [project_id ...]
    %s [-t] [-s] [-l] r_url r_user r_pass y_url y_user y_password [project_id ...]

    r_url          Redmine URL
    r_user         Redmine user
    r_password     Redmine user's password
    y_url          YouTrack URL
    y_user         YouTrack user
    y_password     YouTrack user's password
    project_id     Redmine project identifier

Options:
    -a api_key     Redmine API Key
    -t             Import time entries (works only with YouTrack 4.2 or higher)
    -h             Show this help and exit
    -l             Create a field linking imported redmine tasks with youtrack's
    -s             Skip import of an issue in case of server errors (instead of breaking the whole process) 
""" % (basename, basename))


def main():
    try:
        params = {}
        r_api_key = None
        opts, args = getopt.getopt(sys.argv[1:], 'htsla:')
        for opt, val in opts:
            if opt == '-h':
                usage()
                sys.exit(0)
            if opt == '-t':
                params['import_time_entries'] = True
            if opt == '-a':
                r_api_key = val
            if opt == '-l':
                params['create_redmine_linkage'] = True
            if opt == '-s':
                params['skip_on_error'] = True
        if r_api_key:
            r_url, y_url, y_user, y_password = args[:4]
            project_ids = args[4:]
            redmine_importer = RedmineImporter(
                r_api_key, r_url, None, None, y_url, y_user, y_password, params)
        else:
            r_url, r_user, r_password, y_url, y_user, y_password = args[:6]
            project_ids = args[6:]
            redmine_importer = RedmineImporter(
                None, r_url, r_user, r_password, y_url, y_user, y_password, params)
    except getopt.GetoptError as e:
        print(e)
        usage()
        sys.exit(1)
    except ValueError:
        print('Not enough arguments')
        usage()
        sys.exit(1)
    redmine_importer.do_import(project_ids)


def to_unixtime(time_string):
    tz_diff = 0
    if len(time_string) == 10:
        dt = datetime.strptime(time_string, '%Y-%m-%d')
    else:
        m = re.search('(Z|([+-])(\d\d):?(\d\d))$', time_string)
        if m:
            tzm = m.groups()
            time_string = time_string[0:-len(tzm[0])]
            if tzm[0] != 'Z':
                tz_diff = int(tzm[2]) * 60 + int(tzm[3])
                if tzm[1] == '-':
                    tz_diff = -tz_diff
        dt = parser.parse(time_string)
    return (calendar.timegm(dt.timetuple()) + tz_diff) * 1000


class RedmineImporter(object):
    def __init__(self, r_url, r_api_key, r_user, r_pass, y_url, y_user, y_pass, params):
        self._source = youtrackutils.redmine.RedmineClient(r_url, r_api_key, r_user, r_pass)
        self._target = youtrack.connection.Connection(y_url, y_user, y_pass)
        self._params = params
        self._project_lead = y_user
        self._projects = None
        self._max_issue_ids = {}
        self._issue_ids = {}
        self._relations = {}
        self._users = {}
        self._groups = {}
        self._subsystems = {}
        self._versions = {}

    def do_import(self, project_ids):
        try:
            projects2import = self._get_projects(project_ids)
        except youtrackutils.redmine.RedmineException as e:
            print('FATAL:', e)
            sys.exit(1)

        print('===> Import Roles')
        self._import_roles()

        for project in projects2import.values():
            self._import_project(project)

        print('===> Apply Relations')
        self._apply_relations()

    def _get_projects(self, project_ids=None, by_internal_id=False):
        if by_internal_id:
            by = 'by_iid'
        else:
            by = 'by_pid'
        if self._projects is None:
            self._projects = {'by_iid': {}, 'by_pid': {}}
        if project_ids:
            new_projects = [pid for pid in project_ids
                            if pid not in self._projects[by]]
        else:
            new_projects = None
        if new_projects is None or new_projects:
            for project in self._source.get_projects(new_projects):
                project.identifier = re.sub('\W', '', project.identifier)
                self._projects['by_iid'][project.id] = project
                self._projects['by_pid'][project.identifier] = project
        if project_ids:
            result = {}
            for pid in [re.sub('\W', '', p) for p in project_ids]:
                try:
                    result[pid] = self._projects[by][pid]
                except KeyError:
                    raise youtrackutils.redmine.RedmineException(
                        "Project '%s' doesn't exist in Redmine" % pid)
        return self._projects[by]

    def _get_project(self, project_id, by_internal_id=False):
        return self._get_projects([project_id], by_internal_id)[project_id]

    def _get_project_name(self, project):
        name = project.name
        while True:
            if not hasattr(project, 'parent'):
                break
            name = project.parent.name + ' :: ' + name
            project = self._get_project(project.parent.id, True)
        return name

    def _import_project(self, project):
        project_id = project.identifier
        project_name = self._get_project_name(project)
        project_desc = ''
        if hasattr(project, 'description') and project.description is not None:
            project_desc = project.description

        print("===> Importing Project '%s' (%s)" % \
              (project_name.encode('utf-8'), project_id.encode('utf-8')))
        try:
            print('Creating project...')
            self._target.getProject(project_id)
            print('Project already exists')
        except youtrack.YouTrackException:
            self._target.createProjectDetailed(
                project_id, project_name, project_desc, self._project_lead)
            print('Project successfully created')
        print('Import project members...')
        self._import_members(project)
        print('Import issues...')
        self._import_issues(project)

    def _to_yt_user(self, redmine_user):
        if isinstance(redmine_user, basestring):
            user_id = redmine_user
        else:
            user_id = redmine_user.id
        if user_id not in self._users:
            redmine_user = self._source.get_user(user_id)
            user = youtrack.User()
            try:
                user.email = redmine_user.mail
            except AttributeError:
                pass
            try:
                # In some cases redmine user login can be empty or missing.
                # So, both cases should be handled.
                user.login = redmine_user.login
            except AttributeError:
                pass
            if not hasattr(user, 'login') or not user.login:
                if hasattr(user, 'email'):
                    user.login = user.email
                else:
                    user.login = 'guest'
                print('Cannot get login for user id=%s, set it to "%s"' %
                      (user_id, user.login))
            # user.login = redmine_user.login or 'guest'
            # user.email = redmine_user.mail or 'example@example.com'
            if user.login != 'guest':
                if redmine_user.firstname is None and redmine_user.lastname is None:
                    user.fullName = user.login
                elif redmine_user.firstname is None:
                    user.fullName = redmine_user.lastname
                elif redmine_user.lastname is None:
                    user.fullName = redmine_user.firstname
                else:
                    user.fullName = redmine_user.firstname + ' ' + redmine_user.lastname
            else:
                user.created = True
            if hasattr(redmine_user, 'groups'):
                user.groups = [self._to_yt_group(g) for g in redmine_user.groups]
            self._users[user_id] = user
        return self._users[user_id]

    def _to_yt_group(self, redmine_group, users=None):
        if not isinstance(redmine_group, basestring):
            redmine_group = redmine_group.name
        if redmine_group not in self._groups:
            group = youtrack.Group()
            group.name = redmine_group
            if users is None:
                users = []
            group.users = users
            self._groups[redmine_group] = group
        return self._groups[redmine_group]

    def _to_yt_role(self, name, projects=None):
        role = youtrack.UserRole()
        role.name = name
        if projects:
            if isinstance(projects, list):
                role.projects.extend(projects)
            else:
                role.projects.append(projects)
        return role

    def _to_yt_version(self, version):
        if isinstance(version, basestring):
            vid = version
        else:
            vid = version.id
        if vid not in self._versions:
            redmine_version = self._source.get_version(vid)
            version = youtrack.Version()
            version.name = redmine_version.name
            version.description = redmine_version.description
            if redmine_version.due_date:
                version.releaseDate = str(to_unixtime(redmine_version.due_date))
            version.released = str(redmine_version.status == 'closed').lower()
            version.archived = 'false'
            self._versions[vid] = version
        return self._versions[vid]

    def _to_yt_subsystem(self, category):
        if isinstance(category, basestring):
            cid = category
        else:
            cid = category.id
        if cid not in self._subsystems:
            redmine_cat = self._source.get_category(cid)
            subsystem = youtrack.Subsystem()
            subsystem.name = redmine_cat.name
            if hasattr(redmine_cat, 'assigned_to'):
                subsystem.login = self._create_user(redmine_cat.assigned_to).login
            self._subsystems[cid] = subsystem
        return self._subsystems[cid]

    def _get_assignee_group_name(self, project_id):
        return '%s Assignees' % project_id.upper()

    def _get_yt_issue_id(self, issue, as_number_in_project=False):
        project_id = self._projects['by_iid'][issue.project.id].identifier
        new_id = self._max_issue_ids.get(project_id, 0) + 1
        rid = int(issue.id)
        if rid not in self._issue_ids:
            self._max_issue_ids[project_id] = new_id
            self._issue_ids[rid] = {'id': new_id, 'project_id': project_id}
        if as_number_in_project:
            return self._issue_ids[rid]['id']
        return self._to_yt_issue_id(rid)

    def _to_yt_issue_id(self, iid):
        issue = self._issue_ids[iid]
        return '%s-%d' % (issue['project_id'], issue['id'])

    def _get_yt_issue_number(self, issue):
        return self._get_yt_issue_id(issue, True)

    def _import_members(self, project):
        project_id = project.identifier
        members = self._source.get_project_members(project.id)
        users_by_role = {}
        groups_by_role = {}
        if members:
            for member in members:
                # Sometimes roles can be duplicated
                roles = set([r.name for r in member.roles])
                if hasattr(member, 'group'):
                    group = self._to_yt_group(member.group.name)
                    for role in roles:
                        if role not in groups_by_role:
                            groups_by_role[role] = []
                        groups_by_role[role].append(group)
                else:
                    user = self._to_yt_user(member.user)
                    for role in roles:
                        if role not in users_by_role:
                            users_by_role[role] = []
                        users_by_role[role].append(user)
        for role_name, users in users_by_role.items():
            group = self._to_yt_group('%s %s' % (project_id.upper(), role_name))
            self._create_group(group)
            self._target.addUserRoleToGroup(
                group, self._to_yt_role(role_name, project_id))
            self._target.importUsers(users)
            for user in users:
                self._target.setUserGroup(user.login, group.name)
        for role_name, groups in groups_by_role.items():
            for group in groups:
                self._create_group(group)
                self._target.addUserRoleToGroup(
                    group, self._to_yt_role(role_name, project_id))

    def _import_roles(self):
        existed_roles = [role.name for role in self._target.getRoles()]
        new_roles = {}
        for role in self._source.get_roles():
            if role.name in existed_roles:
                continue
            permissions = None
            if hasattr(role, 'permissions'):
                permissions = []
                for perm in role.permissions:
                    yt_perm = youtrackutils.redmine.Mapping.PERMISSIONS.get(perm.name)
                    if not yt_perm:
                        continue
                    if isinstance(yt_perm, list):
                        permissions.extend(yt_perm)
                    else:
                        permissions.append(yt_perm)
            new_roles[role.name] = permissions
        for role_name, role_permissions in new_roles.items():
            role = self._to_yt_role(role_name)
            self._target.createRole(role)
            if role_permissions:
                for perm_name in role_permissions:
                    perm = youtrack.Permission()
                    perm.name = perm_name
                    self._target.addPermissionToRole(role, perm)

    def _import_issues(self, project, limit=CHUNK_SIZE):
        project_id = project.identifier
        offset = 0
        assignee_group = self._get_assignee_group_name(project_id)
        while True:
            issues = self._source.get_project_issues(project.id, limit, offset,
                                                     self._params.get('skip_on_error', False))
            if not issues:
                break
            issues = [issue for issue in issues if issue.project.id == project.id]
            self._target.importIssues(project_id, assignee_group,
                                      [self._make_issue(issue, project_id) for issue in issues])
            for issue in issues:
                self._collect_relations(issue)
                self._add_attachments(issue)
                if self._params.get('import_time_entries', False):
                    self._enable_timetracking(project)
                    self._add_work_items(issue)
            offset += limit

    def _make_issue(self, redmine_issue, project_id):
        issue = youtrack.Issue()
        issue['comments'] = []
        try:
            if self._params.get('create_redmine_linkage', False):
                self._add_field_to_issue(
                    project_id, issue, "redmine_id", int(redmine_issue.id))
            for name, value in redmine_issue.attributes.items():
                if name in ('project', 'attachments'):
                    continue
                if name == 'assigned_to' and value.name in self._groups:
                    continue
                if name == 'id':
                    value = str(self._get_yt_issue_number(redmine_issue))
                if name == 'custom_fields':
                    for field in value:
                        self._add_field_to_issue(
                            project_id, issue, field.name, field.value)
                elif name == 'journals':
                    self._add_journals(issue, value)
                else:
                    if name == 'category':
                        value = self._to_yt_subsystem(value)
                    if name == 'fixed_version':
                        value = self._to_yt_version(value)
                    self._add_field_to_issue(project_id, issue, name, value)
        except Exception as e:
            print('Failed to process issue:')
            print(redmine_issue)
            traceback.print_exc()
            raise e
        return issue

    def _convert_value(self, field_name, value):
        conv_map = youtrackutils.redmine.Mapping.CONVERSION.get(field_name)
        if conv_map:
            if hasattr(value, 'value'):
                if value.value in conv_map:
                    value.value = conv_map[value.value]
            elif hasattr(value, 'name'):
                if value.name in conv_map:
                    value.name = conv_map[value.name]
        return value

    def _get_yt_field_name(self, field_name):
        return youtrackutils.redmine.Mapping.FIELD_NAMES.get(field_name, field_name)

    def _get_yt_field_type(self, field_name):
        return youtrackutils.redmine.Mapping.FIELD_TYPES.get(
            field_name, youtrack.EXISTING_FIELD_TYPES.get(field_name))

    def _add_field_to_issue(self, project_id, issue, name, value):
        if value is None:
            return
        field_name = self._get_yt_field_name(name)
        field_type = self._get_yt_field_type(field_name)
        if field_type is None:
            return
        value = self._convert_value(field_name, value)
        if isinstance(value, list):
            if not value:
                return
            issue[field_name] = []
            for v in value:
                v = self._create_field_value(project_id, field_name, field_type, v)
                issue[field_name].append(
                    self._get_value_presentation(field_type, v))
        else:
            value = self._create_field_value(project_id, field_name, field_type, value)
            issue[field_name] = self._get_value_presentation(field_type, value)

    def _create_field(self, project_id, field_name, field_type):
        project_fields = self._target.getProjectCustomFields(project_id)
        if field_name.lower() not in [f.name.lower() for f in project_fields]:
            all_fields = self._target.getCustomFields()
            if field_name.lower() not in [f.name.lower() for f in all_fields]:
                self._target.createCustomFieldDetailed(
                    field_name, field_type, False, True, False, {})
            if field_type in ('string', 'date', 'integer', 'float', 'period'):
                self._target.createProjectCustomFieldDetailed(
                    project_id, field_name, 'No ' + field_name)
            else:
                bundle_name = field_name + ' bundle'
                create_bundle_safe(self._target, bundle_name, field_type)
                self._target.createProjectCustomFieldDetailed(
                    project_id, field_name, 'No ' + field_name, {'bundle': bundle_name})

    def _create_field_value(self, project_id, field_name, field_type, value):
        if field_type.startswith('user'):
            if hasattr(value, 'name'):
                value.name = self._create_user(value).login
            else:
                value = self._create_user(value).login
        if field_name == 'Assignee':
            return value
        if field_name in youtrack.EXISTING_FIELDS:
            return value
        self._create_field(project_id, field_name, field_type)
        if field_type in ('string', 'date', 'integer', 'float', 'period'):
            return value
        field = self._target.getProjectCustomField(project_id, field_name)
        bundle = self._target.getBundle(field_type, field.bundle)
        try:
            if hasattr(value, 'value'):
                value = value.value
            elif hasattr(value, 'name'):
                if not (field_type.startswith('version') or
                            field_type.startswith('ownedField')):
                    value = value.name
            self._target.addValueToBundle(bundle, value)
        except youtrack.YouTrackException as e:
            if e.response.status != 409 or e.response.reason.lower() != 'conflict':
                print(e)
        return value

    def _get_value_presentation(self, field_type, value):
        if field_type == 'date':
            return str(to_unixtime(value))
        if field_type == 'integer':
            return '%d' % int(float(value))
        if field_type == 'float':
            return '%.5f' % float(value)
        if field_type == 'string':
            return value
        if field_type == 'period':
            return '%d' % int(float(value) * 60)
        if hasattr(value, 'value'):
            return value.value
        elif hasattr(value, 'name'):
            return value.name
        return value

    def _create_user(self, user):
        user = self._to_yt_user(user)
        if not hasattr(user, 'created'):
            self._target.createUser(user)
            user.created = True
            if hasattr(user, 'groups'):
                for group in user.groups:
                    self._create_group(group)
                    self._target.setUserGroup(user.login, group.name)
        return user

    def _create_group(self, group):
        if isinstance(group, basestring):
            group = self._to_yt_group(group)
        if not hasattr(group, 'created'):
            try:
                self._target.getGroup(group.name)
            except youtrack.YouTrackException:
                self._target.createGroup(group)
            group.created = True
        return group

    def _add_journals(self, issue, journals):
        if not journals:
            return
        for rec in journals:
            if rec.notes is not None and rec.notes != '':
                comment = youtrack.Comment()
                comment.text = rec.notes
                comment.author = self._create_user(rec.user).login
                comment.created = str(to_unixtime(rec.created_on))
                issue['comments'].append(comment)

    def _enable_timetracking(self, project):
        self._target.setProjectTimeTrackingSettings(project.identifier, enabled=True)

    def _add_work_items(self, issue):
        import_data = []
        work_items = self._source.get_time_entries(issue.id)
        for t in sorted(work_items, key=lambda t: t.spent_on):
            work_item = youtrack.WorkItem()
            work_item.authorLogin = self._create_user(t.user).login
            work_item.date = str(to_unixtime(t.spent_on))
            work_item.description = t.comments
            work_item.duration = int(float(t.hours) * 60)
            import_data.append(work_item)
        if import_data:
            self._target.importWorkItems(self._get_yt_issue_id(issue), import_data)

    def _add_attachments(self, issue):
        if not hasattr(issue, 'attachments'):
            return
        max_attempts = 5
        for attach in issue.attachments:
            attach.author.login = self._create_user(attach.author).login
            if not attach.author.login:
                attach.author.login = 'guest'
            attempts = max_attempts
            while attempts:
                attempts -= 1
                try:
                    self._target.createAttachmentFromAttachment(
                        self._get_yt_issue_id(issue),
                        RedmineAttachment(attach, self._source))
                    break
                except Exception as e:
                    print(e)
                    if attempts:
                        delay = 30 + (max_attempts - attempts - 1) * 10
                        print("Can't import attachment: %s. Retry in %d s." %
                              (attach.filename, delay))
                        time.sleep(delay)
                    else:
                        print('Failed to import attachment: %s. Skipped.' %
                              attach.filename)

    def _collect_relations(self, issue):
        link_types = {
            'duplicates': 'duplicate',
            'relates': 'relates',
            'blocks': 'depend',
            'precedes': 'depend'
        }
        if hasattr(issue, 'relations'):
            for rel in issue.relations:
                if rel.relation_type not in link_types:
                    print('Unsuitable link type: %s. Skipped' % rel.relation_type)
                    continue
                from_id = rel.issue_id
                to_id = rel.issue_to_id
                if rel.relation_type == 'duplicates':
                    from_id, to_id = to_id, from_id
                self._push_relation(from_id, to_id, link_types[rel.relation_type])
        if hasattr(issue, 'children'):
            for child in issue.children:
                self._push_relation(issue.id, child.id, 'subtask')

    def _push_relation(self, from_iid, to_iid, relation_type):
        from_iid = int(from_iid)
        to_iid = int(to_iid)
        if relation_type not in self._relations:
            self._relations[relation_type] = {}
        relations = self._relations[relation_type]
        if from_iid not in relations:
            relations[from_iid] = {}
        relations[from_iid][to_iid] = None

    def _apply_relations(self, limit=CHUNK_SIZE):
        links = []
        for link_type, ids in self._relations.items():
            for from_id, to_ids in ids.items():
                for to_id in to_ids:
                    link = youtrack.Link()
                    link.typeName = link_type
                    try:
                        link.source = self._to_yt_issue_id(from_id)
                        link.target = self._to_yt_issue_id(to_id)
                    except KeyError as e:
                        print("Cannot apply link (%s) to issues: %d and %d" %
                              (link_type, from_id, to_id))
                        print("Some issues were not imported to YouTrack")
                        raise e
                    links.append(link)
                    if len(links) >= limit:
                        self._target.importLinks(links)
                        del links[0:]
        if links:
            self._target.importLinks(links)


class RedmineAttachment(object):
    def __init__(self, attach, source):
        self.authorLogin = attach.author.login
        self.name = attach.filename
        self.created = str(to_unixtime(attach.created_on))
        self.url = attach.content_url
        self.headers = source.headers

    def getContent(self):
        return urllib2.urlopen(urllib2.Request(self.url, headers=self.headers))


if __name__ == '__main__':
    main()
