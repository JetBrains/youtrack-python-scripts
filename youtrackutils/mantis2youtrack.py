#! /usr/bin/env python

import sys

if sys.version_info >= (3, 0):
    print("\nThe script doesn't support python 3. Please use python 2.7+\n")
    sys.exit(1)

import urllib2
from youtrack.connection import Connection
from youtrackutils.mantis.mantisClient import MantisClient
from youtrack import *
import youtrackutils.mantis
import youtrackutils.mantis.defaultMantis
from StringIO import StringIO
from youtrack.importHelper import *
import youtrack.importHelper


def main():
    target_url, target_login, target_pass, mantis_db, mantis_host, mantis_port, mantis_login, mantis_pass = sys.argv[1:9]

    youtrackutils.mantis.FIELD_TYPES.update(youtrack.EXISTING_FIELD_TYPES)
    mantis_product_names = [p.strip() for p in sys.argv[9:]]
    mantis2youtrack(target_url, target_login, target_pass, mantis_db, mantis_host,
        mantis_port, mantis_login, mantis_pass, mantis_product_names)


def to_yt_user(mantis_user):
    yt_user = User()
    yt_user.login = mantis_user.user_name
    yt_user.fullName = mantis_user.real_name
    yt_user.email = mantis_user.email if (mantis_user.email is not None) and len(mantis_user.email) else "<no_email>"
    return yt_user


def to_yt_subsystem(mantis_cat, bundle, value_mapping):
    name = mantis_cat.name
    if name in value_mapping:
        name = value_mapping[name]
    name = name.replace("/", " ")
    subsys = bundle.createElement(name)
    subsys.isDefault = False
    assignee = mantis_cat.assignee
    if assignee is not None:
        subsys.owner = assignee
    else:
        subsys.defaultAssignee = ""
    return subsys


def to_yt_version(mantis_version, bundle, value_mapping):
    name = mantis_version.name
    if name in value_mapping:
        name = value_mapping[name]
    yt_version = bundle.createElement(name)
    yt_version.isReleased = mantis_version.is_released
    yt_version.isArchived = mantis_version.is_obsolete
    yt_version.releaseDate = mantis_version.release_date
    return yt_version


def to_yt_comment(mantis_comment, target):
    yt_comment = Comment()
    if mantis_comment.reporter is not None:
        reporter = to_yt_user(mantis_comment.reporter)
        target.importUsers([reporter])
        yt_comment.author = reporter.login
    else:
        yt_comment.author = "guest"
    if (mantis_comment.text is not None) and len(mantis_comment.text.lstrip()):
        yt_comment.text = mantis_comment.text
    else:
        yt_comment.text = "no text"
    yt_comment.created = mantis_comment.date_submitted
    return yt_comment


def get_yt_field_value(yt_field_name, field_type, mantis_value):
    if mantis_value is None:
        return None
    values_map = {}
    if yt_field_name in youtrackutils.mantis.FIELD_VALUES:
        values_map = youtrackutils.mantis.FIELD_VALUES[yt_field_name]

    if isinstance(mantis_value, str) or isinstance(mantis_value, unicode):
        if mantis_value in values_map:
            mantis_value = values_map[mantis_value]
        if yt_field_name not in ('summary', 'description'):
            mantis_value = mantis_value.replace("/", " ")
        return mantis_value
    if isinstance(mantis_value, int) or isinstance(mantis_value, long):
        if mantis_value in values_map:
            mantis_value = values_map[mantis_value]
        return str(mantis_value)
    if isinstance(mantis_value, list):
        return [value.replace("/", " ") for value in [values_map[v] if v in values_map else v for v in mantis_value]]
    if isinstance(mantis_value, youtrackutils.mantis.MantisUser):
        return to_yt_user(mantis_value)
    return mantis_value


def get_yt_field_name(mantis_field_name, target, project_id=None):
    result = None
    if mantis_field_name in youtrackutils.mantis.FIELD_NAMES:
        result = youtrackutils.mantis.FIELD_NAMES[mantis_field_name]
    elif mantis_field_name in youtrack.EXISTING_FIELDS:
        result = mantis_field_name
    else:
        try:
            target.getCustomField(mantis_field_name)
            result = mantis_field_name
        except YouTrackException:
            pass
    if result is None or project_id is None:
        return result
    if result in youtrack.EXISTING_FIELDS:
        return result
    try:
        target.getProjectCustomField(project_id, result)
        return result
    except YouTrackException:
        return None


def get_yt_field_type(field_name, target):
    if field_name in youtrackutils.mantis.FIELD_TYPES:
        return youtrackutils.mantis.FIELD_TYPES[field_name]
    try:
        return target.getCustomField(field_name).type
    except YouTrackException:
        return None


def add_value_to_field(field_name, field_type, value, project_id, target):
    if (field_type is not None) and field_type.startswith("user"):
        target.importUsers([value])
        value = value.login
    if field_name in youtrack.EXISTING_FIELDS:
        return
    custom_field = target.getProjectCustomField(project_id, field_name)
    if hasattr(custom_field, "bundle"):
        bundle = target.getBundle(field_type, custom_field.bundle)
        try:
            target.addValueToBundle(bundle, value)
        except YouTrackException:
            pass


def to_yt_issue(mantis_issue, project_id, target):
    issue = Issue()
    issue.comments = [to_yt_comment(comment, target) for comment in mantis_issue["comments"]]
    for key in mantis_issue.keys():
        field_name = get_yt_field_name(key, target, project_id)
        if field_name is None:
            continue
        field_type = get_yt_field_type(field_name, target)
        if field_type is None and field_name not in youtrack.EXISTING_FIELDS:
            continue
        value = mantis_issue[key]
        if value is None:
            continue
        if isinstance(value, list):
            if not len(value):
                continue
        elif not len(unicode(value)):
            continue
        value = get_yt_field_value(field_name, field_type, value)
        if isinstance(value, list):
            for v in value:
                add_value_to_field(field_name, field_type, v, project_id, target)
        else:
            add_value_to_field(field_name, field_type, value, project_id, target)

        if (field_type is not None) and field_type.startswith("user"):
            if isinstance(value, list):
                value = [v.login for v in value]
            else:
                value = value.login
        if not isinstance(value, list):
            value = unicode(value)

        issue[field_name] = value
    if "reporterName" not in issue:
        issue["reporterName"] = "guest"
    return issue


def to_yt_link(mantis_link):
    link = Link()
    link.source = "%s-%s" % (mantis_link.source_project_id, mantis_link.source)
    link.target = "%s-%s" % (mantis_link.target_project_id, mantis_link.target)
    link.typeName = youtrackutils.mantis.LINK_TYPES[mantis_link.type]
    return link


def create_yt_custom_field(connection, mantis_field_name,
                           attach_bundle_policy="0", auto_attach=True):
    """
    Converts mantis_field_name to yt field name and creates
    auto attached field with such names and values.

    Args:
        connection: Opened Connection instance.
        mantis_field_name: Name of custom field in mantis.
        attach_bundle_policy: Should be "0" if bundle must be attached as is and "1" if it should be cloned.
        auto_attach: 

    Returns:
        new field name
    """
    print("Processing custom field with name [ %s ]" % mantis_field_name.encode('utf-8'))
    field_name = youtrackutils.mantis.FIELD_NAMES[mantis_field_name] if mantis_field_name in youtrackutils.mantis.FIELD_NAMES else mantis_field_name
    create_custom_field(connection, youtrackutils.mantis.FIELD_TYPES[field_name], field_name, auto_attach,
                        bundle_policy=attach_bundle_policy)
    return field_name


def process_mantis_custom_field(connection, mantis_cf_def):
    """
    Converts mantis cf to yt cf.

    Args:
        connection: Opened Connection instance.
        mantis_cf_def: definition of cf in mantis.

    """
    # get names of custom fields in util that are mapped with this prototype
    # calculate type of custom field in util
    yt_cf_type = youtrackutils.mantis.CF_TYPES[mantis_cf_def.type]
    yt_name = youtrackutils.mantis.FIELD_NAMES[mantis_cf_def.name] if mantis_cf_def.name in youtrackutils.mantis.FIELD_NAMES else mantis_cf_def.name
    if yt_name in youtrackutils.mantis.FIELD_TYPES:
        yt_cf_type = youtrackutils.mantis.FIELD_TYPES[yt_name]
    create_custom_field(connection, yt_cf_type, yt_name, False)


def attach_field_to_project(connection, project_id, mantis_field_name):
    name = get_yt_field_name(mantis_field_name, connection)
    project_field = connection.getCustomField(name)
    params = dict([])
    if hasattr(project_field, "defaultBundle"):
        params["bundle"] = project_field.defaultBundle
    try:
        connection.createProjectCustomFieldDetailed(str(project_id), name, u"No " + name, params)
    except YouTrackException:
        pass


def add_values_to_fields(connection, project_id, mantis_field_name, values, mantis_value_to_yt_value):
    """
    Adds values to custom fields, which are mapped with mantis_field_name field.

    Args:
        connection: Opened Connection instance.
        project_id: Id of project to add values to.
        mantis_field_name: name of cf in Mantis.
        values: Values to add to field in Mantis.

    """
    field_name = get_yt_field_name(mantis_field_name, connection)
    pcf = connection.getProjectCustomField(str(project_id), field_name)
    if hasattr(pcf, "bundle"):
        value_mapping = youtrackutils.mantis.FIELD_VALUES[field_name] if field_name in youtrackutils.mantis.FIELD_VALUES else {}
        bundle = connection.getBundle(pcf.type[0:-3], pcf.bundle)
        yt_values = [v for v in [mantis_value_to_yt_value(value, bundle, value_mapping) for value in values] if
                     len(v.name)]
        add_values_to_bundle_safe(connection, bundle, yt_values)


def import_attachments(issue_attachments, issue_id, target):
    for attachment in issue_attachments:
        print("Processing issue attachment [ %s ]" % str(attachment.id))
        content = StringIO(attachment.content)
        author_login = "guest"
        if attachment.author is not None:
            author = to_yt_user(attachment.author)
            target.importUsers([author])
            author_login = author.login
        try:
            target.importAttachment(
                issue_id,
                attachment.filename,
                content,
                author_login,
                attachment.file_type,
                None,
                attachment.date_added)
        except YouTrackException:
            print("Failed to import attachment")
        except urllib2.HTTPError as e:
            msg = 'Failed to import attachment [%s] for issue [%s]. Exception: [%s]' % (attachment.filename, issue_id, str(e))
            if isinstance(msg, unicode):
                msg = msg.encode('utf-8')
            print(msg)


def is_prefix_of_any_other_tag(tag, other_tags):
    for t in other_tags:
        if t.startswith(tag) and (t != tag):
            return True
    return False


def import_tags(source, target, project_ids, collected_tags):
    tags_to_import_now = set([])
    tags_to_import_after = set([])
    for tag in collected_tags:
        if is_prefix_of_any_other_tag(tag, collected_tags):
            tags_to_import_after.add(tag)
        else:
            tags_to_import_now.add(tag)
    max = 100
    for project_id in project_ids:
        go_on = True
        after = 0
        while go_on:
            issues = source.get_mantis_issues(project_id, after, max)
            go_on = False
            for issue in issues:
                go_on = True
                issue_id = issue['id']
                issue_tags = source.get_issue_tags_by_id(issue_id)
                for tag in issue_tags:
                    if tag in tags_to_import_now:
                        try:
                            target.executeCommand("%s-%s" % (project_id, issue_id), "tag " + tag)
                        except YouTrackException:
                            pass
            after += max
    if len(tags_to_import_after):
        import_tags(source, target, project_ids, tags_to_import_after)


def mantis2youtrack(target_url, target_login, target_pass, mantis_db_name, mantis_db_host, mantis_db_port,
                    mantis_db_login, mantis_db_pass, mantis_project_names):
    print("target_url             : " + target_url)
    print("target_login           : " + target_login)
    print("target_pass            : " + target_pass)
    print("mantis_db_name         : " + mantis_db_name)
    print("mantis_db_host         : " + mantis_db_host)
    print("mantis_db_port         : " + mantis_db_port)
    print("mantis_db_login        : " + mantis_db_login)
    print("mantis_db_pass         : " + mantis_db_pass)
    print("mantis_project_names   : " + repr(mantis_project_names))

    #connacting to yt
    target = Connection(target_url, target_login, target_pass)
    #connacting to mantis
    client = MantisClient(mantis_db_host, int(mantis_db_port), mantis_db_login,
                          mantis_db_pass, mantis_db_name, youtrackutils.mantis.CHARSET, youtrackutils.mantis.BATCH_SUBPROJECTS)
    if not len(mantis_project_names):
        print("You should declarer at least one project to import")
        sys.exit()

    print("Creating custom fields definitions")
    create_yt_custom_field(target, u"priority")
    create_yt_custom_field(target, u"severity")
    create_yt_custom_field(target, u"category_id")
    create_yt_custom_field(target, u"version", "1")
    create_yt_custom_field(target, u"fixed_in_version", "1")
    create_yt_custom_field(target, u"build", "1")
    create_yt_custom_field(target, u"platform")
    create_yt_custom_field(target, u"os")
    create_yt_custom_field(target, u"os_build")
    create_yt_custom_field(target, u"due_date")
    create_yt_custom_field(target, u"Reproducibility")
    create_yt_custom_field(target, u"target_version", u'1')
    create_yt_custom_field(target, u"status")
    create_yt_custom_field(target, u"resolution")
    create_yt_custom_field(target, u'project_id', u'1')

    # adding some custom fields that are predefined in mantis
    project_ids = []
    for name in mantis_project_names:
        pid = client.get_project_id_by_name(name)
        if pid is None:
            raise Exception("Cannot find project with name '%s'" % name)
        project_ids.append(pid)

    custom_fields = client.get_mantis_custom_fields(project_ids)

    for cf_def in custom_fields:
        print("Processing custom field [ %s ]" % cf_def.name.encode('utf-8'))
        process_mantis_custom_field(target, cf_def)

    print("Creating custom fields definitions finished")

    issue_tags = set([])
    for name in mantis_project_names:
        project_id = str(client.get_project_id_by_name(name))
        name = name.replace("/", " ")
        print("Creating project [ %s ] with name [ %s ]" % (project_id, name))
        try:
            target.getProject(project_id)
        except YouTrackException:
            target.createProjectDetailed(project_id, name, client.get_project_description(project_id),
                target_login)

        print("Importing components to project [ %s ]" % project_id)
        add_values_to_fields(target, project_id, u"category_id",
            client.get_mantis_categories(project_id),
            lambda component, yt_bundle, value_mapping:
            to_yt_subsystem(component, yt_bundle, value_mapping))
        print("Importing components to project [ %s ] finished" % project_id)

        print("Importing versions to project [ %s ]" % project_id)
        mantis_versions = client.get_mantis_versions(project_id)
        add_values_to_fields(target, project_id, u"version", mantis_versions,
            lambda version, yt_bundle, value_mapping:
            to_yt_version(version, yt_bundle, value_mapping))

        add_values_to_fields(target, project_id, u"fixed_in_version",
            mantis_versions,
            lambda version, yt_bundle, value_mapping:
            to_yt_version(version, yt_bundle, value_mapping))

        print("Importing versions to project [ %s ] finished" % project_id)

        print("Attaching custom fields to project [ %s ]" % project_id)
        cf_ids = client.get_custom_fields_attached_to_project(project_id)

        for cf in custom_fields:
            if cf.field_id in cf_ids:
                attach_field_to_project(target, project_id, cf.name)

        print("Attaching custom fields to project [ %s ] finished" % project_id)

        print("Importing issues to project [ %s ]" % project_id)
        max_count = 100
        after = 0
        go_on = True
        while go_on:
            go_on = False
            mantis_issues = client.get_mantis_issues(project_id, after, max_count)
            after += max_count
            if len(mantis_issues):
                go_on = True
                target.importIssues(project_id, name + " Assignees",
                    [to_yt_issue(issue, project_id, target) for issue in mantis_issues])

                # import attachments
                for issue in mantis_issues:
                    issue_attachments = client.get_attachments(issue['id'])
                    issue_id = "%s-%s" % (project_id, issue['id'])
                    import_attachments(issue_attachments, issue_id, target)
                    issue_tags |= set(client.get_issue_tags_by_id(issue['id']))

        print("Importing issues to project [ %s ] finished" % project_id)

    import_tags(client, target, project_ids, issue_tags)

    print("Importing issue links")
    go_on = True
    after = 0
    max_count = 200
    while go_on:
        go_on = False
        mantis_issue_links = client.get_issue_links(after, max_count)
        yt_issue_links = []
        for link in mantis_issue_links:
            go_on = True
            print("Processing issue link for source issue [ %s ]" % str(link.source))
            yt_issue_links.append(to_yt_link(link))
        after += max_count
        print(target.importLinks(yt_issue_links))

    print("Importing issue links finished")

if __name__ == "__main__":
    main()
