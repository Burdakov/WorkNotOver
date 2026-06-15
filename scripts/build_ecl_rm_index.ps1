param(
    [Parameter(Mandatory = $true)]
    [string]$Source,

    [Parameter(Mandatory = $true)]
    [string]$Output,

    [string[]]$Keywords = @(
        'RUNSPEC', 'DIMENS', 'TABDIMS', 'WELLDIMS', 'OIL', 'WATER', 'GAS', 'METRIC', 'START',
        'GRID', 'DX', 'DY', 'DZ', 'TOPS', 'PORO', 'PERMX', 'PERMY', 'PERMZ', 'MULTPV', 'ACTNUM',
        'PROPS', 'DENSITY', 'PVTW', 'PVTO', 'PVDO', 'PVDG', 'PVTG', 'ROCK', 'SWOF', 'SGOF',
        'REGIONS', 'PVTNUM', 'SATNUM', 'ROCKNUM', 'FIPNUM',
        'SOLUTION', 'PRESSURE', 'SWAT', 'SGAS',
        'SCHEDULE', 'RPTRST', 'RPTSCHED', 'WELSPECS', 'COMPDAT', 'WCONPROD', 'WCONINJE', 'DATES',
        'SUMMARY', 'FOPR', 'FWPR', 'FWIR', 'WOPR', 'WWPR', 'WBHP', 'WWCT'
    )
)

$ErrorActionPreference = 'Stop'

$sourcePath = (Resolve-Path -LiteralPath $Source).Path
$outputPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Output)
$textPath = Join-Path $outputPath 'text'
New-Item -ItemType Directory -Force -Path $textPath | Out-Null

$sectionNames = @('RUNSPEC', 'GRID', 'EDIT', 'PROPS', 'REGIONS', 'SOLUTION', 'SUMMARY', 'SCHEDULE')
$entries = @{}
$htmlFiles = Get-ChildItem -LiteralPath $sourcePath -File -Filter '*.html' | Sort-Object Name

function Strip-Html {
    param([string]$Raw)
    $value = [regex]::Replace($Raw, '(?is)<script.*?</script>', ' ')
    $value = [regex]::Replace($value, '(?is)<style.*?</style>', ' ')
    $value = [regex]::Replace($value, '(?i)<br\s*/?>', "`n")
    $value = [regex]::Replace($value, '(?i)</(p|h1|h2|h3|h4|tr|td|th|li|table|div|blockquote)>', "`n")
    $value = [regex]::Replace($value, '(?s)<[^>]+>', ' ')
    $value = [System.Net.WebUtility]::HtmlDecode($value)
    $lines = @()
    foreach ($line in ($value -split "`r?`n")) {
        $clean = [regex]::Replace($line, '[ \t]+', ' ').Trim()
        if ($clean) {
            $lines += $clean
        }
    }
    return (($lines -join "`n") + "`n")
}

function Extract-Title {
    param([string]$Raw, [string]$Fallback)
    $match = [regex]::Match($Raw, '<title>(.*?)</title>', 'IgnoreCase, Singleline')
    if ($match.Success) {
        return ([System.Net.WebUtility]::HtmlDecode(([regex]::Replace($match.Groups[1].Value, '(?s)<[^>]+>', ' ')))).Trim()
    }
    return $Fallback.ToUpperInvariant()
}

function Keyword-From-Title {
    param([string]$Title, [string]$Fallback)
    $clean = [regex]::Replace($Title, '[^A-Za-z0-9_]+', ' ').Trim()
    if ($clean) {
        return ($clean -split ' ')[0].ToUpperInvariant()
    }
    return $Fallback.ToUpperInvariant()
}

function Extract-Description {
    param([string]$Text, [string]$Keyword)
    $lines = @($Text -split "`r?`n" | Where-Object { $_.Trim() })
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i].Trim().ToUpperInvariant() -eq $Keyword) {
            for ($j = $i + 1; $j -lt $lines.Count; $j++) {
                $desc = $lines[$j].Trim()
                if ($desc.ToUpperInvariant() -ne $Keyword) {
                    if ($desc.Length -gt 500) { return $desc.Substring(0, 500) }
                    return $desc
                }
            }
        }
    }
    if ($lines.Count -gt 0) {
        $desc = $lines[0].Trim()
        if ($desc.Length -gt 500) { return $desc.Substring(0, 500) }
        return $desc
    }
    return ''
}

function Extract-Sections {
    param([string]$Text)
    $lines = @($Text -split "`r?`n" | ForEach-Object { $_.Trim().ToUpperInvariant() } | Where-Object { $_ })
    $result = New-Object System.Collections.Generic.List[string]
    for ($i = 0; $i -lt ($lines.Count - 1); $i++) {
        if ($lines[$i] -eq 'X' -and $sectionNames -contains $lines[$i + 1]) {
            $result.Add($lines[$i + 1])
        }
    }
    return @($result | Select-Object -Unique | Sort-Object { $sectionNames.IndexOf($_) })
}

foreach ($file in $htmlFiles) {
    $raw = [System.IO.File]::ReadAllText($file.FullName, [System.Text.Encoding]::GetEncoding('iso-8859-1'))
    $title = Extract-Title -Raw $raw -Fallback $file.BaseName
    $keyword = Keyword-From-Title -Title $title -Fallback $file.BaseName
    $text = Strip-Html -Raw $raw
    $localText = Join-Path $textPath "$keyword.txt"
    [System.IO.File]::WriteAllText($localText, $text, [System.Text.Encoding]::UTF8)
    $entries[$keyword] = [ordered]@{
        keyword = $keyword
        title = $title
        description = Extract-Description -Text $text -Keyword $keyword
        sections = @(Extract-Sections -Text $text)
        source_html = $file.FullName
        local_text = $localText
        size_bytes = $file.Length
    }
}

$quickReference = [ordered]@{}
$missingQuickKeywords = @()
foreach ($keyword in ($Keywords | ForEach-Object { $_.ToUpperInvariant() })) {
    if ($entries.ContainsKey($keyword)) {
        $quickReference[$keyword] = $entries[$keyword]
    } else {
        $missingQuickKeywords += $keyword
    }
}

$manifest = [ordered]@{
    source = $sourcePath
    generated_at = (Get-Date).ToUniversalTime().ToString('o')
    html_file_count = $htmlFiles.Count
    keyword_count = $entries.Count
    quick_keyword_count = $quickReference.Count
    missing_quick_keywords = $missingQuickKeywords
    encoding = 'source iso-8859-1, generated utf-8'
    note = 'Generated local cache for WorkNotOver deck debugging. Do not commit generated manual text.'
}

$sortedEntries = [ordered]@{}
foreach ($key in ($entries.Keys | Sort-Object)) {
    $sortedEntries[$key] = $entries[$key]
}

New-Item -ItemType Directory -Force -Path $outputPath | Out-Null
($manifest | ConvertTo-Json -Depth 6) | Set-Content -Path (Join-Path $outputPath 'manifest.json') -Encoding UTF8
($sortedEntries | ConvertTo-Json -Depth 6) | Set-Content -Path (Join-Path $outputPath 'keywords_index.json') -Encoding UTF8
($quickReference | ConvertTo-Json -Depth 6) | Set-Content -Path (Join-Path $outputPath 'quick_reference.json') -Encoding UTF8

$manifest | ConvertTo-Json -Depth 6
