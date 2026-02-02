# Developer convenience script (PowerShell)
# Usage:
#   ./backend/scripts/dev.ps1 install
#   ./backend/scripts/dev.ps1 ingest
#   ./backend/scripts/dev.ps1 suggest

param(
  [Parameter(Mandatory=$true)][string]$Command
)

# Ensure commands run from repo root regardless of where the script is invoked from.
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot

if ($Command -eq "install") {
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  pip install -e .
  exit 0
}

.\.venv\Scripts\Activate.ps1

switch ($Command) {
  "ingest" { ki-agent ingest "databases/data/uploads" }
  "suggest" { ki-agent suggest }
  "review" { ki-agent review }
  "apply" { ki-agent apply }
  "build-html" { ki-agent build-html }
  default { throw "Unknown command: $Command" }
}
