# Demo CI Setup — one-shot script.
#
# What this does:
#   1. Creates a private GitHub repo named "evals-demo" under your account
#   2. Pushes the current repo (main + demo branches) to GitHub
#   3. Stores ANTHROPIC_API_KEY as a repo secret (prompts you for the value)
#   4. Enables branch protection on main requiring the "fast-suite" check
#
# Prereqs: gh CLI installed and authenticated (`gh auth status`).
# Run from this folder:  ./setup-github.ps1

$ErrorActionPreference = 'Stop'

# --- Verify prereqs ----------------------------------------------------------
gh --version | Out-Null
gh auth status 2>&1 | Out-Null

if (-not (Test-Path '.git')) {
    throw "Not a git repo. Run this from the demo folder."
}

# --- Create repo & push ------------------------------------------------------
$repoName = 'evals-demo'
$owner    = (gh api user --jq .login).Trim()
$fullName = "$owner/$repoName"

Write-Host "==> Creating private repo $fullName" -ForegroundColor Cyan
$exists = gh repo view $fullName 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "    Repo already exists, skipping creation." -ForegroundColor Yellow
} else {
    gh repo create $repoName --private --description "Live-demo eval harness for S4 Talk B"
}

# Add remote if missing
$remote = git remote get-url origin 2>$null
if (-not $remote) {
    git remote add origin "https://github.com/$fullName.git"
}

Write-Host "==> Pushing main + demo branches" -ForegroundColor Cyan
git push -u origin main
git push -u origin demo/broken-tool

# --- Set the API key secret --------------------------------------------------
Write-Host "==> Setting GITHUB_MODELS_TOKEN repo secret" -ForegroundColor Cyan
Write-Host "    Paste your GitHub Models PAT when prompted (input is hidden):" -ForegroundColor Yellow
gh secret set GITHUB_MODELS_TOKEN --repo $fullName

# --- Branch protection -------------------------------------------------------
Write-Host "==> Enabling branch protection on main (require fast-suite)" -ForegroundColor Cyan
$protectionBody = @{
    required_status_checks = @{
        strict   = $true
        contexts = @('fast-suite')
    }
    enforce_admins                = $false
    required_pull_request_reviews = $null
    restrictions                  = $null
} | ConvertTo-Json -Depth 5

$protectionBody | gh api `
    --method PUT `
    -H 'Accept: application/vnd.github+json' `
    "repos/$fullName/branches/main/protection" `
    --input -

Write-Host ""
Write-Host "==> Setup complete." -ForegroundColor Green
Write-Host ""
Write-Host "Demo flow:" -ForegroundColor Cyan
Write-Host "  1. During the talk, run:"
Write-Host "       gh pr create --base main --head demo/broken-tool --title 'Rename tool parameter' --body 'Schema cleanup' --web"
Write-Host "  2. Wait ~60s for the 'fast-suite' check to run and fail (red X)"
Write-Host "  3. Point at the gray merge button: 'Required statuses must pass before merging'"
Write-Host ""
Write-Host "After each demo run, close (don't merge) the PR so the branch is reusable:"
Write-Host "       gh pr close <number> --delete-branch=false"
Write-Host ""
Write-Host "Repo URL: https://github.com/$fullName"
