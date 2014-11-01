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

    post_view_file_prefix = 'SuperCollider - Post - '
    post_view_file = None
    post_view = None

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
        SuperColliderProcess.create_post_view_file()
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
        SuperColliderProcess.remove_post_view_file()

    def is_alive():
        return (SuperColliderProcess.sclang_thread is not None and
                SuperColliderProcess.sclang_thread.isAlive())

    def execute(cmd):
        if SuperColliderProcess.sclang_process is None:
            sublime.status_message("sclang not running")
            return

        SuperColliderProcess.sclang_process.stdin.write(bytes(cmd + '\x0c', 'utf-8'))
        SuperColliderProcess.sclang_process.stdin.flush()

    def has_post_view_file():
        return SuperColliderProcess.post_view_file is not None

    def has_post_view():
        return SuperColliderProcess.post_view is not None

    def create_post_view_file():
        if SuperColliderProcess.post_view_file is None:
            SuperColliderProcess.post_view_file = tempfile.NamedTemporaryFile(
                buffering = 1,
                prefix = SuperColliderProcess.post_view_file_prefix
            )

    def start_post_view_updates():
        if SuperColliderProcess.post_view.is_loading():
            sublime.set_timeout(SuperColliderProcess.start_post_view_updates, 50)
        else:
            SuperColliderProcess.update_post_view()

    def open_post_view():
        if len(sublime.windows()) is 0:
            sublime.run_command('new_window')

        window = sublime.active_window()
        post_view = window.open_file(SuperColliderProcess.post_view_file.name)
        post_view.set_scratch(True)
        post_view.settings().set('rulers', 0)

        SuperColliderProcess.post_view = post_view
        SuperColliderProcess.start_post_view_updates()

    def update_post_view():
        if SuperColliderProcess.has_post_view_file():
            SuperColliderProcess.post_view.run_command('super_collider_update_post_window')
            sublime.set_timeout(SuperColliderProcess.update_post_view, 50)
        else:
            sublime.status_message("sclang has no post window!")

    def remove_post_view_file():
        SuperColliderProcess.post_view_file.close()
        SuperColliderProcess.post_view_file = None

    def remove_post_view():
        SuperColliderProcess.post_view.set_name(SuperColliderProcess.post_view_file_prefix + 'Closed')
        SuperColliderProcess.post_view = None


class SuperColliderUpdatePostWindowCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        if SuperColliderProcess.is_alive():
            if SuperColliderProcess.has_post_view():
                view = SuperColliderProcess.post_view
                try:
                    line = SuperColliderProcess.sclang_queue.get_nowait()
                except Empty:
                    pass
                else:
                    try:
                        view.insert(edit, view.size(), line)
                        if SuperColliderProcess.sclang_queue.empty():
                            view.run_command('save')
                            view.show(view.size())
                    except UnicodeDecodeError:
                        sublime.status_message("sclang Encoding error!")
            else:
                sublime.status_message("sclang has no post window!")
        else:
            sublime.status_message("sclang is not running!")

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
        if not SuperColliderProcess.has_post_view_file():
            SuperColliderProcess.create_post_view_file()

        SuperColliderProcess.open_post_view()

class SuperColliderTest(sublime_plugin.ApplicationCommand):
    def run(self):
        SuperColliderProcess.execute("\"hi\".postln;")

class SuperColliderLoop(sublime_plugin.ApplicationCommand):
    def run(self):
        SuperColliderProcess.execute("{inf.do{|x| x.postln; 0.5.wait; }}.fork")

class SuperColliderListener(sublime_plugin.EventListener):
    def check_for_post_views(self, file_name):
        count = 0
        for window in sublime.windows():
            if window.find_open_file(file_name) is not None:
                count += 1
        return count

    def on_close(self, view):
        if SuperColliderProcess.has_post_view_file():
            if view.file_name() == SuperColliderProcess.post_view_file.name:
                if self.check_for_post_views(view.file_name()) is 0:
                    SuperColliderProcess.remove_post_view_file()

# TODO clean up temporary file on quit
# TODO add hook when post view closed
# TODO return to original view
# TODO clear buffer if too big? - option
# TODO notify when sclang is quit
# TODO if re-open last tab and context SC, then open new post window