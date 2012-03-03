"""
This module loads render options, provides them in displayable form 
and builds mlt.Consumer for rendering.

Rendering is done in app.player object of class mltplayer.Player
"""
import gtk
import mlt
import os
import time
import xml.dom.minidom

import dialogs
from editorstate import current_sequence
from editorstate import PROJECT
import gui
import guicomponents
import mltenv
import mltprofiles
import respaths
import utils

# File describing existing encoding and quality options
RENDER_ENCODING_FILE = "/res/render/renderencoding.xml"

# User defined Ffmpeg opts file extension
FFMPEG_OPTS_SAVE_FILE_EXTENSION = ".rargs"

# Defaults
DEFAULT_ENCODING_INDEX = 0

# Node, attribute names.
NAME = "name"
TYPE = "type"
ID = "id"
EXTENSION = "extension"
RESIZABLE = "resize"
ARGS = "args"
REPLACED_VALUES = "replvalues"
ADDED_ATTRIBUTES = "addargs"
BITRATE_OPTION = "boption"
QUALITY_GROUP = "qualityqroup"
ENCODING_OPTION = "encodingoption"
QGROUP = "qgroup"
DEFAULT_INDEX = "defaultindex"
PROFILE = "profile"
QUALITY = "quality"
BITRATE = "bitrate"
AUDIO_DESCRIPTION = "audiodesc"

# Replace strings and attribute values
BITRATE_RPL = "%BITRATE%"
VARIABLE_VAL = "%VARIABLE%"
SCREEN_SIZE_RPL = "%SCREENSIZE%"
ASPECT_RPL = "%ASPECT%"

# Option strings
SIZE_OPTION = "s"

render_encoding_doc = None
encoding_options = []
quality_option_groups = {}
quality_option_groups_default_index = {}

render_start_time = 0
widgets = utils.EmptyClass()

aborted = False

# Replace empty strings with None values
def _get_attribute(node, attr_name):
    value = node.getAttribute(attr_name)
    if value == "":
        return None
    
    return value
    
class QualityOption:
    """
    A render quality option for an EncodingOption.
    
    Values of mlt render consumer properties (usually bitrate) that equal 
    key expressions are replaced with corresponding values.
    """
    def __init__(self, quality_node):
        self.name = _get_attribute(quality_node, NAME)
        # Replaced render arguments
        replaced_values_str = _get_attribute(quality_node, REPLACED_VALUES)
        self.replaced_expressions = []
        self.replace_map = {}
        if replaced_values_str != None:
            tokens = replaced_values_str.split(";")
            for token in tokens:
                token_sides = token.split(" ")
                self.replaced_expressions.append(token_sides[0])
                self.replace_map[token_sides[0]] = token_sides[1]
        # Added render arguments
        added_atrrs_str = _get_attribute(quality_node, ADDED_ATTRIBUTES)
        self.add_map = {}
        if added_atrrs_str != None:
            tokens = added_atrrs_str.split(" ")
            for token in tokens:
                token_sides = token.split("=")
                self.add_map[token_sides[0]] = token_sides[1]

class EncodingOption:
    """
    An object that groups together vcodoc, acodec, format and quality options group.
    Object is used to set mlt render consumer properties.
    """
    def __init__(self, option_node):
        self.name = _get_attribute(option_node, NAME)
        self.type = _get_attribute(option_node, TYPE)
        self.resizable = (_get_attribute(option_node, RESIZABLE) == "True")
        self.extension = _get_attribute(option_node, EXTENSION)
        quality_qroup_id = _get_attribute(option_node, QGROUP)
        self.quality_options = quality_option_groups[quality_qroup_id]
        try:
            quality_default_index = int(quality_option_groups_default_index[quality_qroup_id])
        except KeyError:
            quality_default_index = None
        self.quality_default_index = quality_default_index
        self.audio_desc = _get_attribute(option_node, AUDIO_DESCRIPTION)
        profile_node = option_node.getElementsByTagName(PROFILE).item(0)
        self.attr_string =  _get_attribute(profile_node, ARGS)
        self.acodec = None
        self.vcodec = None
        self.format = None

        tokens = self.attr_string.split(" ")
        for token in tokens:
            token_sides = token.split("=")
            if token_sides[0] == "acodec":
                self.acodec = token_sides[1]
            elif token_sides[0] == "vcodec":
                self.vcodec = token_sides[1]
            elif token_sides[0] == "f":
                self.format = token_sides[1]
                    
        self.supported = mltenv.render_profile_supported(self.format, 
                                                         self.vcodec,
                                                         self.acodec)
                                                         
    def get_args_vals_tuples_list(self, profile, quality_option):
        # Encoding options
        tokens = self.attr_string.split(" ")
        args_tuples = []
        for token in tokens:
            # Get property keys and values
            token_sides = token.split("=")
            arg1 = str(token_sides[0])
            arg2 = str(token_sides[1])
            
            # Replace keyword values
            if arg2 == SCREEN_SIZE_RPL:
                arg2 = str(profile.width())+ "x" + str(profile.height())
            if arg2 == ASPECT_RPL:
                arg2 = "@" + str(profile.display_aspect_num()) + "/" + str(profile.display_aspect_den())

            # Replace keyword values from quality options values
            if arg2 in quality_option.replaced_expressions:
                arg2 = str(quality_option.replace_map[arg2])
            args_tuples.append((arg1, arg2))
        
        return args_tuples

    def get_audio_description(self):
        if self.audio_desc == None:
            desc = "Not available"
        else:
            desc = self.audio_desc 
        return "<small>" + desc + "</small>"
    
# ------------------------------------------------- init, other interface
def load_render_profiles():
    """
    Load render profiles from xml into DOM at start-up and build
    object tree.
    """
    file_path = respaths.ROOT_PATH + RENDER_ENCODING_FILE
    global render_encoding_doc
    render_encoding_doc = xml.dom.minidom.parse(file_path)

    # Create quality option groups
    global quality_option_groups
    qgroup_nodes = render_encoding_doc.getElementsByTagName(QUALITY_GROUP)
    for qgnode in qgroup_nodes:
        quality_qroup = []
        group_key = _get_attribute(qgnode, ID)
        group_default_index = _get_attribute(qgnode, DEFAULT_INDEX)
        if group_default_index != None: 
            quality_option_groups_default_index[group_key] = group_default_index
        option_nodes = qgnode.getElementsByTagName(QUALITY)
        for option_node in option_nodes:
            q_option = QualityOption(option_node)
            quality_qroup.append(q_option)
        quality_option_groups[group_key] = quality_qroup

    # Create encoding options
    global encoding_options
    encoding_option_nodes = render_encoding_doc.getElementsByTagName(ENCODING_OPTION)
    for eo_node in encoding_option_nodes:
        encoding_option = EncodingOption(eo_node)
        encoding_options.append(encoding_option)
        
def get_render_consumer():
    """
    Creates and sets parameters to mlt.Consumer 
    based on current selections
    """
    file_path = get_file_path()
    if file_path == None:
        return None

    # Get render profile
    profile = _get_current_profile()

    # Create render consumer
    consumer = mlt.Consumer(profile, "avformat", file_path)
    consumer.set("real_time", -1)

    # Set render consumer properties
    encoding_option = encoding_options[widgets.encodings_cb.get_active()]
    quality_option = encoding_option.quality_options[widgets.quality_cb.get_active()]

    # Encoding options
    if widgets.use_opts_check.get_active() == False:
        args_vals_list = encoding_option.get_args_vals_tuples_list(profile, quality_option)
    else:
        args_vals_list, error = _get_ffmpeg_opts_args_vals_tuples_list()
        if error != None:
            dialogs.warning_message("FFMPeg Args Error", error, gui.editor_window.window)
            return None
        
    for arg_val in args_vals_list:
        k, v = arg_val
        consumer.set(k, v)

    # Quality options
    for k, v in quality_option.add_map.iteritems():
        consumer.set(str(k), str(v))
        
    return consumer

def get_file_path():
    folder = widgets.out_folder.get_filenames()[0]        
    filename = widgets.movie_name.get_text()
    
    return folder + "/" + filename + widgets.extension_label.get_text()

def get_quality_name(quality_option, render_profile):
    name = quality_option.name
    if name.find(BITRATE_RPL) != -1:
        name = name.replace(BITRATE_RPL, (render_profile.bitrate + " kb/s"))
    return name

def get_size_string(group_index, profile_index):
    profiles_group = profiles_groups[group_index]
    if profiles_group.resizable == False:
        profile = profiles_group.profiles[profile_index]
        return profile.size_str
    
    return DEFAULT_SIZE_STR

# --------------------------------------------------- gui
def create_widgets():
    """
    Widgets for editing render properties and viewing render progress.
    """
    # Render panel widgets
    # File
    widgets.out_folder = gtk.FileChooserButton(_("Select Folder"))
    widgets.out_folder.set_action(gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER)
    widgets.out_folder.set_current_folder(os.path.expanduser("~"))
    
    widgets.movie_name = gtk.Entry()
    widgets.movie_name.set_text("movie")
    
    # Render Profile
    widgets.use_project_profile_check = gtk.CheckButton()
    widgets.use_project_profile_check.set_active(True)
    widgets.use_project_profile_check.connect("toggled", _use_project_check_toggled)

    widgets.out_profile_combo = gtk.combo_box_new_text() # filled later when current sequence known
    widgets.out_profile_combo.connect('changed', lambda w:  _out_profile_changed())
    widgets.out_profile_combo.set_sensitive(False)
    
    widgets.out_profile_info_box = gtk.VBox() # filled later when current sequence known
    widgets.out_profile_info_box.add(gtk.Label()) # This is removed when we have data to fill this
    
    # Encoding
    widgets.encodings_cb = gtk.combo_box_new_text()
    for encoding in encoding_options:
        widgets.encodings_cb.append_text(encoding.name)
    widgets.encodings_cb.set_active(DEFAULT_ENCODING_INDEX)
    widgets.encodings_cb.connect("changed", 
                              lambda w,e: _encoding_selection_changed(), 
                              None)

    widgets.extension_label = gtk.Label()
    _fill_extension_label()

    widgets.quality_label = gtk.Label(_("Quality:"))

    widgets.quality_cb = gtk.combo_box_new_text()
    _fill_quality_combo_box()
    #widgets.quality_cb.set_active(DEFAULT_QUALITY_INDEX)
    
    widgets.audio_label = gtk.Label(_("Audio:"))        
    widgets.audio_desc = gtk.Label()

    # FFMpeg opts
    widgets.use_opts_check = gtk.CheckButton()
    widgets.use_opts_check.connect("toggled", _use_ffmpg_opts_check_toggled)
    
    widgets.opts_info_button = gtk.Button()
    icon = gtk.image_new_from_stock(gtk.STOCK_INFO, gtk.ICON_SIZE_MENU)
    widgets.opts_info_button.set_image(icon)

    widgets.opts_save_button = gtk.Button()
    icon = gtk.image_new_from_stock(gtk.STOCK_SAVE, gtk.ICON_SIZE_MENU)
    widgets.opts_save_button.set_image(icon)
    widgets.opts_save_button.connect("clicked", lambda w: _save_opts_pressed())

    widgets.opts_load_button = gtk.Button()
    icon = gtk.image_new_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_MENU)
    widgets.opts_load_button.set_image(icon)
    widgets.opts_load_button.connect("clicked", lambda w: _load_opts_pressed())
    
    widgets.opts_save_button.set_sensitive(False)
    widgets.opts_load_button.set_sensitive(False)
    
    widgets.load_selection_button = gtk.Button(_("Load Selection"))
    widgets.load_selection_button.set_sensitive(False)
    widgets.load_selection_button.connect("clicked", lambda w: _display_selection_in_opts_view())
    
    widgets.opts_view = gtk.TextView()
    widgets.opts_view.set_sensitive(False)
    widgets.opts_view.set_pixels_above_lines(2)
    widgets.opts_view.set_left_margin(2)
    
    # Range
    widgets.range_cb = gtk.combo_box_new_text()
    widgets.range_cb.append_text(_("Program length"))
    widgets.range_cb.append_text(_("Marked range"))
    widgets.range_cb.set_active(0) 

    # Render, Reset buttons
    widgets.render_button = gtk.Button()
    render_icon = gtk.image_new_from_stock(gtk.STOCK_MEDIA_RECORD, 
                                           gtk.ICON_SIZE_BUTTON)

    render_pad1 = gtk.Label()
    render_pad1.set_size_request(10, 10)
    render_pad2 = gtk.Label()
    render_pad2.set_size_request(5, 10)
    render_pad3 = gtk.Label()
    render_pad3.set_size_request(10, 10)
    render_button_box = gtk.HBox()
    render_button_box.pack_start(render_pad1, False, False, 0)
    render_button_box.pack_start(render_icon, False, False, 0)
    render_button_box.pack_start(render_pad2, False, False, 0)
    render_button_box.pack_start(gtk.Label(_("Render")), False, False, 0)
    render_button_box.pack_start(render_pad3, False, False, 0)
    widgets.render_button.add(render_button_box)
    
    widgets.reset_button = gtk.Button(_("Reset"))
    widgets.reset_button.connect("clicked", lambda w: set_default_values_for_widgets())

    # Render progress window
    widgets.progress_window = None #created in dialogs.py, destroyed here
    
    # Render progress window widgets
    widgets.status_label = gtk.Label()
    widgets.remaining_time_label = gtk.Label()
    widgets.passed_time_label = gtk.Label()
    widgets.progress_bar = gtk.ProgressBar()
    widgets.estimation_label = gtk.Label()

    # Tooltips
    widgets.out_folder.set_tooltip_text(_("Select folder to place rendered file in"))
    widgets.movie_name.set_tooltip_text(_("Give name for rendered file"))
    widgets.use_project_profile_check.set_tooltip_text(_("Select used project profile for rendering"))
    widgets.out_profile_combo.set_tooltip_text(_("Select render profile"))
    widgets.encodings_cb.set_tooltip_text(_("Select Render encoding"))
    widgets.quality_cb.set_tooltip_text(_("Select Render quality"))
    widgets.use_opts_check.set_tooltip_text(_("Render using key=value rendering options"))
    widgets.load_selection_button.set_tooltip_text(_("Load render options from currently selected encoding"))
    widgets.opts_view.set_tooltip_text(_("Edit render options"))
    widgets.range_cb.set_tooltip_text(_("Select render range"))
    widgets.reset_button.set_tooltip_text(_("Reset all render options to defaults"))
    widgets.render_button.set_tooltip_text(_("Begin Rendering"))
    widgets.opts_info_button.set_tooltip_text(_("Info on setting FFMpeg options"))
    widgets.out_profile_info_box.set_tooltip_text(_("Render profile info"))
    widgets.opts_save_button.set_tooltip_text(_("Save Render Args into a text file"))
    widgets.opts_load_button.set_tooltip_text(_("Load Render Args from a text file"))
    
    # Put in current audio description
    _fill_audio_desc()

def set_default_values_for_widgets():
    widgets.encodings_cb.set_active(DEFAULT_ENCODING_INDEX)
    widgets.movie_name.set_text("movie")
    widgets.out_folder.set_current_folder(os.path.expanduser("~"))
    widgets.use_opts_check.set_active(False)
    widgets.use_project_profile_check.set_active(True)

def set_render_gui():
    widgets.status_label.set_text(_("<b>Output File: </b>") + get_file_path())
    widgets.status_label.set_use_markup(True)
    widgets.remaining_time_label.set_text(_("<b>Estimated time left: </b>"))
    widgets.remaining_time_label.set_use_markup(True)
    widgets.passed_time_label.set_text(_("<b>Render time: </b>"))
    widgets.passed_time_label.set_use_markup(True)
    widgets.estimation_label.set_text("0%")

def save_render_start_time():
    global render_start_time
    render_start_time = time.time()
    
def set_render_progress_gui(fraction):
    widgets.progress_bar.set_fraction(fraction)
    pros = int(fraction * 100)
    widgets.estimation_label.set_text(str(pros) + "%")

    if pros > 0.99: # Only start giving estimations after rendering has gone on for a while.
        passed_time = time.time() - render_start_time
        full_time_est = (1.0 / fraction) * passed_time
        left_est = full_time_est - passed_time

        left_str = utils.get_time_str_for_sec_float(left_est)
        passed_str = utils.get_time_str_for_sec_float(passed_time)

        widgets.remaining_time_label.set_text(_("<b>Estimated time left: </b>") + left_str)
        widgets.remaining_time_label.set_use_markup(True)
        widgets.passed_time_label.set_text(_("<b>Render time: </b>") + passed_str)
        widgets.passed_time_label.set_use_markup(True)

def exit_render_gui():
    # 'aborted' is set False at render start. If it is True now, rendering has been aborted and 
    # widgets.progress_window has already been destroyed (in useraction._render_cancel_callback).
    if aborted == True:
        return

    set_render_progress_gui(1.0)
    passed_time = time.time() - render_start_time
    passed_str = utils.get_time_str_for_sec_float(passed_time)

    widgets.remaining_time_label.set_text(_("<b>Estimated time left: </b>"))
    widgets.remaining_time_label.set_use_markup(True)
    widgets.passed_time_label.set_text(_("<b>Render time: </b>") + passed_str)
    widgets.passed_time_label.set_use_markup(True)
    widgets.estimation_label.set_text(_("Render Complete!"))
    
    time.sleep(2.0)
    widgets.progress_window.destroy()

def _get_current_profile():
    profile_index = widgets.out_profile_combo.get_active()
    if profile_index == 0:
        # project_profile is first selection in combo box
        profile = PROJECT().profile
    else:
        profile = mltprofiles.get_profile_for_index(profile_index - 1)
    return profile

def fill_out_profile_widgets():
    """
    Called some time after widget creation when current_sequence is known and these can be filled.
    """
    widgets.out_profile_combo.get_model().clear()
    widgets.out_profile_combo.append_text(current_sequence().profile.description())
    profiles = mltprofiles.get_profiles()
    for profile in profiles:
        widgets.out_profile_combo.append_text(profile[0])
    widgets.out_profile_combo.set_active(0)
       
    _fill_info_box(current_sequence().profile)

def reload_profiles():
    load_render_profiles()
    fill_out_profile_widgets()
    
def _use_project_check_toggled(checkbutton):
    widgets.out_profile_combo.set_sensitive(checkbutton.get_active() == False)
    if checkbutton.get_active() == True:
        widgets.out_profile_combo.set_active(0)

def _use_ffmpg_opts_check_toggled(checkbutton):
    active = checkbutton.get_active()
    widgets.opts_view.set_sensitive(active)
    widgets.load_selection_button.set_sensitive(active)
    widgets.opts_save_button.set_sensitive(active)
    widgets.opts_load_button.set_sensitive(active)

    if active == True:
        _display_selection_in_opts_view()
    else:
        widgets.opts_view.set_buffer(gtk.TextBuffer())

def _out_profile_changed():
    selected_index = widgets.out_profile_combo.get_active()
    if selected_index == 0:
        _fill_info_box(current_sequence().profile)
    else:
        profile = mltprofiles.get_profile_for_index(selected_index - 1)
        _fill_info_box(profile)

def _fill_info_box(profile):
    info_box_children = widgets.out_profile_info_box.get_children()
    for child in info_box_children:
        widgets.out_profile_info_box.remove(child)
    
    info_panel = guicomponents.get_profile_info_box(profile, True)
    widgets.out_profile_info_box.add(info_panel)
    widgets.out_profile_info_box.show_all()
    info_panel.show()

def _encoding_selection_changed():
    _fill_quality_combo_box()
    _fill_extension_label()
    _fill_audio_desc()

def _fill_quality_combo_box():
    enc_index = widgets.encodings_cb.get_active()
    encoding = encoding_options[enc_index]

    widgets.quality_cb.get_model().clear()
    for quality_option in encoding.quality_options:
        widgets.quality_cb.append_text(quality_option.name)

    if encoding.quality_default_index != None:
        widgets.quality_cb.set_active(encoding.quality_default_index)
    else:
        widgets.quality_cb.set_active(0)

def _fill_extension_label():
    enc_index = widgets.encodings_cb.get_active()
    ext = encoding_options[enc_index].extension
    widgets.extension_label.set_text("." + ext)

def _fill_audio_desc():
    enc_index = widgets.encodings_cb.get_active()
    encoding = encoding_options[enc_index]
    widgets.audio_desc.set_markup(encoding.get_audio_description())
   
def _display_selection_in_opts_view():
    profile = _get_current_profile()
    encoding_option = encoding_options[widgets.encodings_cb.get_active()]
    quality_option = encoding_option.quality_options[widgets.quality_cb.get_active()]
    _fill_opts_view(encoding_option, quality_option, profile)

def _fill_opts_view(encoding_option, quality_option, profile):
    args_vals_list = encoding_option.get_args_vals_tuples_list(profile, quality_option)
    text = ""
    for arg_val in args_vals_list:
        k, v = arg_val
        line = str(k) + "=" + str(v) + "\n"
        text = text + line
    
    text_buffer = gtk.TextBuffer()
    text_buffer.set_text(text)
    widgets.opts_view.set_buffer(text_buffer)

def _get_ffmpeg_opts_args_vals_tuples_list():
    buf = widgets.opts_view.get_buffer()
    end = buf.get_end_iter()
    arg_vals = []
    for i in range(0, buf.get_line_count()):
        line_start = buf.get_iter_at_line(i)
        if i == buf.get_line_count() - 1:
            line_end = end
        else:
            line_end = buf.get_iter_at_line(i + 1)
        av_tuple, error = _parse_line(line_start, line_end, buf)
        if error != None:
            errs_str = _("Error on line ") + str(i + 1) + ": " + error + _("\nLine contents: ") \
                       + buf.get_text(line_start, line_end, include_hidden_chars=False)
            return (None, errs_str)
        if av_tuple != None:
            arg_vals.append(av_tuple)
    
    return (arg_vals, None)

def _parse_line(line_start, line_end, buf):
    line = buf.get_text(line_start, line_end, include_hidden_chars=False)
    if len(line) == 0:
        return (None, None)
    if line.find("=") == -1:
        return (None, _("No \'=\' found."))
    sides = line.split("=")
    if len(sides) != 2:
        return (None, _("Number of tokens on line is ")+ str(len(sides)) + _(", should be 2 (key, value)."))
    k = sides[0].strip()
    v = sides[1].strip()
    if len(k) == 0:
        return (None, _("Arg name token is empty."))
    if len(v) == 0:
        return (None, _("Arg value token is empty."))
    try:
        k.decode('ascii')
    except UnicodeDecodeError:
        return (None, _("Non-ascii char in Arg name."))
    try:
        v.decode('ascii')
    except UnicodeDecodeError:
        return (None, _("Non-ascii char in Arg value."))
    if k.find(" ") != -1:
        return (None,  _("Whitespace in Arg name."))
    if v.find(" ") != -1:
        return (None,  _("Whitespace in Arg value."))
        
    return ((k,v), None)
     
def _save_opts_pressed():
    dialogs.save_ffmpep_optsdialog(_save_opts_dialog_callback, FFMPEG_OPTS_SAVE_FILE_EXTENSION)

def _save_opts_dialog_callback(dialog, response_id):
    if response_id == gtk.RESPONSE_ACCEPT:
        file_path = dialog.get_filenames()[0]
        opts_file = open(file_path, "w")
        buf = widgets.opts_view.get_buffer()
        opts_text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), include_hidden_chars=True)
        opts_file.write(opts_text)
        opts_file.close()
        dialog.destroy()
    else:
        dialog.destroy()

def _load_opts_pressed():
    dialogs.load_ffmpep_optsdialog(_load_opts_dialog_callback, FFMPEG_OPTS_SAVE_FILE_EXTENSION)

def _load_opts_dialog_callback(dialog, response_id):
    if response_id == gtk.RESPONSE_ACCEPT:
        filename = dialog.get_filenames()[0]
        args_file = open(filename)
        args_text = args_file.read()
        widgets.opts_view.get_buffer().set_text(args_text)
        dialog.destroy()
    else:
        dialog.destroy()