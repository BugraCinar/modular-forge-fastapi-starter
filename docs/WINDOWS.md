# Windows development with PowerShell

Use a supported Python installation and `uv`, then open PowerShell at the
repository root. Paths containing spaces are supported; quote paths in your
own commands. The default development configuration needs no external database
or Redis process.

```powershell
uv sync --frozen --all-extras
uv run --no-sync modular-forge init-env
uv run --no-sync modular-forge migrate
uv run --no-sync uvicorn modular_forge.app:create_app --factory --host 127.0.0.1 --port 8000 --no-proxy-headers --no-server-header
```

No activation script or execution-policy change is needed when using `uv run`.
Stop the server with Ctrl+C. In a second terminal at the same repository root:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/ready
uv run --no-sync modular-forge create-admin --email admin@example.com --username local_admin
```

`create-admin` prompts for a password. `init-env` refuses to overwrite an existing
`.env`; keep the existing file when restarting development. Startup reads `.env`
from the current directory, so run management and server commands from the root.

For a disposable external database contract, use a PowerShell environment variable:

```powershell
$env:CONTRACT_DATABASE_URL = '<URL of your disposable forge_contract database>'
uv run --frozen --all-extras pytest tests/test_persistence.py
Remove-Item Env:CONTRACT_DATABASE_URL
```

Use [the database guide](DATABASES.md) for the selected driver and MongoDB replica
set requirements. A POSIX file-permission test skips on Windows; Linux CI covers
that behavior. Never paste the private environment file into a bug report.
