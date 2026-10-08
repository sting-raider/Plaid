$ErrorActionPreference = "Stop"

Write-Host "Fetching pinned reference repositories..."
python "$PSScriptRoot\fetch_refs.py"

Write-Host "Reference lab ready under .refs/"
Write-Host "Next: install stable Rust, then run: cargo test --workspace"
