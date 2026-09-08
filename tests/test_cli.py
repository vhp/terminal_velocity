"""Tests for command-line and config-file parsing in cli.py."""

import logging
import os
import sys

import pytest

from terminal_velocity.app import TerminalVelocityApp
from terminal_velocity.cli import (
    _parse_bool,
    _split_csv,
    _version,
    main,
    parse_config,
    setup_logging,
)
from terminal_velocity.preview import PreviewApp


@pytest.fixture(autouse=True)
def no_editor_env(monkeypatch):
    monkeypatch.delenv("EDITOR", raising=False)


@pytest.fixture(autouse=True)
def clean_logger():
    logger = logging.getLogger("terminal_velocity")
    before = list(logger.handlers)
    yield
    for handler in list(logger.handlers):
        if handler not in before:
            logger.removeHandler(handler)


def write_config(tmp_path, body: str):
    cfg = tmp_path / "tvrc"
    cfg.write_text("[DEFAULT]\n" + body)
    return cfg


def empty_config(tmp_path):
    return write_config(tmp_path, "")


class TestSplitCsv:
    def test_strips_and_drops_empties(self):
        assert _split_csv(" .txt , .md ,, .rst ") == [".txt", ".md", ".rst"]

    def test_empty_string_is_empty_list(self):
        assert _split_csv("") == []


class TestParseBool:
    @pytest.mark.parametrize("value", ["1", "yes", "true", "on", "TRUE", " On "])
    def test_truthy_strings(self, value):
        assert _parse_bool(value) is True

    @pytest.mark.parametrize("value", ["0", "no", "false", "", "maybe"])
    def test_falsy_strings(self, value):
        assert _parse_bool(value) is False

    def test_passes_through_actual_bools(self):
        assert _parse_bool(True) is True
        assert _parse_bool(False) is False


class TestDefaults:
    def test_builtin_defaults_with_empty_config(self, tmp_path):
        config = parse_config(["-c", str(empty_config(tmp_path))])
        assert config.editor == "vim"
        assert config.extension == "txt"
        assert str(config.notes_dir).endswith("Notes")
        assert ".md" in config.extensions
        assert "backup" in config.exclude
        assert config.debug is False

    def test_editor_falls_back_to_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("EDITOR", "nano")
        config = parse_config(["-c", str(empty_config(tmp_path))])
        assert config.editor == "nano"

    def test_empty_editor_env_falls_through_to_vim(self, tmp_path, monkeypatch):
        monkeypatch.setenv("EDITOR", "")
        config = parse_config(["-c", str(empty_config(tmp_path))])
        assert config.editor == "vim"


class TestConfigFile:
    def test_reads_values_from_config(self, tmp_path):
        cfg = write_config(
            tmp_path,
            "editor = emacs\n"
            "extension = .org\n"
            "extensions = .org, .txt\n"
            "exclude = foo, bar\n"
            "debug = true\n",
        )
        config = parse_config(["-c", str(cfg)])
        assert config.editor == "emacs"
        assert config.extension == ".org"
        assert config.extensions == [".org", ".txt"]
        assert config.exclude == ["foo", "bar"]
        assert config.debug is True

    def test_config_overrides_builtin_default(self, tmp_path):
        cfg = write_config(tmp_path, "notes_dir = /var/notes\n")
        config = parse_config(["-c", str(cfg)])
        assert str(config.notes_dir) == "/var/notes"

    def test_config_editor_wins_over_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("EDITOR", "nano")
        cfg = write_config(tmp_path, "editor = emacs\n")
        assert parse_config(["-c", str(cfg)]).editor == "emacs"

    def test_percent_in_value_does_not_crash(self, tmp_path):
        cfg = write_config(tmp_path, "editor = vim -c 'set statusline=%f'\n")
        config = parse_config(["-c", str(cfg)])
        assert "%f" in config.editor


class TestCliOverrides:
    def test_flags_override_config(self, tmp_path):
        cfg = write_config(tmp_path, "editor = emacs\n")
        config = parse_config(["-c", str(cfg), "-e", "vim", "/tmp/other"])
        assert config.editor == "vim"
        assert str(config.notes_dir) == "/tmp/other"

    def test_positional_notes_dir(self, tmp_path):
        config = parse_config(["-c", str(empty_config(tmp_path)), "/tmp/here"])
        assert str(config.notes_dir) == "/tmp/here"

    def test_debug_flag(self, tmp_path):
        config = parse_config(["-c", str(empty_config(tmp_path)), "-d"])
        assert config.debug is True

    def test_print_config_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            parse_config(["-c", str(empty_config(tmp_path)), "-p"])

    def test_malformed_config_exits_cleanly(self, tmp_path, capsys):
        bad = tmp_path / "tvrc"
        bad.write_text("editor = vim\nno section header here\n[unterminated\n")
        with pytest.raises(SystemExit):
            parse_config(["-c", str(bad)])
        assert "could not parse config" in capsys.readouterr().err

    def test_missing_explicit_config_exits_cleanly(self, tmp_path, capsys):
        with pytest.raises(SystemExit) as exc:
            parse_config(["-c", str(tmp_path / "nope")])
        assert exc.value.code == 1
        assert "config file not found" in capsys.readouterr().err

    def test_dev_null_config_uses_defaults(self):
        assert parse_config(["-c", os.devnull]).layout == "list"

    def test_config_directory_exits_cleanly(self, tmp_path, capsys):
        with pytest.raises(SystemExit) as exc:
            parse_config(["-c", str(tmp_path)])
        assert exc.value.code == 1
        assert "cannot read config" in capsys.readouterr().err

    @pytest.mark.skipif(os.geteuid() == 0, reason="root can read any file")
    def test_unreadable_explicit_config_exits_cleanly(self, tmp_path, capsys):
        cfg = write_config(tmp_path, "layout = preview\n")
        cfg.chmod(0)
        try:
            with pytest.raises(SystemExit) as exc:
                parse_config(["-c", str(cfg)])
        finally:
            cfg.chmod(0o644)
        assert exc.value.code == 1
        assert "cannot read config" in capsys.readouterr().err

    def test_version_ignores_a_missing_config(self, tmp_path, capsys):
        with pytest.raises(SystemExit) as exc:
            parse_config(["-c", str(tmp_path / "nope"), "--version"])
        assert exc.value.code == 0
        assert _version() in capsys.readouterr().out

    def test_multi_dot_extension_exits(self, tmp_path, capsys):
        with pytest.raises(SystemExit) as exc:
            parse_config(["-c", str(empty_config(tmp_path)), "-x", ".page.md"])
        assert exc.value.code == 1
        assert "invalid extension" in capsys.readouterr().err

    def test_non_utf8_config_exits_cleanly(self, tmp_path, capsys):
        bad = tmp_path / "tvrc"
        bad.write_bytes(b"[DEFAULT]\neditor = caf\xe9\n")
        with pytest.raises(SystemExit):
            parse_config(["-c", str(bad)])
        assert "could not parse config" in capsys.readouterr().err


class TestLayout:
    def test_default_is_list(self, tmp_path):
        config = parse_config(["-c", str(empty_config(tmp_path))])
        assert config.layout == "list"

    def test_layout_from_config_file(self, tmp_path):
        cfg = write_config(tmp_path, "layout = preview\n")
        assert parse_config(["-c", str(cfg)]).layout == "preview"

    def test_layout_flag_overrides_config(self, tmp_path):
        cfg = write_config(tmp_path, "layout = list\n")
        config = parse_config(["-c", str(cfg), "--layout", "preview"])
        assert config.layout == "preview"

    def test_invalid_layout_exits(self, tmp_path, capsys):
        cfg = write_config(tmp_path, "layout = sideways\n")
        with pytest.raises(SystemExit):
            parse_config(["-c", str(cfg)])
        assert "invalid layout" in capsys.readouterr().err

    def test_print_config_works_despite_invalid_layout(self, tmp_path, capsys):
        cfg = write_config(tmp_path, "layout = sideways\n")
        with pytest.raises(SystemExit) as exc:
            parse_config(["-c", str(cfg), "-p"])
        assert exc.value.code == 0
        assert "layout='sideways'" in capsys.readouterr().out


class TestExpansion:
    def test_tilde_expanded_in_notes_dir_and_log_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        config = parse_config(["-c", str(empty_config(tmp_path)), "-l", "~/mylog", "~/mynotes"])
        assert str(config.notes_dir) == str(tmp_path / "mynotes")
        assert str(config.log_file) == str(tmp_path / "mylog")


class TestSetupLogging:
    def test_creates_missing_log_dir(self, tmp_path):
        log_file = tmp_path / "logs" / "tv.log"
        cfg = parse_config(["-c", str(empty_config(tmp_path)), "-l", str(log_file)])
        setup_logging(cfg)
        assert (tmp_path / "logs").is_dir()
        assert logging.getLogger("terminal_velocity").handlers

    def test_unwritable_log_path_degrades_without_raising(self, tmp_path, capsys):
        blocker = tmp_path / "blocker"
        blocker.write_text("i am a file, not a dir")
        cfg = parse_config(["-c", str(empty_config(tmp_path)), "-l", str(blocker / "tv.log")])
        setup_logging(cfg)  # must not raise
        assert "cannot open log file" in capsys.readouterr().err


class TestMain:
    def run_main(self, monkeypatch, tmp_path, *argv):
        cfg = empty_config(tmp_path)
        log_file = tmp_path / "tv.log"
        argv = ["terminal-velocity", "-c", str(cfg), "-l", str(log_file), *argv]
        monkeypatch.setattr(sys, "argv", argv)
        main()

    def test_notes_dir_that_is_a_file_exits_with_message(self, tmp_path, monkeypatch, capsys):
        blocker = tmp_path / "notes"
        blocker.write_text("not a directory")
        with pytest.raises(SystemExit) as exc:
            self.run_main(monkeypatch, tmp_path, str(blocker))
        assert exc.value.code == 1
        assert "exists but is not a directory" in capsys.readouterr().err

    def test_layout_selects_app_class_and_runs_it(self, tmp_path, monkeypatch):
        ran = []
        monkeypatch.setattr(PreviewApp, "run", lambda self: ran.append(type(self)))
        self.run_main(monkeypatch, tmp_path, "--layout", "preview", str(tmp_path / "notes"))
        assert ran == [PreviewApp]
        assert (tmp_path / "notes").is_dir()
        assert logging.getLogger("terminal_velocity").handlers

    def test_keyboard_interrupt_exits_zero(self, tmp_path, monkeypatch):
        def interrupt(self):
            raise KeyboardInterrupt

        monkeypatch.setattr(TerminalVelocityApp, "run", interrupt)
        with pytest.raises(SystemExit) as exc:
            self.run_main(monkeypatch, tmp_path, str(tmp_path / "notes"))
        assert exc.value.code == 0
