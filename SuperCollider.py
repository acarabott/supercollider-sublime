import sublime, sublime_plugin
import os
import subprocess
from queue import Queue, Empty
import threading

def enqueue_output(out, queue):
    for line in iter(out.readline, b''):
        queue.put(line)
    out.close()

class SuperColliderStartCommand(sublime_plugin.ApplicationCommand):
    sclang_thread = None
    sclang_process = None
    sclang_queue = None
    sclang_thread = None

    def run(self):
        # start supercollider
        if self.sclang_thread is None or not sclang_thread.isAlive():
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

            self.sclang_process = subprocess.Popen(
                args = args,
                cwd = cwd,
                bufsize = 0,
                stdin = subprocess.PIPE,
                stdout = subprocess.PIPE,
                stderr = subprocess.STDOUT,
                close_fds = close_fds,
                shell = shell
            )

            self.sclang_queue = Queue()
            self.sclang_thread = threading.Thread(
                target=enqueue_output,
                args=(self.sclang_process.stdout, self.sclang_queue)
            )
            self.sclang_thread.daemon = True # thread dies with the program
            self.sclang_thread.start()
            sublime.status_message("Starting SuperCollider")

