Contributing to Terminal Velocity
---------------------------------

If you want to contribute a bug report or feature request, use
[GitHub Issues](https://github.com/vhp/terminal_velocity/issues?state=open).

If you want to contribute documentation, for example to explain how to combine
Terminal Velocity with an external tool that handles something like note
synchronization or encryption, use
[the wiki](https://github.com/vhp/terminal_velocity/wiki).

If you want to contribute code:

1. Fork the repo on GitHub and clone your fork.

2. Set up a development environment (requires Python 3.11+ and
   [uv](https://docs.astral.sh/uv/)):

        make dev      # create the venv and install dependencies
        make run      # run your development copy (make run ARGS="~/Notes")
        make test     # run the test suite
        make lint     # check lint and formatting with ruff
        make fmt      # auto-format and fix lint issues
        make package  # build the sdist and wheel into dist/
        make clean    # remove the venv, build artifacts, and caches

3. Create a bugfix or feature branch from main (don't commit on main),
   e.g. `git checkout -b my-new-feature`.

4. Make your change, add or update tests, and make sure `make test` and
   `make lint` pass.

5. Push the branch to your fork and open a pull request against main.

For code style, follow [PEP 8](https://peps.python.org/pep-0008/) and
[PEP 257](https://peps.python.org/pep-0257/); `make lint` enforces the
important parts via ruff. For git commit messages, follow these
[Commit Guidelines](https://git-scm.com/book/en/v2/Distributed-Git-Contributing-to-a-Project#_commit_guidelines).
