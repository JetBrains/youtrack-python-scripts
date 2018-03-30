import re
from youtrackutils.fbugz.fogbugz import FogBugz
from youtrackutils.fbugz import FBUser, FBArea, FBMilestone, FBIssue, FBComment, FBAttachment
from datetime import datetime
import calendar


class FBClient(object):
    def __init__(self, source_url, source_login, source_password):
        self._source_url = source_url
        self._client = FogBugz(source_url)
        self._client.logon(source_login, source_password)
        self._case_ids = []

    def list_project_names(self):
        projects = dict([])
        for p in self._client.listProjects().findAll('project'):
            projects[p.sproject.string.strip()] = p.ixproject.string.strip()
        return projects

    def get_users(self):
        self._users = []
        try:
            for p in self._client.listPeople(fIncludeNormal=1).findAll('person'):
                self._users.append(self._create_user(p, 'Normal'))
        except:
            print "Can't get Normal users"

        try:
            for p in self._client.listPeople(fIncludeNormal=0, fIncludeDeleted=1).findAll('person'):
                self._users.append(self._create_user(p, 'Deleted'))
        except:
            print "Can't get Deleted users"

        try:
            for p in self._client.listPeople(fIncludeNormal=0, fIncludeVirtual=1).findAll('person'):
                self._users.append(self._create_user(p, 'Virtual'))
        except:
            print "Can't get Virtual users"

        try:
            for p in self._client.listPeople(fIncludeNormal=0, fIncludeCommunity=1).findAll('person'):
                self._users.append(self._create_user(p, 'Community'))
        except:
            print "Can't get Community users"

        if 'FogBugz' not in [u.login for u in self._users]:
            self._users.append(FBUser('FogBugz'))

        return self._users

    def get_areas(self, ix_project):
        result = []
        for a in self._client.listAreas(ixproject=ix_project).findAll('area'):
            area = FBArea(a.sarea.string.encode('utf-8').decode('utf-8'))
            owner = a.spersonowner.string
            if owner is None:
                area.person_owner = None
            else:
                area.person_owner = self.convert_login(owner.encode('utf-8').decode('utf-8'))
            result.append(area)
        return result

    def get_milestones(self, ix_project):
        result = []
        for m in self._client.listFixFors(ixProject=ix_project, fIncludeDeleted=1, fIncludeReallyDeleted=1).findAll(
            "fixfor"):
            milestone = FBMilestone(m.sfixfor.string.encode('utf-8').decode('utf-8'))
            dt = m.dt.string
            milestone.release_date = self._to_unix_date(dt)
            milestone.inactive = bool(m.fdeleted.string)
            result.append(milestone)
        return result

    def get_issues(self, project_name, start_id, num):
        result = []
        cols_string = "ixBug,sArea,sPersonAssignedTo,ixBugParent,sCategory,dtClosed,sComputer,sVersion,dtDue,sFixFor,"
        cols_string += "sLatestTextSummary,fOpen,dtOpened,dtResolved,ixPriority,sPriority,sStatus,sOriginalTitle,sTitle,tags,"
        cols_string += "ixPersonOpenedBy,ixPersonResolvedBy,hrsCurrEst"

        for i in self._client.search(cols=cols_string, q=(
            'case:%d..%d project:"%s"' % (start_id, start_id + num - 1, project_name))).findAll('case'):
            ix_bug = i.ixbug.string
            self._case_ids.append(ix_bug)
            issue = FBIssue(ix_bug)
            issue.field_values['area'] = i.sarea.string.encode('utf-8').decode('utf-8')
            assignee = i.spersonassignedto.string
            if assignee is not None:
                if assignee == 'CLOSED':
                    issue.field_values[u'assignee'] = self.convert_login(
                        self._find_user_login(i.ixpersonresolvedby.string))
                else:
                    issue.field_values[u'assignee'] = self.convert_login(assignee.encode('utf-8'))
            parent_id = i.ixbugparent.string
            if parent_id != '0':
                issue.bug_parent = parent_id
            issue.field_values[u'category'] = i.scategory.string
            issue.field_values[u'estimate'] = i.hrscurrest.string
            issue.closed = self._to_unix_date(i.dtclosed.string)
            computer = i.scomputer.string
            if computer is not None:
                issue.field_values[u'computer'] = computer.encode('utf-8')
            sversion_string = i.sversion.string
            if sversion_string is not None:
                issue.field_values['version'] = sversion_string.encode('utf-8')
            due_dt = i.dtdue.string
            if (due_dt is None) or (due_dt.strip() == ''):
                issue.field_values[u'due'] = None
            else:
                issue.field_values[u'due'] = self._to_unix_date(due_dt)
            issue.field_values[u'fix_for'] = i.sfixfor.string.encode('utf-8').decode('utf-8')
            latest_summary = i.slatesttextsummary.string
            if latest_summary is not None:
                issue.latest_text_summary = latest_summary.encode('utf-8')
            issue.open = bool(i.fopen.string)
            issue.opened = self._to_unix_date(i.dtopened.string)
            issue.resolved = self._to_unix_date(i.dtresolved.string)
            issue.field_values[u'priority'] = i.ixpriority.string.encode('utf-8').decode(
                'utf-8') + u'-' + i.spriority.string.encode('utf-8').decode('utf-8')
            issue.field_values[u'status'] = i.sstatus.string
            original = i.soriginaltitle.string
            if original is not None:
                issue.field_values[u'original_title'] = original.encode('utf-8').decode('utf-8')
            else:
                issue.field_values[u'original_title'] = None
            issue.title = i.stitle.string.encode('utf-8').decode('utf-8')
            events = self._client.search(q=ix_bug, cols='events').findAll('event')
            issue.attachments = self._get_attachments_from_events(events)
            issue.comments = self._get_comments_from_events(events)
            for tag in i.tags.findAll('tag'):
                issue.tags.append(tag.string)
            issue.reporter = self.convert_login(self._find_user_login(i.ixpersonopenedby.string))
            result.append(issue)

        return result

    def get_issue_project_id(self, ix_bug):
        return self._client.search(q=ix_bug, cols='ixProject').case.ixproject.string

    def list_priorities(self):
        return [(elem.ixpriority.string.encode('utf-8').decode('utf-8'),
                 elem.spriority.string.encode('utf-8').decode('utf-8')) for elem in
                                                                        self._client.listPriorities().findAll(
                                                                            'priority')]

    def list_categories(self):
        return [elem.scategory.string.encode('utf-8').decode('utf-8') for elem in
                self._client.listCategories().findAll('category')]

    def list_statuses(self):
        statuses = [
            (elem.sstatus.string.encode('utf-8').decode('utf-8'), elem.fresolved.string.encode('utf-8') == 'true') for
                                                                                                                   elem
                                                                                                                   in
                                                                                                                   self._client.listStatuses().findAll(
                                                                                                                       'status')]
        resulting_statuses = []
        for status in statuses:
            resulting_statuses.append(status)
            if status[1]:
                match_result = re.match("Resolved \((.*)\)", status[0])
                if match_result is not None:
                    resulting_statuses.append(("Closed (%s)" % match_result.groups()[0], True))
                else:
                    resulting_statuses.append(("Closed (%s)" % status[0], True))
        return resulting_statuses

    def _get_comments_from_events(self, events):
        comments = []
        for event in events:
            if hasattr(event, 's'):
                comment = FBComment()
                content = event.s.string
                if (content is None) or (content.strip() == ''):
                    continue
                comment.text = content.encode('utf-8').decode('utf-8')
                comment.author = self.convert_login(event.sperson.string.encode('utf-8'))
                comment.date = self._to_unix_date(event.dt.string)
                comments.append(comment)
        return comments

    def _get_attachments_from_events(self, events):
        attachments = []
        for event in events:
            for a in event.findAll('attachment'):
                attach = FBAttachment(self._source_url, a.surl.string)
                attach.authorLogin = self.convert_login(event.sperson.string)
                attach.token = self._client.get_token()
                attachments.append(attach)
        return attachments


    def _create_user(self, p, type):
        person = FBUser(self.convert_login(p.sfullname.string))
        if len(p.semail.string):
            person.email = p.semail.string
        person.user_type = type
        person.id = p.ixperson.string
        return person

    def _find_user_login(self, id):
        if self._users is None:
            self.get_users()
        for user in self._users:
            if user.id == id:
                return user.login.encode('utf-8')
        return None

    def _to_unix_date(self, date_string):
        if date_string is None:
            dt = datetime.now()
        else:
            dt = datetime.strptime(date_string, '%Y-%m-%dT%H:%M:%SZ')
        return str(calendar.timegm(dt.timetuple()) * 1000)

    def convert_login(self, old_login):
        if old_login is None:
            return None
        return old_login.replace(' ', '_')
