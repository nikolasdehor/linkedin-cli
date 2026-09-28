# linkedin

Opere o LinkedIn pelo terminal: perfil, feed, vagas, empresas, inbox e DMs.

Funciona sobre o motor `mcp-server-linkedin` (sessão de navegador persistente).
O CLI fala com o motor via protocolo MCP e cuida de args, saída e segurança.

## Instalação

```sh
uv tool install /Users/nikolas/Projects/linkedin-cli
linkedin auth login     # abre o navegador uma vez; faça login no LinkedIn
linkedin auth status    # confere a sessão
```

Requer Python 3.11+ e o motor no PATH (`linkedin-scraper-mcp` ou `mcp-server-linkedin`).

## Uso

```
linkedin [flags globais] <comando> [args] [flags]
linkedin profile me [--sections skills,projects] [--max-scrolls 2]
linkedin profile get USERNAME [--sections ...] [--max-scrolls N]
linkedin profile sidebar USERNAME
linkedin people search KEYWORDS [--location L] [--network F,S] [--current-company URN]
linkedin people connect USERNAME [--note TEXTO]
linkedin company get SLUG [--sections posts,jobs]
linkedin company posts SLUG
linkedin company search KEYWORDS
linkedin company employees SLUG [--keywords K]
linkedin jobs search KEYWORDS [--location L] [--max-pages N] [--date-posted X]
                              [--job-type T] [--experience-level E] [--work-type W]
                              [--easy-apply] [--sort-by S]
linkedin jobs get JOB_ID
linkedin feed [--num-posts N]
linkedin inbox [list] [--limit N]
linkedin inbox search KEYWORDS [--limit N]
linkedin inbox read (--username U | --thread-id T) [--index N]
linkedin message send USERNAME (--message TEXTO | --message-file F) [--profile-urn U]
linkedin auth login|status|logout
```

Flags globais (valem antes ou depois do subcomando):

| Flag | Efeito |
|---|---|
| `-h, --help` | ajuda (também `linkedin <cmd> --help`) |
| `--version` | versão em stdout |
| `--json` | saída JSON (scripts) |
| `--plain` | JSONL estável, um item por linha |
| `-q, --quiet` | silencia diagnósticos e saída humana |
| `-v, --verbose` | mostra a chamada ao motor em stderr |
| `--no-color` | desliga cores (também `NO_COLOR=1`, `TERM=dumb`) |
| `--no-input` | nunca pergunta; falha se faltar dado |
| `--dry-run` | mostra o plano de escrita sem executar |
| `--yes` | pula confirmação de escrita |
| `--motor PATH` | binário do motor (padrão: procura no PATH) |
| `--timeout SEG` | timeout por chamada (padrão: 180) |

## Contrato de I/O

- Dados vão para **stdout**, diagnósticos e erros para **stderr**.
- Sucesso humano imprime tabelas/resumo; `--json` imprime o dado cru; `--plain` imprime JSONL.
- Escrita (`people connect`, `message send`) pede confirmação em terminal interativo;
  sem TTY exige `--yes`. `--dry-run` nunca executa.
- Segredos nunca via flag de processo além do necessário: prefira `--message-file`.

## Exit codes

| Código | Significado |
|---|---|
| 0 | sucesso (inclui `--dry-run` e ajuda) |
| 1 | falha do motor ou da operação |
| 2 | uso inválido (args, confirmação ausente) |
| 3 | sem sessão (`linkedin auth login`) |
| 130 | interrompido (Ctrl-C) |

## Config

Precedência: flags > env > `~/.config/linkedin/config.toml` > padrões.

```toml
# ~/.config/linkedin/config.toml (ou $XDG_CONFIG_HOME/linkedin/config.toml)
motor = "/Users/nikolas/.local/bin/linkedin-scraper-mcp"
timeout = 180
output = "human"  # human | json | plain
```

Env: `LINKEDIN_MOTOR`, `LINKEDIN_TIMEOUT`, `LINKEDIN_OUTPUT`.

## Exemplos

```sh
linkedin auth login
linkedin feed --num-posts 5
linkedin profile get williamhgates --sections experience,skills
linkedin people search "engenheiro de dados" --location Remoto --network F
linkedin jobs search "backend python" --location "São Paulo" --work-type remote --easy-apply
linkedin jobs get 4252026496 --json
linkedin company employees acme --keywords engenheiro
linkedin inbox --limit 5
linkedin inbox search "proposta" --plain | head -3
linkedin inbox read --username fulano
linkedin message send fulano --message-file convite.txt --dry-run
echo "obrigado pelo retorno!" | linkedin message send fulano --message - --yes
linkedin people connect fulana --note "Oi! Vamos nos conectar?" --yes
```

## Limites conhecidos

O motor atual não expõe: publicar post, curtir/reagir, comentar, seguir,
aceitar convite avulso nem candidatura easy-apply. Esses comandos entram quando
houver backend (API oficial ou automação própria validada com sessão real).

## Desenvolvimento

```sh
cd /Users/nikolas/Projects/linkedin-cli
uv venv && uv pip install --python .venv/bin/python -e . pytest
.venv/bin/python -m pytest tests/ -q
ruff check .
```
