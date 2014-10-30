import sublime, sublime_plugin
import os
import subprocess
from queue import Queue, Empty
import threading

def enqueue_output(out, queue):
    for line in iter(out.readline, b''):
        queue.put(line)
    out.close()

class SuperColliderProcess():
    sclang_thread = None
    sclang_process = None
    sclang_queue = None
    sclang_thread = None

    post_view_name = "SuperCollider - Post"
    post_view = None

    def start():
        if SuperColliderProcess.is_alive():
            return

        settings = sublime.load_settings("SuperCollider.sublime-settings")
        sc_dir = settings.get("sc_dir")
        sc_exe = settings.get("sc_exe")

        args = ['', '-i', 'sublime']
        cwd = None
        close_fds = None
        shell = None

        if os.name is 'posix':
            args[0] = sc_dir + sc_exe
            close_fds = True
            shell = False
        else:
            args[0] = sc_exe
            cwd = sc_dir
            close_fds = False
            shell = True

        SuperColliderProcess.sclang_process = subprocess.Popen(
            args = args,
            cwd = cwd,
            bufsize = 0,
            stdin = subprocess.PIPE,
            stdout = subprocess.PIPE,
            stderr = subprocess.STDOUT,
            close_fds = close_fds,
            shell = shell
        )

        SuperColliderProcess.sclang_queue = Queue()
        SuperColliderProcess.sclang_thread = threading.Thread(
            target = enqueue_output,
            args = (
                SuperColliderProcess.sclang_process.stdout,
                SuperColliderProcess.sclang_queue
            )
        )
        SuperColliderProcess.sclang_thread.daemon = True #dies with the program
        SuperColliderProcess.sclang_thread.start()
        sublime.status_message("Starting SuperCollider")

    def is_alive():
        return (SuperColliderProcess.sclang_thread is not None and
                SuperColliderProcess.sclang_thread.isAlive())

    def execute(cmd):
        SuperColliderProcess.sclang_process.stdin.write(bytes(cmd, 'utf-8'))
        SuperColliderProcess.sclang_process.stdin.write(bytes("\x0c", 'utf-8'))
        SuperColliderProcess.sclang_process.stdin.flush()

    def has_post_view():
        return SuperColliderProcess.post_view is not None

    def create_post_view():
        if len(sublime.windows()) is 0:
            sublime.run_command('new_window')

        # TODO add hook when post view closed
        # TODO set post_buffer_id to None when all closed
        # TODO return to original view
        # TODO clear buffer if too big?
        window = sublime.active_window()
        post_view = window.new_file()
        post_view.set_name(SuperColliderProcess.post_view_name)
        post_view.set_scratch(True)
        post_view.settings().set('rulers', 0)

        SuperColliderProcess.post_view = post_view

        sublime.set_timeout(SuperColliderProcess.update_post_view, 100)

    def update_post_view():
        if SuperColliderProcess.has_post_view():
            SuperColliderProcess.post_view.run_command('super_collider_update_post_window')
            sublime.set_timeout(SuperColliderProcess.update_post_view, 100)
        else:
            sublime.status_message("SCLang has no post window!")

class SuperColliderUpdatePostWindowCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        if SuperColliderProcess.has_post_view():
            SuperColliderProcess.post_view.insert(edit, 0, "Hi!")
        else:
            sublime.status_message("SCLang has no post window!")

class SuperColliderStartCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        SuperColliderProcess.start()

class SuperColliderStopCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        if SuperColliderProcess.is_alive():
            SuperColliderProcess.execute("0.exit;")
            sublime.status_message("Stopped SCLang")
        else:
            sublime.status_message("SCLang not started")

class SuperColliderPostCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        SuperColliderProcess.window_has_post_view()

class SuperColliderCreatePostWindow(sublime_plugin.ApplicationCommand):
    def run(self):
        SuperColliderProcess.create_post_view()