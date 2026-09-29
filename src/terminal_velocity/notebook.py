"""Note storage and search.

A NoteBook is a directory of plain text note files, read once into memory and
rescanned on demand. Note contents are cached and invalidated by mtime and
size, so searching never touches the disk. The notebook never opens note files
for writing; the only write it ever performs is the atomic creation of a new,
empty note file.
"""

import contextlib
import logging
import os
import stat
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Strip C0/C1 control characters from text that gets rendered to the
# terminal, so crafted filenames or note contents cannot emit escape
# sequences. Tab is kept; everything else in 0x00-0x1f, 0x7f, and
# 0x80-0x9f is removed (newlines optionally kept for multi-line text).
_CONTROL_CHARS = dict.fromkeys([*range(0, 9), *range(10, 32), 127, *range(128, 160)])
_CONTROL_CHARS_KEEP_NEWLINE = {c: None for c in _CONTROL_CHARS if c != 10}


def strip_control_chars(text: str, keep_newlines: bool = False) -> str:
    """Remove terminal control characters from text destined for display."""
    table = _CONTROL_CHARS_KEEP_NEWLINE if keep_newlines else _CONTROL_CHARS
    return text.translate(table)


class Error(Exception):
    """Base class for exceptions in this module."""


class NewNoteBookError(Error):
    """Raised if initializing a new NoteBook fails."""


class NewNoteError(Error):
    """Raised if making a new Note or adding it to a NoteBook fails."""


class NoteAlreadyExistsError(NewNoteError):
    """Raised when trying to add a note that already exists.

    `title` is the existing note's title as scan() would list it, which can
    differ from the title typed (e.g. "a//b" for "a/b").
    """

    def __init__(self, message: str, title: str) -> None:
        super().__init__(message)
        self.title = title


class InvalidNoteTitleError(NewNoteError):
    """Raised when trying to add a note with an invalid title."""


def nfc(text: str) -> str:
    """Normalize to NFC, so "é" matches whether a file or keyboard sent it composed or not."""
    return unicodedata.normalize("NFC", text)


def decode(raw: bytes) -> str:
    """Decode note bytes as UTF-8, falling back to cp1252 so it never raises."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


@dataclass
class Note:
    """A note file held in memory: title, path, and cached contents."""

    title: str
    path: Path
    extension: str
    mtime: float
    contents: str
    size: int = 0
    title_lower: str = field(init=False)
    contents_lower: str = field(init=False)

    def __post_init__(self) -> None:
        self.title_lower = self.title.lower()
        self.contents_lower = self.contents.lower()

    def __eq__(self, other: object) -> bool:
        return getattr(other, "path", None) == self.path

    def __hash__(self) -> int:
        return hash(self.path)


def _is_binary(path: Path) -> bool:
    """Git's heuristic: a NUL byte in the first 8 KB."""
    with open(path, "rb") as f:
        return b"\0" in f.read(8192)


def _has_word(note: Note, word: str) -> bool:
    """Smart case: an all-lowercase word matches any case, anything else matches exactly."""
    if word.islower():
        return word in note.title_lower or word in note.contents_lower
    return word in note.title or word in note.contents


def _title_for(relpath: Path) -> str:
    """The title of the note at `relpath` (relative to the notes directory)."""
    return nfc(strip_control_chars(str(relpath.with_suffix(""))))


def _normalize_extension(extension: str) -> str:
    """Ensure an extension has a leading dot."""
    if extension and not extension.startswith("."):
        return "." + extension
    return extension


class NoteBook:
    """A collection of notes stored as plain text files in a directory."""

    def __init__(
        self,
        path: str | os.PathLike[str],
        extension: str,
        extensions: list[str],
        exclude: list[str] | None = None,
    ) -> None:
        """Read the notes directory at `path`, creating it if missing.

        Raises NewNoteBookError if `path` exists but is not a directory, or
        if it cannot be created.
        """
        try:
            self._path = Path(path).expanduser().resolve()
        except (OSError, RuntimeError) as e:
            raise NewNoteBookError(f"{path} could not be resolved: {e}") from e
        self.extension = _normalize_extension(extension)
        self.extensions = [_normalize_extension(ext) for ext in extensions]
        if self.extension not in self.extensions:
            self.extensions.append(self.extension)
        self.exclude = list(exclude) if exclude else []
        self._notes: dict[Path, Note] = {}
        self._last_search: tuple[str, list[Note]] | None = None

        try:
            exists = self._path.exists()
        except OSError as e:  # Python 3.11-3.13 raise here on EACCES instead of returning False
            raise NewNoteBookError(f"{self._path} could not be read: {e}") from e
        if exists:
            if not self._path.is_dir():
                raise NewNoteBookError(f"{self._path} exists but is not a directory")
        else:
            try:
                self._path.mkdir(parents=True)
            except OSError as e:
                raise NewNoteBookError(f"{self._path} could not be created: {e}") from e

        self.scan()

    @property
    def path(self) -> Path:
        return self._path

    def _skip_dir(self, name: str) -> bool:
        return name in self.exclude or name.startswith(".")

    def _skip_file(self, name: str) -> bool:
        return (
            name in self.exclude
            or name.startswith(".")
            or name.endswith("~")
            or os.path.splitext(name)[1] not in self.extensions
        )

    def _unscannable(self, relpath: Path) -> bool:
        *dirs, name = relpath.parts
        return any(self._skip_dir(part) for part in dirs) or self._skip_file(name)

    def scan(self, force: bool = False) -> None:
        """Sync the in-memory notes with the files on disk.

        Contents are re-read only for new files or files whose mtime or size
        changed. Notes whose files have disappeared are dropped. With
        `force`, the cache is dropped first so every file is re-read, which
        catches edits that leave mtime and size unchanged.
        """
        if force:
            self._notes.clear()
        self._last_search = None
        seen: set[Path] = set()
        for root, dirs, files in os.walk(self._path):
            dirs[:] = [d for d in dirs if not self._skip_dir(d)]
            for filename in files:
                if self._skip_file(filename):
                    continue

                path = Path(root) / filename
                try:
                    st = path.stat()
                    # Reading a FIFO or device (or a symlink to one) would block or never end.
                    if not stat.S_ISREG(st.st_mode):
                        continue
                    cached = self._notes.get(path)
                    if cached is None or cached.mtime != st.st_mtime or cached.size != st.st_size:
                        # Extensionless only, so a note with a real extension is never hidden.
                        if not path.suffix and _is_binary(path):
                            continue
                        contents = nfc(decode(path.read_bytes()))
                        relpath = path.relative_to(self._path)
                        self._notes[path] = Note(
                            title=_title_for(relpath),
                            path=path,
                            extension=path.suffix,
                            mtime=st.st_mtime,
                            contents=contents,
                            size=st.st_size,
                        )
                except OSError as e:
                    logger.warning("Could not read note file %s: %s", path, e)
                    continue
                seen.add(path)

        for path in list(self._notes):
            if path not in seen:
                del self._notes[path]

    def search(self, query: str) -> list[Note]:
        """Return notes matching `query`, most recently modified first.

        Every word in the query must appear in the note's title or contents.
        All-lowercase words match case-insensitively; words with any
        uppercase match case-sensitively. An empty query matches all notes.

        The last result is kept until the notes change. Callers must not mutate
        the returned list.
        """
        query = nfc(query)
        if self._last_search is not None and self._last_search[0] == query:
            return self._last_search[1]
        search_words = query.split()
        matching_notes = [
            note
            for note in self._notes.values()
            if all(_has_word(note, word) for word in search_words)
        ]
        matching_notes.sort(key=lambda note: note.mtime, reverse=True)
        self._last_search = (query, matching_notes)
        return matching_notes

    def get_by_title(self, title: str, extension: str | None = None) -> Note | None:
        """Return the note with the given title, or None.

        If `extension` is None, any extension matches (first hit wins).
        """
        for note in self._notes.values():
            if note.title == title and (extension is None or note.extension == extension):
                return note
        return None

    @staticmethod
    def normalize_title(title: str) -> str:
        """Strip a leading path separator and surrounding whitespace from a title."""
        return nfc(title.removeprefix(os.sep).strip())

    def add_new(self, title: str, extension: str | None = None) -> Note:
        """Create a new empty note file and return its Note.

        Titles may contain slashes to create notes in subdirectories.

        Raises InvalidNoteTitleError for titles scan() would skip (empty,
        hidden, excluded, or escaping the notes directory) or that contain
        control characters, and NoteAlreadyExistsError if the note (or its
        file) already exists.
        """
        if extension is None:
            extension = self.extension

        title = self.normalize_title(title)

        if not os.path.split(title)[1] or strip_control_chars(title) != title:
            raise InvalidNoteTitleError(f"Invalid note title: {title!r}")

        relpath = Path(title + extension)
        if self._unscannable(relpath):
            raise InvalidNoteTitleError(f"Invalid note title: {title}")

        try:
            path = (self._path / relpath).resolve()
        except (OSError, RuntimeError) as e:  # RuntimeError: a symlink loop on Python 3.11-3.12
            raise InvalidNoteTitleError(f"Invalid note title: {title}") from e
        # Checked again after resolving, since a symlink can land the file where scan never looks.
        if not path.is_relative_to(self._path) or self._unscannable(path.relative_to(self._path)):
            raise InvalidNoteTitleError(f"Invalid note title: {title}")

        # Derived from the path, as scan() does, so "a//b" and "./a/b" are the note "a/b".
        title = _title_for(path.relative_to(self._path))
        if self.get_by_title(title, extension) is not None:
            raise NoteAlreadyExistsError(f"Note already in NoteBook: {title}", title)

        # Undone on failure, so a rejected title leaves no trace on disk.
        new_dirs = []
        try:
            parent = path.parent
            while not parent.exists():
                new_dirs.append(parent)
                parent = parent.parent
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "x", encoding="utf-8"):
                pass
        except FileExistsError as e:
            # mkdir raises it too, when a parent is a file or a symlink loop.
            if not path.parent.is_dir():
                raise InvalidNoteTitleError(f"Invalid note title: {title}") from e
            raise NoteAlreadyExistsError(f"File already exists: {path}", title) from e
        except OSError as e:
            for directory in new_dirs:
                with contextlib.suppress(OSError):
                    directory.rmdir()
            raise NewNoteError(f"Could not create note {path}: {e}") from e

        st = path.stat()
        note = Note(
            title=title,
            path=path,
            extension=extension,
            mtime=st.st_mtime,
            contents="",
            size=st.st_size,
        )
        self._notes[path] = note
        self._last_search = None
        return note

    def __len__(self) -> int:
        return len(self._notes)

    def __iter__(self):
        return iter(self._notes.values())

    def __contains__(self, note: Note) -> bool:
        return note.path in self._notes
