param(
    [Parameter(Mandatory = $true)][string]$InputPath,
    [Parameter(Mandatory = $true)][string]$OutputDir
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$resolvedInput = (Resolve-Path -LiteralPath $InputPath).Path
$resolvedOutput = [System.IO.Path]::GetFullPath($OutputDir)
[System.IO.Directory]::CreateDirectory($resolvedOutput) | Out-Null

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0

try {
    $doc = $word.Documents.Open($resolvedInput, $false, $true)
    try {
        $pageCount = $doc.ComputeStatistics(2)
        $pdfPath = Join-Path $resolvedOutput 'REPORT.pdf'
        $doc.ExportAsFixedFormat($pdfPath, 17)

        for ($page = 1; $page -le $pageCount; $page++) {
            $start = $doc.GoTo(1, 1, $page).Start
            if ($page -lt $pageCount) {
                $end = $doc.GoTo(1, 1, $page + 1).Start - 1
            } else {
                $end = $doc.Content.End - 1
            }
            $range = $doc.Range($start, $end)
            $range.CopyAsPicture()
            Start-Sleep -Milliseconds 500
            $image = [System.Windows.Forms.Clipboard]::GetImage()
            if ($null -eq $image) {
                throw "Word did not place page $page on the image clipboard."
            }
            try {
                $pngPath = Join-Path $resolvedOutput ("page-{0}.png" -f $page)
                $image.Save($pngPath, [System.Drawing.Imaging.ImageFormat]::Png)
            } finally {
                $image.Dispose()
            }
        }
        Write-Output "pages=$pageCount"
        Write-Output $pdfPath
    } finally {
        $doc.Close($false)
    }
} finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}
