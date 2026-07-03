# Terminal Velocity

Terminal Velocity is currently in maintenance mode. Python pip installs are 
still supported and the software is stable for day to day use with python 2.
The software is being moved into maintenance mode because both authors 
no longer use terminal_velocity. Life happens and finding the time to maintain 
it is difficult. We hope you understand.

**If you find a true bug and need help then please reach out via email to Vincent.
You can find my email in my profile https://github.com/vhp.**


Terminal Velocity is a fast note-taking app for the UNIX terminal, that
focuses on letting you create or find a note as quickly and easily as
possible, then uses your `$EDITOR` to open and edit the note. It is
heavily inspired by the OS X app [Notational
Velocity](http://notational.net/). For screenshots and features, see the
[Terminal Velocity website](https://github.com/vhp/terminal_velocity).

## Installation

### pip - Python package manager
To install Terminal Velocity, run:

    pip install terminal_velocity

Then to launch it just run:

    terminal_velocity

To use a different notes directory, run:

    terminal_velocity path/to/your/notes/dir

To see all the command-line options, run:

    terminal_velocity -h

To quit the app, press `ctrl-c` or `ctrl-x`.

To upgrade Terminal Velocity to the latest version, run:

    pip install --upgrade terminal_velocity

To uninstall it, run:

    pip uninstall terminal_velocity

### From Source

Ensure python modules `urwid`, `setuptools`  and `chardet` are installed. Python-dev also.

```
apt install python-setuptools python-chardet python-urwid python-dev
```

Clone the repository from:

    git@github.com:vhp/terminal_velocity.git
    or
    https://github.com/vhp/terminal_velocity.git

Move into terminal_velocity directory you just cloned and run the following:

    sudo python setup.py install

## Releasing to PyPi

To release a new version of Terminal Velocity:

1.  Make sure you have setup your \~/.pypirc file for PyPi uploading
2.  Increment the version number in the [setup.py file](setup.py), add
    an entry te the [changelog](CHANGELOG.txt), commit both changes to
    git and push them to github. For example, see
    [aae87b](https://github.com/seanh/terminal_velocity/commit/aae87bcc50f88037b8fc76c78c0da2086c5e89ae).
3.  Upload the new release to [the terminal\_velocity package on
    pypi](https://pypi.python.org/pypi/terminal_velocity): run
    `python setup.py sdist upload -r pypi`.

For more information see <https://packaging.python.org/>.

To contribute code to Terminal Velocity, see
[CONTRIBUTING](https://github.com/vhp/terminal_velocity/blob/master/CONTRIBUTING.md#contributing-to-terminal-velocity).

