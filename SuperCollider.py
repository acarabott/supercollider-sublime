import sublime, sublime_plugin
import os
import sys
import subprocess
import threading
import tempfile
from queue import Queue, Empty

class SuperColliderProcess():
    sclang_thread = None
    sclang_process = None
    sclang_queue = None
    sclang_thread = None

    post_view_name = 'SuperCollider - Post'
    post_view = None
    post_view_cache = None

    def start():
        if SuperColliderProcess.is_alive():
            sublime.status_message("sclang already running!")
            return

        # load settings
        settings = sublime.load_settings("SuperCollider.sublime-settings")
        sc_dir = settings.get("sc_dir")
        sc_exe = settings.get("sc_exe")

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
        SuperColliderProcess.execute("0.exit;")

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

    def update_post_view():
        if SuperColliderProcess.has_post_view():
            SuperColliderProcess.post_view.run_command('super_collider_update_post_view')
            sublime.set_timeout(SuperColliderProcess.update_post_view, 50)
        else:
            sublime.status_message("sclang has no post window!")

    def cache_post_view(content):
        SuperColliderProcess.post_view_cache = content

    def open_post_view():
        if len(sublime.windows()) is 0:
            sublime.run_command('new_window')

        window = sublime.active_window()
        post_view = window.new_file()
        post_view.set_name(SuperColliderProcess.post_view_name)
        post_view.set_scratch(True)
        post_view.settings().set('rulers', 0)

        if SuperColliderProcess.has_post_view():
            view = SuperColliderProcess.post_view
            content = view.substr(sublime.Region(0, view.size()))
            SuperColliderProcess.cache_post_view(content)

        if SuperColliderProcess.post_view_cache is not None:
            post_view.run_command('super_collider_clone_post_view', {
                'content': SuperColliderProcess.post_view_cache
            })
            SuperColliderProcess.post_view_cache = None

        SuperColliderProcess.post_view = post_view
        SuperColliderProcess.update_post_view()

    def remove_post_view():
        SuperColliderProcess.post_view.set_name(post_view_name + ' - Closed')
        SuperColliderProcess.post_view = None


class SuperColliderUpdatePostViewCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        if SuperColliderProcess.is_alive():
            try:
                line = SuperColliderProcess.sclang_queue.get_nowait()
            except Empty:
                pass
            else:
                self.view.insert(edit, self.view.size(), line)
                self.view.show(self.view.size())
        else:
            sublime.status_message("sclang not running")

class SuperColliderClonePostViewCommand(sublime_plugin.TextCommand):
    def run(self, edit, content):
        self.view.insert(edit, 0, content)
        self.view.show(self.view.size())

class SuperColliderStartCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        SuperColliderProcess.start()

class SuperColliderStopCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        if SuperColliderProcess.is_alive():
            SuperColliderProcess.stop()
            sublime.status_message("Stopped sclang")
        else:
            sublime.status_message("sclang not started")

class SuperColliderOpenPostViewCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        SuperColliderProcess.open_post_view()

class SuperColliderTest(sublime_plugin.ApplicationCommand):
    def run(self):
        SuperColliderProcess.execute("\"hi\".postln;")

class SuperColliderLoop(sublime_plugin.ApplicationCommand):
    def run(self):
        SuperColliderProcess.execute("{inf.do{|x| x.postln; 0.5.wait; }}.fork")

class SuperColliderListener(sublime_plugin.EventListener):
    def on_close(self, view):
        if SuperColliderProcess.has_post_view():
            if view.id() is SuperColliderProcess.post_view.id():
                content = view.substr(sublime.Region(0, view.size()))
                SuperColliderProcess.cache_post_view(content)

# TODO add hook when post view closed
# TODO label post window when closed
# TODO return to original view
# TODO clear buffer if too big? - option
# TODO notify when sclang is quit
# TODO if re-open last tab and context SC, then open new post window