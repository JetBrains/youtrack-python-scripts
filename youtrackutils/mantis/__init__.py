CF_TYPES = dict([])
LINK_TYPES = dict([])
CREATE_CF_FOR_SUBPROJECT = True
CHARSET = "cp866"
FIELD_NAMES = dict([])
FIELD_TYPES = dict([])
FIELD_VALUES = dict([])

class MantisUser(object) :

    def __init__(self, name) :
        self.user_name = name
        self.real_name = ""
        self.email = ""

class MantisCategory(object) :
    def __init__(self, name) :
        self.name = name
        self.assignee = None

class MantisVersion(object) :
    def __init__(self, name) :
        self.name = name
        self.is_released = True
        self.is_obsolete = False

class MantisCustomFieldDef(object) :
    def __init__(self, id) :
        self.name = None
        self.type = None
        self.values = None
        self.field_id = id
        self.default_value = None

class MantisComment(object) :
    def __init__(self) :
        self.reporter = ""
        self.date_submitted = None
        self.text = ""

class MantisIssueLink(object) :
    def __init__(self, source, target, type):
        self.source = source
        self.target = target
        self.source_project_id = None
        self.target_project_id = None
        self.type = type

class MantisAttachment(object):
    def __init__(self, id):
        self.id = id
        self.title = ""
        self.filename = ""
        self.file_type = ""
        self.content = None
        self.user_id = ""
        self.date_added = ""
