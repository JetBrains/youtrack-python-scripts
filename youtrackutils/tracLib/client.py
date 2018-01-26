from trac.env import Environment
from trac.attachment import Attachment
from youtrackutils.tracLib import *
from ConfigParser import ConfigParser
from youtrackutils import tracLib
from youtrackutils.tracLib import timetracking


class Client(object):
    def __init__(self, env_path):
        self.env_path = env_path
        self.env = Environment(env_path)
        self.db_cnx = self.env.get_db_cnx()
        self._registered_users_logins = []
        self._timetracking_plugins = self._get_timetracking_plugins()

    def _get_timetracking_plugins(self):
        plugins = {}
        if tracLib.SUPPORT_TIME_TRACKING == 'auto':
            for plugin in tracLib.timetracking.plugins:
                plugin_name = plugin.get_name()
                for com_name, com_enabled in self.env._component_rules.items():
                    if com_name.startswith(plugin_name) and com_enabled and plugin_name not in plugins:
                        plugins[plugin_name] = plugin(self.env)
        else:
            for plugin in tracLib.timetracking.plugins:
                plugin_name = plugin.get_name()
                if plugin_name == tracLib.SUPPORT_TIME_TRACKING:
                    plugins[plugin_name] = plugin(self.env)
                    break;
        for plugin_name in plugins.keys():
            print "Plugin '%s' will be used to get workitems." % plugin_name
        return plugins.values()

    def get_project_description(self):
        return self.env.project_description

    def get_users(self):
        result = self.env.get_known_users()
        trac_users = list([])
        for user in result:
            user_login = user[0].lower()
            if user_login in self._registered_users_logins:
                continue
            u = TracUser(user_login)
            u.email = user[2]
            trac_users.append(u)
            self._registered_users_logins.append(user_login)
        # if we accept only authorised users, we don't have any more users to return
        # all of them were returned by "get_known_users" method
        if not tracLib.ACCEPT_NON_AUTHORISED_USERS:
            return trac_users
        # here we must to get component owners, issue reporters, owners and attachment authors
        # that are not registered users
        user_fields = [("owner", "component"), ("reporter", "ticket"), ("owner", "ticket"), ("author", "attachment")]
        first = True
        request = ""
        for column_name, table_name in user_fields :
            if first:
                first = False
            else:
                request += "UNION "
            request += "SELECT DISTINCT lower(%s) FROM %s " % (column_name, table_name)
        cursor = self.db_cnx.cursor()
        cursor.execute(request)
        for row in cursor:
            if row[0] not in self._registered_users_logins:
                trac_user = self._get_non_authorised_user(row[0])
                if trac_user is not None :
                    trac_users.append(trac_user)
                    self._registered_users_logins.append(trac_user.name)
        return trac_users

    def _get_non_authorised_user(self, user_name):
        if user_name is None :
            return None
        # non authorized users in trac are stored like this "name <email_address>"
        start = user_name.find("<")
        end = user_name.rfind(">")
        # we don't accept users who didn't leave the email
        if (start > -1) and (end > start + 1):
            if user_name.find("@", start, end) > 0:
                user = TracUser(user_name[start + 1 : end].replace(" ", "_"))
                user.email = user_name[start + 1 : end].replace(" ", "_")
                return user
        return None

    def _get_user_login(self, user_name):
        if user_name is None:
            return None
        if user_name in self._registered_users_logins:
            return user_name
        if not tracLib.ACCEPT_NON_AUTHORISED_USERS:
            return None
        user = self._get_non_authorised_user(user_name)
        if (user is None) or (user.name not in self._registered_users_logins) :
            return None
        return user.name

    def get_severities(self):
        return self._get_data_from_enum("severity")

    def get_issue_types(self):
        return self._get_data_from_enum("ticket_type")

    def get_issue_priorities(self):
        return self._get_data_from_enum("priority")

    def get_issue_resolutions(self):
        return [TracResolution(name) for name in self._get_data_from_enum("resolution")]

    def get_components(self):
        cursor = self.db_cnx.cursor()
        cursor.execute("SELECT name, owner, description FROM component")
        trac_components = list([])
        for row in cursor:
            component = TracComponent(row[0])
            component.owner = self._get_user_login(component.owner)
            if row[2] is not None:
                component.description = row[2]
            trac_components.append(component)
        return trac_components

    def get_versions(self):
        cursor = self.db_cnx.cursor()
        cursor.execute("SELECT name, time, description FROM version")
        trac_versions = list([])
        for row in cursor:
            version = TracVersion(row[0])
            if row[1]:
                version.time = to_unix_time(row[1])
            if row[2] is not None:
                version.description = row[2]
            trac_versions.append(version)
        return trac_versions

    def get_milestones(self):
        cursor = self.db_cnx.cursor()
        cursor.execute("SELECT name, completed, description FROM milestone")
        trac_milestones = list([])
        for row in cursor:
            version = TracMilestone(row[0])
            if row[1]:
                version.time = to_unix_time(row[1])
            if row[2] is not None:
                version.description = row[2]
            trac_milestones.append(version)
        return trac_milestones

    def get_issues(self):
        cursor = self.db_cnx.cursor()
        cursor.execute("SELECT id, type, time, changetime, component, severity, priority, owner, reporter,"
                       "cc, version, milestone, status, resolution, summary, description, keywords FROM ticket")
        trac_issues = list([])
        for row in cursor:
            issue = TracIssue(row[0])
            issue.time = to_unix_time(row[2])
            issue.changetime = to_unix_time(row[3])
            issue.reporter = self._get_user_login(row[8])
            if row[9] is not None:
                cc = row[9].split(",")
                for c in cc:
                    if len(c) > 0:
                        cc_name = self._get_user_login(c.strip())
                        if cc_name is not None:
                            issue.cc.add(cc_name)
            issue.summary = row[14]
            issue.description = row[15]
            issue.custom_fields["Type"] = row[1]
            issue.custom_fields["Component"] = row[4]
            issue.custom_fields["Severity"] = row[5]
            issue.custom_fields["Priority"] = row[6]
            issue.custom_fields["Owner"] = self._get_user_login(row[7])
            issue.custom_fields["Version"] = row[10]
            issue.custom_fields["Milestone"] = row[11]
            issue.custom_fields["Status"] = row[12]
            issue.custom_fields["Resolution"] = row[13]
            if row[16] is not None:
                keywords = row[16].rsplit(",")
                for kw in keywords:
                    if len(kw) > 0:
                        issue.keywords.add(kw.strip())
            #getting custom fields from ticket_custom table
            custom_field_cursor = self.db_cnx.cursor()
            custom_field_cursor.execute("SELECT name, value FROM ticket_custom WHERE ticket=%s", (str(row[0]),))
            for cf in custom_field_cursor:
                issue.custom_fields[cf[0].capitalize()] = cf[1]
            # getting attachments from attachment table
            attachment_cursor = self.db_cnx.cursor()
            attachment_cursor.execute("SELECT filename, size, time, description, author FROM attachment WHERE "
                                      "type = %s AND id = %s", ("ticket", str(issue.id)))
            #path = self.env_path + "/attachments/ticket/" + str(issue.id) + "/"
            for elem in attachment_cursor:
                #at = TracAttachment(path + elem[0])
                at = TracAttachment(Attachment._get_path(self.env.path, 'ticket', str(issue.id), elem[0]))
                at.name = elem[0]
                at.size = elem[1]
                at.time = to_unix_time(elem[2])
                at.description = elem[3]
                at.author_name = elem[4]
                issue.attachment.add(at)
            trac_issues.append(issue)
            #getting comments
            change_cursor = self.db_cnx.cursor()
            change_cursor.execute("SELECT time, author, newvalue, oldvalue FROM ticket_change WHERE ticket = %s AND field = %s ORDER BY time DESC", (str(row[0]), "comment",))
            for elem in change_cursor:
                if (elem[2] is None) or (not len(elem[2].lstrip())):
                    continue
                comment = TracComment(to_unix_time(elem[0]))
                comment.author = str(elem[1])
                comment.content = unicode(elem[2])
                comment.id = elem[3]
                issue.comments.add(comment)
            #getting workitems
            for ttp in self._timetracking_plugins:
                issue.workitems.update(set(ttp[row[0]]))
        return trac_issues


    def get_custom_fields_declared(self):
        ini_file_path = self.env_path + "/conf/trac.ini"
        parser = ConfigParser()
        parser.read(ini_file_path)
        if not("ticket-custom" in parser.sections()):
              return set([])
        result = parser.items("ticket-custom")
        items = dict([])
        for elem in result:
            items[elem[0]] = elem[1]

        keys = items.keys()
        custom_fields = list([])
        for k in keys:
            if not("." in k):
                field = TracCustomFieldDeclaration(k.capitalize())
                field.type = items[k]
                options_key = k + ".options"
                if options_key in items:
                    opts_str = items[options_key]
                    opts = opts_str.rsplit("|")
                    for o in opts:
                        field.options.append(o)
                value_key = k + ".value"
                if value_key in items:
                    field.value = items[value_key]
                label_key = k + ".label"
                if label_key in items:
                    field.label = items[label_key]
                custom_fields.append(field)

        return custom_fields

    def _get_data_from_enum(self, type_name):
        cursor = self.db_cnx.cursor()
        cursor.execute("SELECT name, value FROM enum WHERE type=%s", (type_name,))
        return [row[0] for row in cursor]
