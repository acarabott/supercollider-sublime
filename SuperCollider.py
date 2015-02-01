import sublime, sublime_plugin
import os
import subprocess
import threading
from collections import deque

TERMINATE_MSG = 'SublimeText: sclang terminated!\n'
SYNTAX_SC = 'Packages/supercollider-sublime/SuperCollider.tmLanguage'
SYNTAX_PLAIN = 'Packages/Text/Plain text.tmLanguage'

sc = None

def plugin_loaded():
    global sc
    sc = SuperColliderProcess()

def plugin_unloaded():
    global sc
    if sc is not None:
        sc.stop()
        sc.deactivate_post_view(TERMINATE_MSG)

class SuperColliderProcess():
    post_view = None

    def __init__(self):
        self.settings = sublime.load_settings("SuperCollider.sublime-settings")

        # load settings
        self.sc_dir = self.settings.get("sc_dir")
        self.settings.add_on_change('sc_dir', self.update_sc_dir)

        self.sc_exe = self.settings.get("sc_exe")
        self.settings.add_on_change('sc_exe', self.update_sc_exe)

        self.post_view_max_lines = self.settings.get('max_post_view_lines')
        self.settings.add_on_change('max_post_view_lines',
                                    self.update_post_view_max_lines)

        self.stdout_flag = self.settings.get('stdout_flag')
        self.settings.add_on_change('stdout_flag', self.update_stdout_flag)

        self.open_post_view_in = self.settings.get('open_post_view_in')
        self.settings.add_on_change('open_post_view_in',
                                    self.update_open_post_view_in)

        self.update_highlight_post_view()
        self.settings.add_on_change('highlight_post_view',
                                    self.update_highlight_post_view)

        self.sclang_thread = None
        self.sclang_process = None
        self.sclang_queue = None
        self.sclang_thread = None

        self.post_view_name = 'SuperCollider - Post'
        self.inactive_post_view_name = self.post_view_name + ' - Inactive'
        self.post_view = None
        self.post_view_cache = None
        self.panel_open = False
        # the post view buffer is kept alive, even when the views into it are
        # closed with this cache, we can restore the previous state when
        # re-opening the window
        # Just trying to pull the content from the view doesn't work as
        # sometimes content is empty (problem with async timeout? being garbage
        # collected?)
        # Instead using an explicit cache, updated lazily when view is closed
        # and new view being opened


    # Settings callbacks
    # --------------------------------------------------------------------------

    def update_sc_dir(self):
        self.sc_dir = self.settings.get('sc_dir')

    def update_sc_exe(self):
        self.sc_exe = self.settings.get('sc_exe')

    def update_post_view_max_lines(self):
        self.post_view_max_lines = self.settings.get('max_post_view_lines')

    def update_stdout_flag(self):
        self.stdout_flag = self.settings.get('stdout_flag')

    def update_open_post_view_in(self):
        self.open_post_view_in = self.settings.get('open_post_view_in')

    def update_highlight_post_view(self):
        self.highlight_post = self.settings.get('highlight_post_view') == 'True'

        if self.has_post_view():
            syntax = SYNTAX_SC if self.highlight_post else SYNTAX_PLAIN
            self.post_view.set_syntax_file(syntax)

    # Interpreter
    # --------------------------------------------------------------------------
    def is_alive(self):
        if (self.sclang_process is None
            or self.sclang_thread is None
            or not self.sclang_thread.isAlive()):
           return False

        self.sclang_process.poll()

        return self.sclang_process.returncode is None

    def start(self):
        if self.is_alive():
            sublime.status_message("sclang already running!")
            return

        # create subprocess
        path = None
        cwd = None
        close_fds = None
        shell = None

        if os.name is 'posix':
            path = self.sc_dir + self.sc_exe
            close_fds = True
            shell = False
        else:
            path = self.sc_exe
            cwd = self.sc_dir
            close_fds = False
            shell = True

        self.sclang_process = subprocess.Popen(
            args = [path, '-i', 'sublime'],
            cwd = cwd,
            bufsize = 0,
            stdin = subprocess.PIPE,
            stdout = subprocess.PIPE,
            stderr = subprocess.STDOUT,
            close_fds = close_fds,
            shell = shell
        )

        # create post window update queue and thread
        # this function is the thread target, it reads input until the process
        # is terminated, after which it closes the input and deactivates post
        def enqueue_output(input, queue):
            for line in iter(input.readline, b''):
                decoded = line.decode('utf-8')
                if self.stdout_flag in decoded:
                    self.handle_flagged_output(decoded)
                queue.append(decoded)
            input.close()
            if self.has_post_view():
                self.deactivate_post_view(TERMINATE_MSG)

        # queue and thread for getting sclang output
        self.sclang_queue = deque()
        self.sclang_thread = threading.Thread(
            target = enqueue_output,
            args = (
                self.sclang_process.stdout,
                self.sclang_queue
            )
        )

        self.sclang_thread.daemon = True # dies with the program
        self.sclang_thread.start()
        sublime.status_message("Starting SuperCollider")

    def kill(self):
        try:
            self.sclang_process.kill()
        except:
            pass

    def stop(self):
        if self.is_alive():
            self.execute("0.exit;")
            sublime.set_timeout(self.kill, 1000)
        else:
            sublime.status_message("stop: sclang not running")

    def write_out(self, cmd, token):
        if self.is_alive():
            self.sclang_process.stdin.write(bytes(cmd + token, 'utf-8'))
            self.sclang_process.stdin.flush()

    def execute(self, cmd):
        self.write_out(cmd, '\x0c')

    def execute_silently(self, cmd):
        self.write_out(cmd, '\x1b')

    def execute_flagged(self, flag, cmd):
        msg = '"' + self.stdout_flag + flag + self.stdout_flag + '".post;'
        msg += '(' + cmd + ').postln;'

        self.execute_silently(msg)

    def handle_flagged_output(self, output):
        split = output.split(self.stdout_flag)
        action = split[1]
        arg = split[2].rstrip()

        if action in ['open_file', 'open_startup']:
            if not os.path.isfile(arg):
                if action == 'open_file':
                    return

                if action == 'open_startup':
                    open(arg, 'a').close()

            if len(sublime.windows()) is 0:
                sublime.run_command('new_window')

            window = sublime.active_window()
            window.open_file(arg)
        elif action == 'open_dir':
            if sublime.platform() == 'osx':
                subprocess.Popen(['open', arg])
            elif sublime.platform() == 'linux':
                subprocess.Popen(['xdg-open', arg])
            elif sublime.platform() == 'windows':
                os.startfile(arg)

    # Post View
    # --------------------------------------------------------------------------
    def has_post_view(self):
        return self.post_view is not None

    def post_view_buffer_id(self):
        if self.has_post_view():
            return self.post_view.buffer_id()
        else:
            return None

    def get_all_post_views(self):
        win_views = [window.views() for window in sublime.windows()]
        return [view for view in win_views for view in view]

    def post_view_visible(self):
        if not self.has_post_view():
            return False

        ids = [view.buffer_id() for view in self.get_all_post_views()]
        return self.post_view_buffer_id() in ids

    def set_post_view(self, view):
        self.post_view = view

    def create_post_view(self, window):
        self.post_view = window.new_file()
        self.post_view.set_name(self.post_view_name)
        # move post view to new pane if set
        if self.open_post_view_in == 'group':
            if window.num_groups() is 1:
                window.run_command('new_pane')
            else:
                window.set_view_index(self.post_view, 1, 0)

        # set post view attributes
        if self.highlight_post:
            self.post_view.set_syntax_file(
                'Packages/supercollider-sublime/SuperCollider.tmLanguage')
        self.post_view.set_name(self.post_view_name)
        self.post_view.set_scratch(True)
        self.post_view.settings().set('rulers', 0)
        self.post_view.settings().set('line_numbers', False)

    def remove_post_view(self):
        self.post_view = None

    def open_post_view(self):
        # create a new window if necessary
        if len(sublime.windows()) is 0:
            sublime.run_command('new_window')

        # remember the original view
        focus_window = sublime.active_window()
        prev_view = focus_window.active_view()

        if self.open_post_view_in == 'panel':
            if not self.panel_open:
                focus_window.run_command("show_panel", {
                    "panel": "output." + self.post_view_name
                })
                self.post_view = focus_window.get_output_panel(
                    self.post_view_name)
                self.panel_open = True
        else:
            # focus the post window if it currently open
            if self.post_view_visible():
                self.post_view.window().focus_view(self.post_view)
                if self.post_view.name() != self.inactive_post_view_name:
                    focus_window.focus_view(prev_view)
                    return
                else:
                    self.post_view.set_name(self.post_view_name)
            else:
                # create a new window if post window should open in it
                if self.open_post_view_in == 'window':
                    sublime.run_command('new_window')

                # create new post view in the active window
                window = sublime.active_window()
                self.create_post_view(window)

        # update the view with previous view content if possible
        if self.post_view_cache is not None:
            self.post_view.run_command('super_collider_update_post_view', {
                'content': self.post_view_cache,
                'max_lines': self.post_view_max_lines,
                'force_scroll': True
            })
            self.post_view_cache = None

        # focus on original view
        focus_window.focus_view(prev_view)

        # start updating post view
        self.update_post_view()

    def update_post_view(self):
        sublime.set_timeout(self.update_post_view, 5)
        if (not self.is_alive()
            or not self.has_post_view()
            or len(self.sclang_queue) is 0):
                return

        get_max = min(100, len(self.sclang_queue))

        content = ""
        for i in range(0, get_max):
            content += self.sclang_queue.popleft()

        self.post_view.run_command('super_collider_update_post_view', {
            'content': content,
            'max_lines': self.post_view_max_lines
        })

    def cache_post_view(self, content):
        self.post_view_cache = content

    def deactivate_post_view(self, msg):
        if self.has_post_view():
            self.post_view.run_command('super_collider_update_post_view', {
                'content': msg,
                'force_scroll': True
            })
            self.post_view.set_name(self.inactive_post_view_name)

    def clear_post_view(self, edit):
        if self.has_post_view():
            self.post_view.erase(edit, sublime.Region(0, self.post_view.size()))

    def open_help(self, word):
        self.execute('HelpBrowser.openHelpFor("' + word + '");')

    def open_class(self, klass):
        cmd = """
            if('{}'.asClass.notNil) {{
                '{}'.asClass.filenameSymbol;
            }} {{
                "{} is not a Class!".postln;
            }}
        """.format(klass, klass, klass)
        self.execute_flagged('open_file', cmd)

# ==============================================================================
# Commands
# ==============================================================================

# ------------------------------------------------------------------------------
# Abstract Command Classes
# ------------------------------------------------------------------------------
class SuperColliderAliveAbstract():
    def is_enabled(self):
        return sc.is_alive()

class SuperColliderDeadAbstract():
    def is_enabled(self):
        return not sc.is_alive()

# ------------------------------------------------------------------------------
# Interpreter Commands
# ------------------------------------------------------------------------------
class SuperColliderStartInterpreterCommand(SuperColliderDeadAbstract,
                                           sublime_plugin.ApplicationCommand):
    def run(self):
        sc.start()
        sc.open_post_view()

class SuperColliderStopInterpreterCommand(SuperColliderAliveAbstract,
                                          sublime_plugin.ApplicationCommand):
    def run(self):
        sc.stop()

class SuperColliderEvaluateCommand(SuperColliderAliveAbstract,
                                   sublime_plugin.TextCommand):

    HIGHLIGHT_KEY = 'supercollider-eval'
    HIGHLIGHT_SCOPE = 'supercollider-eval'

    def expand_selections(self):
        reached_limit = False
        expanded = False
        # expand selection to brackets until the selections are the same as
        # the previous selections (no further expansion possible)
        while not reached_limit:
            old = list(map(lambda s: sublime.Region(s.a, s.b), self.view.sel()))

            # nested selections get merged by this, so number of selections can
            # get reduced
            self.view.run_command('expand_selection', {'to': 'brackets'})

            reached_limit = all(s.a == old[i].a and s.b == old[i].b
                                for i, s, in enumerate(self.view.sel()))

            if not reached_limit:
                expanded = True

        # if we expanded, expand further to whole line, makes it possible
        # to execute blocks without surrouding with parenthesis
        if expanded:
            self.view.run_command('expand_selection', {'to': 'line'})

    def run(self, edit, expand=False):

        # store selection for later restoration
        prev = []
        for sel in self.view.sel():
            prev.append(sel)

        if expand == 'True':
            self.expand_selections()

        for sel in self.view.sel():
            # "selection" is a single point
            if sel.a == sel.b:
                sel = self.view.line(sel)
                self.view.sel().add(sel)

            sc.execute(self.view.substr(sel))

        # highlight
        self.view.add_regions(self.HIGHLIGHT_KEY,
            self.view.sel(),
            self.HIGHLIGHT_SCOPE,
            flags=sublime.DRAW_NO_OUTLINE)

        # clear selection so highlighting will be visible
        self.view.sel().clear()

        sublime.set_timeout(lambda: self.view.sel().add_all(prev), 10)
        # remove highlight and restore selection
        sublime.set_timeout(lambda: self.view.erase_regions(self.HIGHLIGHT_KEY),
                            500)

class SuperColliderStopCommand(SuperColliderAliveAbstract,
                               sublime_plugin.ApplicationCommand):
    def run(self):
        sc.execute("CmdPeriod.run;")

class SuperColliderRecompileCommand(SuperColliderAliveAbstract,
                                    sublime_plugin.ApplicationCommand):
    def run(self):
        sc.execute('\x18')

# ------------------------------------------------------------------------------
# Post View Commands
# ------------------------------------------------------------------------------
class SuperColliderUpdatePostViewCommand(SuperColliderAliveAbstract,
                                         sublime_plugin.TextCommand):
    update_count = 0
    update_every = 20
    inf = float('inf')
    # updating and re-using regions is more performant than creating on the fly
    all_region = sublime.Region(0, 0)
    erase_region = sublime.Region(0, 0)

    def view_is_at_bottom(self):
        return self.view.visible_region().b + 100 > self.view.size()

    def run(self, edit, content, max_lines=-1, force_scroll=False):
        scroll = self.view_is_at_bottom()
        # insert text
        self.view.insert(edit, self.view.size(), content)

        # erase overspill
        if max_lines >= 1 and self.update_count is 0:
            self.all_region.b = self.view.size()
            all_lines = self.view.lines(self.all_region)
            total_lines = len(all_lines)
            if total_lines > max_lines:
                self.erase_region.b = all_lines[total_lines - max_lines].b + 1
                self.view.erase(edit, self.erase_region)

        # scroll
        if scroll or force_scroll:
            # for some reason set_viewport_position doesn't work when no
            # scrolling has occured, i.e. with a cleared post window
            # so we use show in this case
            # set_viewport_position is preferred as animation can be disabled
            if self.view.viewport_position()[1] == 0:
                self.view.show(self.view.size())
            else:
                x = self.view.viewport_position()[0]
                self.view.set_viewport_position((x, self.inf), False)

        self.update_count = (self.update_count + 1) % self.update_every

class SuperColliderOpenPostViewCommand(SuperColliderAliveAbstract,
                                       sublime_plugin.ApplicationCommand):
    def run(self):
        sc.open_post_view()

class SuperColliderClearPostViewCommand(SuperColliderAliveAbstract,
                                        sublime_plugin.TextCommand):
    def run(self, edit):
        sc.clear_post_view(edit)

class SuperColliderCloseInactivePostsCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        active_window = sublime.active_window()
        active_view = active_window.active_view()

        for window in sublime.windows():
            for view in window.views():
                if view.name() == sc.inactive_post_view_name:
                    view.window().focus_view(view)
                    view.window().run_command('close_file')

        active_window.focus_view(active_view)

# ------------------------------------------------------------------------------
# Server Commands
# ------------------------------------------------------------------------------
class SuperColliderStartServerCommand(SuperColliderAliveAbstract,
                                      sublime_plugin.ApplicationCommand):
    def run(self):
        sc.execute("Server.default.boot;")

class SuperColliderRebootServerCommand(SuperColliderAliveAbstract,
                                       sublime_plugin.ApplicationCommand):
    def run(self):
        sc.execute("Server.default.reboot;")

class SuperColliderShowServerMeterCommand(SuperColliderAliveAbstract,
                                          sublime_plugin.ApplicationCommand):
    def run(self):
        sc.execute("Server.default.meter;")

class SuperColliderShowServerWindowCommand(SuperColliderAliveAbstract,
                                           sublime_plugin.ApplicationCommand):
    def run(self):
        sc.execute("Server.default.makeWindow;")

class SuperColliderToggleMute(SuperColliderAliveAbstract,
                              sublime_plugin.ApplicationCommand):
    def run(self):
        sc.execute_silently("""
            if (Server.default.volume.isMuted) {
                Server.default.unmute();
                "Server unmuted".postln;
            } {
                Server.default.mute();
                "Server muted".postln;
            };
        """)

class SuperColliderChangeVolume(SuperColliderAliveAbstract,
                                  sublime_plugin.ApplicationCommand):
    def run(self, change):
        sc.execute_silently("""
            s.volume.volume_({});
            ("Server volume:" + s.volume.volume).postln;
        """.format(change))

class SuperColliderIncreaseVolume(SuperColliderChangeVolume):
    def run(self):
        new_vol = "s.volume.volume + 1.5"
        return super(SuperColliderIncreaseVolume, self).run(new_vol)

class SuperColliderDecreaseVolume(SuperColliderChangeVolume):
    def run(self):
        new_vol = "s.volume.volume - 1.5"
        return super(SuperColliderDecreaseVolume, self).run(new_vol)

class SuperColliderRestoreVolume(SuperColliderChangeVolume):
    def run(self):
        new_vol = "0"
        return super(SuperColliderRestoreVolume, self).run(new_vol)

# ------------------------------------------------------------------------------
# Open Commands
# ------------------------------------------------------------------------------
class SuperColliderOpenClassCommand(SuperColliderAliveAbstract,
                                    sublime_plugin.WindowCommand):
    def run(self):
        view = self.window.active_view()
        sel = view.sel()[0]
        if sel.a != sel.b:
            sc.open_class(view.substr(view.word(sel)));
        else:
            self.window.show_input_panel(caption = "Open Class File for",
                                         initial_text = "",
                                         on_done = lambda x:sc.open_class(x),
                                         on_change = None,
                                         on_cancel = None)

class SuperColliderOpenUserSupportDirCommand(SuperColliderAliveAbstract,
                                             sublime_plugin.ApplicationCommand):
    def run(self):
        sc.execute_flagged('open_dir', 'Platform.userConfigDir')

class SuperColliderOpenStartupFileCommand(SuperColliderAliveAbstract,
                                          sublime_plugin.ApplicationCommand):
    def run(self):
        sc.execute_flagged('open_startup',
                           'Platform.userConfigDir +/+ "startup.scd"')

class SuperColliderHelpCommand(SuperColliderAliveAbstract,
                               sublime_plugin.WindowCommand):
    def run(self):
        view = self.window.active_view()
        sel = view.sel()[0]
        if sel.a != sel.b:
            sc.open_help(view.substr(view.word(sel)))
        else:
            self.window.show_input_panel(caption = "Search Help for",
                                         initial_text = "",
                                         on_done = lambda x:sc.open_help(x),
                                         on_change = None,
                                         on_cancel = None);

# ==============================================================================
# Event Listener
# ==============================================================================
class SuperColliderListener(sublime_plugin.EventListener):
    def on_close(self, view):
        if sc is None:
            return
        if view.buffer_id() != sc.post_view_buffer_id():
            return;
        if sc.post_view_visible():
            if view.id() == sc.post_view.id():
                sc.set_post_view(
                    next(view for view
                         in sc.get_all_post_views()
                         if view.buffer_id() == sc.post_view_buffer_id()))
        else:
            sc.cache_post_view(view.substr(sublime.Region(0, view.size())))
            sc.remove_post_view()

    def on_window_command(self, window, command_name, args):
        if sc is None or not sc.has_post_view() or window is not sc.post_view:
            return

        if command_name == "hide_panel":
            value = sc.post_view.substr(sublime.Region(0, sc.post_view.size()))
            sc.cache_post_view(value)
            sc.panel_open = False
