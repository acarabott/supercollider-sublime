import sublime, sublime_plugin
import os
import sys
import subprocess
import threading
import tempfile
from queue import Queue, Empty

sc = None

def plugin_loaded():
    global sc
    sc = SuperColliderProcess()

def plugin_unloaded():
    global sc
    if sc is not None:
        sc.stop()
        sc.deactivate_post_view('SublimeText: sclang terminated!\n')

class SuperColliderProcess():
    def __init__(self):
        self.settings = sublime.load_settings("SuperCollider.sublime-settings")
        # load settings
        self.sc_dir = self.settings.get("sc_dir")
        self.sc_exe = self.settings.get("sc_exe")
        self.post_view_max_lines = self.settings.get('max_post_view_lines')
        self.settings.add_on_change('max_post_view_lines',
                                    self.update_post_view_max_lines)
        self.stdout_flag = self.settings.get('stdout_flag')
        self.settings.add_on_change('stdout_flag', self.update_stdout_flag)
        self.open_post_view_in = self.settings.get('open_post_view_in')
        self.settings.add_on_change('open_post_view_in',
                                    self.update_open_post_view_in)

        self.sclang_thread = None
        self.sclang_process = None
        self.sclang_queue = None
        self.sclang_thread = None

        self.post_view_name = 'SuperCollider - Post'
        self.post_view = None
        self.post_view_cache = None
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

    def update_post_view_max_lines(self):
        self.post_view_max_lines = self.settings.get('max_post_view_lines')

    def update_stdout_flag(self):
        self.stdout_flag = self.settings.get('stdout_flag')

    def update_open_post_view_in(self):
        self.open_post_view_in = self.settings.get('open_post_view_in')

    # Interpreter
    # --------------------------------------------------------------------------
    def is_alive(self):
        return (self.sclang_thread is not None and
                self.sclang_thread.isAlive())

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
                queue.put(decoded)
            input.close()
            if self.has_post_view():
                self.deactivate_post_view('SublimeText: sclang terminated!\n')

        # queue and thread for getting sclang output
        self.sclang_queue = Queue()
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

    def stop(self):
        if self.is_alive():
            self.execute("0.exit;")
        else:
            sublime.status_message("sclang not running")

    def execute(self, cmd):
        if self.is_alive():
            self.sclang_process.stdin.write(bytes(cmd + '\x0c', 'utf-8'))
            self.sclang_process.stdin.flush()

    def execute_flagged(self, flag, cmd):
        msg = '"' + self.stdout_flag + flag + self.stdout_flag + '".post;'
        msg += '(' + cmd + ').postln;'

        self.execute(msg)

    def handle_flagged_output(self, output):
        split = output.split(self.stdout_flag)
        action = split[1]
        arg = split[2].rstrip()

        if action == 'open_file':
            if not os.path.isfile(arg):
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

    def post_view_id(self):
        if self.has_post_view():
            return self.post_view.id()
        else:
            return None

    def open_post_view(self):
        # focus the post window if it currently open
        if self.has_post_view():
            old = self.post_view
            window = old.window()
            if window is not None:
                window.focus_view(old)
                return
            else:
                # cache old post view contents
                self.cache_post_view(old.substr(sublime.Region(0, old.size())))
                self.deactivate_post_view('Sublime Text: Window deactivated!\n')

        window = None

        if len(sublime.windows()) is 0:
            sublime.run_command('new_window')

        if self.open_post_view_in == 'window':
            sublime.run_command('new_window')

        window = sublime.active_window()
        self.post_view = window.new_file()

        if self.open_post_view_in == 'pane':
            window.run_command('new_pane')

        self.post_view.set_name(self.post_view_name)
        self.post_view.set_scratch(True)
        self.post_view.settings().set('rulers', 0)
        self.post_view.settings().set('line_numbers', False)

        # update the view with previous view content if possible
        if self.post_view_cache is not None:
            self.post_view.run_command('super_collider_update_post_view', {
                'content': self.post_view_cache,
                'max_lines': self.post_view_max_lines,
                'force_scroll': True
            })
            self.post_view_cache = None

        self.update_post_view()

    def update_post_view(self):
        if self.is_alive() and self.has_post_view():
            try:
                line = self.sclang_queue.get_nowait()
            except Empty:
                pass
            else:
                self.post_view.run_command('super_collider_update_post_view', {
                    'content': line,
                    'max_lines': self.post_view_max_lines
                })

        sublime.set_timeout(self.update_post_view, 20)

    def cache_post_view(self, content):
        self.post_view_cache = content

    def deactivate_post_view(self, msg):
        if self.has_post_view():
            self.post_view.run_command('super_collider_update_post_view', {
                'content': msg,
                'force_scroll': True
            })
            if self.post_view is not None:
                self.post_view.set_name(self.post_view_name + ' - Inactive')
            # self.post_view = None

    def clear_post_view(self, edit):
        if self.has_post_view():
            self.post_view.erase(edit, sublime.Region(0, self.post_view.size()))

# Commands
# ------------------------------------------------------------------------------
class SuperColliderStartInterpreterCommand(sublime_plugin.ApplicationCommand):
    global sc
    def run(self):
        sc.start()
        sc.open_post_view()

    def is_enabled(self):
        return not sc.is_alive()

class SuperColliderStopInterpreterCommand(sublime_plugin.ApplicationCommand):
    global sc

    def run(self):
        sc.stop()

    def is_enabled(self):
        return sc.is_alive()

class SuperColliderUpdatePostViewCommand(sublime_plugin.TextCommand):
    global sc
    def view_is_at_bottom(self):
        layout_h = self.view.layout_extent()[1]
        view_h = self.view.viewport_extent()[1]
        view_y = self.view.viewport_position()[1]
        line_h = self.view.line_height()

        view_taller_than_content = layout_h <= view_h
        at_bottom_of_content = view_y + view_h >= layout_h - line_h

        return view_taller_than_content or at_bottom_of_content

    def run(self, edit, content, max_lines=-1, force_scroll=False):
        # insert text
        self.view.insert(edit, self.view.size(), content)

        # erase overspill
        all_lines = self.view.lines(sublime.Region(0, self.view.size()))
        total_lines = len(all_lines)
        if total_lines > max_lines and max_lines >= 1:
            end = all_lines[total_lines - max_lines].b + 1
            self.view.erase(edit, sublime.Region(0, end))

        # scroll
        if force_scroll or self.view_is_at_bottom():
            self.view.show(self.view.size())

    def is_enabled(self):
        return sc.is_alive()

class SuperColliderOpenPostViewCommand(sublime_plugin.ApplicationCommand):
    global sc
    def run(self):
        sc.open_post_view()

    def is_enabled(self):
        return sc.is_alive()

class SuperColliderClearPostViewCommand(sublime_plugin.TextCommand):
    global sc
    def run(self, edit):
        sc.clear_post_view(edit)

    def is_enabled(self):
        return sc.is_alive()


class SuperColliderEvaluateCommand(sublime_plugin.TextCommand):
    global sc

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
        if expand:
            self.expand_selections()

        for sel in self.view.sel():
            cmd = None

            if sel.a == sel.b:
                # "selection" is a single point
                cmd = self.view.substr(self.view.line(sel))
            else:
                # send actual selection
                cmd = self.view.substr(sel)

            sc.execute(cmd)

    def is_enabled(self):
        return sc.is_alive()

class SuperColliderStartServerCommand(sublime_plugin.ApplicationCommand):
    global sc

    def run(self):
        sc.execute("Server.default.boot;")

    def is_enabled(self):
        return sc.is_alive()

class SuperColliderRebootServerCommand(sublime_plugin.ApplicationCommand):
    global sc

    def run(self):
        sc.execute("Server.default.reboot;")

    def is_enabled(self):
        return sc.is_alive()

class SuperColliderShowServerMeterCommand(sublime_plugin.ApplicationCommand):
    global sc

    def run(self):
        sc.execute("Server.default.meter;")

    def is_enabled(self):
        return sc.is_alive()

class SuperColliderStopCommand(sublime_plugin.ApplicationCommand):
    global sc

    def run(self):
        sc.execute("CmdPeriod.run;")

    def is_enabled(self):
        return sc.is_alive()

class SuperColliderRecompileCommand(sublime_plugin.ApplicationCommand):
    global sc

    def run(self):
        sc.execute('\x18')

    def is_enabled(self):
        return sc.is_alive()

class SuperColliderOpenUserSupportDirCommand(sublime_plugin.ApplicationCommand):
    global sc

    def run(self):
        sc.execute_flagged('open_dir', 'Platform.userConfigDir')

    def is_enabled(self):
        return sc.is_alive()

class SuperColliderOpenStartupFileCommand(sublime_plugin.ApplicationCommand):
    global sc

    def run(self):
        sc.execute_flagged('open_file',
                           'Platform.userConfigDir +/+ "startup.scd"')

    def is_enabled(self):
        return sc.is_alive()

class SuperColliderListener(sublime_plugin.EventListener):
    def on_close(self, view):
        global sc
        if sc is not None and view.id() is sc.post_view_id():
            content = view.substr(sublime.Region(0, view.size()))
            sc.cache_post_view(content)
