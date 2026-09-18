set shell := ["pwsh", "-NoLogo", "-NoProfile", "-Command"]

default:
    @just --list

setup:
    pwsh -NoProfile -File scripts/setup.ps1

bootstrap:
    pwsh -NoProfile -File scripts/workspace.ps1

plan:
    pwsh -NoProfile -File scripts/workspace.ps1 -WhatIf

directories:
    pwsh -NoProfile -File scripts/directories.ps1

packages:
    pwsh -NoProfile -File scripts/packages.ps1

status:
    pwsh -NoProfile -File scripts/status.ps1

doctor:
    pwsh -NoProfile -File scripts/doctor.ps1

test:
    pwsh -NoProfile -File tests/bootstrap.tests.ps1
