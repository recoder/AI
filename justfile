set shell := ["pwsh", "-NoLogo", "-NoProfile", "-Command"]

default:
    @just --list

setup:
    pwsh -NoProfile -File scripts/setup.ps1

bootstrap profile='':
    pwsh -NoProfile -File scripts/workspace.ps1 -Profile '{{profile}}'

plan profile='':
    pwsh -NoProfile -File scripts/workspace.ps1 -Profile '{{profile}}' -WhatIf

directories:
    pwsh -NoProfile -File scripts/directories.ps1

packages:
    pwsh -NoProfile -File scripts/packages.ps1

status profile='':
    pwsh -NoProfile -File scripts/status.ps1 -Profile '{{profile}}'

doctor profile='':
    pwsh -NoProfile -File scripts/doctor.ps1 -Profile '{{profile}}'

doctor-helpers:
    pwsh -NoProfile -File scripts/doctor.ps1 -HelpersOnly

test:
    pwsh -NoProfile -File tests/bootstrap.tests.ps1
    pwsh -NoProfile -File tests/yue.tests.ps1

source tool:
    pwsh -NoProfile -File scripts/tools.ps1 -Operation source -Tool '{{tool}}'

validate tool:
    pwsh -NoProfile -File scripts/tools.ps1 -Operation validate -Tool '{{tool}}'

plan-tool tool:
    pwsh -NoProfile -File scripts/tools.ps1 -Operation plan -Tool '{{tool}}'

install tool:
    pwsh -NoProfile -File scripts/tools.ps1 -Operation install -Tool '{{tool}}'

models tool:
    pwsh -NoProfile -File scripts/tools.ps1 -Operation models -Tool '{{tool}}'

test-music:
    pwsh -NoProfile -File tests/music.ps1

repos:
    pwsh -NoProfile -File scripts/repositories.ps1
