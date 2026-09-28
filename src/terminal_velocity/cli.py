"""Command-line entry point: argument and config-file parsing, logging setup.

Reads an INI config file (default ~/.tvrc, [DEFAULT] section) whose options
mirror the command-line flags; command-line arguments win over the config
file, which wins over built-in defaults.
"""

import argparse
import configparser
import logging
import logging.handlers
import os
import re
import sys
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

DEFAULT_EXTENSIONS = ".txt, .text, .md, .markdown, .mdown, .mdwn, .mkdn, .mkd, .rst"
DEFAULT_EXCLUDE = "src, backup, ignore, tmp, old"
DEFAULT_CONFIG = "~/.tvrc"


def _list_app():
    from terminal_velocity.app import TerminalVelocityApp

    return TerminalVelocityApp


def _preview_app():
    from terminal_velocity.preview import PreviewApp

    return PreviewApp


# Single source of truth for valid layouts: drives --layout validation and
# the app-class dispatch in main().
LAYOUTS = {"list": _list_app, "preview": _preview_app}

YANK_FORMATS = {
    "wiki": "[[{title}]]",
    "markdown": "[{title}]({path})",
    "title": "{title}",
    "filename": "{path}",
}

# Shape check only: Textual silently ignores a key it can't match, such as ctrl-k or C-y.
_KEY_PATTERN = re.compile(r"(?:(?:ctrl|shift|alt|meta|super|hyper)\+)*[a-z0-9_]+|\S")

# One suffix or none: scanning matches only the last suffix, so ".page.md" would never be found.
_EXTENSION_PATTERN = re.compile(r"\.?[^./\\\s]*")


@dataclass(frozen=True)
class Config:
    """Resolved settings from defaults, the config file, and the command line."""

    notes_dir: Path
    editor: str
    extension: str
    extensions: list[str]
    exclude: list[str]
    log_file: Path
    layout: str = "list"
    copy_command: str = ""
    yank_key: str = "ctrl+y"
    yank_format: str = "wiki"


def _split_csv(value: str) -> list[str]:
    """Parse a comma-separated option into a list of trimmed, non-empty items."""
    return [item.strip() for item in value.split(",") if item.strip()]


def _version() -> str:
    """The installed package version, or "unknown" when run from an uninstalled checkout."""
    try:
        return version("terminal-velocity")
    except PackageNotFoundError:
        return "unknown"


def _normalize_keys(value: str) -> str:
    """Lowercase each key in a comma-separated key list, leaving single characters as typed.

    A lone "K" is a different key from "k" in Textual; "Ctrl+K" is just a miscased "ctrl+k".
    """
    keys = [key.strip() for key in value.split(",")]
    return ",".join(key if len(key) == 1 else key.lower() for key in keys)


def parse_config(argv: list[str] | None = None) -> Config:
    """Build the Config from the config file, environment, and command line."""
    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument(
        "-c",
        "--config",
        dest="config",
        action="store",
        default=None,
        help=f"the config file to use (default: {DEFAULT_CONFIG})",
    )
    # Here rather than on the main parser so a bad config file can't block it.
    config_parser.add_argument(
        "-V", "--version", action="version", version=f"%(prog)s {_version()}"
    )
    args, remaining_argv = config_parser.parse_known_args(argv)

    config_file = os.path.abspath(os.path.expanduser(args.config or DEFAULT_CONFIG))
    config = configparser.ConfigParser(interpolation=None)
    try:
        if args.config is None:
            config.read(config_file)
        else:
            # read() silently skips a file it can't open; a path the user typed must load.
            with open(config_file, encoding="utf-8") as f:
                config.read_file(f)
    except FileNotFoundError:
        print(f"terminal-velocity: config file not found: {config_file}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"terminal-velocity: cannot read config {config_file}: {e.strerror}", file=sys.stderr)
        sys.exit(1)
    except (configparser.Error, UnicodeDecodeError) as e:
        print(f"terminal-velocity: could not parse config {config_file}: {e}", file=sys.stderr)
        sys.exit(1)
    defaults = dict(config.items("DEFAULT"))

    description = "A fast note-taking app for the UNIX terminal"
    epilog = """
The config file can override the defaults for the optional arguments.
Example config file contents:

    [DEFAULT]
    editor = vim
    # The filename extension to use for new notes.
    extension = .txt
    # The filename extensions to recognize in the notes directory.
    extensions = .txt, .text, .md, .markdown, .mdown, .mdwn, .mkdn, .mkd, .rst
    notes_dir = ~/Notes
    # The UI layout: list (default) or preview (dual-pane with preview).
    layout = list
    # Command that receives the yanked text on stdin. Empty uses OSC 52.
    copy_command = pbcopy
    # The key that yanks the highlighted note, in Textual key syntax.
    yank_key = ctrl+y
    # What a yank copies: wiki, markdown, title, or filename.
    yank_format = wiki

If there is no config file, or a setting is missing from it, the built-in
default is used."""

    parser = argparse.ArgumentParser(
        description=description,
        epilog=epilog,
        parents=[config_parser],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-e",
        "--editor",
        dest="editor",
        action="store",
        default=defaults.get("editor") or os.getenv("EDITOR") or "vim",
        help="the text editor to use (default: %(default)s)",
    )
    parser.add_argument(
        "-x",
        "--extension",
        dest="extension",
        action="store",
        default=defaults.get("extension", "txt"),
        help="the filename extension for new notes (default: %(default)s)",
    )
    parser.add_argument(
        "--extensions",
        dest="extensions",
        action="store",
        default=defaults.get("extensions", DEFAULT_EXTENSIONS),
        help="the filename extensions to recognize in the notes dir, a "
        "comma-separated list (default: %(default)s)",
    )
    parser.add_argument(
        "--exclude",
        dest="exclude",
        action="store",
        default=defaults.get("exclude", DEFAULT_EXCLUDE),
        help="the file/directory names to skip while recursively searching "
        "the notes dir for notes, a comma-separated list "
        "(default: %(default)s)",
    )
    parser.add_argument(
        "-l",
        "--log-file",
        dest="log_file",
        action="store",
        default=defaults.get("log_file", "~/.tvlog"),
        help="the file to log to (default: %(default)s)",
    )
    parser.add_argument(
        "--layout",
        dest="layout",
        action="store",
        default=defaults.get("layout", "list"),
        help=f"UI layout, one of: {', '.join(LAYOUTS)} (default: %(default)s)",
    )
    parser.add_argument(
        "--copy-command",
        dest="copy_command",
        action="store",
        default=defaults.get("copy_command", ""),
        help="the command the yanked text is piped to, e.g. pbcopy, wl-copy, "
        "or 'xclip -selection clipboard'; empty copies via the terminal's "
        "OSC 52 support (default: %(default)r)",
    )
    parser.add_argument(
        "--yank-key",
        dest="yank_key",
        action="store",
        default=defaults.get("yank_key", "ctrl+y"),
        help="the key that yanks the highlighted note, e.g. ctrl+g or f2 (default: %(default)s)",
    )
    parser.add_argument(
        "--yank-format",
        dest="yank_format",
        action="store",
        default=defaults.get("yank_format", "wiki"),
        help="what a yank copies: wiki [[title]], markdown [title](path), "
        "title, or filename (default: %(default)s)",
    )
    parser.add_argument(
        "-p",
        "--print-config",
        dest="print_config",
        action="store_true",
        default=False,
        help="print the resolved configuration and exit",
    )
    parser.add_argument(
        "notes_dir",
        action="store",
        nargs="?",
        default=defaults.get("notes_dir", "~/Notes"),
        help="the notes directory to use (default: %(default)s)",
    )

    args = parser.parse_args(remaining_argv)

    parsed = Config(
        notes_dir=Path(args.notes_dir).expanduser(),
        editor=args.editor,
        extension=args.extension,
        extensions=_split_csv(args.extensions),
        exclude=_split_csv(args.exclude),
        log_file=Path(args.log_file).expanduser(),
        layout=args.layout,
        copy_command=args.copy_command,
        yank_key=_normalize_keys(args.yank_key),
        yank_format=args.yank_format,
    )

    # -p prints the resolved config even when a value is invalid, so it stays
    # usable for debugging config problems.
    if args.print_config:
        print(parsed)
        sys.exit(0)

    # Validated manually because argparse choices= does not check defaults,
    # and the value may come from the config file.
    if parsed.layout not in LAYOUTS:
        print(
            f"terminal-velocity: invalid layout {parsed.layout!r} "
            f"(use one of: {', '.join(LAYOUTS)})",
            file=sys.stderr,
        )
        sys.exit(1)
    for extension in [parsed.extension, *parsed.extensions]:
        if not _EXTENSION_PATTERN.fullmatch(extension):
            print(
                f"terminal-velocity: invalid extension {extension!r} "
                "(use a single suffix such as .md, or an empty one)",
                file=sys.stderr,
            )
            sys.exit(1)
    if parsed.yank_format not in YANK_FORMATS:
        print(
            f"terminal-velocity: invalid yank_format {parsed.yank_format!r} "
            f"(use one of: {', '.join(YANK_FORMATS)})",
            file=sys.stderr,
        )
        sys.exit(1)
    if not all(_KEY_PATTERN.fullmatch(key) for key in parsed.yank_key.split(",")):
        print(
            f"terminal-velocity: invalid yank_key {parsed.yank_key!r} "
            "(use Textual key syntax, e.g. ctrl+g or f2)",
            file=sys.stderr,
        )
        sys.exit(1)

    return parsed


def setup_logging(config: Config) -> None:
    """Configure file logging; if the log file can't be opened, warn and run without it."""
    logger = logging.getLogger("terminal_velocity")
    logger.setLevel(logging.WARNING)
    try:
        config.log_file.parent.mkdir(parents=True, exist_ok=True)
        # backupCount must be at least 1, or RotatingFileHandler never rolls over.
        handler = logging.handlers.RotatingFileHandler(
            config.log_file, maxBytes=1_000_000, backupCount=1
        )
    except OSError as e:
        print(f"terminal-velocity: cannot open log file {config.log_file}: {e}", file=sys.stderr)
        return
    handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
    logger.addHandler(handler)


def main() -> None:
    """Entry point: parse config, load the notebook, and run the chosen UI."""
    from terminal_velocity.notebook import NewNoteBookError, NoteBook

    config = parse_config()
    setup_logging(config)

    app_class = LAYOUTS[config.layout]()

    try:
        notebook = NoteBook(
            path=config.notes_dir,
            extension=config.extension,
            extensions=config.extensions,
            exclude=config.exclude,
        )
    except NewNoteBookError as e:
        print(f"terminal-velocity: {e}", file=sys.stderr)
        sys.exit(1)

    app = app_class(config=config, notebook=notebook)
    try:
        app.run()
    except KeyboardInterrupt:
        sys.exit(0)
    if app.return_code:
        sys.exit(app.return_code)
