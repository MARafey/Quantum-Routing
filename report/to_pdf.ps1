# Converts the report .docx to PDF with Microsoft Word (must be installed).
# Usage:  powershell -File report/to_pdf.ps1
#
# Notes from getting this to work reliably:
#  - Word is driven from inside a PowerShell job; driving it directly from the script hung on the machine we tested.
#  - The PDF is written to a temp folder first and then copied, which avoids writing into a synced folder.
#  - On timeout only a Word process started by this script is stopped, never one the user already had open.
$ErrorActionPreference = "Stop"
$dir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$docx = Join-Path $dir "Quantum_Relief_Routing_Report.docx"
$pdf = Join-Path $dir "Quantum_Relief_Routing_Report.pdf"
$tmp = Join-Path $env:TEMP "Quantum_Relief_Routing_Report.pdf"
if (Test-Path $tmp) { Remove-Item $tmp -Force }
$started = Get-Date

$job = Start-Job -ArgumentList $docx, $tmp {
    param($src, $out)
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0                                   # wdAlertsNone: never block on a dialog
    try {
        $doc = $word.Documents.Open($src, $false, $true, $false)   # no conversion prompt, read-only
        "opened, $($doc.ComputeStatistics(2)) pages"                  # 2 = wdStatisticPages
        $doc.ExportAsFixedFormat($out, 17)                            # 17 = wdExportFormatPDF
        $doc.Close($false)
    } finally {
        $word.Quit()
    }
}
if (-not (Wait-Job $job -Timeout 180)) {
    Stop-Job $job
    Get-Process WINWORD -ErrorAction SilentlyContinue | Where-Object { $_.StartTime -ge $started } | Stop-Process -Force
    throw "Word did not finish within 180 s"
}
Receive-Job $job
Copy-Item $tmp $pdf -Force
Write-Output "wrote $pdf"
