import cgi
from time import time
import urllib2

CATEGORY = dict([])
PRIORITY = dict([])
STATUS = dict([])
CF_NAMES = dict([])
CF_TYPES = dict([])
CF_VALUES = dict([])
PROJECTS_TO_IMPORT = list([])

class FBArea(object) :
    def __init__(self, name) :
        self.name = name
        self.person_owner = ""
        self.n_type = None

class FBUser(object) :
    def __init__(self, login):
        self.login = login
        self.email = '<no_email>'
        self.user_type = 'Normal'
        self.id = ""

class FBMilestone(object) :
    def __init__(self, name) :
        self.name = name
        self.deleted = False
        self.inactive = False
        self.release_date = str(int(time()))

class FBCustomField(object) :
    def __init__(self, name, column_name) :
        self.name = name
        self.column_name = column_name
        self.type = 0
        self.possible_values = list([])

class FBIssue(object) :
    def __init__(self, ix_bug) :
        self.ix_bug = ix_bug
        self.bug_parent = None
        self.tags = []
        self.open = True
        self.title = 'title'
        self.field_values = dict([])
        self.original_title = None
        self.latest_text_summary = 'None'
        self.area = 'No subsystem'
        self.assignee = '<no user>'
        self.status = None
        self.priority = None
        self.fix_for = None
        self.first_field = ''
        self.second_field = ''
        self.category = ''
        self.opened = int(time())
        self.resolved = int(time())
        self.closed = int(time())
        self.due = int(time())
        self.reporter = 'guest'
        self.attachments = []
        self.comments = []
        self.version = None
        self.computer = None


class FBAttachment(object) :
    def __init__(self, base_url, url) :
        self._url = base_url + url
        parsed_url = urllib2.urlparse.urlparse(self._url)
        parse_qs = cgi.parse_qs(parsed_url.query)
        file_name_arg = 'sFileName'
        if file_name_arg in parse_qs.keys():
            attachment_name = parse_qs[file_name_arg][0]
            if isinstance(attachment_name, unicode):
                attachment_name = attachment_name.encode('utf-8')
            self.name = attachment_name
        else:
            self.name = 'Attachment'
        self.authorLogin = 'guest'
        self.token = 'no_token_available'

    def getContent(self) :
        url = self._url.replace('&amp;', '&') + '&token=' + self.token
        f = urllib2.urlopen(urllib2.Request(url))
        return f

class FBComment(object) :
    def __init__(self) :
        self.author = 'guest'
        self.date = time()
        self.text = ''

