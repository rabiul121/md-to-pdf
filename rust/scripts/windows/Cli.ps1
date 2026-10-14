param([Parameter(ValueFromRemainingArguments = $true)][string[]]$AppArgs)
$ErrorActionPreference = "Stop"
$RustRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
cargo run --manifest-path (Join-Path $RustRoot "Cargo.toml") --release --bin pdf-creator-studio-cli -- @AppArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
