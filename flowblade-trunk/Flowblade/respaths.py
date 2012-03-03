"""
Module contains absolute paths to various resources.
"""

ROOT_PATH = None

BLACK_IMAGE_PATH = None
IMAGE_PATH = None
PROFILE_PATH = None
PREFS_PATH = None
WIPE_RESOURCES_PATH = None
FILTERS_XML_DOC = None
COMPOSITORS_XML_DOC = None
HELP_DOC = None
FFMPEG_HELP_DOC = None
GPL_3_DOC = None
LOCALE_PATH = None
USER_PROFILES = None

def set_paths(root_path):
    global ROOT_PATH, IMAGE_PATH, THUMBNAIL_PATH, PROFILE_PATH,\
    BLACK_IMAGE_PATH, FILTERS_XML_DOC, COMPOSITORS_XML_DOC, \
    WIPE_RESOURCES_PATH, PREFS_PATH, HELP_DOC, FFMPEG_HELP_DOC, LOCALE_PATH, \
    USER_PROFILES, GPL_3_DOC
    
    ROOT_PATH = root_path
    IMAGE_PATH = root_path + "/res/img/"
    WIPE_RESOURCES_PATH = root_path + "/res/filters/wipes/"
    PROFILE_PATH = root_path + "/res/profiles/"
    BLACK_IMAGE_PATH = root_path + "/res/img/black.jpg"
    FILTERS_XML_DOC = root_path + "/res/filters/filters.xml"
    COMPOSITORS_XML_DOC = root_path + "/res/filters/compositors.xml"
    PREFS_PATH = root_path + "/res/prefs/"
    HELP_DOC = root_path + "/res/help/help.xml"
    FFMPEG_HELP_DOC = root_path + "/res/help/ffmpeg_opts_help.xml"
    LOCALE_PATH = root_path + "/locale/"
    USER_PROFILES = root_path + "/res/user_profiles/"
    GPL_3_DOC = root_path + "/res/help/gpl3"