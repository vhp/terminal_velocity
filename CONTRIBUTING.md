Contributing to Terminal Velocity
---------------------------------


If you want to contribute bug reports or feature requests, documentation, or
code to Terminal Velocity, you can send them to me by email or by whatever means
you prefer. But if you're looking for instructions, here are my suggestions:

If you want to contribute a bug report or feature request to Terminal Velocity,
use
[GitHub Issues](https://github.com/vhp/terminal_velocity/issues?state=open).

If you want to contribute documentation, for example to explain how to combine
Terminal Velocity with an external tool that handles something like note
synchronisation or encryption, use
[the wiki](https://github.com/vhp/terminal_velocity/wiki).

If you want to contribute code to Terminal Velocity: create your own GitHub
account, fork Terminal Velocity, create a new bugfix or feature branch and
commit your code to it, push your branch to your Terminal Velocity fork on
GitHub, then send me a pull request asking me to pull your feature branch into
my master branch. In detail:

1. [Install the Terminal Velocity development version](https://github.com/vhp/terminal_velocity/blob/master/CONTRIBUTING.md#how-to-install-the-terminal-velocity-development-version).

2. Checkout a new branch, forked from the master branch, e.g.
   `git checkout -b my-new-feature`. _Don't commit on the master branch_,
   instead develop each bugfix or feature on its own branch forked from master.

3. [Create a GitHub account](https://github.com/signup) (it's free!)

4. Fork my Terminal Velocity repo: click the _Fork_ button on the Terminal
   Velocity GitHub page.

5. In the git clone on your dev machine, add your GitHub fork as a remote (you
   only need to this once):

        git remote add MY_FORK https://github.com/YOUR_USERNAME/terminal_velocity.git

6. Push your feature or bugfix branch to your fork:

        git push MY_FORK my-new-feature

7. Use the _Pull Request_ button on the main Terminal Velocity project page to
   send me a pull request, asking me to pull your bugfix or feature branch into
   my master branch.

8. Once I've pulled your pull request, then you can pull my master branch into
   the master branch on your dev machine and push it to the master branch on
   your GitHub fork, to get the new feature in those master branches as well:

        git checkout master
        git pull origin master
        git push MY_FORK master

For code style, I try to follow [PEP 8](http://www.python.org/dev/peps/pep-0008/) and
[PEP 257](http://www.python.org/dev/peps/pep-0257/). I try to make code compatible
with Python 2, version 2.6 or newer (i.e. don't use
[Python 2.7-only features](http://docs.python.org/2/whatsnew/2.7.html)).
That being said, I also try to write Python 2 code that's
[forward-compatible with Python 3](http://lucumr.pocoo.org/2011/1/22/forwards-compatible-python/).
For git commit messages, I try to follow these [Commit Guidelines](http://git-scm.com/book/en/Distributed-Git-Contributing-to-a-Project#Commit-Guidelines).


### How To Install the Terminal Velocity Development Version

To install Terminal Velocity for development, you need
[Python](http://www.python.org/),
[virtualenv](http://www.virtualenv.org/),
[virtualenvwrapper](http://www.doughellmann.com/projects/virtualenvwrapper/)
and [git](http://git-scm.com/)
(technically you can make do without virtualenv and virtualenvwrapper, but they
make development a lot more convenient).

Use virtualenvwrapper to create a Python virtualenv and install Terminal
Velocity and its dependences into the virtualenv, for example:

    $ mkvirtualenv terminal_velocity
    (terminal_velocity) $ mkdir -p ~/Projects/terminal_velocity
    (terminal_velocity) $ cd ~/Projects/terminal_velocity
    (terminal_velocity) $ setvirtualenvproject
    (terminal_velocity) $ git clone https://github.com/vhp/terminal_velocity.git
    (terminal_velocity) $ cd terminal_velocity
    (terminal_velocity) $ python setup.py develop
    (terminal_velocity) $ deactivate
    $ workon terminal_velocity

At this point, the `terminal_velocity` command should run your development
copy of Terminal Velocity from your virtualenv:

    (terminal_velocity) $ which terminal_velocity
    /home/seanh/.virtualenvs/terminal_velocity/bin/terminal_velocity

Each time you open a new shell to start working on Terminal Velocity
development, you need to activate your terminal_velocity virtualenv:

    $ workon terminal_velocity
    (terminal_velocity) $

When you're finished working, deactivate the virtualenv:

    (terminal_velocity) $ deactivate
    $

While the virtualenv is deactivated, the `terminal_velocity` command will run
your installed release version of Terminal Velocity (if you have one) rather
than the development version installed in your virtualenv:

    $ which terminal_velocity
    /usr/local/bin/terminal_velocity

So you can easily switch between your stable and development copies of Terminal
Velocity by activating and deactivating your virtualenv with the `workon` and
`deactivate` commands. You can also have multiple shells open, some with the
virtualenv activated and others not, so you can use your stable copy of
Terminal Velocity to takes note while you hack on your development version.

You can also setup different aliases (e.g. in your `~/.bashrc` or
`~/.zshrc`) for running the release and development versions:

    alias tv="/usr/local/bin/terminal_velocity"
    alias tvdev="/home/seanh/.virtualenvs/terminal_velocity/bin/python /home/seanh/Projects/terminal_velocity/bin/terminal_velocity"


## Testing

Automatic testing for all required python versions are performed using [pytest](https://docs.pytest.org/en/latest/) via [tox](https://tox.readthedocs.io/en/latest/).

The `tox.ini` file defined which python versions will this package be tested on.
To run the tests for all the defined python version, simply run

    $ workon terminal_velocity
    (terminal_velocity) $ pip install tox
    (terminal_velocity) $ tox

To run a single python version pass the `-e` flag. For example for python 3.6:

    (terminal_velocity) $ tox -e py36

