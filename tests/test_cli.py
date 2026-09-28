"""Testes do linkedin-cli. Sem rede, sem LinkedIn: motor falso via stdio real."""

import io
import json
import os
import stat
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from linkedin_cli import backend, cli, config
from linkedin_cli.output import emit

FAKE_MOTOR = Path(__file__).resolve().parent / "fake_motor.py"


@pytest.fixture()
def fake_motor():
    FAKE_MOTOR.chmod(FAKE_MOTOR.stat().st_mode | stat.S_IEXEC)
    return str(FAKE_MOTOR)


def parse(*argv):
    return cli.build_parser().parse_args(list(argv))


# --- resolve_call: cada comando mapeia para a tool certa ---

@pytest.mark.parametrize(("argv", "tool", "args"), [
    (("profile", "me"), "get_my_profile", {}),
    (("profile", "me", "--sections", "skills", "--max-scrolls", "2"),
     "get_my_profile", {"sections": "skills", "max_scrolls": 2}),
    (("profile", "get", "fulano"), "get_person_profile", {"linkedin_username": "fulano"}),
    (("profile", "sidebar", "fulano"), "get_sidebar_profiles", {"linkedin_username": "fulano"}),
    (("people", "search", "dev"), "search_people", {"keywords": "dev"}),
    (("people", "search", "dev", "--network", "F,S"),
     "search_people", {"keywords": "dev", "network": ["F", "S"]}),
    (("company", "get", "acme"), "get_company_profile", {"company_name": "acme"}),
    (("company", "posts", "acme"), "get_company_posts", {"company_name": "acme"}),
    (("company", "search", "fintech"), "search_companies", {"keywords": "fintech"}),
    (("company", "employees", "acme"), "get_company_employees", {"company_name": "acme"}),
    (("jobs", "get", "123"), "get_job_details", {"job_id": "123"}),
    (("jobs", "search", "dados"), "search_jobs", {"keywords": "dados", "max_pages": 3}),
    (("jobs", "search", "dados", "--easy-apply", "--work-type", "remote"),
     "search_jobs", {"keywords": "dados", "max_pages": 3, "easy_apply": True, "work_type": "remote"}),
    (("feed",), "get_feed", {"num_posts": 10}),
    (("inbox", "list"), "get_inbox", {"limit": 20}),
    (("inbox",), "get_inbox", {"limit": 20}),
    (("inbox", "--limit", "5"), "get_inbox", {"limit": 5}),
    (("inbox", "search", "proposta"), "search_conversations", {"keywords": "proposta", "limit": 20}),
    (("inbox", "read", "--username", "fulano"),
     "get_conversation", {"linkedin_username": "fulano", "index": 0}),
    (("inbox", "read", "--thread-id", "abc"),
     "get_conversation", {"thread_id": "abc", "index": 0}),
])
def test_resolve_read_commands(argv, tool, args):
    got_tool, got_args, plan = cli.resolve_call(parse(*argv))
    assert got_tool == tool
    assert got_args == args
    assert plan is None


def test_resolve_connect():
    tool, args, plan = cli.resolve_call(parse("people", "connect", "fulano", "--note", "oi"))
    assert tool == "connect_with_person"
    assert args == {"linkedin_username": "fulano", "note": "oi"}
    assert "fulano" in plan


def test_resolve_send_message():
    tool, args, plan = cli.resolve_call(parse("message", "send", "fulano", "--message", "olá"))
    assert tool == "send_message"
    assert args["confirm_send"] is True
    assert args["message"] == "olá"
    assert "fulano" in plan


def test_resolve_send_message_file(tmp_path):
    f = tmp_path / "msg.txt"
    f.write_text("  texto do arquivo\n", encoding="utf-8")
    _, args, _ = cli.resolve_call(parse("message", "send", "u", "--message-file", str(f)))
    assert args["message"] == "texto do arquivo"


def test_resolve_errors():
    with pytest.raises(cli.UsageError):
        cli.resolve_call(parse("inbox", "read"))
    with pytest.raises(cli.UsageError):
        cli.resolve_call(parse("message", "send", "u", "--message", "a", "--message-file", "b"))
    with pytest.raises(cli.UsageError):
        cli.resolve_call(parse("message", "send", "u", "--message", "  "))


# --- confirmação / dry-run ---

def test_dry_run_skips_write(capsys):
    parsed = parse("message", "send", "u", "--message", "oi", "--dry-run")
    assert cli._confirmed("plano", parsed) is False
    assert "dry-run" in capsys.readouterr().err


def test_yes_skips_prompt():
    assert cli._confirmed("plano", parse("message", "send", "u", "--message", "oi", "--yes")) is True


def test_no_input_requires_yes():
    with pytest.raises(cli.UsageError):
        cli._confirmed("plano", parse("message", "send", "u", "--message", "oi", "--no-input"))


# --- saída ---

def test_emit_json_and_plain():
    buf = io.StringIO()
    with redirect_stdout(buf):
        emit({"a": 1}, "json")
    assert json.loads(buf.getvalue()) == {"a": 1}
    buf = io.StringIO()
    with redirect_stdout(buf):
        emit([{"a": 1}, {"a": 2}], "plain")
    lines = buf.getvalue().strip().split("\n")
    assert [json.loads(line) for line in lines] == [{"a": 1}, {"a": 2}]


def test_emit_human_table():
    buf = io.StringIO()
    with redirect_stdout(buf):
        emit([{"nome": "Ana", "cargo": "Dev"}], "human")
    out = buf.getvalue()
    assert "Ana" in out and "nome" in out


# --- config ---

def test_config_precedence(tmp_path, monkeypatch):
    cfg = tmp_path / "config.toml"
    cfg.write_text('motor = "/x"\ntimeout = 10\noutput = "json"\n', encoding="utf-8")
    s = config.load_file_settings(cfg)
    assert (s.motor, s.timeout, s.output) == ("/x", 10.0, "json")
    monkeypatch.setenv("LINKEDIN_TIMEOUT", "5")
    monkeypatch.setenv("LINKEDIN_OUTPUT", "plain")
    s = config.apply_env(s)
    assert (s.timeout, s.output) == (5.0, "plain")
    assert config.find_motor("/explicit") == "/explicit"


# --- backend contra motor falso (transporte MCP real) ---

def test_backend_echo(fake_motor):
    data = backend.call_tool(fake_motor, "get_feed", {"num_posts": 3}, 30)
    assert data == {"tool": "get_feed", "args": {"num_posts": 3}}


def test_backend_auth_error(fake_motor):
    with pytest.raises(backend.AuthError):
        backend.call_tool(fake_motor, "boom", {}, 30)


def test_backend_preflight_no_session(fake_motor, monkeypatch):
    monkeypatch.setenv("FAKE_NO_SESSION", "1")
    with pytest.raises(backend.AuthError):
        backend.call_tool(fake_motor, "get_feed", {}, 30)


def test_backend_motor_missing():
    with pytest.raises(backend.MotorNotFound):
        backend.call_tool(None, "get_feed", {}, 5)


# --- main wiring (backend mockado) ---

def test_main_json(monkeypatch, capsys):
    monkeypatch.setattr(backend, "call_tool", lambda *a, **k: {"ok": True})
    rc = cli.main(["--motor", "/fake", "--json", "feed", "--num-posts", "2"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out) == {"ok": True}


def test_main_global_flags_after_subcommand(monkeypatch, capsys):
    seen = {}
    def fake_call(motor, tool, args, timeout, **k):
        seen.update(motor=motor, tool=tool, timeout=timeout)
        return {"ok": True}
    monkeypatch.setattr(backend, "call_tool", fake_call)
    rc = cli.main(["feed", "--num-posts", "2", "--json", "--motor", "/fake", "--timeout", "12"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out) == {"ok": True}
    assert seen == {"motor": "/fake", "tool": "get_feed", "timeout": 12.0}


def test_main_auth_error_exit_code(monkeypatch, capsys):
    def boom(*a, **k):
        raise backend.AuthError("sem sessão")
    monkeypatch.setattr(backend, "call_tool", boom)
    assert cli.main(["--motor", "/fake", "feed"]) == cli.EXIT_AUTH


def test_main_usage_error_exit_code(capsys):
    assert cli.main(["--motor", "/fake", "inbox", "read"]) == cli.EXIT_USAGE


def test_main_help_and_version(capsys):
    assert cli.main(["--help"]) == 0
    assert cli.main(["--version"]) == 0
    assert cli.main(["--bad-flag"]) == cli.EXIT_USAGE
    # sem variável de ambiente que quebre outros testes
    os.environ.pop("LINKEDIN_MOTOR", None)
