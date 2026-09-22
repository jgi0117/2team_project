param(
    [Parameter(Mandatory = $true)][string]$Workspace
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$root = [System.IO.Path]::GetFullPath($Workspace)
$outDir = Join-Path $root 'outputs\model3\evaluation'
$csvPath = Join-Path $outDir 'model_failure_comparison.csv'
$imagePath = Join-Path $outDir 'model_failure_comparison.png'
$docxPath = Join-Path $outDir 'REPORT.docx'
$renderDir = Join-Path $root '.tmp\report_render_word'
[System.IO.Directory]::CreateDirectory($renderDir) | Out-Null

$rows = Import-Csv -LiteralPath $csvPath
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0

function Add-ReportParagraph {
    param(
        [object]$Document,
        [string]$Text,
        [double]$Size = 10,
        [bool]$Bold = $false,
        [int]$Alignment = 0,
        [double]$Before = 0,
        [double]$After = 3,
        [bool]$KeepWithNext = $false
    )
    $range = $Document.Range($Document.Content.End - 1, $Document.Content.End - 1)
    $range.Text = $Text
    $paragraph = $range.Paragraphs.Item(1)
    $paragraph.Alignment = $Alignment
    $paragraph.SpaceBefore = $Before
    $paragraph.SpaceAfter = $After
    $paragraph.LineSpacingRule = 0
    $paragraph.KeepWithNext = $(if ($KeepWithNext) { -1 } else { 0 })
    $paragraph.Range.Font.Name = 'Malgun Gothic'
    $paragraph.Range.Font.NameFarEast = 'Malgun Gothic'
    $paragraph.Range.Font.Size = $Size
    $paragraph.Range.Font.Bold = $(if ($Bold) { -1 } else { 0 })
    $paragraph.Range.Font.Color = 0
    $paragraph.Range.InsertParagraphAfter()
    return $paragraph
}

try {
    $doc = $word.Documents.Add()
    try {
        Write-Output 'stage=document-created'
        $section = $doc.Sections.Item(1)
        $section.PageSetup.PaperSize = 2
        $section.PageSetup.Orientation = 0
        $section.PageSetup.TopMargin = 32.4
        $section.PageSetup.BottomMargin = 32.4
        $section.PageSetup.LeftMargin = 39.6
        $section.PageSetup.RightMargin = 39.6

        $normal = $doc.Styles.Item(-1)
        $normal.Font.Name = 'Malgun Gothic'
        $normal.Font.NameFarEast = 'Malgun Gothic'
        $normal.Font.Size = 10
        $normal.Font.Color = 0
        Write-Output 'stage=page-and-styles'

        $title = Add-ReportParagraph -Document $doc -Text '이상 탐지 모델 비교 결과' -Size 17 -Bold $true -Alignment 1 -After 5 -KeepWithNext $true
        $title.Style = $doc.Styles.Item(-63)
        $title.Range.Font.Name = 'Malgun Gothic'
        $title.Range.Font.NameFarEast = 'Malgun Gothic'
        $title.Range.Font.Size = 17
        $title.Range.Font.Color = 0
        Write-Output 'stage=title'

        Add-ReportParagraph -Document $doc -Text 'Isolation Forest는 경고 신뢰도가 가장 높고 3-Sigma는 탐지율과 경고 부담의 균형이 좋다. IQR은 고장 누락이 가장 적지만 오경보가 가장 많다.' -Size 9.5 -After 3 | Out-Null
        Write-Output 'stage=intro'
        $meta = Add-ReportParagraph -Document $doc -Text '대상  테스트 173,800건  실제 고장 140건  평가 구간  고장 전 24시간 48시간 72시간' -Size 8.5 -After 5
        $meta.Range.Font.Color = 5592405
        Write-Output 'stage=opening'

        Add-ReportParagraph -Document $doc -Text '핵심 결과' -Size 11.5 -Bold $true -Before 1 -After 3 -KeepWithNext $true | Out-Null

        $tableRange = $doc.Range($doc.Content.End - 1, $doc.Content.End - 1)
        $table = $doc.Tables.Add($tableRange, 10, 7)
        $table.AllowAutoFit = $false
        $table.Alignment = 1
        $table.Borders.Enable = 1
        $table.Rows.AllowBreakAcrossPages = 0
        $headers = @('모델', '구간', '탐지율', '적중률', '오경보율', '선행시간', 'Lift')
        $widths = @(110, 43, 57, 57, 63, 67, 48)
        for ($column = 1; $column -le 7; $column++) {
            $table.Columns.Item($column).Width = $widths[$column - 1]
            $cell = $table.Cell(1, $column)
            $cell.Range.Text = $headers[$column - 1]
            $cell.Shading.BackgroundPatternColor = 7888927
            $cell.Range.Font.Color = 16777215
            $cell.Range.Font.Bold = 1
        }

        for ($index = 0; $index -lt $rows.Count; $index++) {
            $row = $rows[$index]
            $values = @(
                $row.model,
                ('{0}h' -f [int]$row.horizon_hours),
                ('{0:P1}' -f [double]$row.failure_detection_rate),
                ('{0:P1}' -f [double]$row.alert_precision),
                ('{0:P1}' -f [double]$row.false_alert_rate),
                ('{0:N1}h' -f [double]$row.mean_lead_time_hours),
                ('{0:N2}' -f [double]$row.lift)
            )
            for ($column = 1; $column -le 7; $column++) {
                $cell = $table.Cell($index + 2, $column)
                $cell.Range.Text = $values[$column - 1]
                if ($index % 2 -eq 1) {
                    $cell.Shading.BackgroundPatternColor = 16316664
                }
            }
        }
        foreach ($cell in $table.Range.Cells) {
            $cell.VerticalAlignment = 1
            $cell.Range.ParagraphFormat.Alignment = 1
            $cell.Range.ParagraphFormat.SpaceAfter = 0
            $cell.Range.ParagraphFormat.SpaceBefore = 0
            $cell.Range.Font.Name = 'Malgun Gothic'
            $cell.Range.Font.NameFarEast = 'Malgun Gothic'
            $cell.Range.Font.Size = 8
            $cell.TopPadding = 2
            $cell.BottomPadding = 2
            $cell.LeftPadding = 2
            $cell.RightPadding = 2
        }
        $table.Rows.Item(1).HeadingFormat = -1
        $afterTable = $doc.Range($table.Range.End, $table.Range.End)
        $afterTable.InsertParagraphAfter()
        Write-Output 'stage=table'

        Add-ReportParagraph -Document $doc -Text '비교 시각화' -Size 11.5 -Bold $true -Before 3 -After 1 -KeepWithNext $true | Out-Null
        $imageRange = $doc.Range($doc.Content.End - 1, $doc.Content.End - 1)
        $imageRange.ParagraphFormat.Alignment = 1
        $shape = $doc.InlineShapes.AddPicture($imagePath, $false, $true, $imageRange)
        $shape.LockAspectRatio = -1
        $shape.Width = 430
        $shape.Range.ParagraphFormat.SpaceAfter = 2
        $shape.Range.InsertParagraphAfter()
        Write-Output 'stage=image'

        Add-ReportParagraph -Document $doc -Text '운영 판단' -Size 11.5 -Bold $true -Before 1 -After 2 -KeepWithNext $true | Out-Null
        Add-ReportParagraph -Document $doc -Text '• 경고 신뢰도와 적은 이벤트 수가 중요하면 Isolation Forest가 적합하다.' -Size 8.8 -After 1 | Out-Null
        Add-ReportParagraph -Document $doc -Text '• 탐지율과 경고 부담의 균형이 필요하면 3-Sigma가 적합하다.' -Size 8.8 -After 1 | Out-Null
        Add-ReportParagraph -Document $doc -Text '• 고장 누락 최소화가 최우선이면 IQR이 적합하다.' -Size 8.8 -After 2 | Out-Null
        $note = Add-ReportParagraph -Document $doc -Text '오경보율이 모든 방식에서 80% 이상이므로 실제 적용 전 경고 병합 간격과 임계값 조정이 필요하다. 고장 기록은 센서 이상 정답이 아니라 이후 운영 결과이므로 본 결과는 고장 사전 경고의 유용성을 평가한다.' -Size 8 -After 0
        $note.Range.Font.Color = 5592405
        Write-Output 'stage=conclusion'

        $doc.BuiltInDocumentProperties.Item('Title').Value = '이상 탐지 모델 비교 결과'
        $doc.BuiltInDocumentProperties.Item('Author').Value = 'Codex'
        $doc.SaveAs2($docxPath, 16)
        Write-Output 'stage=saved'

        $pdfPath = Join-Path $renderDir 'REPORT.pdf'
        $doc.ExportAsFixedFormat($pdfPath, 17)
        $pageCount = $doc.ComputeStatistics(2)
        Write-Output "pages=$pageCount"

        for ($page = 1; $page -le $pageCount; $page++) {
            $start = $doc.GoTo(1, 1, $page).Start
            if ($page -lt $pageCount) {
                $end = $doc.GoTo(1, 1, $page + 1).Start - 1
            } else {
                $end = $doc.Content.End - 1
            }
            $range = $doc.Range($start, $end)
            $range.CopyAsPicture()
            Start-Sleep -Milliseconds 400
            $bitmap = [System.Windows.Forms.Clipboard]::GetImage()
            if ($null -eq $bitmap) {
                throw "Word did not render page $page to the clipboard."
            }
            try {
                $pngPath = Join-Path $renderDir ("page-{0}.png" -f $page)
                $bitmap.Save($pngPath, [System.Drawing.Imaging.ImageFormat]::Png)
            } finally {
                $bitmap.Dispose()
            }
        }
        Write-Output $docxPath
    } finally {
        $doc.Close($false)
    }
} finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}

