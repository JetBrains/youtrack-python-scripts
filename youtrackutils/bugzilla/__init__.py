import time

FIELD_TYPES = dict()
FIELD_NAMES = dict()

DEFAULT_EMAIL = "example@example.com"
STATUS = dict([])
RESOLUTION = dict([])
PRIORITY = dict([])
CF_TYPES = dict([])
ACCEPT_EMPTY_COMMENTS = True
BZ_DB_CHARSET = ''

USE_STATE_MAP = False
STATE_MAP = dict([])
STATE_STATUS = "bug_status"
STATE_RESOLUTION = "resolution"


class BzUser(object):
    def __init__(self, id):
        self.user_id = id
        self.login = ""
        self.full_name = None
        self.email = None


class BzComponent(object):
    def __init__(self, id):
        self.id = id
        self.description = None
        self.initial_owner = None
        self.name = str(id)


class BzVersion(object):
    def __init__(self, id):
        self.id = id
        self.value = str(id)


class BzCustomField(object):
    def __init__(self, name):
        self.name = name
        self.type = "FIELD_TYPE_FREETEXT"
        self.values = list([])


class BzIssue(object):
    def __init__(self, id):
        self.id = id
        self.assignee = None
        self.severity = None
        self.status = None
        self.component = None
        self.created = time.time()
        self.keywords = set([])
        self.op_sys = None
        self.priority = None
        self.platform = None
        self.reporter = None
        self.resolution = None
        self.summary = None
        self.version = None
        self.voters = set([])
        self.cc = list([])
        self.cf = dict([])
        self.comments = list([])
        self.attachments = list([])
        self.flags = set([])


class BzComment(object):
    def __init__(self, time):
        self.time = time
        self.content = ""
        self.reporter = None


class BzAttachment(object):
    def __init__(self, name):
        self.created = None
        self.reporter = ""
        self.name = name
        self.content = None


class BzIssueLink(object):
    def __init__(self, name, source, target):
        self.name = name
        self.target_product_id = None
        self.source_product_id = None
        self.source = source
        self.target = target


class BzIssueLinkType(object):
    def __init__(self, name):
        self.name = name
        self.description = ""
