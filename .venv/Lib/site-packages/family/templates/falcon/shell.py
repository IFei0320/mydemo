#!/usr/bin/env python
# coding: utf-8

import os
import sys
import atexit
import code


try:
    import IPython
    has_ipython = True
except ImportError:
    has_ipython = False


def hook_readline_hist():
    try:
        # Try to set up command history completion/saving/reloading
        import readline
    except ImportError:
        return

    # The place to store your command history between sessions
    histfile = os.environ["HOME"] + "/.ipython_history"
    readline.parse_and_bind('tab: complete')
    try:
        readline.read_history_file(histfile)
    except IOError:
        pass  # It doesn't exist yet.

    def savehist():
        try:
            readline.write_history_file(histfile)
        except:
            print 'Unable to save Python command history'
    atexit.register(savehist)


def get_banner():
    return 'Use it carefully!'


def pre_imports():
    # fill sth.
    return locals()


def plain_shell(user_ns):
    sys.exit(code.interact(banner=get_banner(), local=user_ns))


def ipython_shell(user_ns):
    if getattr(IPython, 'version_info', None) and IPython.version_info[0] >= 1:
        from IPython.terminal.ipapp import TerminalIPythonApp
        from IPython.terminal.interactiveshell import TerminalInteractiveShell
    else:
        from IPython.frontend.terminal.ipapp import TerminalIPythonApp
        from IPython.frontend.terminal.interactiveshell import TerminalInteractiveShell

    class DaixmIPythonApp(TerminalIPythonApp):
        def init_shell(self):
            self.shell = TerminalInteractiveShell.instance(
                config=self.config,
                display_banner=False, profile_dir=self.profile_dir,
                ipython_dir=self.ipython_dir, banner1=get_banner(), banner2='')
            self.shell.configurables.append(self)

    app = DaixmIPythonApp.instance()
    app.initialize()
    app.shell.user_ns.update(user_ns)
    sys.exit(app.start())


def main():
    hook_readline_hist()
    user_ns = pre_imports()
    use_plain_shell = not has_ipython or \
            '--plain' in sys.argv[1:]

    if use_plain_shell:
        plain_shell(user_ns)
    else:
        ipython_shell(user_ns)


if __name__ == '__main__':
    main()
