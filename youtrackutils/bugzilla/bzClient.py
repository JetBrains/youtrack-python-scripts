import MySQLdb
import MySQLdb.cursors
from youtrackutils.bugzilla import *
import time
from youtrackutils import bugzilla


class Client(object):
    def __init__(self, host, port, login, password, db_name="bugs"):
        self.sql_cnx = MySQLdb.connect(host=host, port=port, user=login, passwd=password,
                                       db=db_name, cursorclass=MySQLdb.cursors.DictCursor, charset=bugzilla.BZ_DB_CHARSET)
        self.db_host = "%s:%s/" % (host, str(port))

    def get_project_description(self, product_id):
        cursor = self.sql_cnx.cursor()
        description_row = "description"
        request = "SELECT %s FROM products WHERE id = %s" % (description_row, product_id)
        cursor.execute(request)
        desc = cursor.fetchone()[description_row].encode('utf8')
        return desc

    def get_components(self, product_id):
        cursor = self.sql_cnx.cursor()
        request = "SELECT * FROM components WHERE product_id = %s" % product_id
        cursor.execute(request)
        result = list([])
        for row in cursor :
            cmp = BzComponent(row["id"])
            cmp.description = row["description"]
            cmp.initial_owner = self.get_user_by_id(row["initialowner"])
            cmp.name = row["name"]
            result.append(cmp)
        return result

    def get_versions(self, product_id):
        cursor = self.sql_cnx.cursor()
        id_row = 'id'
        value_row = 'value'
        request = "SELECT %s, %s FROM versions WHERE product_id = %s" % (id_row, value_row, product_id)
        cursor.execute(request)
        result = list([])
        for row in cursor:
            version = BzVersion(row[id_row])
            version.value = row[value_row]
            result.append(version)
        return result

    def get_custom_fields(self):
        cursor = self.sql_cnx.cursor()
        name_row = 'name'
        type_row = 'type'
        request = "SELECT %s, %s FROM fielddefs WHERE (custom = 1) AND NOT (type = 6)" % (name_row, type_row)
        cursor.execute(request)
        result = list([])
        for row in cursor:
            cf = BzCustomField(row[name_row][3:])
            cf.type = str(row[type_row])
            if cf.type in ["2", "3"]:
                values_cursor = self.sql_cnx.cursor()
                value_row = 'value'
                request = "SELECT %s FROM %s" % (value_row, row[name_row])
                values_cursor.execute(request)
                for v in values_cursor:
                    value = v[value_row]
                    if value != "---":
                        cf.values.append(value)
            result.append(cf)
        return result

    def get_issue_link_types(self):
        cursor = self.sql_cnx.cursor()
        name_row = 'name'
        description_row = 'description'
        request = "SELECT %s, %s FROM fielddefs WHERE (custom = 1) AND (type = 6)" % (name_row, description_row)
        cursor.execute(request)
        result = list([])
        for row in cursor:
            link_type = BzIssueLinkType(row[name_row][3:])
            link_type.description = row[description_row].encode('utf8')
            result.append(link_type)
        return result

    def get_issue_links(self):
        link_types = self.get_issue_link_types()
        result = set([])
        if not len(link_types):
            return result
        request = "SELECT bug_id, product_id, "
        for elem in link_types:
            request = request + "cf_" + elem.name + ", "
        request = request[:-2]
        request += " FROM bugs"
        cursor = self.sql_cnx.cursor()
        cursor.execute(request)
        for row in cursor:
            bug_id = row['bug_id']
            for type in link_types:
                target = row["cf_" + type.name]
                if target is not None:
                    link = BzIssueLink(type.name, str(bug_id), str(target))
                    link.source_product_id = str(row["product_id"])
                    link.target_product_id = str(self._get_product_id_by_bug_id(target))
                    result.add(link)
        return result

    def _get_component_by_id(self, component_id):
        cursor = self.sql_cnx.cursor()
        name_row = 'name'
        request = "SELECT %s FROM components WHERE id = %s" % (name_row, component_id)
        cursor.execute(request)
        result = cursor.fetchone()
        if result is None:
            return "No subsystem"
        else:
            return result[name_row]

    def get_issues(self, product_id, from_id, to_id):
        component_row = "component_id"
        user_rows = ["assigned_to", "qa_contact", "reporter"]

        if self.check_column_exists('bugs', 'keywords'):
            query = '''
                SELECT 
                    *
                FROM
                    bugs
                WHERE
                    product_id=%s
                AND
                    bug_id BETWEEN %d AND %d
                ''' % (product_id, from_id, to_id - 1)
        else:
            query = '''
                SELECT
                    b.*,
                    ifnull(group_concat(d.name), '') keywords
                FROM
                    bugs b
                LEFT JOIN
                    keywords k
                    ON b.bug_id = k.bug_id
                LEFT JOIN
                    keyworddefs d
                    ON k.keywordid = d.id
                WHERE
                    b.product_id=%s
                AND
                    b.bug_id BETWEEN %d AND %d
                GROUP BY
                    b.bug_id
                ''' % (product_id, from_id, to_id - 1)

        cursor = self.sql_cnx.cursor()
        cursor.execute(query)

        result = []
        for row in cursor:
            if component_row in row:
                row["component"] = self._get_component_by_id(row[component_row])
            for user_row in user_rows:
                if user_row in row:
                    user_row_value = row[user_row]
                    if user_row_value is not None:
                        row[user_row] = self.get_user_by_id(user_row_value)
            id = row["bug_id"]
            row["flags"] = self.get_flags_by_id(id)
            row["voters"] = self.get_voters_by_id(id)
            row.update(self.get_cf_values_by_id(id))
            row["comments"] = self.get_comments_by_id(id)
            row["attachments"] = self.get_attachments_by_id(id)
            row["cc"] = self._get_cc_by_id(id)
            row["estimated_time"] = int(row["estimated_time"])
            row["keywords"] = set([kw.strip() for kw in row["keywords"].split(",") if len(kw.strip())])
            for key in row.keys():
                if row[key] == "---":
                    row[key] = None
            result.append(row)
        return result

    def get_issues_count(self, project_id):
        cursor = self.sql_cnx.cursor()
        cursor.execute("SELECT COUNT(*) FROM bugs WHERE product_id = %s" % project_id)
        return int(cursor.fetchone()["COUNT(*)"])

    def _get_cc_by_id(self, id):
        cc_cursor = self.sql_cnx.cursor()
        who_row = 'who'
        request = "SELECT %s FROM cc WHERE bug_id = %s" % (who_row, id)
        cc_cursor.execute(request)
        result = []
        for cc in cc_cursor :
            result.append(self.get_user_by_id(cc[who_row]))
        return result

    def get_duplicate_links(self):
        cursor = self.sql_cnx.cursor()
        dupe_row = 'dupe'
        dupe_of_row = "dupe_of"
        request = "SELECT %s, %s FROM duplicates" % (dupe_row, dupe_of_row)
        cursor.execute(request)
        result = set([])
        for row in cursor:
            link = BzIssueLink("Duplicate", str(row[dupe_row]), str(row[dupe_of_row]))
            link.source_product_id = self._get_product_id_by_bug_id(row[dupe_row])
            link.target_product_id = self._get_product_id_by_bug_id(row[dupe_of_row])
            result.add(link)
        return result

    def get_dependencies_link(self):
        cursor = self.sql_cnx.cursor()
        blocked_row = 'blocked'
        depends_on_row = "dependson"
        request = "SELECT %s, %s FROM dependencies" % (blocked_row, depends_on_row)
        cursor.execute(request)
        result = set([])
        for row in cursor:
            link = BzIssueLink("Depend", str(row[blocked_row]), str(row[depends_on_row]))
            link.source_product_id = self._get_product_id_by_bug_id(row[blocked_row])
            link.target_product_id = self._get_product_id_by_bug_id(row[depends_on_row])
            result.add(link)
        return result

    def get_user_by_id(self, id):
        cursor = self.sql_cnx.cursor()
        login_name = 'login_name'
        real_name = "realname"
        user_id = "userid"
        request = "SELECT %s, %s, %s FROM profiles WHERE userid = %s" %  (login_name, real_name, user_id, id)
        cursor.execute(request)
        result = cursor.fetchone()
        user = BzUser(result[user_id])
        user.login = result[login_name]
        user.email = result[login_name]
        user.full_name = result[real_name]
        return user

    def get_cf_values_by_id(self, bug_id):
        existing_custom_fields = self.get_custom_fields()

        single_fields = list([])
        multiple_fields = list([])
        for cf in existing_custom_fields:
            if cf.type == '3' :
                multiple_fields.append(cf.name)
            else:
                single_fields.append(cf.name)

        result = dict([])
        sing_cursor = self.sql_cnx.cursor()
        if len(single_fields):
            request = "SELECT "
            for elem in single_fields:
                request = request + "cf_" + elem + ", "
            request = request[:-2]
            request += " FROM bugs WHERE bug_id = %s" % (str(bug_id))
            sing_cursor.execute(request)
            for row in sing_cursor:
                for elem in single_fields:
                    elem_row = "cf_" + elem
                    if (row[elem_row] != "---") and (row[elem_row] is not None):
                        result[elem] = row[elem_row]
        for cf in multiple_fields:
            mult_cursor = self.sql_cnx.cursor()
            mult_cursor.execute("SELECT value FROM bug_cf_" + cf + " WHERE bug_id = %s", (str(bug_id)))
            result[cf] = list([])
            for row in mult_cursor:
                if row['value'] != '---':
                    result[cf].append(row['value'])
        return result

    def get_comments_by_id(self, bug_id):
        result = list([])
        cursor = self.sql_cnx.cursor()
        when_row = 'bug_when'
        who_row = 'who'
        text_row = 'thetext'
        request = "SELECT %s, %s, %s FROM longdescs WHERE bug_id = %s" % (when_row, who_row, text_row, str(bug_id))
        cursor.execute(request)
        for row in cursor:
            comment = BzComment(time.mktime(row[when_row].timetuple()) + 1e-6 * row[when_row].microsecond)
            comment.reporter = self.get_user_by_id(row[who_row])
            comment.content = row[text_row]
            result.append(comment)
        return result

    def get_attachments_by_id(self, bug_id):
        def get_attach_data_table():
            cursor = self.sql_cnx.cursor()
            cursor.execute("show tables like 'attach_data'")
            if cursor.fetchone():
                return 'attach_data'
            return 'attachments'
        result = list([])
        cursor = self.sql_cnx.cursor()
        id_row = 'attach_id'
        created_row = 'creation_ts'
        filename_row = 'filename'
        submitter_row = 'submitter_id'
        attach_data_table = get_attach_data_table()
        attach_data_table_id_row = 'id' if attach_data_table == 'attach_data' else 'attach_id'
        request = "SELECT %s, %s, %s, %s " % (id_row, created_row, filename_row, submitter_row)
        request += "FROM attachments WHERE bug_id = %s" % str(bug_id)
        cursor.execute(request)
        for row in cursor:
            file_cursor = self.sql_cnx.cursor()
            data_row = 'thedata'
            file_request = "SELECT %s FROM %s WHERE %s = %s" % (data_row, attach_data_table, attach_data_table_id_row, str(row[id_row]))
            file_cursor.execute(file_request)
            attach_row = file_cursor.fetchone()
            if attach_row is None:
                continue
            attach = BzAttachment(row[filename_row])
            attach.content = attach_row[data_row]
            attach.reporter = self.get_user_by_id(row[submitter_row])
            attach.created = time.mktime(row[created_row].timetuple()) + 1e-6 * row[created_row].microsecond
            result.append(attach)
        return result

    def get_flags_by_id(self, bug_id):
        result = set([])
        cursor = self.sql_cnx.cursor()
        type_row = 'type_id'
        request = "SELECT %s FROM flags WHERE (bug_id = %s) AND (status = '+')" % (type_row, str(bug_id))
        cursor.execute(request)
        for row in cursor:
            flag_cursor = self.sql_cnx.cursor()
            name_row = 'name'
            flag_request = "SELECT %s FROM flagtypes WHERE id = %s LIMIT 1" % (name_row, str(row[type_row]))
            flag_cursor.execute(flag_request)
            result.add(flag_cursor.fetchone()[name_row].encode('utf8'))
        return result

    def get_voters_by_id(self, bug_id):
        result = list([])
        if self.check_table_exists('votes'):
            cursor = self.sql_cnx.cursor()
            who_row = 'who'
            request = "SELECT %s FROM votes WHERE bug_id=%s" % (who_row, str(bug_id))
            cursor.execute(request)
            for row in cursor:
                result.append(self.get_user_by_id(row[who_row]))
        return result

    def _get_product_id_by_bug_id(self, bug_id):
        cursor = self.sql_cnx.cursor()
        id_row = "product_id"
        request = "SELECT %s FROM bugs WHERE bug_id=%s LIMIT 1" % (id_row, str(bug_id))
        cursor.execute(request)
        return cursor.fetchone()[id_row]

    def get_product_id_by_name(self, name):
        cursor = self.sql_cnx.cursor()
        id_row = "id"
        name_row = "name"
        request = "SELECT %s FROM products WHERE products.name='%s'" % (id_row, name)
        cursor.execute(request)
        result = cursor.fetchone()
        return result[id_row] if result is not None else None

    def get_product_names(self):
        cursor = self.sql_cnx.cursor()
        name_row = "name"
        request = "SELECT %s FROM products" % name_row
        cursor.execute(request)
        result = []
        for row in cursor:
            result.append(row[name_row].encode('utf8'))
        return result

    def check_table_exists(self, table_name):
        cursor = self.sql_cnx.cursor()
        request = "SHOW TABLES LIKE '%s'" % table_name
        return cursor.execute(request) > 0

    def check_column_exists(self, table_name, column_name):
        cursor = self.sql_cnx.cursor()
        request = "SHOW COLUMNS FROM %s LIKE '%s'" % (table_name, column_name)
        return cursor.execute(request) > 0
        
