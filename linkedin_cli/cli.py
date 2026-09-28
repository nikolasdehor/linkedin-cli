"""Árvore de comandos do `linkedin`."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from . import backend, config
from .output import emit, eprint

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
EXIT_AUTH = 3
EXIT_SIGINT = 130


class UsageError(Exception):
    """Uso inválido: mensagem curta + exit 2."""


def _optional(args: dict) -> dict:
    return {k: v for k, v in args.items() if v is not None}


def _globals(suppress: bool = False) -> argparse.ArgumentParser:
    g = argparse.ArgumentParser(add_help=False)
    def maybe(default):
        return argparse.SUPPRESS if suppress else default
    g.add_argument("--version", action="version", version=f"linkedin {__version__}")
    g.add_argument("--motor", default=maybe(None), help="caminho do binário do motor MCP")
    g.add_argument("--timeout", type=float, default=maybe(None), help="timeout por chamada em segundos")
    g.add_argument("--json", action="store_true", default=maybe(False), help="saída JSON (scripts)")
    g.add_argument("--plain", action="store_true", default=maybe(False), help="saída JSONL estável, uma linha por item")
    g.add_argument("-q", "--quiet", action="store_true", default=maybe(False), help="silencia diagnósticos e saída humana")
    g.add_argument("-v", "--verbose", action="store_true", default=maybe(False), help="mostra a chamada ao motor em stderr")
    g.add_argument("--no-color", action="store_true", default=maybe(False), help="desliga cores")
    g.add_argument("--no-input", action="store_true", default=maybe(False), help="nunca pergunta; falha se faltar dado")
    g.add_argument("--dry-run", action="store_true", default=maybe(False), help="mostra o que faria sem executar")
    g.add_argument("--yes", action="store_true", default=maybe(False), help="pula confirmação de escrita")
    return g


def build_parser() -> argparse.ArgumentParser:
    g = _globals()
    gs = _globals(suppress=True)
    p = argparse.ArgumentParser(
        prog="linkedin",
        description="Opere o LinkedIn pelo terminal (perfil, feed, vagas, inbox, DMs).",
        epilog=(
            "exemplos:\n"
            "  linkedin auth login\n"
            "  linkedin feed --num-posts 5\n"
            "  linkedin jobs search \"engenheiro de dados\" --location Remoto\n"
            "  linkedin message send fulano --message-file msg.txt --dry-run\n"
            "  linkedin inbox --limit 5 --json | jq .\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[g],
    )

    sub = p.add_subparsers(dest="cmd", required=True, metavar="<comando>")

    auth = sub.add_parser("auth", parents=[gs], help="sessão do LinkedIn (login/status/logout)")
    auth.add_argument("action", choices=["login", "status", "logout"])

    prof = sub.add_parser("profile", parents=[gs], help="perfis")
    prof_sub = prof.add_subparsers(dest="sub", required=True, metavar="<ação>")
    me = prof_sub.add_parser("me", parents=[gs], help="seu próprio perfil")
    me.add_argument("--sections", default=None, help="ex: experience,skills,projects")
    me.add_argument("--max-scrolls", type=int, default=None)
    get = prof_sub.add_parser("get", parents=[gs], help="perfil de outra pessoa")
    get.add_argument("username")
    get.add_argument("--sections", default=None)
    get.add_argument("--max-scrolls", type=int, default=None)
    sidebar = prof_sub.add_parser("sidebar", parents=[gs], help="perfis recomendados na barra lateral")
    sidebar.add_argument("username")

    people = sub.add_parser("people", parents=[gs], help="buscar pessoas e conectar")
    people_sub = people.add_subparsers(dest="sub", required=True, metavar="<ação>")
    ps = people_sub.add_parser("search", parents=[gs], help="buscar pessoas")
    ps.add_argument("keywords")
    ps.add_argument("--location", default=None)
    ps.add_argument("--network", default=None, help="ex: F ou F,S (1º, 2º grau)")
    ps.add_argument("--current-company", default=None, help="URN numérica da empresa")
    pc = people_sub.add_parser("connect", parents=[gs], help="enviar convite (escrita)")
    pc.add_argument("username")
    pc.add_argument("--note", default=None, help="nota do convite")

    co = sub.add_parser("company", parents=[gs], help="empresas")
    co_sub = co.add_subparsers(dest="sub", required=True, metavar="<ação>")
    cog = co_sub.add_parser("get", parents=[gs], help="perfil da empresa")
    cog.add_argument("slug")
    cog.add_argument("--sections", default=None, help="ex: posts ou posts,jobs")
    cop = co_sub.add_parser("posts", parents=[gs], help="posts recentes da empresa")
    cop.add_argument("slug")
    cos = co_sub.add_parser("search", parents=[gs], help="buscar empresas")
    cos.add_argument("keywords")
    coe = co_sub.add_parser("employees", parents=[gs], help="funcionários e demografia")
    coe.add_argument("slug")
    coe.add_argument("--keywords", default=None, help="filtrar por nome, cargo ou skill")

    jobs = sub.add_parser("jobs", parents=[gs], help="vagas")
    jobs_sub = jobs.add_subparsers(dest="sub", required=True, metavar="<ação>")
    js = jobs_sub.add_parser("search", parents=[gs], help="buscar vagas")
    js.add_argument("keywords")
    js.add_argument("--location", default=None)
    js.add_argument("--max-pages", type=int, default=3)
    js.add_argument("--date-posted", default=None, help="past_hour, past_24_hours, past_week, past_month")
    js.add_argument("--job-type", default=None, help="full_time, contract, ... (vírgula)")
    js.add_argument("--experience-level", default=None, help="entry, mid_senior, ... (vírgula)")
    js.add_argument("--work-type", default=None, help="on_site, remote, hybrid (vírgula)")
    js.add_argument("--easy-apply", action="store_true")
    js.add_argument("--sort-by", default=None, help="date ou relevance")
    jg = jobs_sub.add_parser("get", parents=[gs], help="detalhes da vaga")
    jg.add_argument("job_id")

    feed = sub.add_parser("feed", parents=[gs], help="posts do seu feed")
    feed.add_argument("--num-posts", type=int, default=10)

    inbox = sub.add_parser("inbox", parents=[gs], help="caixa de entrada")
    inbox_sub = inbox.add_subparsers(dest="sub", required=False, metavar="<ação>")
    inbox_list = inbox_sub.add_parser("list", parents=[gs], help="conversas recentes")
    inbox_list.add_argument("--limit", type=int, default=20)
    inbox_search = inbox_sub.add_parser("search", parents=[gs], help="buscar nas mensagens")
    inbox_search.add_argument("keywords")
    inbox_search.add_argument("--limit", type=int, default=20)
    inbox_read = inbox_sub.add_parser("read", parents=[gs], help="ler uma conversa")
    inbox_read.add_argument("--username", default=None)
    inbox_read.add_argument("--thread-id", default=None)
    inbox_read.add_argument("--index", type=int, default=0)
    inbox.add_argument("--limit", type=int, default=20, help="atalho para `inbox list --limit`")

    msg = sub.add_parser("message", parents=[gs], help="mensagens diretas")
    msg_sub = msg.add_subparsers(dest="sub", required=True, metavar="<ação>")
    send = msg_sub.add_parser("send", parents=[gs], help="enviar DM (escrita)")
    send.add_argument("username")
    send.add_argument("--message", default=None, help="texto; use - para ler do stdin")
    send.add_argument("--message-file", default=None, help="arquivo com o texto")
    send.add_argument("--profile-urn", default=None)
    return p


def _read_message(parsed: argparse.Namespace) -> str:
    text, path = parsed.message, parsed.message_file
    if text and path:
        raise UsageError("use --message ou --message-file, não ambos")
    if path:
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError as exc:
            raise UsageError(f"não li {path}: {exc}")
    elif text == "-":
        text = sys.stdin.read()
    if not text or not text.strip():
        raise UsageError("mensagem vazia: informe --message, --message-file ou stdin com -")
    return text.strip()


def resolve_call(parsed: argparse.Namespace) -> tuple[str, dict, str | None]:
    """Mapeia args para (tool, args, plano_de_escrita ou None). Pura e testável."""
    cmd, sub = parsed.cmd, getattr(parsed, "sub", None)
    if cmd == "profile" and sub == "me":
        return "get_my_profile", _optional({"sections": parsed.sections, "max_scrolls": parsed.max_scrolls}), None
    if cmd == "profile" and sub == "get":
        return "get_person_profile", _optional({
            "linkedin_username": parsed.username,
            "sections": parsed.sections,
            "max_scrolls": parsed.max_scrolls,
        }), None
    if cmd == "profile" and sub == "sidebar":
        return "get_sidebar_profiles", {"linkedin_username": parsed.username}, None
    if cmd == "people" and sub == "search":
        network = parsed.network.split(",") if parsed.network else None
        return "search_people", _optional({
            "keywords": parsed.keywords,
            "location": parsed.location,
            "network": network,
            "current_company": parsed.current_company,
        }), None
    if cmd == "people" and sub == "connect":
        plan = f"convidar {parsed.username}" + (f" com nota ({len(parsed.note)} chars)" if parsed.note else "")
        return "connect_with_person", _optional({
            "linkedin_username": parsed.username, "note": parsed.note,
        }), plan
    if cmd == "company" and sub == "get":
        return "get_company_profile", _optional({"company_name": parsed.slug, "sections": parsed.sections}), None
    if cmd == "company" and sub == "posts":
        return "get_company_posts", {"company_name": parsed.slug}, None
    if cmd == "company" and sub == "search":
        return "search_companies", {"keywords": parsed.keywords}, None
    if cmd == "company" and sub == "employees":
        return "get_company_employees", _optional({"company_name": parsed.slug, "keywords": parsed.keywords}), None
    if cmd == "jobs" and sub == "search":
        args = _optional({
            "keywords": parsed.keywords,
            "location": parsed.location,
            "max_pages": parsed.max_pages,
            "date_posted": parsed.date_posted,
            "job_type": parsed.job_type,
            "experience_level": parsed.experience_level,
            "work_type": parsed.work_type,
            "sort_by": parsed.sort_by,
        })
        if parsed.easy_apply:
            args["easy_apply"] = True
        return "search_jobs", args, None
    if cmd == "jobs" and sub == "get":
        return "get_job_details", {"job_id": parsed.job_id}, None
    if cmd == "feed":
        return "get_feed", {"num_posts": parsed.num_posts}, None
    if cmd == "inbox" and sub in (None, "list"):
        return "get_inbox", {"limit": parsed.limit}, None
    if cmd == "inbox" and sub == "search":
        return "search_conversations", {"keywords": parsed.keywords, "limit": parsed.limit}, None
    if cmd == "inbox" and sub == "read":
        if not parsed.username and not parsed.thread_id:
            raise UsageError("inbox read exige --username ou --thread-id")
        return "get_conversation", _optional({
            "linkedin_username": parsed.username,
            "thread_id": parsed.thread_id,
            "index": parsed.index,
        }), None
    if cmd == "message" and sub == "send":
        text = _read_message(parsed)
        plan = f"enviar DM para {parsed.username} ({len(text)} chars)"
        return "send_message", _optional({
            "linkedin_username": parsed.username,
            "message": text,
            "confirm_send": True,
            "profile_urn": parsed.profile_urn,
        }), plan
    raise UsageError(f"comando não suportado: {cmd} {sub}")


def _confirmed(plan: str, parsed: argparse.Namespace) -> bool:
    if parsed.dry_run:
        if not parsed.quiet:
            eprint(f"[dry-run] {plan} (nada executado)")
        return False
    if parsed.yes:
        return True
    if parsed.no_input:
        raise UsageError(f"escrita exige confirmação: {plan}. Use --yes ou rode sem --no-input.")
    if not sys.stdin.isatty():
        raise UsageError(f"confirmação necessária ({plan}): use --yes ou rode em terminal interativo.")
    answer = input(f"{plan}. Confirmar? [s/N] ").strip().lower()
    return answer in ("s", "sim", "y", "yes")


def main(argv: list[str] | None = None) -> int:
    try:
        try:
            parsed = build_parser().parse_args(argv)
        except SystemExit as exc:
            return EXIT_OK if exc.code == 0 else EXIT_USAGE
        settings = config.apply_env(config.load_file_settings())
        fmt = "json" if parsed.json else "plain" if parsed.plain else settings.output
        timeout = parsed.timeout if parsed.timeout is not None else settings.timeout
        motor = config.find_motor(parsed.motor or settings.motor)
        color = config.colors_allowed(parsed.no_color) and fmt == "human"

        if parsed.cmd == "auth":
            try:
                code = backend.run_auth(motor, parsed.action)
            except backend.MotorNotFound as exc:
                eprint(f"erro: {exc}")
                return EXIT_FAIL
            return EXIT_OK if code == 0 else EXIT_FAIL

        if parsed.dry_run and parsed.cmd not in ("people", "message"):
            eprint("[dry-run] comando de leitura: nada a simular além da chamada")
        tool, args, plan = resolve_call(parsed)
        if plan is not None and not _confirmed(plan, parsed):
            return EXIT_OK
        if parsed.verbose and not parsed.quiet:
            shown = dict(args)
            if tool == "send_message" and "message" in shown:
                shown["message"] = "<%d chars>" % len(shown["message"])
            eprint(f"> {tool} {shown}")
        data = backend.call_tool(motor, tool, args, timeout, quiet_child=not parsed.verbose)
        if not (parsed.quiet and fmt == "human"):
            emit(data, fmt, color)
        return EXIT_OK
    except UsageError as exc:
        eprint(f"erro de uso: {exc}")
        return EXIT_USAGE
    except backend.AuthError as exc:
        eprint(f"não autenticado: {exc}")
        return EXIT_AUTH
    except backend.MotorError as exc:
        eprint(f"erro: {exc}")
        return EXIT_FAIL
    except KeyboardInterrupt:
        eprint("interrompido")
        return EXIT_SIGINT


if __name__ == "__main__":
    raise SystemExit(main())
