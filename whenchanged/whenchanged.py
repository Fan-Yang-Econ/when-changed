#!/usr/bin/env python
"""%(prog)s - run a command when a file is changed

Usage: %(prog)s [-vr1s] FILE COMMAND...
       %(prog)s [-vr1s] FILE [FILE ...] -c COMMAND

FILE can be a directory. Use %%f to pass the filename to the command.

Options:
-r Watch recursively
-v Verbose output. Multiple -v options increase the verbosity.
   The maximum is 3: -vvv.
-1 Don't re-run command if files changed while command was running
-s Run command immediately at start
-q Run command quietly

Environment variables:
- WHEN_CHANGED_EVENT: reflects the current event type that occurs.
    Could be either: file_created, file_modified, file_moved, file_deleted

- WHEN_CHANGED_FILE: provides the full path of the file that has generated the event.

Copyright (c) 2011-2016, Johannes H. Jensen.
License: BSD, see LICENSE for more details.
"""

# Standard library
import logging
import os
import re
import time
from datetime import datetime
import subprocess

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class WhenChanged(FileSystemEventHandler):
    # files to exclude from being watched
    exclude_list = [
        # Vim swap files
        r'\..*\.sw[px]*$',
        # file creation test file 4913
        r'4913$',
        # backup files
        r'.~$',
        # git directories
        r'\.git/?',
        # __pycache__ directories
        r'__pycache__/?',
    ]
    
    def __init__(self, files,
                 command,
                 recursive=False,
                 run_once=False,
                 run_at_start=False,
                 verbose_mode=3,
                 quiet_mode=False):
        self.files = files
        paths = {}
        for f in self.files:
            paths[os.path.realpath(f)] = f
        
        # {'/Users/yafa/Dropbox/fundamentalist/NLP_News': '.'}
        
        self.paths = paths
        self.command = command
        self.recursive = recursive
        self.run_once = run_once
        self.run_at_start = run_at_start
        self.last_run = 0
        self.verbose_mode = verbose_mode
        self.quiet_mode = quiet_mode
        self.process_env = os.environ.copy()
        
        self.observer = Observer(timeout=0.1)
        
        for p in self.paths:
            if os.path.isdir(p):
                # Add directory
                self.observer.schedule(self, p, recursive=True)
            else:
                # Add parent directory
                p = os.path.dirname(p)
                self.observer.schedule(self, p)
    
    def run_command(self, thefile):
        if self.run_once:
            if not os.path.exists(thefile):
                return
            elif os.path.getmtime(thefile) < self.last_run:
                logging.info(f'Ignore {thefile}, as its modified time `{os.path.getmtime(thefile)}` is '
                             f'earlier then last run time of command `{self.last_run}`')
                return
        
        new_command = []
        for item in self.command:
            new_command.append(item.replace('%f', thefile))
        now = datetime.now()
        
        self.set_envvar('file', thefile)
        stdout = open(os.devnull, 'wb') if self.quiet_mode else None
        subprocess.call(new_command, shell=(len(new_command) == 1), env=self.process_env, stdout=stdout)
        self.last_run = time.time()
        
        event_name = re.sub(r'^[^_]+_', '', self.get_envvar('event'))
        print_message = f"`{thefile}` {event_name} at {now.strftime('%F %T')}, so run command at {self.last_run}"
        
        logging.info('==> ' + print_message + ' <==')
    
    def is_interested(self, path):
        for i in self.exclude_list:
            if re.compile(i).findall(path):
                return False
        
        if path in self.paths:
            return True
        
        path = os.path.dirname(path)
        if path in self.paths:
            return True
        
        if self.recursive:
            while os.path.dirname(path) != path:
                path_ = os.path.dirname(path)
                if path_ in self.paths:
                    return True
        
        return False
    
    def on_change(self, path):
        if self.is_interested(path):
            self.run_command(path)
    
    def on_created(self, event):
        if self.observer.__class__.__name__ == 'InotifyObserver':
            # inotify also generates modified events for created files
            return
        
        if not event.is_directory:
            self.set_envvar('event', 'file_created')
            self.on_change(event.src_path)
    
    def on_modified(self, event):
        if not event.is_directory:
            self.set_envvar('event', 'file_modified')
            self.on_change(event.src_path)
    
    def on_moved(self, event):
        if not event.is_directory:
            self.set_envvar('event', 'file_moved')
            self.on_change(event.dest_path)
    
    def on_deleted(self, event):
        if not event.is_directory:
            self.set_envvar('event', 'file_deleted')
            self.on_change(event.src_path)
    
    def set_envvar(self, name, value):
        self.process_env['WHEN_CHANGED_' + name.upper()] = value
    
    def get_envvar(self, name):
        return self.process_env['WHEN_CHANGED_' + name.upper()]
    
    def run(self):
        if self.run_at_start:
            self.run_command('/dev/null')
        
        self.observer.start()
        try:
            while True:
                time.sleep(60 * 60)
        except KeyboardInterrupt:
            self.observer.stop()
        self.observer.join()


def print_usage(prog):
    print(__doc__ % {'prog': prog}, end='')


def set_logging(level=10,
                path=None,
                log_format='%(asctime)s:%(name)s-%(funcName)s: %(message)s'  # use "%(message)s" simpler format for lambda logging
                ):
    """

    :param level:
    :param path:
    :param log_format:
        '%(levelname)s-%(name)s-%(funcName)s:\n %(message)s'
    :return:
    """
    
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    if path:
        logging.basicConfig(level=level, format=log_format, filename=path, datefmt='%Y-%m-%d %H:%M:%S')
    else:
        logging.basicConfig(level=level, format=log_format, datefmt='%Y-%m-%d %H:%M:%S')


def main():
    import argparse
    set_logging(20)
    parser = argparse.ArgumentParser(description="run_wathcer.py")
    
    parser.add_argument('--folders_to_watch', default=['.'])
    parser.add_argument('--command_to_run_under_watched_folder', default='npm run build')
    
    logging.info(f"Current folder {os.path.abspath('.')}")
    
    # parsed_args = parser.parse_args(['--command_to_run_under_watched_folder', 'echo changed'])
    
    parsed_args = parser.parse_args()
    
    command = f"cd {os.path.abspath('.')}; {parsed_args.command_to_run_under_watched_folder}"
    
    wc = WhenChanged(files=parsed_args.folders_to_watch,
                     command=[command],
                     recursive=True,
                     # run_at_start=
                     # verbose_mode=3,
                     run_once=True)
    
    try:
        wc.run()
    except KeyboardInterrupt:
        logging.info('^C')
        exit(0)
