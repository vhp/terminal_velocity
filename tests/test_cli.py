"""Tests for command-line and config-file parsing in cli.py."""

import logging

import pytest

from terminal_velocity.cli import (
    _parse_bool,
    _split_csv,
    parse_config,
    setup_logging,
)


@pytest.fixture(autouse=True)
def no_editor_env(monkeypatch):
    monkeypatch.delenv("EDITOR", raising=False)


def write_config(tmp_path, body: str):
    cfg = tmp_path / "tvrc"
    cfg.write_text("[DEFAULT]\n" + body)
    return cfg


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
    def test_builtin_defaults_with_no_config(self, tmp_path):
        missing = tmp_path / "nope"
        config = parse_config(["-c", str(missing)])
        assert config.editor == "vim"
        assert config.extension == "txt"
        assert str(config.notes_dir).endswith("Notes")
        assert ".md" in config.extensions
        assert "backup" in config.exclude
        assert config.debug is False

    def test_editor_falls_back_to_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("EDITOR", "nano")
        config = parse_config(["-c", str(tmp_path / "nope")])
        assert config.editor == "nano"

    def test_empty_editor_env_falls_through_to_vim(self, tmp_path, monkeypatch):
        monkeypatch.setenv("EDITOR", "")
        config = parse_config(["-c", str(tmp_path / "nope")])
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
        config = parse_config(["-c", str(tmp_path / "nope"), "/tmp/here"])
        assert str(config.notes_dir) == "/tmp/here"

    def test_debug_flag(self, tmp_path):
        config = parse_config(["-c", str(tmp_path / "nope"), "-d"])
        assert config.debug is True

    def test_print_config_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            parse_config(["-c", str(tmp_path / "nope"), "-p"])

    def test_malformed_config_exits_cleanly(self, tmp_path, capsys):
        bad = tmp_path / "tvrc"
        bad.write_text("editor = vim\nno section header here\n[unterminated\n")
        with pytest.raises(SystemExit):
            parse_config(["-c", str(bad)])
        assert "could not parse config" in capsys.readouterr().err

    def test_non_utf8_config_exits_cleanly(self, tmp_path, capsys):
        bad = tmp_path / "tvrc"
        bad.write_bytes(b"[DEFAULT]\neditor = caf\xe9\n")
        with pytest.raises(SystemExit):
            parse_config(["-c", str(bad)])
        assert "could not parse config" in capsys.readouterr().err


class TestLayout:
    def test_default_is_list(self, tmp_path):
        config = parse_config(["-c", str(tmp_path / "nope")])
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


class TestYankSettings:
    def test_defaults(self, tmp_path):
        config = parse_config(["-c", str(tmp_path / "nope")])
        assert config.copy_command == ""
        assert config.yank_key == "ctrl+y"
        assert config.yank_format == "wiki"

    def test_from_config_file(self, tmp_path):
        cfg = write_config(tmp_path, "copy_command = xclip -selection clipboard\nyank_key = f2\n")
        config = parse_config(["-c", str(cfg)])
        assert config.copy_command == "xclip -selection clipboard"
        assert config.yank_key == "f2"

    def test_flags_override_config(self, tmp_path):
        cfg = write_config(tmp_path, "copy_command = pbcopy\nyank_key = f2\n")
        config = parse_config(["-c", str(cfg), "--copy-command", "wl-copy", "--yank-key", "ctrl+k"])
        assert config.copy_command == "wl-copy"
        assert config.yank_key == "ctrl+k"

    def test_yank_format_from_config_and_flag(self, tmp_path):
        cfg = write_config(tmp_path, "yank_format = markdown\n")
        assert parse_config(["-c", str(cfg)]).yank_format == "markdown"
        assert parse_config(["-c", str(cfg), "--yank-format", "title"]).yank_format == "title"

    def test_invalid_yank_format_exits(self, tmp_path, capsys):
        cfg = write_config(tmp_path, "yank_format = html\n")
        with pytest.raises(SystemExit):
            parse_config(["-c", str(cfg)])
        assert "invalid yank_format" in capsys.readouterr().err

    def test_yank_key_is_lowercased(self, tmp_path):
        cfg = write_config(tmp_path, "yank_key = Ctrl+K, F2\n")
        assert parse_config(["-c", str(cfg)]).yank_key == "ctrl+k,f2"

    def test_single_character_yank_key_keeps_its_case(self, tmp_path):
        assert parse_config(["-c", str(tmp_path / "nope"), "--yank-key", "K"]).yank_key == "K"

    @pytest.mark.parametrize("yank_key", ["ctrl-k", "C-y", "", "ctrl+y,"])
    def test_invalid_yank_key_exits(self, tmp_path, capsys, yank_key):
        with pytest.raises(SystemExit):
            parse_config(["-c", str(tmp_path / "nope"), "--yank-key", yank_key])
        assert "invalid yank_key" in capsys.readouterr().err


class TestExpansion:
    def test_tilde_expanded_in_notes_dir_and_log_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        config = parse_config(["-c", str(tmp_path / "nope"), "-l", "~/mylog", "~/mynotes"])
        assert str(config.notes_dir) == str(tmp_path / "mynotes")
        assert str(config.log_file) == str(tmp_path / "mylog")


class TestSetupLogging:
    @pytest.fixture(autouse=True)
    def clean_logger(self):
        logger = logging.getLogger("terminal_velocity")
        before = list(logger.handlers)
        yield
        for handler in list(logger.handlers):
            if handler not in before:
                logger.removeHandler(handler)

    def test_creates_missing_log_dir(self, tmp_path):
        cfg = parse_config(["-c", str(tmp_path / "nope"), "-l", str(tmp_path / "logs" / "tv.log")])
        setup_logging(cfg)
        assert (tmp_path / "logs").is_dir()
        assert logging.getLogger("terminal_velocity").handlers

    def test_unwritable_log_path_degrades_without_raising(self, tmp_path, capsys):
        blocker = tmp_path / "blocker"
        blocker.write_text("i am a file, not a dir")
        cfg = parse_config(["-c", str(tmp_path / "nope"), "-l", str(blocker / "tv.log")])
        setup_logging(cfg)  # must not raise
        assert "cannot open log file" in capsys.readouterr().err
