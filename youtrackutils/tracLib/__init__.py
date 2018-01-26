import client

CUSTOM_FIELD_TYPES = None
PERMISSIONS = None
DEFAULT_EMAIL = " "
ACCEPT_NON_AUTHORISED_USERS = True
FIELD_VALUES = dict([])
FIELD_TYPES = dict([])
FIELD_NAMES = dict([])

SUPPORT_TIME_TRACKING = 'auto'

class TracUser(object):

    def __init__(self, name):
        self.name = name
        self.email = ""

class TracIssue(object):

    def __init__(self, id):
        self.id = id
        self.type = None
        self.time = None
        self.changetime = None
        self.component = None
        self.severity = None
        self.priority = None
        self.owner = None
        self.reporter = None
        self.cc = set([])
        self.version = None
        self.milestone = None
        self.status = None
        self.resolution = None
        self.summary = None
        self.description = None
        self.keywords = set([])
        self.custom_fields = {}
        self.attachment = set([])
        self.comments = set([])
        self.workitems = set([])

class TracVersion(object):

    def __init__(self, name):
        self.name = name
        self.time = None
        self.description = ""

class TracMilestone(object):

    def __init__(self, name):
        self.name = name
        self.time = None
        self.description = ""

class TracComponent(object):

    def __init__(self, name):
        self.name = name
        self.owner = None
        self.description = ""

class TracCustomFieldDeclaration(object):

    def __init__(self, name):
        self.name = name
        self.type = "text"
        self.label = ""
        self.options = list([])
        self.value = ""

    def __str__(self):
        result = "name :   " + self.name + "    type :   " + self.type + "    label :   " + self.label
        result = result + "    value :   " + self.value + "    options :    "
        for elem in self.options:
            result = result + elem + ",    "    
        return result

class TracAttachment(object):

    def __init__(self, filename):
        self.filename = filename
        self.size = -1
        self.time = None
        self.description = ""
        self.author_name = None
        self.name = ""

class TracComment(object):

    def __init__(self, time):
        self.time = time
        self.author = ""
        self.content = ""
        self.id = 0

    def __eq__(self, other):
        return self.id == other.id

class TracWorkItem(object):
    def __init__(self, time, duration, author, comment):
        self.time = time
        self.duration = duration
        self.author = author
        self.comment = comment.strip() if comment is not None else ""

class TracResolution(object):

    def __init__(self, name):
        self.name = name


def to_unix_time(time):
    return time / 1000
