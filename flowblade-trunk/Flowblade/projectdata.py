"""
Module contains objects used to capture project data.
"""
import gtk
import multiprocessing
import mlt
import md5
import os
import time
import thread
import threading

import appconsts
import editorpersistance
import cliprenderer
import mltprofiles
import respaths
import sequence
import utils

PROJECT_FILE_EXTENSION = ".flb"

THUMB_WIDTH = 40
THUMB_HEIGHT = 30
FALLBACK_THUMB = "fallback_thumb.png"

# Singleton
thumbnail_thread = None

class Project:
    """
    Collection of all the data edited as a single unit.
    
    Contains collection of media files and one or more sequences
    Only one sequence is edited at a time.
    """
    def __init__(self, profile): #profile is mlt.Profile here, made using file path
        self.name = _("untitled") + PROJECT_FILE_EXTENSION
        self.profile = profile
        self.profile_desc = profile.description()
        self.bins = []
        self.media_files = {} # MediaFile.id(key) -> MediaFile object(value)
        self.sequences = []
        self.next_media_file_id = 0 
        self.next_bin_number = 1 # This is for creating name for new bin 
        self.next_seq_number = 1 # This is for creating name for new bin
        self.last_save_path = None
        
        # c_seq is the currently edited Sequence
        self.add_unnamed_sequence()
        self.c_seq = self.sequences[0]
        
        # c_bin is the currently displayed bin
        self.add_unnamed_bin()
        self.c_bin = self.bins[0]
        
        # We're running a thumbnail thread here.
        self.start_thumbnail_thread()
    
    def start_thumbnail_thread(self):
        # Thumbnails are made in thread to avoid some MLT crashes
        global thumbnail_thread
        if thumbnail_thread == None:
            thumbnail_thread = ThumbnailThread()
            thumbnail_thread.set_context(self.profile)
            thumbnail_thread.start()

    def add_media_file(self, file_path):
        """
        Adds media file to project if exists and file is of right type.
        """
        # Check and split path
        if not os.path.exists(file_path):
            pass #not impl
            
        (dir, file_name) = os.path.split(file_path)
        (name, ext) = os.path.splitext(file_name)
        
        # Get media type
        media_type = sequence.get_media_type(file_path)
        
        # Get length and icon
        if media_type == appconsts.AUDIO:
            icon_path = respaths.IMAGE_PATH + "audio_file.png" # icon's from Oxygen theme, check licence sometimes
            length = thumbnail_thread.get_file_length(file_path)
        else: # For non-audio we need write a thumbbnail file and get file lengh while we're at it
            (icon_path, length) = thumbnail_thread.write_image(file_path)
        
        # Create media file object
        media_file = MediaFile(self.next_media_file_id, file_path, 
                               file_name, media_type, length, icon_path)
            
        self._add_media_object(media_file)

    def add_color_clip(self, clip_name, gdk_color_str):
        """
        Adds color clip to project.
        """
        color_clip = BinColorClip(self.next_media_file_id, clip_name,
                                  gdk_color_str)
                                  
        self._add_media_object(color_clip)

    def _add_media_object(self, media_object):
        """
        Adds media file or color clip to project data structures.
        """
        self.media_files[media_object.id] = media_object
        self.next_media_file_id += 1

        # Add to bin
        self.c_bin.file_ids.append(media_object.id)

    def media_file_exists(self, file_path):
        for key, media_file in self.media_files.items():
            if media_file.type == appconsts.PATTERN_PRODUCER:
                continue
            if file_path == media_file.path:
                return True
        return False

    def get_media_file_for_path(self, file_path):
        for key, media_file in self.media_files.items():
            if media_file.type == appconsts.PATTERN_PRODUCER:
                continue
            if file_path == media_file.path:
                return media_file
        return None

    def delete_media_file_from_current_bin(self, media_file):
        self.c_bin.file_ids.pop(media_file.id)

    def add_unnamed_bin(self):
        """
        Adds bin with default name.
        """
        name = _("bin_") + str(self.next_bin_number)
        self.bins.append(Bin(name))
        self.next_bin_number += 1
    
    def add_unnamed_sequence(self):
        """
        Adds sequence with default name
        """
        name = _("sequence_") + str(self.next_seq_number)
        seq = sequence.Sequence(self.profile, name)
        seq.create_default_tracks()
        self.sequences.append(seq)
        self.next_seq_number += 1
        
    def exit_clip_renderer_process(self):
        pass
        

class MediaFile:
    """
    Media file that can added to and edited in Sequence.
    """
    def __init__(self, id, file_path, name, type, length, icon_path):
        self.id = id
        self.path = file_path
        self.name = name
        self.type = type
        self.length = length
        self.icon_path = icon_path
        self.icon = None
        self.create_icon()

        self.mark_in = -1
        self.mark_out = -1
        
    def create_icon(self):
        try:
            icon = gtk.gdk.pixbuf_new_from_file(self.icon_path)
            self.icon = icon.scale_simple(THUMB_WIDTH, THUMB_HEIGHT, \
                                          gtk.gdk.INTERP_BILINEAR)
        except:
            print "failed to make icon from:", self.icon_path
            self.icon_path = respaths.IMAGE_PATH + FALLBACK_THUMB
            icon = gtk.gdk.pixbuf_new_from_file(self.icon_path)
            self.icon = icon.scale_simple(THUMB_WIDTH, THUMB_HEIGHT, \
                                          gtk.gdk.INTERP_BILINEAR)

class BinColorClip:
    """
    Color Clip that can added to and edited in Sequence.
    """   
    def __init__(self, id, name, gdk_color_str):
        self.id = id
        self.name = name
        self.gdk_color_str = gdk_color_str
        self.length = 15000
        self.type = appconsts.PATTERN_PRODUCER
        self.icon = None
        self.create_icon()
        self.patter_producer_type = appconsts.COLOR_CLIP

        self.mark_in = -1
        self.mark_out = -1

    def create_icon(self):
        icon = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, False, 8, THUMB_WIDTH, THUMB_HEIGHT)
        pixel = utils.gdk_color_str_to_int(self.gdk_color_str)
        icon.fill(pixel)
        self.icon = icon

class Bin:
    """
    Group of media files
    """
    def __init__(self, name="name"):
        self.name  = name # Displayed name
        self.file_ids = [] # List of media files ids in the bin.
                           # Ids are increasing integers given in 
                           # Project.add_media_file(...)
        
        
# THIS MAY NEED SOME TIDYING UP
class ThumbnailThread(threading.Thread):

    def run(self):
        """
        Runs and blocks 
        """
        # There are seg faults in MLT unless this...?
        self.file_path = ""
        self.thumbnail_path = ""
        self.consumer = None
        self.producer = None
        self.running = True
        self.stopped = False

        while self.running:
            time.sleep(1)
            
        self.stopped = True
        
    def set_context(self, profile):
        self.profile = profile
    
    def write_image(self, file_path):
        """
        Writes thumbnail image from file producer
        """
        # Get data
        self.file_path = file_path
        md_str = md5.new(file_path).hexdigest()
        self.thumbnail_path = editorpersistance.prefs.thumbnail_folder + "/" + md_str +  ".png"
        
        # Create consumer
        self.consumer = mlt.Consumer(self.profile, "avformat", 
                                     self.thumbnail_path)
        self.consumer.set("real_time", 0)
        self.consumer.set("vcodec", "png")

        # Create one frame producer
        self.producer = mlt.Producer(self.profile, \
                                     '%s' %  self.file_path)
        length = self.producer.get_length()
        frame = length / 2
        self.producer = self.producer.cut(frame, frame)

        # Connect and write image
        self.consumer.connect(self.producer)
        self.consumer.run()
        
        return (self.thumbnail_path, length)

    def get_file_length(self, file_path):
        # This is used for audio files which don't need a thumbnail written
        # but do need file length known
        # Get data
        self.file_path = file_path

        # Create one frame producer
        self.producer = mlt.Producer(self.profile, \
                                     '%s' %  self.file_path)
        return self.producer.get_length()


    def shutdown(self):
        if self.consumer != None:
            self.consumer.stop()
        self.running = False
    

# ------------------------------- MODULE FUNCTIONS
def get_default_project():
    """
    Creates the project displayed at start up.
    """
    profile = mltprofiles.get_profile_for_index(editorpersistance.prefs.default_profile_index)
    project = Project(profile)
    return project


    
    
    