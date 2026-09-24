"""Note storage and search.

A NoteBook is a directory of plain text note files, read once into memory and
rescanned on demand. Note contents are cached and invalidated by mtime and
size, so searching never touches the disk. The notebook never opens note files
for writing; the only write it ever performs is the atomic creation of a new,
empty note file.
"""

import logging
import os
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
    """Raised when trying to add a note that already exists."""


class InvalidNoteTitleError(NewNoteError):
    """Raised when trying to add a note with an invalid title."""


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
        self._path = Path(path).expanduser().resolve()
        self.extension = _normalize_extension(extension)
        self.extensions = [_normalize_extension(ext) for ext in extensions]
        self.exclude = list(exclude) if exclude else []
        self._notes: dict[Path, Note] = {}

        if self._path.exists():
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

    def scan(self, force: bool = False) -> None:
        """Sync the in-memory notes with the files on disk.

        Contents are re-read only for new files or files whose mtime or size
        changed. Notes whose files have disappeared are dropped. With
        `force`, the cache is dropped first so every file is re-read, which
        catches edits that leave mtime and size unchanged.
        """
        if force:
            self._notes.clear()
        seen: set[Path] = set()
        for root, dirs, files in os.walk(self._path):
            dirs[:] = [d for d in dirs if d not in self.exclude]
            for filename in files:
                if filename in self.exclude:
                    continue
                if filename.startswith(".") or filename.endswith("~"):
                    continue
                if os.path.splitext(filename)[1] not in self.extensions:
                    continue

                path = Path(root) / filename
                try:
                    stat = path.stat()
                    cached = self._notes.get(path)
                    if (
                        cached is None
                        or cached.mtime != stat.st_mtime
                        or cached.size != stat.st_size
                    ):
                        contents = decode(path.read_bytes())
                        relpath = path.relative_to(self._path)
                        title = strip_control_chars(str(relpath.with_suffix("")))
                        self._notes[path] = Note(
                            title=title,
                            path=path,
                            extension=path.suffix,
                            mtime=stat.st_mtime,
                            contents=contents,
                            size=stat.st_size,
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
        """
        search_words = query.strip().split()
        matching_notes = []
        for note in self._notes.values():
            match = True
            for word in search_words:
                if word.islower():
                    in_note = word in note.title_lower or word in note.contents_lower
                else:
                    in_note = word in note.title or word in note.contents
                if not in_note:
                    match = False
                    break
            if match:
                matching_notes.append(note)
        matching_notes.sort(key=lambda note: note.mtime, reverse=True)
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
        return title.removeprefix(os.sep).strip()

    def add_new(self, title: str, extension: str | None = None) -> Note:
        """Create a new empty note file and return its Note.

        Titles may contain slashes to create notes in subdirectories.

        Raises InvalidNoteTitleError for an empty title or one that would
        escape the notes directory, and NoteAlreadyExistsError if the note
        (or its file) already exists.
        """
        if extension is None:
            extension = self.extension

        title = self.normalize_title(title)

        if not os.path.split(title)[1]:
            raise InvalidNoteTitleError(f"Invalid note title: {title}")

        if self.get_by_title(title, extension) is not None:
            raise NoteAlreadyExistsError(f"Note already in NoteBook: {title}")

        path = (self._path / (title + extension)).resolve()
        if not path.is_relative_to(self._path):
            raise InvalidNoteTitleError(f"Invalid note title: {title}")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "x", encoding="utf-8"):
                pass
        except FileExistsError as e:
            raise NoteAlreadyExistsError(f"File already exists: {path}") from e
        except OSError as e:
            raise NewNoteError(f"Could not create note {path}: {e}") from e

        stat = path.stat()
        note = Note(
            title=title,
            path=path,
            extension=extension,
            mtime=stat.st_mtime,
            contents="",
            size=stat.st_size,
        )
        self._notes[path] = note
        return note

    def __len__(self) -> int:
        return len(self._notes)

    def __iter__(self):
        return iter(self._notes.values())

    def __contains__(self, note: Note) -> bool:
        return note.path in self._notes
