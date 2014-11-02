import sublime, sublime_plugin
import os
import sys
import subprocess
import threading
import tempfile
from queue import Queue, Empty

def view_is_at_bottom(view):
    layout_h = view.layout_extent()[1]
    view_h = view.viewport_extent()[1]
    view_y = view.viewport_position()[1]
    line_h = view.line_height()

    view_taller_than_content = layout_h <= view_h
    at_bottom_of_content = view_y + view_h >= layout_h - line_h

    return view_taller_than_content or at_bottom_of_content

def plugin_unloaded():
    SuperColliderProcess.stop()
    SuperColliderProcess.deactivate_post_view('SublimeText: sclang terminated!\n')

class SuperColliderProcess():
    settings = sublime.load_settings("SuperCollider.sublime-settings")
    sclang_thread = None
    sclang_process = None
    sclang_queue = None
    sclang_thread = None

    post_view_name = 'SuperCollider - Post'
    post_view = None
    post_view_cache = None
    post_view_max_lines = None
    # the post view buffer is kept alive, even when the views into it are closed
    # with this cache, we can restore the previous state when re-opening the
    # window
    # Just trying to pull the content from the view doesn't work as sometimes
    # content is empty (problem with async timeout? being garbage collected?)
    # Instead using an explicit cache, updated lazily when view is closed and
    # new view being opened

    def update_post_view_max_lines():
        SuperColliderProcess.post_view_max_lines = SuperColliderProcess.settings.get('max_post_view_lines')

    def start():
        if SuperColliderProcess.is_alive():
            sublime.status_message("sclang already running!")
            return

        # load settings
        sc_dir = SuperColliderProcess.settings.get("sc_dir")
        sc_exe = SuperColliderProcess.settings.get("sc_exe")
        SuperColliderProcess.update_post_view_max_lines()
        SuperColliderProcess.settings.add_on_change('max_post_view_lines',
            SuperColliderProcess.update_post_view_max_lines)


        # create subprocess
        path = None
        cwd = None
        close_fds = None
        shell = None

        if os.name is 'posix':
            path = sc_dir + sc_exe
            close_fds = True
            shell = False
        else:
            path = sc_exe
            cwd = sc_dir
            close_fds = False
            shell = True

        SuperColliderProcess.sclang_process = subprocess.Popen(
            args = [path, '-i', 'sublime'],
            cwd = cwd,
            bufsize = 0,
            stdin = subprocess.PIPE,
            stdout = subprocess.PIPE,
            stderr = subprocess.STDOUT,
            close_fds = close_fds,
            shell = shell
        )

        # create post window temp file
        SuperColliderProcess.open_post_view()

        # create post window update queue and thread
        def enqueue_output(input, queue):
            for line in iter(input.readline, b''):
                queue.put(line.decode('utf-8'))
            input.close()
            if SuperColliderProcess.has_post_view():
                SuperColliderProcess.deactivate_post_view('SublimeText: sclang terminated!\n')

        SuperColliderProcess.sclang_queue = Queue()
        SuperColliderProcess.sclang_thread = threading.Thread(
            target = enqueue_output,
            args = (
                SuperColliderProcess.sclang_process.stdout,
                SuperColliderProcess.sclang_queue
            )
        )

        SuperColliderProcess.sclang_thread.daemon = True # dies with the program
        SuperColliderProcess.sclang_thread.start()
        sublime.status_message("Starting SuperCollider")

    def stop():
        if SuperColliderProcess.is_alive():
            SuperColliderProcess.execute("0.exit;")
        else:
            sublime.status_message("sclang not running")

    def is_alive():
        return (SuperColliderProcess.sclang_thread is not None and
                SuperColliderProcess.sclang_thread.isAlive())

    def execute(cmd):
        if SuperColliderProcess.sclang_process is None:
            sublime.status_message("sclang not running")
            return

        SuperColliderProcess.sclang_process.stdin.write(bytes(cmd + '\x0c', 'utf-8'))
        SuperColliderProcess.sclang_process.stdin.flush()

    def has_post_view():
        return SuperColliderProcess.post_view is not None

    def post_view_id():
        if SuperColliderProcess.has_post_view():
            return SuperColliderProcess.post_view.id()
        else:
            return None

    def update_post_view():
        if SuperColliderProcess.is_alive() and SuperColliderProcess.has_post_view():
            try:
                line = SuperColliderProcess.sclang_queue.get_nowait()
            except Empty:
                pass
            else:
                SuperColliderProcess.post_view.run_command('super_collider_update_post_view', {
                    'content': line,
                    'max_lines': SuperColliderProcess.post_view_max_lines
                })

        sublime.set_timeout(SuperColliderProcess.update_post_view, 20)

    def cache_post_view(content):
        SuperColliderProcess.post_view_cache = content

    def deactivate_post_view(msg):
        if SuperColliderProcess.has_post_view():
            SuperColliderProcess.post_view.run_command('super_collider_update_post_view', {
                'content': msg,
                'force_scroll': True
            })
            if SuperColliderProcess.post_view is not None:
                SuperColliderProcess.post_view.set_name(SuperColliderProcess.post_view_name + ' - Inactive')
            SuperColliderProcess.post_view = None

    def open_post_view():
        if len(sublime.windows()) is 0:
            sublime.run_command('new_window')

        old_view = None

        if SuperColliderProcess.has_post_view():
            old_view = SuperColliderProcess.post_view
            # switch to the post window if it is in the current window
            for window in sublime.windows():
                if window.views().count(old_view):
                    window.focus_view(old_view)
                    return
                else:
                    # cache old post view contents
                    content = old_view.substr(sublime.Region(0, old_view.size()))
                    SuperColliderProcess.cache_post_view(content)

        window = sublime.active_window()

        # create new post view
        post_view = window.new_file()
        post_view.set_name(SuperColliderProcess.post_view_name)
        post_view.set_scratch(True)
        post_view.settings().set('rulers', 0)
        post_view.settings().set('line_numbers', False)

        # update the view with previoius view content if possible
        if SuperColliderProcess.post_view_cache is not None:
            post_view.run_command('super_collider_update_post_view', {
                'content': SuperColliderProcess.post_view_cache,
                'max_lines': SuperColliderProcess.post_view_max_lines,
                'force_scroll': True
            })
            SuperColliderProcess.post_view_cache = None

        # deactivate old view
        if old_view is not None:
            SuperColliderProcess.deactivate_post_view('Sublime Text: This post window now deactivated!\n')

        # update post view to newly created
        SuperColliderProcess.post_view = post_view
        SuperColliderProcess.update_post_view()

class SuperColliderStartCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        SuperColliderProcess.start()

class SuperColliderStopCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        SuperColliderProcess.stop()

class SuperColliderUpdatePostViewCommand(sublime_plugin.TextCommand):
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
        if force_scroll or view_is_at_bottom(self.view):
            self.view.show(self.view.size())

class SuperColliderOpenPostViewCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        SuperColliderProcess.open_post_view()

class SuperColliderListener(sublime_plugin.EventListener):
    def on_close(self, view):
        if view.id() is SuperColliderProcess.post_view_id():
            content = view.substr(sublime.Region(0, view.size()))
            SuperColliderProcess.cache_post_view(content)

class SuperColliderSendCommand(sublime_plugin.TextCommand):
    def run(self, edit, expand=False):
        if expand:
            reached_limit = False
            expanded = False
            while not reached_limit:
                prev = list(map(
                    lambda sel: sublime.Region(sel.a, sel.b),
                    self.view.sel()
                ))
                # nested selections get merged by this, so nested selections
                # get reduced
                self.view.run_command('expand_selection', {'to': 'brackets'})

                sels = enumerate(self.view.sel())
                if all(sel.a == prev[i].a and sel.b == prev[i].b for i, sel in sels):
                    reached_limit = True

                if not reached_limit:
                    expanded = True

            # if we expanded, expand further to whole line, makes it possible
            # to execute blocks without surrouding with parenthesis
            if expanded:
                self.view.run_command('expand_selection', {'to': 'line'})

        for sel in self.view.sel():
            cmd = None

            if sel.a == sel.b:
                # "selection" is a single point
                cmd = self.view.substr(self.view.line(sel))
            else:
                # send actual selection
                cmd = self.view.substr(sel)

            SuperColliderProcess.execute(cmd)

class SuperColliderLoop(sublime_plugin.ApplicationCommand):
    def run(self):
        SuperColliderProcess.execute("{inf.do{|x| x.postln; 0.1.wait; }}.fork")

class SuperColliderTest(sublime_plugin.ApplicationCommand):
    def run(self, count):
        SuperColliderProcess.execute(str(count) + ".do {|i| i.postln; };")

# TODO if post window moved to another pane/window, can't restore
# TODO if re-open last tab and context SC, then open new post window
# TODO option on where to open post window: new tab, new group, new window, terminal
# TODO refocus on original window on open_post_view
# TODO re-write with plugin_loaded and process instance?