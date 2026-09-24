"""Tests for the NoteBook data layer: scanning, searching, creation, rescans."""

import os
import time
from pathlib import Path

import pytest

from terminal_velocity.notebook import (
    InvalidNoteTitleError,
    NewNoteBookError,
    Note,
    NoteAlreadyExistsError,
    NoteBook,
    decode,
)

EXTENSIONS = [".txt", ".md"]


def make_notebook(path, **kwargs):
    kwargs.setdefault("extension", ".txt")
    kwargs.setdefault("extensions", EXTENSIONS)
    return NoteBook(path, **kwargs)


def write(path: Path, contents: str, mtime: float | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))


def snapshot(directory: Path) -> dict:
    return {
        p: (p.stat().st_mtime_ns, p.stat().st_size, p.read_bytes())
        for p in directory.rglob("*")
        if p.is_file()
    }


class TestScan:
    def test_finds_notes_recursively_with_relpath_titles(self, tmp_path):
        write(tmp_path / "apple.txt", "fruit")
        write(tmp_path / "sub" / "banana.md", "yellow")
        nb = make_notebook(tmp_path)
        assert sorted(n.title for n in nb) == ["apple", os.path.join("sub", "banana")]

    def test_skips_hidden_backup_wrong_extension_and_excluded(self, tmp_path):
        write(tmp_path / ".hidden.txt", "x")
        write(tmp_path / "backup.txt~", "x")
        write(tmp_path / "image.png", "x")
        write(tmp_path / "skipme.txt", "x")
        write(tmp_path / "old" / "note.txt", "x")
        write(tmp_path / "keep.txt", "x")
        nb = make_notebook(tmp_path, exclude=["old", "skipme.txt"])
        assert [n.title for n in nb] == ["keep"]

    def test_scanning_and_searching_modify_no_files(self, tmp_path):
        write(tmp_path / "a.txt", "alpha contents")
        write(tmp_path / "sub" / "b.md", "beta contents")
        before = snapshot(tmp_path)
        nb = make_notebook(tmp_path)
        nb.search("alpha")
        nb.search("")
        nb.scan()
        assert snapshot(tmp_path) == before

    def test_control_chars_stripped_from_title(self, tmp_path):
        # ESC (0x1b) and C1 (0x9b) bytes in a filename must not survive into
        # the title, which is rendered to the terminal.
        write(tmp_path / "e\x1bvi\x9bl.txt", "x")
        nb = make_notebook(tmp_path)
        titles = [n.title for n in nb]
        assert titles == ["evil"]
        assert "\x1b" not in titles[0] and "\x9b" not in titles[0]

    def test_invalid_utf8_decodes_without_crash(self, tmp_path):
        (tmp_path / "latin.txt").write_bytes(b"caf\xe9 notes")
        nb = make_notebook(tmp_path)
        notes = nb.search("caf")
        assert len(notes) == 1
        assert "caf" in notes[0].contents

    def test_same_title_different_extension_coexist(self, tmp_path):
        write(tmp_path / "note.txt", "one")
        write(tmp_path / "note.md", "two")
        nb = make_notebook(tmp_path)
        assert len(nb) == 2
        assert {n.extension for n in nb} == {".txt", ".md"}

    def test_notes_dir_is_a_file_raises(self, tmp_path):
        target = tmp_path / "notafile"
        target.write_text("oops")
        with pytest.raises(NewNoteBookError):
            make_notebook(target)

    def test_missing_notes_dir_is_created(self, tmp_path):
        target = tmp_path / "new" / "notes"
        nb = make_notebook(target)
        assert target.is_dir()
        assert len(nb) == 0


class TestSearch:
    @pytest.fixture
    def nb(self, tmp_path):
        write(tmp_path / "python.txt", "Decorators are Cool", mtime=1000)
        write(tmp_path / "recipes.txt", "tomato soup", mtime=2000)
        write(tmp_path / "Journal.txt", "today I wrote python", mtime=3000)
        return make_notebook(tmp_path)

    def test_lowercase_word_matches_case_insensitively(self, nb):
        assert {n.title for n in nb.search("cool")} == {"python"}

    def test_mixed_case_word_matches_case_sensitively(self, nb):
        assert {n.title for n in nb.search("Journal")} == {"Journal"}
        assert nb.search("JOURNAL") == []

    def test_all_words_must_match_title_or_contents(self, nb):
        assert {n.title for n in nb.search("python wrote")} == {"Journal"}
        assert nb.search("python soup") == []

    def test_empty_query_returns_all_mtime_desc(self, nb):
        assert [n.title for n in nb.search("  ")] == ["Journal", "recipes", "python"]


class TestAddNew:
    def test_creates_empty_file(self, tmp_path):
        nb = make_notebook(tmp_path)
        note = nb.add_new("my note")
        assert note.path == tmp_path / "my note.txt"
        assert note.path.read_text() == ""
        assert note in nb

    def test_subdir_title_creates_directories(self, tmp_path):
        nb = make_notebook(tmp_path)
        note = nb.add_new("projects/ideas")
        assert note.path == tmp_path / "projects" / "ideas.txt"
        assert note.path.exists()

    def test_duplicate_title_raises(self, tmp_path):
        nb = make_notebook(tmp_path)
        nb.add_new("dupe")
        with pytest.raises(NoteAlreadyExistsError):
            nb.add_new("dupe")

    def test_file_created_out_of_band_raises(self, tmp_path):
        nb = make_notebook(tmp_path)
        write(tmp_path / "sneaky.txt", "already here")
        with pytest.raises(NoteAlreadyExistsError):
            nb.add_new("sneaky")
        assert (tmp_path / "sneaky.txt").read_text() == "already here"

    def test_collision_leaves_existing_file_untouched(self, tmp_path):
        write(tmp_path / "dupe.txt", "precious contents")
        nb = make_notebook(tmp_path)
        before = snapshot(tmp_path)
        with pytest.raises(NoteAlreadyExistsError):
            nb.add_new("dupe")
        assert snapshot(tmp_path) == before

    def test_titles_cannot_escape_notes_dir(self, tmp_path):
        notes_dir = tmp_path / "notes"
        nb = make_notebook(notes_dir)
        # A single leading slash is stripped, so the note stays inside the notes dir.
        note = nb.add_new("/etc/passwd")
        assert note.path == notes_dir / "etc" / "passwd.txt"
        assert note.path.is_relative_to(notes_dir)
        # Real escapes (still absolute after the strip, or using ..) are rejected.
        for title in ["//sibling", "sub/../../escape"]:
            with pytest.raises(InvalidNoteTitleError):
                nb.add_new(title)
        assert not (tmp_path / "escape.txt").exists()

    def test_invalid_titles_raise(self, tmp_path):
        nb = make_notebook(tmp_path)
        for title in ["", "   ", "sub/"]:
            with pytest.raises(InvalidNoteTitleError):
                nb.add_new(title)

    def test_title_escaping_notes_dir_raises(self, tmp_path):
        notes_dir = tmp_path / "notes"
        nb = make_notebook(notes_dir)
        with pytest.raises(InvalidNoteTitleError):
            nb.add_new("../escape")
        assert not (tmp_path / "escape.txt").exists()


class TestRescan:
    def test_new_and_deleted_files(self, tmp_path):
        write(tmp_path / "a.txt", "a")
        nb = make_notebook(tmp_path)
        write(tmp_path / "b.txt", "b")
        (tmp_path / "a.txt").unlink()
        nb.scan()
        assert [n.title for n in nb] == ["b"]

    def test_modified_file_contents_refresh(self, tmp_path):
        write(tmp_path / "a.txt", "old words", mtime=1000)
        nb = make_notebook(tmp_path)
        write(tmp_path / "a.txt", "new words", mtime=2000)
        nb.scan()
        assert nb.search("new")
        assert not nb.search("old")

    def test_force_rereads_content_preserving_change(self, tmp_path):
        # Same size, same (preserved) mtime, different content: the normal
        # heuristic misses it, so force=True must catch it.
        write(tmp_path / "a.txt", "aaaa", mtime=1000)
        nb = make_notebook(tmp_path)
        write(tmp_path / "a.txt", "bbbb", mtime=1000)
        nb.scan()
        assert nb.search("aaaa") and not nb.search("bbbb")
        nb.scan(force=True)
        assert nb.search("bbbb") and not nb.search("aaaa")

    def test_unchanged_files_not_reread(self, tmp_path, monkeypatch):
        write(tmp_path / "a.txt", "stable", mtime=time.time() - 60)
        nb = make_notebook(tmp_path)
        calls = []
        original = Path.read_bytes
        monkeypatch.setattr(Path, "read_bytes", lambda self: calls.append(self) or original(self))
        nb.scan()
        assert calls == []

    def test_excludes_nested_directory(self, tmp_path):
        write(tmp_path / "keep.txt", "x")
        write(tmp_path / "deep" / "backup" / "buried.txt", "x")
        nb = make_notebook(tmp_path, exclude=["backup"])
        assert [n.title for n in nb] == ["keep"]


class TestDecode:
    def test_utf8_passthrough(self):
        assert decode("héllo".encode()) == "héllo"

    def test_cp1252_fallback(self):
        # 0xe9 is 'é' in cp1252 but invalid as a standalone byte in UTF-8.
        assert decode(b"caf\xe9") == "café"

    def test_never_raises_on_garbage(self):
        assert isinstance(decode(b"\xff\xfe\x00\x81"), str)


class TestGetByTitle:
    @pytest.fixture
    def nb(self, tmp_path):
        write(tmp_path / "note.txt", "one")
        write(tmp_path / "note.md", "two")
        return make_notebook(tmp_path)

    def test_matches_specific_extension(self, nb):
        assert nb.get_by_title("note", ".md").extension == ".md"

    def test_any_extension_when_none(self, nb):
        assert nb.get_by_title("note") is not None

    def test_missing_title_returns_none(self, nb):
        assert nb.get_by_title("absent") is None

    def test_wrong_extension_returns_none(self, nb):
        assert nb.get_by_title("note", ".rst") is None


class TestNoteIdentity:
    def test_equality_and_hash_by_path(self):
        a = Note("t", Path("/n/a.txt"), ".txt", 1.0, "body")
        a2 = Note("other", Path("/n/a.txt"), ".txt", 2.0, "different")
        b = Note("t", Path("/n/b.txt"), ".txt", 1.0, "body")
        assert a == a2
        assert a != b
        assert len({a, a2, b}) == 2


class TestNormalization:
    def test_normalize_title_strips_leading_sep_and_whitespace(self):
        assert NoteBook.normalize_title("/leading") == "leading"
        assert NoteBook.normalize_title("  spaced  ") == "spaced"

    def test_extension_without_dot_is_normalized(self, tmp_path):
        nb = NoteBook(tmp_path, extension="md", extensions=["md", "txt"])
        assert nb.extension == ".md"
        assert nb.extensions == [".md", ".txt"]
        note = nb.add_new("new")
        assert note.path.suffix == ".md"
