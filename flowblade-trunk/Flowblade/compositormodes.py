"""
Module handles editing positions and clip ends of compositors on timeline.
"""
import edit
import editorstate
from editorstate import current_sequence
import tlinewidgets
import updater

TRIM_HANDLE_WIDTH = 10
MOVE_EDIT = 0
TRIM_EDIT = 1

compositor = None
edit_data = None
sub_mode = None
prev_edit_mode = None

def set_compositor_mode(new_compositor):
    global prev_edit_mode
    prev_edit_mode = editorstate.EDIT_MODE()
    editorstate.edit_mode = editorstate.COMPOSITOR_EDIT
    set_compositor_selected(new_compositor)

def set_compositor_selected(new_compositor):
    global compositor
    if compositor != None:
        compositor.selected = False
    compositor = new_compositor
    compositor.selected = True

def clear_compositor_selection():
    global compositor
    if compositor == None:
        return
    compositor.selected = False
    compositor = None

def delete_current_selection():
    global compositor
    if compositor == None:
        return
    data = {"compositor":compositor}
    action = edit.delete_compositor_action(data)
    action.do_edit()
    compositor.selected = False # this may return in undo?
    compositor = None

def mouse_press(event, frame):
    track = current_sequence().tracks[compositor.transition.a_track]

    global edit_data, sub_mode
    
    compositor_y = tlinewidgets._get_track_y(track.id) - tlinewidgets.COMPOSITOR_HEIGHT_OFF
    
    if abs(event.x - tlinewidgets._get_frame_x(compositor.clip_in)) < TRIM_HANDLE_WIDTH:
        edit_data = {"clip_in":compositor.clip_in,
                     "clip_out":compositor.clip_out,
                     "trim_is_clip_in":True,
                     "compositor_y":  compositor_y}
        tlinewidgets.set_edit_mode(edit_data, tlinewidgets.draw_compositor_trim)
        sub_mode = TRIM_EDIT
    elif abs(event.x - tlinewidgets._get_frame_x(compositor.clip_out + 1)) < TRIM_HANDLE_WIDTH:
        edit_data = {"clip_in":compositor.clip_in,
                     "clip_out":compositor.clip_out,
                     "trim_is_clip_in":False,
                     "compositor_y": compositor_y}
        tlinewidgets.set_edit_mode(edit_data, tlinewidgets.draw_compositor_trim)
        sub_mode = TRIM_EDIT
    else:
        edit_data = {"press_frame":frame,
                     "current_frame":frame,
                     "clip_in":compositor.clip_in,
                     "clip_length":(compositor.clip_out - compositor.clip_in + 1),
                     "compositor_y": compositor_y}
        tlinewidgets.set_edit_mode(edit_data, tlinewidgets.draw_compositor_move_overlay)
        sub_mode = MOVE_EDIT
    updater.repaint_tline()

def mouse_move(x, y, frame, state):
    global edit_data
    if sub_mode == TRIM_EDIT:
        # bounds check
        if edit_data["trim_is_clip_in"] == True:
            if frame > edit_data["clip_out"]:
                frame = edit_data["clip_out"]
            edit_data["clip_in"] = frame
        else:
            if frame < edit_data["clip_in"]:
                frame = edit_data["clip_in"]
            edit_data["clip_out"] = frame
        if edit_data["clip_in"] < 0:
            edit_data["clip_in"] = 0
        if edit_data["clip_out"] < 0:
            edit_data["clip_out"] = 0
    else:
        edit_data["current_frame"] = frame

    updater.repaint_tline()
    
def mouse_release(x, y, frame, state):
    editorstate.edit_mode = prev_edit_mode
    if editorstate.edit_mode == editorstate.INSERT_MOVE:
        tlinewidgets.set_edit_mode(None, tlinewidgets.draw_insert_overlay)
    else:
        tlinewidgets.set_edit_mode(None, tlinewidgets.draw_overwrite_overlay)

    if sub_mode == TRIM_EDIT:
        # bounds check
        if edit_data["trim_is_clip_in"] == True:
            if frame > edit_data["clip_out"]:
                frame = edit_data["clip_out"]
            edit_data["clip_in"] = frame
        else:
            if frame < edit_data["clip_in"]:
                frame = edit_data["clip_in"]
            edit_data["clip_out"] = frame
        if edit_data["clip_in"] < 0:
            edit_data["clip_in"] = 0
        if edit_data["clip_out"] < 0:
            edit_data["clip_out"] = 0
        data = {"compositor":compositor,
                "clip_in":edit_data["clip_in"],
                "clip_out":edit_data["clip_out"]}
        action = edit.move_compositor_action(data)
        action.do_edit()
    else:
        press_frame = edit_data["press_frame"]
        current_frame = frame
        delta = current_frame - press_frame

        data = {"compositor":compositor,
                "clip_in":compositor.clip_in + delta,
                "clip_out":compositor.clip_out + delta}
        if data["clip_in"] < 0:
            data["clip_in"] = 0
        if data["clip_out"] < 0:
            data["clip_out"] = 0
        action = edit.move_compositor_action(data)
        action.do_edit()
    
    updater.repaint_tline()