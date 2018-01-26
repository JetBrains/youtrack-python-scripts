#! /usr/bin/env python

import sys

if sys.version_info >= (3, 0):
    print("\nThe script doesn't support python 3. Please use python 2.7+\n")
    sys.exit(1)

import urllib
from youtrack.connection import Connection
from youtrackutils.tracLib.client import Client
import youtrack
import re
import youtrackutils.tracLib
import youtrackutils.tracLib.defaultTrac
import youtrack.connection
from youtrack.importHelper import *


def main():
    try:
        target_url, target_login, target_password, project_ID, project_name, env_path = sys.argv[1:]
        print("url                  : " + target_url)
        print("login                : " + target_login)
        print("pass                 : " + target_password)
        print("id                   : " + project_ID)
        print("name                 : " + project_name)
        print("trac environment at  : " + env_path)
    except BaseException as e:
        print(e)
        return
    trac2youtrack(target_url, target_login, target_password, project_ID, project_name, env_path)


def to_youtrack_user(trac_user) :
    """
    Converts Trac user to YT user.

    Args:
        trac_user: TracUser instance.

    Returns:
        YT user with same email and login as trac user. If trac_user doesn't have email,
        tracLib.DEFAULT_EMAIL is set.
    """
    user = youtrack.User()
    user.login = trac_user.name
    user.email = youtrackutils.tracLib.DEFAULT_EMAIL
    if not (trac_user.email is None):
        if len(trac_user.email):
            user.email = trac_user.email
    return user


def to_non_authorised_youtrack_user(user_name):
    """
    This method is for creating YT users for people, who were not authorised in Trac, but left their names,
    and probably emails.

    Args:
        user_name: String, that represents user. It must have format "login_name <email_address>".

    Returns:
        If user_name can be parsed, returns YT user with login login_name and email email_address,
         else returns None

    """
    if user_name is None:
        return None
    user = youtrack.User()
    # non authorized users in trac are stored like this "name <email_address>"
    start = user_name.find("<")
    end = user_name.rfind(">")
    # we don't accept users who didn't leave the email
    if (start > -1) and (end > start + 1):
        if user_name.find("@", start, end) > 0:
            user.email = user_name[start + 1 : end].replace(" ", "_")
            user.login = user_name[start + 1 : end].replace(" ", "_")
            return user
    return None


def process_non_authorised_user(connection, registered_users, user_name) :
    """
    This method tries to create new YT user for trac non-authorised user.

    Args:
        connection: youtrack.connection object.
         registered_users: list of user logins, that were previously registered in YT.
         user_name: String, that represents user. It must have format "login_name <email_address>".

    Returns:
        New user login and updated list of registered users logins. If it is impossible to create
        new YT user, then user login is None.
    """
    if youtrackutils.tracLib.ACCEPT_NON_AUTHORISED_USERS:
        yt_user = to_non_authorised_youtrack_user(user_name)
        if yt_user is None:
            return None, registered_users
        else:
            if not (yt_user.login in registered_users):
                connection.importUsers([yt_user])
                registered_users.add(yt_user.login)
            return yt_user.login, registered_users
    else:
        return None, registered_users


def to_youtrack_subsystem(trac_component, yt_bundle):
    """
    Converts trac component to YT subsystem.

    Args:
        trac_component: Trac component to convert.
        yt_bundle: YT field bundle to create component in.

    Returns:
        YT field, that has same name, owner and description, as trac component has.

    """
    yt_subsystem = yt_bundle.createElement(trac_component.name)
    yt_subsystem.owner = trac_component.owner
    yt_subsystem.description = trac_component.description
    return yt_subsystem


def to_youtrack_issue(project_ID, trac_issue, check_box_fields):
    issue = youtrack.Issue()

    issue.numberInProject = str(trac_issue.id)
    issue.summary = trac_issue.summary
    issue.description = trac_issue.description
    if trac_issue.time > 0:
        issue.created = str(trac_issue.time)
    if trac_issue.changetime > 0:
        issue.updated = str(trac_issue.changetime)
        # anonymous in trac == guest in util
    if trac_issue.reporter is None:
        issue.reporterName = "guest"
    else:
        issue.reporterName = trac_issue.reporter
    # watchers
    issue.watcherName = set([])
    for cc in trac_issue.cc:
        issue.watcherName.add(cc)
    # adding custom fields to issue
    custom_fields = trac_issue.custom_fields
    for cf in custom_fields.keys():
        if cf in check_box_fields:
            if custom_fields[cf] != "0":
                issue[cf] = check_box_fields[cf]
        else:
            value = custom_fields[cf]
            if cf in youtrackutils.tracLib.FIELD_NAMES.keys():
                cf = youtrackutils.tracLib.FIELD_NAMES[cf]
            if cf in youtrackutils.tracLib.FIELD_VALUES.keys():
                cf_values_mapping = youtrackutils.tracLib.FIELD_VALUES[cf]
                if value in cf_values_mapping:
                    value = cf_values_mapping[value]
            if (value is not None) and (value.strip() != ""):
                issue[cf] = value

    # handle special case of status:closed / resolution:fixed
    if (custom_fields["Status"] is not None) and (custom_fields["Status"] == "closed"):
        if (custom_fields["Resolution"] is not None) and (custom_fields["Resolution"] == "fixed"):
            issue["State"] = "Verified"

    issue.comments = []
    for comment in trac_issue.comments:
        issue.comments.append(to_youtrack_comment(project_ID, comment))
    return issue


def to_youtrack_version(trac_version, yt_bundle):
    """"
    This method converts trac version to YT version.

    Args:
        trac_version: Trac version to convert.
        yt_bundle: YT field bundle to create version in.

    Returns:
        YT version that has same name, description and release date as trac version.
        New version is released and not archived.
    """""
    version = yt_bundle.createElement(trac_version.name)
    version.isReleased = (trac_version.time is not None)
    version.isArchived = False
    version.description = trac_version.description
    version.releaseDate = trac_version.time
    return version


def to_youtrack_comment(project_ID, trac_comment):
    """
    This method converts trac comment to youtrack comment

    Args:
        trac_comment: Trac comment to convert

    Returns:
        YT comment, which has same author as initial comment. If initial comment
        author was anonymous, comment is added from behalf of guest user. YT comment
        gets same creation date as trac comment.
    """
    comment = youtrack.Comment()
    if trac_comment.author == "anonymous":
        comment.author = "guest"
    else:
        comment.author = trac_comment.author

    comment.text = trac_comment.content

    # translate Trac wiki ticket link format to YouTrack id format
    comment.text = re.sub(r'\#(\d+)', project_ID+'-'+r'\1', comment.text)

    # translate trac preformatted blocks, {{{ and }}}
    # opening tag done as two lines for python 2.7 that doesn't really support optional capture group
    comment.text = re.sub(r'{{{\s*#!(\w+)', r'```\1', comment.text)
    comment.text = re.sub(r'{{{', r'```', comment.text)
    comment.text = re.sub(r'}}}', r'```', comment.text)

    comment.created = str(trac_comment.time)
    return comment


def trac_values_to_youtrack_values(field_name, value_names):
    """
    This method converts trac custom field valued values to YT custom field values using
    mapping file (FIELD_VALUES dict). If some value is not in this dictionary, it is added
    to result as is.

    Args:
        field_name: Name of YT custom field to convert values for.
        value_names: trac value names.

    Returns:
        List of strings, that ahs YT field values. If value_names is None, returns None.
    """
    if value_names is None:
        return None
    field_values = []
    for name in value_names:
        if field_name in youtrackutils.tracLib.FIELD_VALUES:
            if name in youtrackutils.tracLib.FIELD_VALUES[field_name].keys():
                name = youtrackutils.tracLib.FIELD_VALUES[field_name][name]
        if name not in field_values:
            field_values.append(name)
    return field_values


def trac_field_name_to_yt_field_name(trac_field_name):
    if trac_field_name in youtrackutils.tracLib.FIELD_NAMES:
        return youtrackutils.tracLib.FIELD_NAMES[trac_field_name]
    return trac_field_name


def create_yt_custom_field(connection, project_Id, field_name, value_names):
    """
    Creates YT custom field if needed and attaches it to project with id project_id. Converts Trac value_names
    to YT values and sets those values to project custom field.

    Args:
        connection: Connection instance.
        project_id: Id of project to attach field to.
        field_name: Name of trac field. It will be converted to YT cf name. YT field should be mentioned in tracLib.FIELD_TYPES mapping.
        value_names: Names of Trac cf values. They will be converted to YT values.
    """
    field_values = trac_values_to_youtrack_values(field_name, value_names)
    field_name = trac_field_name_to_yt_field_name(field_name)
    process_custom_field(connection, project_Id, youtrackutils.tracLib.FIELD_TYPES[field_name], field_name, field_values)


def to_youtrack_state(trac_resolution, yt_bundle) :
    """
    Creates YT state in yt_bundle with trac_resolution name.

    Args:
        track_resolution: Name of new state to add.
        yt_bundle: FieldBundle to create new state in.

    Returns:
        New resolved YT state with trac_resolution name.
    """
    state = yt_bundle.createElement(trac_resolution.name)
    state.isResolved = True
    return state


def to_youtrack_workitem(trac_workitem):
    workitem = youtrack.WorkItem()
    workitem.date = str(trac_workitem.time)
    workitem.duration = str(int(trac_workitem.duration) / 60)
    workitem.authorLogin = trac_workitem.author
    workitem.description = trac_workitem.comment
    return workitem


def create_yt_bundle_custom_field(target, project_id, field_name, trac_field_values, trac_field_to_youtrack_field):
    """
    Creates YT bundle custom field if needed and attaches it to project with id project_id. If Field is already attached to project,
    adds missing values to bundle, attached with this field. If there is no such custom field, attached to this project, creates bundle
    to attaches with this field, converts trac_field_values to YT field values and adds them to created bundle.

     Args:
        target: Connection instance..
        project_id: Id of project to attach field to.
        field_name: Name of custom field in trac. It will be converted to custom field name in YT.
        trac_field_values: Field values in Trac.
        trac_field_to_yt_field: Methods, that converts trac field value to YT Field in particular bundle
    """
    create_yt_custom_field(target, project_id, field_name, [])
    field_name = trac_field_name_to_yt_field_name(field_name)

    field_bundle = target.getBundle(
        youtrackutils.tracLib.FIELD_TYPES[field_name][0:-3],
        target.getProjectCustomField(project_id, field_name).bundle)
    values_to_add = []
    for field in trac_field_values:
        if field_name in youtrackutils.tracLib.FIELD_VALUES.keys():
            if field.name in youtrackutils.tracLib.FIELD_VALUES[field_name].keys():
                field.name = youtrackutils.tracLib.FIELD_VALUES[field_name][field.name]
        values_to_add.append(trac_field_to_youtrack_field(field, field_bundle))
    add_values_to_bundle_safe(target, field_bundle, values_to_add)


def trac2youtrack(target_url, target_login, target_password, project_ID, project_name, env_path):
    # creating connection to trac to import issues to
    client = Client(env_path)
    # creating connection to util to import issues in
    target = Connection(target_url, target_login, target_password)

    # create project
    print("Creating project[%s]" % project_name)
    try:
        target.getProject(project_ID)
    except youtrack.YouTrackException:
        target.createProjectDetailed(project_ID, project_name, client.get_project_description(), target_login)

    # importing users
    trac_users = client.get_users()
    print("Importing users")
    yt_users = list([])

    # converting trac users to yt users
    registered_users = set([])
    for user in trac_users :
        print("Processing user [ %s ]" % user.name)
        registered_users.add(user.name)
        yt_users.append(to_youtrack_user(user))
        # adding users to yt project
    target.importUsers(yt_users)
    print("Importing users finished")

    print("Creating project custom fields")

    create_yt_custom_field(target, project_ID, "Priority", client.get_issue_priorities())

    create_yt_custom_field(target, project_ID, "Type", client.get_issue_types())

    trac_resolution_to_yt_state = lambda track_field, yt_bundle : to_youtrack_state(track_field, yt_bundle)
    create_yt_bundle_custom_field(target, project_ID, "Resolution", client.get_issue_resolutions(), trac_resolution_to_yt_state)

    trac_version_to_yt_version = lambda trac_field, yt_bundle : to_youtrack_version(trac_field, yt_bundle)

    trac_versions = client.get_versions()
    create_yt_bundle_custom_field(target, project_ID, "Affected versions", trac_versions, trac_version_to_yt_version)

    trac_milestones = client.get_milestones()
    create_yt_bundle_custom_field(target, project_ID, "Fix versions", trac_milestones, trac_version_to_yt_version)

    trac_components = client.get_components()
    for cmp in trac_components :
        if cmp.owner not in registered_users :
            cmp.owner, registered_users = process_non_authorised_user(target, registered_users, cmp.owner)
    trac_component_to_yt_subsystem = lambda trac_field, yt_bundle : to_youtrack_subsystem(trac_field, yt_bundle)
    create_yt_bundle_custom_field(target, project_ID, "Component", trac_components, trac_component_to_yt_subsystem)

    create_yt_custom_field(target, project_ID, "Severity", client.get_severities())

    trac_custom_fields = client.get_custom_fields_declared()
    check_box_fields = dict([])
    for elem in trac_custom_fields:
        print("Processing custom field [ %s ]" % elem.name)
        if elem.type == "checkbox":
            if len(elem.label) > 0:
                opt = elem.label
            else:
                opt = elem.name
            options = list([opt])
            check_box_fields[elem.name] = opt
        else:
            options = elem.options

        values = None
        if len(options):
            values = options

        field_name = elem.name
        if field_name in youtrackutils.tracLib.FIELD_NAMES.keys() :
            field_name = youtrackutils.tracLib.FIELD_NAMES[field_name]

        field_type = youtrackutils.tracLib.CUSTOM_FIELD_TYPES[elem.type]
        if field_name in youtrackutils.tracLib.FIELD_TYPES.keys():
            field_type = youtrackutils.tracLib.FIELD_TYPES[field_name]

        process_custom_field(target, project_ID, field_type, field_name, trac_values_to_youtrack_values(field_name, values))
        print("Creating project custom fields finished")

    print("Importing issues")
    trac_issues = client.get_issues()
    yt_issues = list([])
    counter = 0
    max = 100
    for issue in trac_issues:
        print("Processing issue [ %s ]" % (str(issue.id)))
        counter += 1
        if not (issue.reporter in registered_users):
            yt_user, registered_users = process_non_authorised_user(target, registered_users, issue.reporter)
            if yt_user is None :
                issue.reporter = "guest"
            else:
                issue.reporter = yt_user
        if not (issue.owner in registered_users):
            yt_user, registered_users = process_non_authorised_user(target, registered_users, issue.owner)
            if yt_user is None :
                issue.owner = ""
            else:
                issue.owner = yt_user
        legal_cc = set([])
        for cc in issue.cc:
            if cc in registered_users:
                legal_cc.add(cc)
        issue.cc = legal_cc

        yt_issues.append(to_youtrack_issue(project_ID, issue, check_box_fields))
        if counter == max:
            counter = 0
            print(target.importIssues(project_ID, project_name + ' Assignees', yt_issues))
            yt_issues = list([])
    print(target.importIssues(project_ID, project_name + ' Assignees', yt_issues))
    print('Importing issues finished')

    # importing tags
    print("Importing keywords")
    for issue in trac_issues:
        print("Importing tags from issue [ %s ]" % (str(issue.id)))
        tags = issue.keywords
        for t in tags:
            target.executeCommand(str(project_ID) + "-" + str(issue.id), "tag " + t.encode('utf-8'))
    print("Importing keywords finished")

    print("Importing attachments")
    for issue in trac_issues:
        print("Processing issue [ %s ]" % (str(issue.id)))
        issue_attach = issue.attachment
        for attach in issue_attach:
            print("Processing attachment [ %s ]" % attach.filename.encode('utf-8'))
            if not (attach.author_name in registered_users):
                yt_user, registered_users = process_non_authorised_user(target, registered_users, attach.author_name)
                if yt_user is None:
                    attach.author_name = "guest"
                else:
                    attach.author_name = yt_user
            content = open(urllib.quote(attach.filename.encode('utf-8')))
            target.createAttachment(str(project_ID) + "-" + str(issue.id), attach.name, content, attach.author_name,
                                    created=attach.time)
    print("Importing attachments finished")

    print("Importing workitems")
    tt_enabled = False
    for issue in trac_issues:
        if issue.workitems:
            if not tt_enabled:
                tt_settings = target.getProjectTimeTrackingSettings(str(project_ID))
                if not tt_settings.Enabled:
                    print("Enabling TimeTracking for the project")
                    target.setProjectTimeTrackingSettings(str(project_ID), enabled=True)
                tt_enabled = True
            print("Processing issue [ %s ]" % (str(issue.id)))
            workitems = [to_youtrack_workitem(w) for w in issue.workitems]
            target.importWorkItems(str(project_ID) + "-" + str(issue.id), workitems)
    print("Importing workitems finished")

if __name__ == "__main__":
    main()
