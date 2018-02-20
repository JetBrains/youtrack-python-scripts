#! /usr/bin/env python

import sys

if sys.version_info >= (3, 0):
    print("\nThe script doesn't support python 3. Please use python 2.7+\n")
    sys.exit(1)

import os
from youtrack.connection import Connection, youtrack, utf8encode
import traceback
from youtrack.sync.users import UserImporter
from youtrack.sync.links import LinkImporter
import re
import getopt
import datetime

convert_period_values = False
days_in_a_week = 5
hours_in_a_day = 8


def usage():
    print("""
Usage:
    %s [OPTIONS] s_url s_user s_pass t_url t_user t_pass [project_id ...]

    s_url         Source YouTrack URL
    s_user        Source YouTrack user
    s_pass        Source YouTrack user's password
    t_url         Target YouTrack URL
    t_user        Target YouTrack user
    t_pass        Target YouTrack user's password
    project_id    ProjectID to import

Options:
    -h,  Show this help and exit
    -a,  Import attachments only
    -n,  Create new issues instead of importing them
    -c,  Add new comments to target issues
    -f,  Sync custom field values
    -T,  Sync tags (tags will be created on behalf of logged in user)
    -r,  Replace old attachments with new ones (remove and re-import)
    -d,  Disable users caching
    -p,  Covert period values (used as workaroud for JT-19362)
    -t TIME_SETTINGS,
         Time Tracking settings in format "days_in_a_week:hours_in_a_day"
""" % os.path.basename(sys.argv[0]))


def main():
    global convert_period_values
    global days_in_a_week
    global hours_in_a_day
    attachments_only = False
    try:
        params = {}
        opts, args = getopt.getopt(sys.argv[1:], 'hanrcdfpt:T')
        for opt, val in opts:
            if opt == '-h':
                usage()
                sys.exit(0)
            if opt == '-p':
                convert_period_values = True
            elif opt == '-a':
                attachments_only = True
            elif opt == '-r':
                params['replace_attachments'] = True
            elif opt == '-c':
                params['add_new_comments'] = True
            elif opt == '-f':
                params['sync_custom_fields'] = True
            elif opt == '-d':
                params['enable_user_caching'] = False
            elif opt == '-n':
                params['create_new_issues'] = True
            elif opt == '-T':
                params['sync_tags'] = True
            elif opt == '-t':
                if ':' in val:
                    d, h = val.split(':')
                    if d:
                        days_in_a_week = int(d)
                    if h:
                        hours_in_a_day = int(h)
                else:
                    days_in_a_week = int(val)
        (source_url, source_login, source_password,
         target_url, target_login, target_password) = args[:6]
        project_ids = args[6:]
    except getopt.GetoptError as e:
        print(e)
        usage()
        sys.exit(1)
    except ValueError:
        print('Not enough arguments')
        usage()
        sys.exit(1)
    if attachments_only:
        import_attachments_only(source_url, source_login, source_password,
                                target_url, target_login, target_password,
                                project_ids, params=params)
    else:
        youtrack2youtrack(source_url, source_login, source_password,
                          target_url, target_login, target_password,
                          project_ids, params=params)


def create_bundle_from_bundle(source, target, bundle_name, bundle_type, user_importer):
    source_bundle = source.getBundle(bundle_type, bundle_name)
    # here we should check whether target YT has bundle with same name. But actually, to check tis, we should
    # get all bundles of every field type. So here we'll do a hack: just check if there is a bundle of bundle_type
    # type with this name, if there is bundle of another type -- there will be conflict, and we'll just exit with
    # corresponding message, as we can't proceed import anyway
    target_bundle_names = [bundle.name.strip() for bundle in target.getAllBundles(bundle_type)]
    if bundle_name in target_bundle_names:
        target_bundle = target.getBundle(bundle_type, bundle_name)
        if isinstance(source_bundle, youtrack.UserBundle):
            # get users and try to import them
            user_importer.importUsersRecursively(set(source_bundle.get_all_users()))
            # get field and calculate not existing groups
            target_bundle_group_names = [elem.name.capitalize() for elem in target_bundle.groups]
            groups_to_add = [group for group in source_bundle.groups if
                             group.name.capitalize() not in target_bundle_group_names]
            user_importer.importGroupsWithoutUsers(groups_to_add)
            for group in groups_to_add:
                target.addValueToBundle(target_bundle, group)
                # add individual users to bundle
            target_bundle_user_logins = [elem.login.capitalize() for elem in target_bundle.get_all_users()]
            users_to_add = [user for user in source_bundle.users if
                            user.login.capitalize() not in target_bundle_user_logins]
            for user in users_to_add:
                try:
                    target.addValueToBundle(target_bundle, user)
                except youtrack.YouTrackException as e:
                    if e.response.status != 409:
                        raise e
            return
        target_value_names = [utf8encode(element.name).capitalize() for element in target_bundle.values]
        for value in [elem for elem in source_bundle.values if
                      utf8encode(elem.name).strip().capitalize() not in target_value_names]:
            try:
                target.addValueToBundle(target_bundle, value)
            except youtrack.YouTrackException as e:
                if e.response.status != 409:
                    raise e
    else:
        users = set([])
        groups = []
        if isinstance(source_bundle, youtrack.UserBundle):
            groups = source_bundle.groups
            users = set(source_bundle.get_all_users())
        elif isinstance(source_bundle, youtrack.OwnedFieldBundle):
            users = set([source.getUser(elem.owner) for elem in source_bundle.values if elem.owner is not None])
        user_importer.importUsersRecursively(users)
        user_importer.importGroupsWithoutUsers(groups)
        print(target.createBundle(source_bundle))


def create_project_custom_field(target, field, project_id):
    params = dict([])
    if hasattr(field, "bundle"):
        params["bundle"] = field.bundle
    emptyFieldText = "No " + field.name.lower()
    if hasattr(field, "emptyFieldText"):
        emptyFieldText = field.emtyFieldText
    target.createProjectCustomFieldDetailed(project_id, field.name, emptyFieldText, params)


def create_project_stub(source, target, projectId, user_importer):
    project = source.getProject(projectId)

    print("Create project stub [" + project.name + "]")
    lead = source.getUser(project.lead)

    print("Create project lead [" + lead.login + "]")
    user_importer.importUser(lead)

    try:
        target.getProject(projectId)
    except youtrack.YouTrackException:
        target.createProject(project)

    return target.getProject(projectId)


def enable_time_tracking(source, target, project_id):
    dst_settings = target.getProjectTimeTrackingSettings(project_id)
    if dst_settings:
        f_est = None
        f_spent = None
        src_settings = source.getProjectTimeTrackingSettings(project_id)
        # If no settings available then there is YouTrack <= 4.2.1
        if src_settings:
            # Do not override existing field settings.
            if not (dst_settings.EstimateField or dst_settings.TimeSpentField):
                f_est = src_settings.EstimateField
                f_spent = src_settings.TimeSpentField
            if src_settings.Enabled:
                print("Enabling Time Tracking")
                target.setProjectTimeTrackingSettings(project_id, f_est, f_spent, True)
                # Sync work types
                for t in source.get_work_types(project_id):
                    target.create_project_work_type(project_id, work_type=t)
                return True
    return False


def period_to_minutes(value):
    minutes = 0
    for period in re.findall('\d+[wdhm]', value):
        punit = period[-1]
        pvalue = int(period[:-1])
        if punit == 'm':
            minutes += pvalue
        elif punit == 'h':
            minutes += pvalue * 60
        elif punit == 'd':
            minutes += pvalue * hours_in_a_day * 60
        elif punit == 'w':
            minutes += pvalue * days_in_a_week * hours_in_a_day * 60
    return str(minutes)


def create_issues(target, issues, last_issue_number):
    for issue in issues:
        summary = utf8encode(issue.summary)
        description = None
        if hasattr(issue, 'description'):
            description = utf8encode(issue.description)
        group = None
        if hasattr(issue, 'permittedGroup'):
            group = utf8encode(issue.permittedGroup)
        # This loop creates and then deletes issues that don't exist in source
        # database. In other words this loop creates holes in issue numeration.
        next_number = last_issue_number + 1
        number_gap = int(issue.numberInProject) - last_issue_number - 1
        for i in range(next_number, next_number + number_gap):
            print('Creating and deleting dummy issue #%s-%d' % (issue.projectShortName, i))
            target.createIssue(issue.projectShortName, None, 'dummy', None)
            target.deleteIssue('%s-%d' % (issue.projectShortName, i))
        try:
            print('Creating issue from source issue with id %s' % issue.id)
            target.createIssue(issue.projectShortName, None, summary, description, permittedGroup=group)
        except youtrack.YouTrackException as e:
            print('Cannot create issue from source issue with id %s' % issue.id)
            print(e)
        last_issue_number = int(issue.numberInProject)
    return last_issue_number


def youtrack2youtrack(source_url, source_login, source_password, target_url, target_login, target_password,
                      project_ids, query='', params=None):
    if not len(project_ids):
        print("You should sign at least one project to import")
        return
    if params is None:
        params = {}

    source = Connection(source_url, source_login, source_password)
    target = Connection(target_url, target_login, target_password)
    #, proxy_info = httplib2.ProxyInfo(socks.PROXY_TYPE_HTTP, 'localhost', 8888)

    print("Import issue link types")
    for ilt in source.getIssueLinkTypes():
        try:
            print(target.createIssueLinkType(ilt))
        except youtrack.YouTrackException as e:
            print(e.message)

    user_importer = UserImporter(source, target, caching_users=params.get('enable_user_caching', True))
    link_importer = LinkImporter(target)

    #create all projects with minimum info and project lead set
    created_projects = []
    for project_id in project_ids:
        created = create_project_stub(source, target, project_id, user_importer)
        created_projects.append(created)

    #save created project ids to create correct group roles afterwards
    user_importer.addCreatedProjects([project.id for project in created_projects])
    #import project leads with group they are included and roles assigned to these groups
    user_importer.importUsersRecursively([target.getUser(project.lead) for project in created_projects])
    #afterwards in a script any user import imply recursive import

    cf_names_to_import = set([]) # names of cf prototypes that should be imported
    for project_id in project_ids:
        cf_names_to_import.update([pcf.name.capitalize() for pcf in source.getProjectCustomFields(project_id)])

    target_cf_names = [pcf.name.capitalize() for pcf in target.getCustomFields()]

    period_cf_names = []

    for cf_name in cf_names_to_import:
        source_cf = source.getCustomField(cf_name)
        if source_cf.type.lower() == 'period':
            period_cf_names.append(source_cf.name.lower())

        print("Processing custom field '%s'" % utf8encode(cf_name))
        if cf_name in target_cf_names:
            target_cf = target.getCustomField(cf_name)
            if not(target_cf.type == source_cf.type):
                print("In your target and source YT instances you have field with name [ %s ]" % utf8encode(cf_name))
                print("They have different types. Source field type [ %s ]. Target field type [ %s ]" %
                      (source_cf.type, target_cf.type))
                print("exiting...")
                exit()
        else:
            if hasattr(source_cf, "defaultBundle"):
                create_bundle_from_bundle(source, target, source_cf.defaultBundle, source_cf.type, user_importer)
            target.createCustomField(source_cf)

    failed_commands = []

    for projectId in project_ids:
        source = Connection(source_url, source_login, source_password)
        target = Connection(target_url, target_login,
            target_password) #, proxy_info = httplib2.ProxyInfo(socks.PROXY_TYPE_HTTP, 'localhost', 8888)
        #reset connections to avoid disconnections
        user_importer.resetConnections(source, target)
        link_importer.resetConnections(target)

        # copy project, subsystems, versions
        project = source.getProject(projectId)

        link_importer.addAvailableIssuesFrom(projectId)
        project_custom_fields = source.getProjectCustomFields(projectId)
        # create bundles and additional values
        for pcf_ref in project_custom_fields:
            pcf = source.getProjectCustomField(projectId, pcf_ref.name)
            if hasattr(pcf, "bundle"):
                try:
                    create_bundle_from_bundle(source, target, pcf.bundle, source.getCustomField(pcf.name).type, user_importer)
                except youtrack.YouTrackException as e:
                    if e.response.status != 409:
                        raise e
                    else:
                        print(e)

        target_project_fields = [pcf.name.lower() for pcf in target.getProjectCustomFields(projectId)]
        for field in project_custom_fields:
            if field.name.lower() in target_project_fields:
                if hasattr(field, 'bundle'):
                    if field.bundle != target.getProjectCustomField(projectId, field.name).bundle:
                        target.deleteProjectCustomField(projectId, field.name)
                        create_project_custom_field(target, field, projectId)
            else:
                try:
                    create_project_custom_field(target, field, projectId)
                except youtrack.YouTrackException as e:
                    if e.response.status != 409:
                        raise e
                    else:
                        print(e)

        # copy issues
        start = 0
        max = 20

        sync_workitems = enable_time_tracking(source, target, projectId)
        tt_settings = target.getProjectTimeTrackingSettings(projectId)

        print("Import issues")
        last_created_issue_number = 0

        while True:
            try:
                print("Get issues from " + str(start) + " to " + str(start + max))
                issues = source.getIssues(projectId, query, start, max)

                if len(issues) <= 0:
                    break

                if convert_period_values and period_cf_names:
                    for issue in issues:
                        for pname in period_cf_names:
                            for fname in issue.__dict__:
                                if fname.lower() != pname:
                                    continue
                                issue[fname] = period_to_minutes(issue[fname])

                users = set([])

                for issue in issues:
                    print("Collect users for issue [%s]" % issue.id)

                    users.add(issue.getReporter())
                    if issue.hasAssignee():
                        if isinstance(issue.Assignee, (list, tuple)):
                            users.update(issue.getAssignee())
                        else:
                            users.add(issue.getAssignee())
                    # TODO: http://youtrack.jetbrains.net/issue/JT-6100
                    users.add(issue.getUpdater())
                    if issue.hasVoters():
                        users.update(issue.getVoters())
                    for comment in issue.getComments():
                        users.add(comment.getAuthor())

                    print("Collect links for issue [%s]" % issue.id)
                    link_importer.collectLinks(issue.getLinks(True))
                    # links.extend(issue.getLinks(True))

                    # fix problem with comment.text
                    for comment in issue.getComments():
                        if not hasattr(comment, "text") or (len(comment.text.strip()) == 0):
                            setattr(comment, 'text', 'no text')

                user_importer.importUsersRecursively(users)

                print("Create issues [" + str(len(issues)) + "]")
                if params.get('create_new_issues'):
                    create_issues(target, issues, last_created_issue_number)
                else:
                    print(target.importIssues(projectId, project.name + ' Assignees', issues))
                link_importer.addAvailableIssues(issues)

                for issue in issues:
                    try:
                        target_issue = target.getIssue(issue.id)
                    except youtrack.YouTrackException as e:
                        print("Cannot get target issue")
                        print(e)
                        continue

                    if params.get('sync_tags') and issue.tags:
                        try:
                            for tag in issue.tags:
                                tag = re.sub(r'[,&<>]', '_', tag)
                                try:
                                    target.executeCommand(issue.id, 'tag ' + tag, disable_notifications=True)
                                except youtrack.YouTrackException:
                                    tag = re.sub(r'[\s-]', '_', tag)
                                    target.executeCommand(issue.id, 'tag ' + tag, disable_notifications=True)
                        except youtrack.YouTrackException as e:
                            print("Cannot sync tags for issue " + issue.id)
                            print(e)

                    if params.get('add_new_comments'):
                        target_comments = dict()
                        max_id = 0
                        for c in target_issue.getComments():
                            target_comments[c.created] = c
                            if max_id < c.created:
                                max_id = c.created
                        for c in issue.getComments():
                            if c.created > max_id or c.created not in target_comments:
                                group = None
                                if hasattr(c, 'permittedGroup'):
                                    group = c.permittedGroup
                                try:
                                    target.executeCommand(issue.id, 'comment', c.text, group, c.author, disable_notifications=True)
                                except youtrack.YouTrackException as e:
                                    print('Cannot add comment to issue')
                                    print(e)

                    if params.get('sync_custom_fields'):
                        skip_fields = []
                        if tt_settings and tt_settings.Enabled and tt_settings.TimeSpentField:
                            skip_fields.append(tt_settings.TimeSpentField)
                        skip_fields = [name.lower() for name in skip_fields]
                        for pcf in [pcf for pcf in project_custom_fields if pcf.name.lower() not in skip_fields]:
                            target_cf_value = None
                            if pcf.name in target_issue:
                                target_cf_value = target_issue[pcf.name]
                                if isinstance(target_cf_value, (list, tuple)):
                                    target_cf_value = set(target_cf_value)
                                elif target_cf_value == target.getProjectCustomField(projectId, pcf.name).emptyText:
                                    target_cf_value = None
                            source_cf_value = None
                            if pcf.name in issue:
                                source_cf_value = issue[pcf.name]
                                if isinstance(source_cf_value, (list, tuple)):
                                    source_cf_value = set(source_cf_value)
                                elif source_cf_value == source.getProjectCustomField(projectId, pcf.name).emptyText:
                                    source_cf_value = None
                            if source_cf_value == target_cf_value:
                                continue
                            if isinstance(source_cf_value, set) or isinstance(target_cf_value, set):
                                if source_cf_value is None:
                                    source_cf_value = set([])
                                elif not isinstance(source_cf_value, set):
                                    source_cf_value = set([source_cf_value])
                                if target_cf_value is None:
                                    target_cf_value = set([])
                                elif not isinstance(target_cf_value, set):
                                    target_cf_value = set([target_cf_value])
                                for v in target_cf_value:
                                    if v not in source_cf_value:
                                        target.executeCommand(issue.id, 'remove %s %s' % (pcf.name, v), disable_notifications=True)
                                for v in source_cf_value:
                                    if v not in target_cf_value:
                                        target.executeCommand(issue.id, 'add %s %s' % (pcf.name, v), disable_notifications=True)
                            else:
                                if source_cf_value is None:
                                    source_cf_value = target.getProjectCustomField(projectId, pcf.name).emptyText
                                if pcf.type.lower() == 'date':
                                    m = re.match(r'(\d{10})(?:\d{3})?', str(source_cf_value))
                                    if m:
                                        source_cf_value = datetime.datetime.fromtimestamp(
                                            int(m.group(1))).strftime('%Y-%m-%d')
                                elif pcf.type.lower() == 'period':
                                    source_cf_value = '%sm' % source_cf_value
                                command = '%s %s' % (pcf.name, source_cf_value)
                                try:
                                    target.executeCommand(issue.id, command, disable_notifications=True)
                                except youtrack.YouTrackException as e:
                                    if e.response.status == 412 and e.response.reason.find('Precondition Failed') > -1:
                                        print('WARN: Some workflow blocks following command: %s' % command)
                                        failed_commands.append((issue.id, command))

                    if sync_workitems:
                        workitems = source.getWorkItems(issue.id)
                        if workitems:
                            existing_workitems = dict()
                            target_workitems = target.getWorkItems(issue.id)
                            if target_workitems:
                                for w in target_workitems:
                                    _id = '%s\n%s\n%s' % (w.date, w.authorLogin, w.duration)
                                    if hasattr(w, 'description'):
                                        _id += '\n%s' % w.description
                                    existing_workitems[_id] = w
                            new_workitems = []
                            for w in workitems:
                                _id = '%s\n%s\n%s' % (w.date, w.authorLogin, w.duration)
                                if hasattr(w, 'description'):
                                    _id += '\n%s' % w.description
                                if _id not in existing_workitems:
                                    new_workitems.append(w)
                            if new_workitems:
                                print("Process workitems for issue [ " + issue.id + "]")
                                try:
                                    user_importer.importUsersRecursively(
                                        [source.getUser(w.authorLogin)
                                         for w in new_workitems])
                                    target.importWorkItems(issue.id, new_workitems)
                                except youtrack.YouTrackException as e:
                                    if e.response.status == 404:
                                        print("WARN: Target YouTrack doesn't support workitems importing.")
                                        print("WARN: Workitems won't be imported.")
                                        sync_workitems = False
                                    else:
                                        print("ERROR: Skipping workitems because of error:" + str(e))

                    print("Process attachments for issue [%s]" % issue.id)
                    existing_attachments = dict()
                    try:
                        for a in target.getAttachments(issue.id):
                            existing_attachments[a.name + '\n' + a.created] = a
                    except youtrack.YouTrackException as e:
                        if e.response.status == 404:
                            print("Skip importing attachments because issue %s doesn't exist" % issue.id)
                            continue
                        raise e

                    attachments = []

                    users = set([])
                    for a in issue.getAttachments():
                        if a.name + '\n' + a.created in existing_attachments and not params.get('replace_attachments'):
                            a.name = utf8encode(a.name)
                            try:
                                print("Skip attachment '%s' (created: %s) because it's already exists"
                                      % (utf8encode(a.name), utf8encode(a.created)))
                            except Exception:
                                pass
                            continue
                        attachments.append(a)
                        author = a.getAuthor()
                        if author is not None:
                            users.add(author)
                    user_importer.importUsersRecursively(users)

                    for a in attachments:
                        print("Transfer attachment of " + utf8encode(issue.id) + ": " + utf8encode(a.name))
                        # TODO: add authorLogin to workaround http://youtrack.jetbrains.net/issue/JT-6082
                        # a.authorLogin = target_login
                        try:
                            target.createAttachmentFromAttachment(issue.id, a)
                        except BaseException as e:
                            print("Cant import attachment [ %s ]" % utf8encode(a.name))
                            print(repr(e))
                            continue
                        if params.get('replace_attachments'):
                            try:
                                old_attachment = existing_attachments.get(a.name + '\n' + a.created)
                                if old_attachment:
                                    print('Deleting old attachment')
                                    target.deleteAttachment(issue.id, old_attachment.id)
                            except BaseException as e:
                                print("Cannot delete attachment '%s' from issue %s" % (utf8encode(a.name), utf8encode(issue.id)))
                                print(e)

            except Exception as e:
                print('Cant process issues from ' + str(start) + ' to ' + str(start + max))
                traceback.print_exc()
                raise e

            start += max

    print("Import issue links")
    link_importer.importCollectedLinks()

    print("Trying to execute failed commands once again")
    for issue_id, command in failed_commands:
        try:
            print('Executing command on issue %s: %s' % (issue_id, command))
            target.executeCommand(issue_id, command, disable_notifications=True)
        except youtrack.YouTrackException as e:
            print('Failed to execute command for issue #%s: %s' % (issue_id, command))
            print(e)


def import_attachments_only(source_url, source_login, source_password,
                            target_url, target_login, target_password,
                            project_ids, params=None):
    if not project_ids:
        print('No projects to import. Exit...')
        return
    if params is None:
        params = {}
    start = 0
    max = 20
    source = Connection(source_url, source_login, source_password)
    target = Connection(target_url, target_login, target_password)
    user_importer = UserImporter(source, target, caching_users=params.get('enable_user_caching', True))
    for projectId in project_ids:
        while True:
            try:
                print('Get issues from %d to %d' % (start, start + max))
                issues = source.getIssues(projectId, '', start, max)
                if len(issues) <= 0:
                    break
                for issue in issues:
                    print('Process attachments for issue %s' % issue.id)
                    existing_attachments = dict()
                    try:
                        for a in target.getAttachments(issue.id):
                            existing_attachments[a.name + '\n' + a.created] = a
                    except youtrack.YouTrackException as e:
                        if e.response.status == 404:
                            print("Skip importing attachments because issue %s doesn't exist" % issue.id)
                            continue
                        raise e

                    attachments = []

                    users = set([])
                    for a in issue.getAttachments():
                        if a.name + '\n' + a.created in existing_attachments and not params.get('replace_attachments'):
                            print("Skip attachment '%s' (created: %s) because it's already exists" %
                                  (utf8encode(a.name), utf8encode(a.created)))
                            continue
                        attachments.append(a)
                        author = a.getAuthor()
                        if author is not None:
                            users.add(author)
                    user_importer.importUsersRecursively(users)

                    for a in attachments:
                        print('Transfer attachment of %s: %s' % (utf8encode(issue.id), utf8encode(a.name)))
                        try:
                            target.createAttachmentFromAttachment(issue.id, a)
                        except BaseException as e:
                            print('Cannot import attachment [ %s ]' % utf8encode(a.name))
                            print(repr(e))
                            continue
                        if params.get('replace_attachments'):
                            try:
                                old_attachment = existing_attachments.get(a.name + '\n' + a.created)
                                if old_attachment:
                                    print('Deleting old attachment')
                                    target.deleteAttachment(issue.id, old_attachment.id)
                            except BaseException as e:
                                print("Cannot delete attachment '%s' from issue %s" % (utf8encode(a.name), utf8encode(issue.id)))
                                print(e)
            except Exception as e:
                print('Cannot process issues from %d to %d' % (start, start + max))
                traceback.print_exc()
                raise e
            start += max


if __name__ == "__main__":
    main()
