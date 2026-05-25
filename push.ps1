# Usage: .\push.ps1 "commit message"
# Adds all changes, commits with the supplied message, pushes to origin/main.
param(
    [Parameter(Mandatory=$true)]
    [string]$Message
)
git add .
git commit -m $Message
git push
