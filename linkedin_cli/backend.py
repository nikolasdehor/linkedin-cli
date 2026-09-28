"""Backend: fala com o motor (servidor MCP) via stdio e delega auth."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

AUTH_HINTS = (
    "no valid source session",
    "no valid linkedin session",
    "login browser window",
    "not authenticated",
    "authentication required",
    "please log in",
    "session expired",
)


class MotorError(Exception):
    """Falha no motor (tool, transporte, timeout)."""


class AuthError(MotorError):
    """Sem sessão válida: rode `linkedin auth login`."""


class MotorNotFound(MotorError):
    """Binário do motor não encontrado."""


def _looks_like_auth_error(text: str) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in AUTH_HINTS)


def _normalize(content: list) -> Any:
    texts = [getattr(block, "text", None) for block in content]
    texts = [t for t in texts if isinstance(t, str)]
    if not texts:
        return None
    parsed = []
    for text in texts:
        try:
            parsed.append(json.loads(text))
        except (json.JSONDecodeError, ValueError):
            parsed.append(text)
    if len(parsed) == 1:
        return parsed[0]
    return parsed


async def _call(motor: str, tool: str, args: dict, timeout: float) -> Any:
    params = StdioServerParameters(command=motor, args=[])
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(session.initialize(), timeout)
                result = await asyncio.wait_for(
                    session.call_tool(tool, args), timeout
                )
        data = _normalize(list(result.content or []))
        if getattr(result, "is_error", getattr(result, "isError", False)):
            text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
            if _looks_like_auth_error(text):
                raise AuthError(f"{text}\nRode `linkedin auth login` e tente de novo.")
            raise MotorError(text)
        return data
    except FileNotFoundError:
        raise MotorNotFound(f"motor não encontrado: {motor}")
    except (asyncio.TimeoutError, TimeoutError):
        raise MotorError(f"tempo esgotado após {timeout:g}s chamando {tool}")
    except AuthError:
        raise
    except MotorError:
        raise
    except Exception as exc:  # transporte MCP quebrou: mensagem legível
        raise MotorError(f"falha ao falar com o motor: {exc}")


def check_session(motor: str, timeout: float = 30) -> None:
    """Preflight rápido: falha limpa sem abrir janela de login de surpresa."""
    try:
        proc = subprocess.run(
            [motor, "--status"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return  # ambíguo: deixa a tool responder
    out = ((proc.stdout or "") + (proc.stderr or "")).lower()
    if proc.returncode != 0 and "no valid" in out:
        raise AuthError("sem sessão válida no LinkedIn. Rode `linkedin auth login` e tente de novo.")


@contextmanager
def _child_stderr_to_devnull():
    """O filho MCP herda o fd 2: desvia o ruído dele sem tocar no pai."""
    sys.stderr.flush()
    old_fd = os.dup(2)
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, 2)
        yield
    finally:
        sys.stderr.flush()
        os.dup2(old_fd, 2)
        os.close(old_fd)
        os.close(devnull)


def call_tool(
    motor: str | None, tool: str, args: dict, timeout: float, *, quiet_child: bool = True
) -> Any:
    if not motor:
        raise MotorNotFound(
            "motor não encontrado. Instale o mcp-server-linkedin ou informe "
            "--motor / LINKEDIN_MOTOR."
        )
    check_session(motor)
    if quiet_child:
        with _child_stderr_to_devnull():
            return asyncio.run(_call(motor, tool, args, timeout))
    return asyncio.run(_call(motor, tool, args, timeout))


def run_auth(motor: str | None, action: str) -> int:
    """Delega login/status/logout ao motor com stdio herdado (interativo)."""
    if not motor:
        raise MotorNotFound(
            "motor não encontrado. Instale o mcp-server-linkedin ou informe "
            "--motor / LINKEDIN_MOTOR."
        )
    try:
        proc = subprocess.run([motor, f"--{action}"])
    except FileNotFoundError:
        raise MotorNotFound(f"motor não encontrado: {motor}")
    return proc.returncode
