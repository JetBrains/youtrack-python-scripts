#! /usr/bin/env python

import sys

if sys.version_info >= (3, 0):
    print("\nThe script doesn't support python 3. Please use python 2.7+\n")
    sys.exit(1)

from youtrackutils.fbugz.fbSOAPClient import FBClient
from youtrack.connection import Connection
from youtrack import Group, User, Issue, Comment, Link
import youtrackutils.fbugz
from youtrack.importHelper import *


def main() :
    try :
        target_url, target_login, target_password, source_url, source_login, source_password, num = sys.argv[1:8]
        max_issue_id = int(num)
    except BaseException:
        print("Usage : ")
        print("fb2youtrack.py target_url target_login target_password source_url source_login source_password max_issue_id project_names")
        sys.exit()
    project_names = youtrackutils.fbugz.PROJECTS_TO_IMPORT
    if not source_url.endswith("/") :
        source_url += "/"
    fb2youtrack(target_url, target_login, target_password, source_url, source_login, source_password, project_names, max_issue_id)


def _to_yt_user(fb_user) :
    user = User()
    user.login = fb_user.login.replace(' ', '_')

    user.fullName = fb_user.login
    user.email = fb_user.email
    user.group = fb_user.user_type
    return user


def _to_yt_subsystem(bundle, area) :
    subsystem = bundle.createElement(area.name)
    assignee = area.person_owner
    if assignee is not None:
        subsystem.owner = assignee.replace(' ', "_")
    return subsystem


def _to_yt_version(bundle, milestone) :
    version = bundle.createElement(milestone.name)
    version.released = milestone.inactive
    version.archived = False
    version.releaseDate = milestone.release_date
    return version


def _to_yt_comment(fb_comment) :
    comment = Comment()
    comment.author = fb_comment.author.replace(" ", "_")
    comment.text = fb_comment.text
    comment.created = fb_comment.date
    return comment


def _to_yt_issue(fb_issue, value_sets) :
    issue = Issue()
    issue.numberInProject = str(fb_issue.ix_bug)
    issue.summary = fb_issue.title
    issue.created = fb_issue.opened
    issue.reporterName = fb_issue.reporter.replace(' ', "_")

    for field_name in fb_issue.field_values.keys():
        value_set = None
        if field_name in value_sets:
            value_set = value_sets[field_name]
        yt_field_name = get_yt_name_from_fb_field_name(field_name)
        field_value = fb_issue.field_values[field_name]
        if value_set is not None and field_value not in value_set :
            field_value = None
        value = to_yt_field_value(yt_field_name, field_value)
        if value is not None:
            issue[yt_field_name] = value
        
    issue.comments = []
    is_description = True
    for c in fb_issue.comments :
        if is_description:
            issue.description = c.text
            is_description = False
        else :
            issue.comments.append(_to_yt_comment(c))
    return issue


def add_field_values_to_bundle(connection, bundle, field_values):
    missing_names = calculate_missing_value_names(bundle, [value.name for value in field_values])
    for value in field_values:
        if value.name in missing_names:
            connection.addValueToBundle(bundle, value)


def _do_import_users(target, users_to_import):
    target.importUsers(users_to_import)
    for u in users_to_import:
        target.setUserGroup(u.login, u.group)


def get_yt_name_from_fb_field_name(fb_name):
    if fb_name in youtrackutils.fbugz.CF_NAMES:
        return youtrackutils.fbugz.CF_NAMES[fb_name]
    return fb_name.decode('utf-8')


def create_bundle_with_values(connection, bundle_type, bundle_name, values, value_converter):
    bundle = create_bundle_safe(connection, bundle_name, bundle_type)
    values = set(values)
    values_to_add = [value_converter(bundle, value) for value in values if value is not None]
    add_field_values_to_bundle(connection, bundle, values_to_add)


def add_values_to_field(connection, field_name, project_id, values, create_value):
    field = connection.getProjectCustomField(project_id, field_name)
    values = set(values)
    if hasattr(field, 'bundle'):
        bundle = connection.getBundle(field.type, field.bundle)
        yt_values = [create_value(bundle, to_yt_field_value(field_name, value)) for value in values]
        add_field_values_to_bundle(connection, bundle, yt_values)


def to_yt_status(bundle, fb_status):
    status_name, resolved = fb_status
    status = bundle.createElement(status_name)
    status.is_resolved = str(resolved)
    return status


def to_yt_field_value(field_name, value):
    if field_name not in youtrackutils.fbugz.CF_VALUES:
        return value
    if value not in youtrackutils.fbugz.CF_VALUES[field_name]:
        return value
    return youtrackutils.fbugz.CF_VALUES[field_name][value]


def fb2youtrack(target_url, target_login, target_password, source_url, source_login, source_password, project_names, max_issue_id) :
    #encoding = 'utf-8'
    source = FBClient(source_url, source_login, source_password)
    target = Connection(target_url, target_login, target_password)
    accessible_projects = source.list_project_names()
    for p_name in project_names :
        if not(p_name in  accessible_projects.keys()) :
            print('Unknown project names. Exiting...')
            sys.exit()

#    for p_name in accessible_projects :
#        if (p_name.encode('utf-8') in project_names_str) :
#            project_names_str.remove(p_name.encode('utf-8'))
#            project_names.append(p_name)
#
#    if (len(project_names_str) != 0) :
#        print 'Unknown project names!'

    print('Creating custom fields')
#
#    for field_name in ['Category', 'Priority', 'Status']:
#        field_name = get_yt_name_from_fb__field_name(field_name)
#        create_custom_field(target, fbugz.CF_TYPES[field_name], field_name, False)

    fb_category_bundle_name = u'FB Categories'
    fb_priorities_bundle_name = u'FB Priorities'
    fb_statuses_bundle_name = u'FB Statuses'

    common_fields = {
        u'category'  :   fb_category_bundle_name,
        u'priority'  :   fb_priorities_bundle_name,
        u'status'    :   fb_statuses_bundle_name
    }

    field_name = u'category'
    create_bundle_with_values(target,
                              youtrackutils.fbugz.CF_TYPES[get_yt_name_from_fb_field_name(field_name)],
                              common_fields[field_name],
                              source.list_categories(),
                              lambda bundle, value : bundle.createElement(to_yt_field_value(field_name, value)))
    field_name = u'priority'
    create_bundle_with_values(target, youtrackutils.fbugz.CF_TYPES[get_yt_name_from_fb_field_name(field_name)],
                              common_fields[field_name],
                              [elem[0] + '-' + elem[1] for elem in source.list_priorities()],
                              lambda bundle, value : bundle.createElement(to_yt_field_value(field_name, value)))

    field_name = u'status'
    statuses = [(to_yt_field_value(field_name, value), resolved) for (value, resolved) in source.list_statuses()]
    create_bundle_with_values(target, youtrackutils.fbugz.CF_TYPES[get_yt_name_from_fb_field_name(field_name)],
                              common_fields[field_name],
                              statuses, lambda bundle, value : to_yt_status(bundle, value))

    simple_fields = [u'original_title', u'version', u'computer', u'due', u'estimate']

    for name in simple_fields:
        name = get_yt_name_from_fb_field_name(name)
        create_custom_field(target, youtrackutils.fbugz.CF_TYPES[name], name, False)

    print('Importing users')
    for name in ['Normal', 'Deleted', 'Community', 'Virtual'] :
        group = Group()
        group.name = name
        try :
            target.createGroup(group)
            print('Group with name [ %s ] successfully created' % name)
        except:
            print("Can't create group with name [ %s ] (maybe because it already exists)" % name)

    users_to_import = []
    max = 100
    for user in source.get_users() :
        yt_user = _to_yt_user(user)
        print('Importing user [ %s ]' % yt_user.login)
        users_to_import.append(yt_user)
        if len(users_to_import) >= max:
            _do_import_users(target, users_to_import)
            users_to_import = []
    _do_import_users(target, users_to_import)
    print('Importing users finished')

    # to handle linked issues
    try :
        target.createIssueLinkTypeDetailed('parent-child', 'child of', 'parent of', True)
    except YouTrackException:
        print("Can't create issue link type [ parent-child ] (maybe because it already exists)")
    links_to_import = []

    for project_name in project_names :
        value_sets = dict([])

        project_id = accessible_projects[project_name]
        print('Importing project [ %s ]' % project_name)
        target.createProjectDetailed(project_id, project_name.encode('utf-8'), 'no description', 'root')

        print('Creating custom fields in project [ %s ]' % project_name)

        for cf_name in common_fields:
            bundle_name = common_fields[cf_name]
            cf_name = get_yt_name_from_fb_field_name(cf_name)
            target.deleteProjectCustomField(project_id, cf_name)
            target.createProjectCustomFieldDetailed(project_id, cf_name, 'No ' + cf_name.lower(),
                    {'bundle' : bundle_name})

        for cf_name in simple_fields:
            cf_name = get_yt_name_from_fb_field_name(cf_name)
            try:
                target.createProjectCustomFieldDetailed(project_id, cf_name, 'No ' + cf_name.lower())
            except YouTrackException:
                print("Can't create custom field with name [%s]" % cf_name)
        cf_name = get_yt_name_from_fb_field_name('fix_for')
        milestones = source.get_milestones(project_id)
        value_sets["fix_for"] = []
        for milestone in milestones:
            value_sets["fix_for"].append(milestone.name)
            milestone.name = to_yt_field_value('fix_for', milestone.name)
        add_values_to_field(target, cf_name, project_id, milestones,
                            lambda bundle, value: _to_yt_version(bundle, value))

        cf_name = get_yt_name_from_fb_field_name('area')
        areas = source.get_areas(project_id)
        value_sets["area"] = []
        for area in areas:
            value_sets["area"].append(area.name)
            area.name = to_yt_field_value('area', area.name)
        add_values_to_field(target, cf_name, project_id, areas,
                            lambda bundle, value: _to_yt_subsystem(bundle, value))

        print('Importing issues for project [ %s ]' % project_name)
        start = 0
        issues_to_import = []
        # create dictionary with child : parent pairs
        while start <= max_issue_id:
            fb_issues = source.get_issues(project_name, start, 30)
            for issue in fb_issues :
                add_values_to_field(target, get_yt_name_from_fb_field_name('area'), project_id,
                    [issue.field_values['area']], lambda bundle, value: bundle.createElement(value))
                issues_to_import.append(_to_yt_issue(issue, value_sets))
            target.importIssues(project_id, project_name.encode('utf-8') + " assignees", issues_to_import)
            for issue in fb_issues :
                full_issue_id = '%s-%s' % (project_id, issue.ix_bug)
                for attach in issue.attachments :
                    target.createAttachmentFromAttachment(full_issue_id, attach)
                for tag in issue.tags :
                    target.executeCommand(full_issue_id, 'tag ' + tag)
                if issue.bug_parent is not None:
                    parent_issue_id = '%s-%s' % (source.get_issue_project_id(issue.bug_parent), issue.bug_parent)
                    link = Link()
                    link.typeName = 'parent-child'
                    link.source = full_issue_id
                    link.target = parent_issue_id
                    links_to_import.append(link)
            issues_to_import = []
            start += 30
        print('Importing issues for project [ %s ] finished' % project_name)

    print('Importing issue links')
    print(target.importLinks(links_to_import))
    print('Importing issue links finished')

if __name__ == '__main__':
    main()
