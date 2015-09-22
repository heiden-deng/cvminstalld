#!/usr/bin/env python

import glob
import os, string, stat, sys
import subprocess
from errno import *
import re
import shutil
import xml.dom.minidom as minidom
import threading

class logger:
    def __init__(self, path , loglevel):
        self.path = path;
	self.loglevel = loglevel

    def info(self, msg):
	pass  #print "[INFO]%s" % msg

    def debug(self, msg):
	pass #print "[DEBUG]%s" % msg

    def warn(self, msg):
	print "[WARN]%s" % msg

    def error(self, msg):
	print "[ERROR]%s" % msg

log = logger("/tmp",1)

#Python reimplementation of the shell tee process, so we can
#feed the pipe output into two places at the same time
class tee(threading.Thread):
    def __init__(self, inputdesc, outputdesc, logmethod, command):
        threading.Thread.__init__(self)
        self.inputdesc = os.fdopen(inputdesc, "r")
        self.outputdesc = outputdesc
        self.logmethod = logmethod
        self.running = True
        self.command = command

    def run(self):
        while self.running:
            try:
                data = self.inputdesc.readline()
            except IOError:
                self.logmethod("Can't read from pipe during a call to %s. "
                               "(program terminated suddenly?)" % self.command)
                break
            if data == "":
                self.running = False
            else:
                self.logmethod(data.rstrip('\n'))
                os.write(self.outputdesc, data)

    def stop(self):
        self.running = False
        return self

## Run an external program and redirect the output to a file.
# @param command The command to run.
# @param argv A list of arguments.
# @param stdin The file descriptor to read stdin from.
# @param stdout The file descriptor to redirect stdout to.
# @param stderr The file descriptor to redirect stderr to.
# @param root The directory to chroot to before running command.
# @return The return code of command.
def execWithRedirect(command, argv, stdin = None, stdout = None,
                     stderr = None, root = '/'):
    def chroot ():
        os.chroot(root)

    if command.startswith('/'):
        log.warn("'%s' specified as full path" % (command,))

    stdinclose = stdoutclose = stderrclose = lambda : None

    argv = list(argv)
    if isinstance(stdin, str):
        if os.access(stdin, os.R_OK):
            stdin = os.open(stdin, os.O_RDONLY)
            stdinclose = lambda : os.close(stdin)
        else:
            stdin = sys.stdin.fileno()
    elif isinstance(stdin, int):
        pass
    elif stdin is None or not isinstance(stdin, file):
        stdin = sys.stdin.fileno()

    orig_stdout = stdout
    if isinstance(stdout, str):
        stdout = os.open(stdout, os.O_RDWR|os.O_CREAT)
        stdoutclose = lambda : os.close(stdout)
    elif isinstance(stdout, int):
        pass
    elif stdout is None or not isinstance(stdout, file):
        stdout = sys.stdout.fileno()

    if isinstance(stderr, str) and isinstance(orig_stdout, str) and stderr == orig_stdout:
        stderr = stdout
    elif isinstance(stderr, str):
        stderr = os.open(stderr, os.O_RDWR|os.O_CREAT)
        stderrclose = lambda : os.close(stderr)
    elif isinstance(stderr, int):
        pass
    elif stderr is None or not isinstance(stderr, file):
        stderr = sys.stderr.fileno()

    log.info("Running... %s" % ([command] + argv,))

    #prepare os pipes for feeding tee proceses
    pstdout, pstdin = os.pipe()
    perrout, perrin = os.pipe()

    env = os.environ.copy()
    env.update({"LC_ALL": "C"})

    try:
        #prepare tee proceses
        proc_std = tee(pstdout, stdout, log.info, command)
        proc_err = tee(perrout, stderr, log.error, command)

        #start monitoring the outputs
        proc_std.start()
        proc_err.start()

        proc = subprocess.Popen([command] + argv, stdin=stdin,
                                stdout=pstdin,
                                stderr=perrin,
                                preexec_fn=chroot, cwd=root,
                                env=env)

        proc.wait()
        ret = proc.returncode

        #close the input ends of pipes so we get EOF in the tee processes
        os.close(pstdin)
        os.close(perrin)

        #wait for the output to be written and destroy them
        proc_std.join()
        del proc_std

        proc_err.join()
        del proc_err

        stdinclose()
        stdoutclose()
        stderrclose()
    except OSError as e:
        errstr = "Error running %s: %s" % (command, e.strerror)
        log.error(errstr)
        #close the input ends of pipes so we get EOF in the tee processes
        os.close(pstdin)
        os.close(perrin)
        proc_std.join()
        proc_err.join()

        stdinclose()
        stdoutclose()
        stderrclose()
        raise RuntimeError, errstr

    return ret

## Run an external program and capture standard out.
# @param command The command to run.
# @param argv A list of arguments.
# @param stdin The file descriptor to read stdin from.
# @param stderr The file descriptor to redirect stderr to.
# @param root The directory to chroot to before running command.
# @param fatal Boolean to determine if non-zero exit is fatal.
# @return The output of command from stdout.
def execWithCapture(command, argv, stdin = None, stderr = None, root='/',
                    fatal = False):
    def chroot():
        os.chroot(root)

    def closefds ():
        stdinclose()
        stderrclose()

    if command.startswith('/'):
        log.warn("'%s' specified as full path" % (command,))

    stdinclose = stderrclose = lambda : None
    rc = ""
    argv = list(argv)

    if isinstance(stdin, str):
        if os.access(stdin, os.R_OK):
            stdin = os.open(stdin, os.O_RDONLY)
            stdinclose = lambda : os.close(stdin)
        else:
            stdin = sys.stdin.fileno()
    elif isinstance(stdin, int):
        pass
    elif stdin is None or not isinstance(stdin, file):
        stdin = sys.stdin.fileno()

    if isinstance(stderr, str):
        stderr = os.open(stderr, os.O_RDWR|os.O_CREAT)
        stderrclose = lambda : os.close(stderr)
    elif isinstance(stderr, int):
        pass
    elif stderr is None or not isinstance(stderr, file):
        stderr = sys.stderr.fileno()

    log.info("Running... %s" % ([command] + argv,))

    env = os.environ.copy()
    env.update({"LC_ALL": "C"})

    try:
        proc = subprocess.Popen([command] + argv, stdin=stdin,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                preexec_fn=os.setsid, cwd=root,env=env)

        log.info("call popen")
	while True:
            (outStr, errStr) = proc.communicate()
            if outStr:
                map(log.info, outStr.splitlines())
                rc += outStr
            if errStr:
                map(log.error, errStr.splitlines())
                os.write(stderr, errStr)

            if proc.returncode is not None:
                break
        # if we have anything other than a clean exit, and we get the fatal
        # option, raise the OSError.
        if proc.returncode and fatal:
            raise OSError(proc.returncode, errStr)
    except OSError as e:
        log.error("Error running " + command + ": " + e.strerror)
        closefds()
    closefds()
    return rc

## Get the amount of RAM installed in the machine.
# @return The amount of installed memory in kilobytes.
def memInstalled():
    f = open("/proc/meminfo", "r")
    lines = f.readlines()
    f.close()

    for l in lines:
        if l.startswith("MemTotal:"):
            fields = string.split(l)
            mem = fields[1]
            break

    return long(mem)


