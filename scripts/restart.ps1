# Registry indicators are warnings until a new restart requirement blocks package reconciliation.
function Get-WorkspaceRestartReasons {
    foreach ($entry in @(
        @{Name='Component servicing'; Path='HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'},
        @{Name='Windows Update'; Path='HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'})) {
        if (Test-Path -LiteralPath $entry.Path) { $entry.Name }
    }
}
