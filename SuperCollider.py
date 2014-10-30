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

    def start():
        if SuperColliderProcess.isAlive():
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

    def isAlive():
        return (SuperColliderProcess.sclang_thread is not None and
                SuperColliderProcess.sclang_thread.isAlive())

    def execute(cmd):
        SuperColliderProcess.sclang_process.stdin.write(bytes(cmd, 'utf-8'))
        SuperColliderProcess.sclang_process.stdin.write(bytes("\x0c", 'utf-8'))
        SuperColliderProcess.sclang_process.stdin.flush()

class SuperColliderStartCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        SuperColliderProcess.start()

class SuperColliderStopCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        if SuperColliderProcess.isAlive():
            SuperColliderProcess.execute("0.exit;")
            sublime.status_message("Stopped SCLang")
        else:
            sublime.status_message("SCLang not started")