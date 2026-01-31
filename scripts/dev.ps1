# Developer convenience script (PowerShell)
# Usage:
#   ./scripts/dev.ps1 install
#   ./scripts/dev.ps1 ingest
#   ./scripts/dev.ps1 suggest

param(
  [Parameter(Mandatory=$true)][string]$Command
)

if ($Command -eq "install") {
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  pip install -e .
  exit 0
}

.\.venv\Scripts\Activate.ps1

switch ($Command) {
  "ingest" { ki-agent ingest "data/uploads" }
  "suggest" { ki-agent suggest }
  "review" { ki-agent review }
  "apply" { ki-agent apply }
  "build-html" { ki-agent build-html }
  "index-kb" { ki-agent index-kb }
  "search" { ki-agent search "ventil" }
  default { throw "Unknown command: $Command" }
}
