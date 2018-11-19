import MySQLdb
import MySQLdb.cursors
from youtrackutils.mantis import *


class MantisClient(object):
    def __init__(self, host, port, login, password, db_name, charset_name, batch_subprojects):
        self.batch_subprojects = batch_subprojects
        self.sql_cnx = MySQLdb.connect(host=host, port=port, user=login, passwd=password,
            db=db_name, cursorclass=MySQLdb.cursors.DictCursor, charset=charset_name)


    def get_project_id_by_name(self, project_name):
        cursor = self.sql_cnx.cursor()
        id_row = "id"
        name_row = "name"
        request = "SELECT %s, %s FROM mantis_project_table" % (id_row, name_row,)
        cursor.execute(request)
        for row in cursor:
            if row[name_row].encode('utf8').strip() == project_name:
                return row[id_row]

    def _to_user(self, row):
        user = MantisUser(row["username"].replace(" ", "_"))
        user.real_name = row["realname"]
        user.email = row["email"]
        return user

    def get_mantis_categories(self, project_id):
        cursor = self.sql_cnx.cursor()
        project_ids_string = repr(self._calculate_project_ids(project_id)).replace('[', '(').replace(']', ')')
        name_row = "name"
        user_id_row = "user_id"
        request = "SELECT %s, %s FROM mantis_category_table WHERE project_id IN %s" % (
        user_id_row, name_row, project_ids_string)
        cursor.execute(request)
        result = []
        for row in cursor:
            category = MantisCategory(row[name_row])
            user_id = row[user_id_row]
            if user_id:
                category.assignee = self.get_user_by_id(user_id)
            result.append(category)
        return result

    def get_mantis_versions(self, project_id):
        cursor = self.sql_cnx.cursor()
        project_ids_string = repr(self._calculate_project_ids(project_id)).replace('[', '(').replace(']', ')')
        version_row = "version"
        released_row = "released"
        obsolete_row = "obsolete"
        date_order = "date_order"
        request = "SELECT %s, %s, %s, %s FROM mantis_project_version_table " % (
        version_row, released_row, obsolete_row, date_order)
        request += "WHERE project_id IN %s" % project_ids_string
        cursor.execute(request)
        result = []
        for row in cursor:
            version = MantisVersion(row[version_row])
            version.is_released = (row[released_row] > 0)
            version.is_obsolete = (row[obsolete_row] > 0)
            version.release_date = self._to_epoch_time(row[date_order])
            result.append(version)
        return result

    def get_mantis_custom_fields(self, project_ids):
        cursor = self.sql_cnx.cursor()
        ids = set([])
        for project_id in project_ids:
            ids = ids | set(self._calculate_project_ids(project_id))
        project_ids_string = repr(list(ids)).replace('[', '(').replace(']', ')')
        cf_ids_request = "SELECT DISTINCT field_id FROM mantis_custom_field_project_table WHERE project_id IN " + project_ids_string
        id_row = "id"
        type_row = "type"
        name_row = "name"
        default_value_row = "default_value"
        possible_values_row = "possible_values"
        request = "SELECT %s, %s, %s, %s, %s " % (id_row, name_row, type_row, possible_values_row, default_value_row)
        request += "FROM mantis_custom_field_table WHERE %s IN (%s)" % (id_row, cf_ids_request)
        cursor.execute(request)
        result = []
        for row in cursor:
            cf = MantisCustomFieldDef(row[id_row])
            cf.type = row[type_row]
            cf.name = row[name_row]
            cf.default_value = row[default_value_row]
            if row[type_row] in [3, 6, 7, 9, 5]:
                # possible values
                values = row[possible_values_row].split("|")
                cf.values = []
                for v in values:
                    v = v.strip()
                    if v != "":
                        cf.values.append(v)
            result.append(cf)
        return result

    def get_custom_fields_attached_to_project(self, project_id):
        cursor = self.sql_cnx.cursor()
        project_ids = (repr(self._calculate_project_ids(project_id)).replace('[', '(').replace(']', ')'))
        field_id_row = "field_id"
        request = "SELECT DISTINCT %s FROM mantis_custom_field_project_table WHERE project_id IN %s" % (
        field_id_row, project_ids)
        cursor.execute(request)
        result = []
        for row in cursor:
            result.append(row[field_id_row])
        return result


    def get_mantis_issues(self, project_id, after, max):
        cursor = self.sql_cnx.cursor()
        project_ids = (repr(self._calculate_project_ids(project_id)).replace('[', '(').replace(']', ')'))
        id_row = "id"
        project_id_row = "project_id"
        reporter_id_row = "reporter_id"
        handler_id_row = "handler_id"
        bug_text_id_row = "bug_text_id"
        category_id_row = "category_id"
        date_submitted_row = "date_submitted"
        due_date_row = "due_date"
        last_updated_row = "last_updated"

        rows_to_retrieve = [id_row, project_id_row, reporter_id_row, handler_id_row, bug_text_id_row, "summary",
                            category_id_row, date_submitted_row, due_date_row, last_updated_row, "priority", "severity",
                            "reproducibility", "status", "resolution", "os_build", "os", "platform", "version",
                            "fixed_in_version", "build", "target_version"]



        request = "SELECT %s FROM mantis_bug_table WHERE project_id IN %s LIMIT %d OFFSET %d" % (
            ", ".join(rows_to_retrieve), project_ids, max, after)
        cursor.execute(request)
        result = []
        for row in cursor:
            row[id_row] = str(row[id_row])
            row[reporter_id_row] = self.get_user_by_id(row[reporter_id_row])
            row[handler_id_row] = self.get_user_by_id(row[handler_id_row])

            row.update(self._get_text_fields(row[bug_text_id_row]))
            row[bug_text_id_row] = None

            row[project_id_row] = self._get_project_name_by_id(row[project_id_row])
            row[category_id_row] = self._get_category_by_id(row[category_id_row])

            row[date_submitted_row] = self._to_epoch_time(row[date_submitted_row])
            row[due_date_row] = self._to_epoch_time(row[due_date_row])
            row[last_updated_row] = self._to_epoch_time(row[last_updated_row])

            row.update(self._get_cf_values(row[id_row]))

            row["comments"] = self._get_comments_by_id(row[id_row])

            result.append(row)
        return result

    def get_mantis_subprojects(self, project_id):
        cursor = self.sql_cnx.cursor()
        project_ids = (repr(self._calculate_project_ids(project_id)).replace('[', '(').replace(']', ')'))
        name_row = "name"
        request = "SELECT %s FROM mantis_project_table WHERE id IN %s" % (name_row, project_ids)
        cursor.execute(request)
        result = []
        for row in cursor:
            result.append(row[name_row])
        return result

    def _get_cf_values(self, bug_id):
        result = {}
        cf_cursor = self.sql_cnx.cursor()
        cf_cursor.execute("SELECT field_id, value FROM mantis_custom_field_string_table WHERE bug_id=%s",
            (bug_id,))
        for row in cf_cursor:
            issue_cf = self._get_cf_name_by_id(row["field_id"])
            value = row["value"]
            cf_name = issue_cf["name"]
            if issue_cf["type"] in [3, 6, 7, 9, 5]:
                values = value.split("|")
                result[cf_name] = []
                for v in values:
                    v = v.strip()
                    if v != "":
                        result[cf_name].append(v)
            elif issue_cf["type"] == 8:
                result[cf_name] = self._to_epoch_time(value) if len(value) else ""
            else:
                result[cf_name] = value
        return result

    def get_issue_links(self, after, max):
        cursor = self.sql_cnx.cursor()
        result = []
        cursor.execute("SELECT * FROM mantis_bug_relationship_table LIMIT %d OFFSET %d" % (max, after))
        for row in cursor:
            source_bug_id = row["source_bug_id"]
            target_bug_id = row["destination_bug_id"]
            link = MantisIssueLink(source_bug_id, target_bug_id, row["relationship_type"])
            link.source_project_id = self._get_project_id_by_bug_id(source_bug_id)
            link.target_project_id = self._get_project_id_by_bug_id(target_bug_id)
            result.append(link)
        return result

    def get_attachments(self, bug_id):
        cursor = self.sql_cnx.cursor()
        id_row = "id"
        title_row = "title"
        filename_row = "filename"
        file_type_row = "file_type"
        content_row = "content"
        user_id_row = "user_id"
        date_added_row = "date_added"
        diskfile_row = "diskfile"
        folder_row = "folder"
        rows_to_get = [id_row, title_row, diskfile_row, folder_row, filename_row, file_type_row, content_row, user_id_row, date_added_row]
        request = "SELECT %s FROM mantis_bug_file_table WHERE bug_id=%s" % (", ".join(rows_to_get), bug_id)
        cursor.execute(request)
        result = []
        for row in cursor:
            attachment = MantisAttachment(row[id_row])
            attachment.title = row[title_row]
            attachment.filename = row[filename_row]
            attachment.file_type = row[file_type_row]
            attachment.author = self.get_user_by_id(row[user_id_row])
            attachment.date_added = self._to_epoch_time(row[date_added_row])
            if row[content_row] and not row[diskfile_row]:
                attachment.content = row[content_row]
            else:
                file_path = row[folder_row].rstrip("/") + "/" + row[diskfile_row]
                with open(file_path.encode('utf-8')) as f:
                    attachment.content = f.read()
            result.append(attachment)
        return result

    def get_project_description(self, project_id):
        cursor = self.sql_cnx.cursor()
        description_row = "description"
        cursor.execute("SELECT %s FROM mantis_project_table WHERE id=%s LIMIT 1", (description_row, project_id))
        description = cursor.fetchone()[description_row]
        if description is None:
            return "empty description"
        return description.encode('utf8')

    def get_user_by_id(self, id):
        if id:
            cursor = self.sql_cnx.cursor()
            request = "SELECT * FROM mantis_user_table WHERE id=%s LIMIT 1" %  str(id)
            cursor.execute(request)
            element = cursor.fetchone()
            if element is not None:
                return self._to_user(element)
        return None

    def _calculate_project_ids(self, project_id):
        result = [int(project_id)]
        if self.batch_subprojects:
            result.extend(self._get_child_projects_by_project_id(project_id))
        # TODO: Why do we add projectid=0? Invesigate it!
        #result.append(int(0))
        return result

    def _get_child_projects_by_project_id(self, id):
        cursor = self.sql_cnx.cursor()
        child_id_row = "child_id"
        request = "SELECT %s FROM mantis_project_hierarchy_table h\
                   WHERE parent_id = %s AND EXISTS (\
                     SELECT * FROM mantis_project_table p WHERE p.id = h.%s)" % (child_id_row, id, child_id_row)
        cursor.execute(request)
        result = []
        for row in cursor:
            result.append(int(row[child_id_row]))
            result.extend(self._get_child_projects_by_project_id(row[child_id_row]))
        return result


    def _get_text_fields(self, text_id):
        cursor = self.sql_cnx.cursor()
        description_row = "description"
        steps_row = "steps_to_reproduce"
        additional_row = "additional_information"
        request = "SELECT %s, %s, %s " % (description_row, steps_row, additional_row)
        request += "FROM mantis_bug_text_table WHERE id=%s LIMIT 1" % str(text_id)
        cursor.execute(request)
        row = cursor.fetchone()
        description = row[description_row]
        if (row[steps_row] is not None) and len(row[steps_row]):
            description += "\n Steps to reproduce : \n" + row[steps_row]
        if (row[additional_row] is not None) and len(row[additional_row]):
            description += "\n Steps to reproduce : \n" + row[additional_row]
        return {"description" : description}

    def _get_category_by_id(self, id):
        cursor = self.sql_cnx.cursor()
        name_row = "name"
        request = "SELECT %s FROM mantis_category_table WHERE id=%s LIMIT 1" % (name_row, str(id))
        cursor.execute(request)
        category = cursor.fetchone()
        if category is None:
            return None
        else:
            return category[name_row]

    def _get_comments_by_id(self, id):
        cursor = self.sql_cnx.cursor()
        reporter_id_row = "reporter_id"
        bugnote_row = "bugnote_text_id"
        date_submitted_row = "date_submitted"
        request = "SELECT %s, %s, %s" % (reporter_id_row, bugnote_row, date_submitted_row)
        request += " FROM mantis_bugnote_table WHERE bug_id=%s" % str(id)
        cursor.execute(request)
        result = []
        for row in cursor:
            text_cursor = self.sql_cnx.cursor()
            note_row = "note"
            req = "SELECT %s FROM mantis_bugnote_text_table WHERE id=%s LIMIT 1" % (note_row, str(row[bugnote_row]))
            text_cursor.execute(req)
            comment = MantisComment()
            comment.reporter = self.get_user_by_id(row[reporter_id_row])
            comment.date_submitted = self._to_epoch_time(row[date_submitted_row])
            comment.text = text_cursor.fetchone()[note_row]
            result.append(comment)
        return result

    def _get_project_id_by_bug_id(self, bug_id):
        cursor = self.sql_cnx.cursor()
        project_id_row = "project_id"
        request = "SELECT %s FROM mantis_bug_table WHERE id=%s LIMIT 1" % (project_id_row, bug_id)
        cursor.execute(request)
        return cursor.fetchone()[project_id_row]


    def _get_cf_name_by_id(self, id):
        cursor = self.sql_cnx.cursor()
        cursor.execute("SELECT name, type  FROM mantis_custom_field_table WHERE id=%s LIMIT 1", (str(id),))
        return cursor.fetchone()

    def _get_project_name_by_id(self, id):
        cursor = self.sql_cnx.cursor()
        name_row = "name"
        request = "SELECT %s FROM mantis_project_table WHERE id=%s LIMIT 1" % (name_row, str(id))
        cursor.execute(request)
        return cursor.fetchone()[name_row]

    def get_issue_tags_by_id(self, id):
        cursor = self.sql_cnx.cursor()
        name_row = "name"
        request = "SELECT %s FROM mantis_tag_table WHERE id IN (SELECT tag_id FROM mantis_bug_tag_table WHERE bug_id = %s) LIMIT 1" % (
        name_row, str(id))
        cursor.execute(request)
        return [row[name_row] for row in cursor]

    def _to_epoch_time(self, time):
        if time is None:
            return ""
        if isinstance(time, long):
            return str(time * 1000)
        if len(time):
            return str(int(time) * 1000)
        return ""
