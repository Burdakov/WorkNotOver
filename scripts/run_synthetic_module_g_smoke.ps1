param(
  [string]$BaseUrl = 'http://localhost:8010/api',
  [string]$OutputRelativePath = 'backend\storage\mock\module_g_synthetic_smoke.xlsx'
)

$ErrorActionPreference = 'Stop'

function Invoke-ApiJson {
  param(
    [Parameter(Mandatory = $true)][string]$Method,
    [Parameter(Mandatory = $true)][string]$Uri,
    [object]$Body = $null
  )

  if ($null -ne $Body) {
    $json = $Body | ConvertTo-Json -Depth 20
    return Invoke-RestMethod -Method $Method -Uri $Uri -ContentType 'application/json; charset=utf-8' -Body $json
  }

  return Invoke-RestMethod -Method $Method -Uri $Uri
}

function Upload-ExcelFile {
  param(
    [Parameter(Mandatory = $true)][string]$Uri,
    [Parameter(Mandatory = $true)][string]$FilePath
  )

  Add-Type -AssemblyName System.Net.Http
  $handler = [System.Net.Http.HttpClientHandler]::new()
  $client = [System.Net.Http.HttpClient]::new($handler)
  $form = [System.Net.Http.MultipartFormDataContent]::new()
  $stream = [System.IO.File]::OpenRead($FilePath)
  $fileContent = [System.Net.Http.StreamContent]::new($stream)
  $fileContent.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
  $form.Add($fileContent, 'file', [System.IO.Path]::GetFileName($FilePath))

  try {
    $response = $client.PostAsync($Uri, $form).Result
    $body = $response.Content.ReadAsStringAsync().Result
    if (-not $response.IsSuccessStatusCode) {
      throw "Upload failed: $($response.StatusCode) $body"
    }
    return $body | ConvertFrom-Json
  }
  finally {
    $stream.Dispose()
    $form.Dispose()
    $client.Dispose()
    $handler.Dispose()
  }
}

function New-Row {
  param([hashtable]$Values)
  return [pscustomobject]$Values
}

function Get-NumberOrDefault {
  param(
    [object]$Value,
    [double]$Default = 0.0
  )

  if ($null -eq $Value -or $Value -eq '') {
    return $Default
  }

  return [double]$Value
}

function Write-SheetRows {
  param(
    [Parameter(Mandatory = $true)]$Worksheet,
    [Parameter(Mandatory = $true)][string[]]$Headers,
    [Parameter(Mandatory = $true)][object[]]$Rows
  )

  for ($col = 0; $col -lt $Headers.Count; $col += 1) {
    $Worksheet.Cells.Item(1, $col + 1) = $Headers[$col]
  }

  for ($rowIndex = 0; $rowIndex -lt $Rows.Count; $rowIndex += 1) {
    $row = $Rows[$rowIndex]
    for ($col = 0; $col -lt $Headers.Count; $col += 1) {
      $header = $Headers[$col]
      $Worksheet.Cells.Item($rowIndex + 2, $col + 1) = $row.$header
    }
  }

  $Worksheet.UsedRange.Columns.AutoFit() | Out-Null
}

function Build-Workbook {
  param([Parameter(Mandatory = $true)][string]$OutputPath)

  $wellsHeaders = @('well', 'area', 'lu', 'sloy', 'well_pad', 'brigade', 'fund_type', 'oil_rate', 'gas_rate', 'liquid_rate', 'watercut', 'gor', 'cumulative_oil', 'cumulative_gas', 'niz')
  $wellsRows = @(
    (New-Row @{ well = 'WA_101'; area = 'Area East'; lu = 'LU_A'; sloy = 'SLOY_A1'; well_pad = 'PAD_A01'; brigade = ''; fund_type = 'Base'; oil_rate = 42; gas_rate = 4200; liquid_rate = 105; watercut = 60; gor = 100; cumulative_oil = 32000; cumulative_gas = 3200000; niz = 90000 }),
    (New-Row @{ well = 'WA_201'; area = 'Area East'; lu = 'LU_A'; sloy = 'SLOY_A2'; well_pad = 'PAD_A02'; brigade = ''; fund_type = 'Base'; oil_rate = 35; gas_rate = 3150; liquid_rate = 70; watercut = 50; gor = 90; cumulative_oil = 18000; cumulative_gas = 1620000; niz = 85000 }),
    (New-Row @{ well = 'WB_301'; area = 'Area West'; lu = 'LU_B'; sloy = 'SLOY_B1'; well_pad = 'PAD_B01'; brigade = ''; fund_type = 'Base'; oil_rate = 58; gas_rate = 6960; liquid_rate = 145; watercut = 60; gor = 120; cumulative_oil = 40000; cumulative_gas = 4800000; niz = 120000 }),
    (New-Row @{ well = 'WA_401'; area = 'Area East'; lu = 'LU_A'; sloy = 'SLOY_A1'; well_pad = 'PAD_A03'; brigade = ''; fund_type = 'New wells'; oil_rate = 0; gas_rate = 0; liquid_rate = 0; watercut = 20; gor = 85; cumulative_oil = 0; cumulative_gas = 0; niz = 100000 }),
    (New-Row @{ well = 'WB_402'; area = 'Area West'; lu = 'LU_B'; sloy = 'SLOY_B1'; well_pad = 'PAD_B02'; brigade = ''; fund_type = 'New wells'; oil_rate = 0; gas_rate = 0; liquid_rate = 0; watercut = 15; gor = 95; cumulative_oil = 0; cumulative_gas = 0; niz = 110000 })
  )

  $gtmHeaders = @('well', 'area', 'lu', 'sloy', 'well_pad', 'brigade', 'gtm_type', 'planned_work', 'start_date', 'end_date', 'duration_days', 'increment', 'liquid_increment', 'gas_increment', 'gor_change')
  $gtmRows = @(
    (New-Row @{ well = 'WA_101'; area = 'Area East'; lu = 'LU_A'; sloy = 'SLOY_A1'; well_pad = 'PAD_A01'; brigade = 'KRS-01'; gtm_type = 'well_service'; planned_work = 'OPZ'; start_date = '2026-06-15'; end_date = '2026-06-22'; duration_days = 8; increment = 14; liquid_increment = 24; gas_increment = 900; gor_change = 4 }),
    (New-Row @{ well = 'WA_201'; area = 'Area East'; lu = 'LU_A'; sloy = 'SLOY_A2'; well_pad = 'PAD_A02'; brigade = 'KRS-02'; gtm_type = 'fracturing'; planned_work = 'GRP'; start_date = '2026-07-10'; end_date = '2026-07-19'; duration_days = 10; increment = 18; liquid_increment = 30; gas_increment = 1200; gor_change = 6 }),
    (New-Row @{ well = 'WA_401'; area = 'Area East'; lu = 'LU_A'; sloy = 'SLOY_A1'; well_pad = 'PAD_A03'; brigade = 'KRS-03'; gtm_type = 'new_well'; planned_work = 'NEW_WELL_START'; start_date = '2026-08-01'; end_date = '2026-08-12'; duration_days = 12; increment = 70; liquid_increment = 120; gas_increment = 10800; gor_change = 90 }),
    (New-Row @{ well = 'WB_402'; area = 'Area West'; lu = 'LU_B'; sloy = 'SLOY_B1'; well_pad = 'PAD_B02'; brigade = 'KRS-04'; gtm_type = 'new_well'; planned_work = 'NEW_WELL_START'; start_date = '2026-09-10'; end_date = '2026-09-22'; duration_days = 13; increment = 78; liquid_increment = 135; gas_increment = 12825; gor_change = 95 }),
    (New-Row @{ well = 'WB_301'; area = 'Area West'; lu = 'LU_B'; sloy = 'SLOY_B1'; well_pad = 'PAD_B01'; brigade = 'KRS-05'; gtm_type = 'rir'; planned_work = 'RIR'; start_date = '2027-02-20'; end_date = '2027-03-03'; duration_days = 12; increment = 16; liquid_increment = 28; gas_increment = 1100; gor_change = 5 }),
    (New-Row @{ well = 'WA_101'; area = 'Area East'; lu = 'LU_A'; sloy = 'SLOY_A1'; well_pad = 'PAD_A01'; brigade = 'KRS-01'; gtm_type = 'well_service'; planned_work = 'OPZ_REPEAT'; start_date = '2027-05-05'; end_date = '2027-05-11'; duration_days = 7; increment = 10; liquid_increment = 18; gas_increment = 600; gor_change = 2 })
  )

  $infraHeaders = @('area', 'lu', 'sloy', 'well_pad', 'object_name', 'object_type', 'commissioning_date', 'capacity_oil', 'capacity_gas', 'capacity_liquid', 'capacity_water', 'connection_well', 'parent_object')
  $infraRows = @(
    (New-Row @{ area = 'Area East'; lu = 'LU_A'; sloy = ''; well_pad = ''; object_name = 'CPF_LU_A'; object_type = 'facility'; commissioning_date = '2026-01-01'; capacity_oil = 280; capacity_gas = 25000; capacity_liquid = 420; capacity_water = 250; connection_well = ''; parent_object = '' }),
    (New-Row @{ area = 'Area East'; lu = 'LU_A'; sloy = 'SLOY_A1'; well_pad = 'PAD_A01'; object_name = 'PIPE_A_101'; object_type = 'pipeline'; commissioning_date = '2026-01-01'; capacity_oil = 120; capacity_gas = 9000; capacity_liquid = 180; capacity_water = 120; connection_well = 'WA_101'; parent_object = 'CPF_LU_A' }),
    (New-Row @{ area = 'Area East'; lu = 'LU_A'; sloy = 'SLOY_A2'; well_pad = 'PAD_A02'; object_name = 'PIPE_A_201'; object_type = 'pipeline'; commissioning_date = '2026-01-01'; capacity_oil = 120; capacity_gas = 9000; capacity_liquid = 180; capacity_water = 120; connection_well = 'WA_201'; parent_object = 'CPF_LU_A' }),
    (New-Row @{ area = 'Area East'; lu = 'LU_A'; sloy = 'SLOY_A1'; well_pad = 'PAD_A03'; object_name = 'PIPE_A_401'; object_type = 'pipeline'; commissioning_date = '2026-07-20'; capacity_oil = 150; capacity_gas = 12000; capacity_liquid = 220; capacity_water = 150; connection_well = 'WA_401'; parent_object = 'CPF_LU_A' }),
    (New-Row @{ area = 'Area West'; lu = 'LU_B'; sloy = ''; well_pad = ''; object_name = 'CPF_LU_B'; object_type = 'facility'; commissioning_date = '2026-01-01'; capacity_oil = 320; capacity_gas = 30000; capacity_liquid = 500; capacity_water = 320; connection_well = ''; parent_object = '' }),
    (New-Row @{ area = 'Area West'; lu = 'LU_B'; sloy = 'SLOY_B1'; well_pad = 'PAD_B01'; object_name = 'PIPE_B_301'; object_type = 'pipeline'; commissioning_date = '2026-01-01'; capacity_oil = 160; capacity_gas = 15000; capacity_liquid = 240; capacity_water = 160; connection_well = 'WB_301'; parent_object = 'CPF_LU_B' }),
    (New-Row @{ area = 'Area West'; lu = 'LU_B'; sloy = 'SLOY_B1'; well_pad = 'PAD_B02'; object_name = 'PIPE_B_402'; object_type = 'pipeline'; commissioning_date = '2026-09-01'; capacity_oil = 170; capacity_gas = 16000; capacity_liquid = 260; capacity_water = 170; connection_well = 'WB_402'; parent_object = 'CPF_LU_B' })
  )

  $krsHeaders = @('brigade', 'area', 'lu', 'sloy', 'well_pad', 'well', 'start_date', 'end_date', 'planned_work', 'increment', 'liquid_increment', 'gas_increment', 'gor_change')
  $krsRows = @(
    (New-Row @{ brigade = 'KRS-01'; area = 'Area East'; lu = 'LU_A'; sloy = 'SLOY_A1'; well_pad = 'PAD_A01'; well = 'WA_101'; start_date = '2026-06-12'; end_date = '2026-06-20'; planned_work = 'OPZ'; increment = 14; liquid_increment = 24; gas_increment = 900; gor_change = 4 }),
    (New-Row @{ brigade = 'KRS-02'; area = 'Area East'; lu = 'LU_A'; sloy = 'SLOY_A2'; well_pad = 'PAD_A02'; well = 'WA_201'; start_date = '2026-07-06'; end_date = '2026-07-16'; planned_work = 'GRP'; increment = 18; liquid_increment = 30; gas_increment = 1200; gor_change = 6 }),
    (New-Row @{ brigade = 'KRS-03'; area = 'Area East'; lu = 'LU_A'; sloy = 'SLOY_A1'; well_pad = 'PAD_A03'; well = 'WA_401'; start_date = '2026-07-25'; end_date = '2026-08-06'; planned_work = 'NEW_WELL_START'; increment = 70; liquid_increment = 120; gas_increment = 10800; gor_change = 90 }),
    (New-Row @{ brigade = 'KRS-04'; area = 'Area West'; lu = 'LU_B'; sloy = 'SLOY_B1'; well_pad = 'PAD_B02'; well = 'WB_402'; start_date = '2026-08-28'; end_date = '2026-09-12'; planned_work = 'NEW_WELL_START'; increment = 78; liquid_increment = 135; gas_increment = 12825; gor_change = 95 }),
    (New-Row @{ brigade = 'KRS-05'; area = 'Area West'; lu = 'LU_B'; sloy = 'SLOY_B1'; well_pad = 'PAD_B01'; well = 'WB_301'; start_date = '2027-02-15'; end_date = '2027-02-27'; planned_work = 'RIR'; increment = 16; liquid_increment = 28; gas_increment = 1100; gor_change = 5 })
  )

  $excel = New-Object -ComObject Excel.Application
  $excel.Visible = $false
  $excel.DisplayAlerts = $false
  $workbook = $excel.Workbooks.Add()

  try {
    while ($workbook.Worksheets.Count -lt 4) {
      [void]$workbook.Worksheets.Add()
    }

    $sheetWells = $workbook.Worksheets.Item(1)
    $sheetWells.Name = 'Wells'
    Write-SheetRows -Worksheet $sheetWells -Headers $wellsHeaders -Rows $wellsRows

    $sheetGtm = $workbook.Worksheets.Item(2)
    $sheetGtm.Name = 'GTM'
    Write-SheetRows -Worksheet $sheetGtm -Headers $gtmHeaders -Rows $gtmRows

    $sheetInfra = $workbook.Worksheets.Item(3)
    $sheetInfra.Name = 'Infrastructure'
    Write-SheetRows -Worksheet $sheetInfra -Headers $infraHeaders -Rows $infraRows

    $sheetKrs = $workbook.Worksheets.Item(4)
    $sheetKrs.Name = 'KRS'
    Write-SheetRows -Worksheet $sheetKrs -Headers $krsHeaders -Rows $krsRows

    while ($workbook.Worksheets.Count -gt 4) {
      $workbook.Worksheets.Item($workbook.Worksheets.Count).Delete()
    }

    $directory = Split-Path -Parent $OutputPath
    if (-not (Test-Path $directory)) {
      New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }

    if (Test-Path $OutputPath) {
      Remove-Item $OutputPath -Force
    }

    $workbook.SaveAs($OutputPath, 51)
  }
  finally {
    $workbook.Close($false)
    $excel.Quit()
    [void][System.Runtime.Interopservices.Marshal]::ReleaseComObject($sheetWells)
    [void][System.Runtime.Interopservices.Marshal]::ReleaseComObject($sheetGtm)
    [void][System.Runtime.Interopservices.Marshal]::ReleaseComObject($sheetInfra)
    [void][System.Runtime.Interopservices.Marshal]::ReleaseComObject($sheetKrs)
    [void][System.Runtime.Interopservices.Marshal]::ReleaseComObject($workbook)
    [void][System.Runtime.Interopservices.Marshal]::ReleaseComObject($excel)
    [System.GC]::Collect()
    [System.GC]::WaitForPendingFinalizers()
  }
}

function New-DisplacementConfig {
  param(
    [string]$ConfigId,
    [string]$LuId,
    [string]$SloyId,
    [double[]]$Watercuts
  )

  $nizAxis = @(0.0, 0.25, 0.5, 0.75, 1.0)
  $curvePoints = @()
  for ($i = 0; $i -lt $nizAxis.Count; $i += 1) {
    $curvePoints += @{
      NIZ = $nizAxis[$i]
      watercut = $Watercuts[$i]
    }
  }

  return @{
    config_id = $ConfigId
    lu_id = $LuId
    sloy_id = $SloyId
    curve_points = $curvePoints
    watercut_unit = 'percent'
    notes = "Synthetic displacement for $LuId/$SloyId"
  }
}

function New-DeclineConfig {
  param(
    [string]$ConfigId,
    [string]$LuId,
    [string]$SloyId
  )

  $base = @()
  $newWells = @()
  for ($month = 1; $month -le 24; $month += 1) {
    $base += @{
      month_index = $month
      liquid_decline_factor = 5
    }
    $newWells += @{
      month_index = $month
      liquid_decline_factor = $(if ($month -le 12) { 50 } else { 5 })
    }
  }

  return @{
    config_id = $ConfigId
    lu_id = $LuId
    sloy_id = $SloyId
    base_monthly_decline_values = $base
    new_wells_monthly_decline_values = $newWells
    notes = "Synthetic decline for $LuId/$SloyId"
  }
}

function Get-ProductionBreakdown {
  param([object]$ScenarioDetail)

  $result = @{
    base = 0.0
    gtm = 0.0
    vns = 0.0
  }

  foreach ($well in @($ScenarioDetail.wells)) {
    $isNew = [string]$well.fund_type -eq 'New wells'
    foreach ($point in @($well.points)) {
      $oilRate = Get-NumberOrDefault $point.oil_rate
      $oilIncrement = Get-NumberOrDefault $point.oil_increment
      if ($isNew) {
        $result.vns += $oilRate
      }
      else {
        $result.gtm += $oilIncrement
        $result.base += [Math]::Max($oilRate - $oilIncrement, 0)
      }
    }
  }

  return @{
    base = [Math]::Round($result.base, 3)
    gtm = [Math]::Round($result.gtm, 3)
    vns = [Math]::Round($result.vns, 3)
  }
}

function Get-HierarchySummary {
  param([object]$ScenarioDetail)

  $summary = @()
  foreach ($luGroup in (@($ScenarioDetail.wells) | Group-Object lu_id | Sort-Object Name)) {
    $luName = if ($luGroup.Name) { $luGroup.Name } else { 'NO_LU' }
    $luOil = 0.0
    $luLiquid = 0.0
    $luGas = 0.0
    foreach ($well in @($luGroup.Group)) {
      $luOil += Get-NumberOrDefault $well.total_oil
      $luLiquid += Get-NumberOrDefault $well.total_liquid
      $luGas += Get-NumberOrDefault $well.total_gas
    }

    $sloyItems = @()
    foreach ($sloyGroup in ($luGroup.Group | Group-Object sloy_id | Sort-Object Name)) {
      $sloyName = if ($sloyGroup.Name) { $sloyGroup.Name } else { 'NO_SLOY' }
      $padItems = @()
      foreach ($padGroup in ($sloyGroup.Group | Group-Object well_pad_id | Sort-Object Name)) {
        $padName = if ($padGroup.Name) { $padGroup.Name } else { 'NO_PAD' }
        $padOil = 0.0
        $padLiquid = 0.0
        $padGas = 0.0
        foreach ($well in @($padGroup.Group)) {
          $padOil += Get-NumberOrDefault $well.total_oil
          $padLiquid += Get-NumberOrDefault $well.total_liquid
          $padGas += Get-NumberOrDefault $well.total_gas
        }
        $padItems += @{
          well_pad_id = $padName
          well_count = @($padGroup.Group).Count
          total_oil = [Math]::Round($padOil, 3)
          total_liquid = [Math]::Round($padLiquid, 3)
          total_gas = [Math]::Round($padGas, 3)
          wells = @($padGroup.Group | ForEach-Object {
            @{
              well_name = $_.well_name
              fund_type = $_.fund_type
              total_oil = [Math]::Round((Get-NumberOrDefault $_.total_oil), 3)
              total_liquid = [Math]::Round((Get-NumberOrDefault $_.total_liquid), 3)
              total_gas = [Math]::Round((Get-NumberOrDefault $_.total_gas), 3)
            }
          })
        }
      }

      $sloyOil = 0.0
      $sloyLiquid = 0.0
      $sloyGas = 0.0
      foreach ($padItem in $padItems) {
        $sloyOil += Get-NumberOrDefault $padItem.total_oil
        $sloyLiquid += Get-NumberOrDefault $padItem.total_liquid
        $sloyGas += Get-NumberOrDefault $padItem.total_gas
      }
      $sloyItems += @{
        sloy_id = $sloyName
        well_count = @($sloyGroup.Group).Count
        total_oil = [Math]::Round($sloyOil, 3)
        total_liquid = [Math]::Round($sloyLiquid, 3)
        total_gas = [Math]::Round($sloyGas, 3)
        pads = $padItems
      }
    }

    $summary += @{
      lu_id = $luName
      well_count = @($luGroup.Group).Count
      total_oil = [Math]::Round($luOil, 3)
      total_liquid = [Math]::Round($luLiquid, 3)
      total_gas = [Math]::Round($luGas, 3)
      sloys = $sloyItems
    }
  }

  return $summary
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$outputPath = Join-Path $repoRoot $OutputRelativePath

Build-Workbook -OutputPath $outputPath

$upload = Upload-ExcelFile -Uri "$BaseUrl/files/upload" -FilePath $outputPath

$sheetMappings = @{
  wells = @{
    sheet_name = 'Wells'
    dataset_name = 'Synthetic Wells smoke 2026-05-01'
    columns = @{
      well = 'well'
      area = 'area'
      lu = 'lu'
      sloy = 'sloy'
      well_pad = 'well_pad'
      brigade = 'brigade'
      fund_type = 'fund_type'
      oil_rate = 'oil_rate'
      gas_rate = 'gas_rate'
      liquid_rate = 'liquid_rate'
      watercut = 'watercut'
      gor = 'gor'
      cumulative_oil = 'cumulative_oil'
      cumulative_gas = 'cumulative_gas'
      niz = 'niz'
    }
  }
  gtm = @{
    sheet_name = 'GTM'
    dataset_name = 'Synthetic GTM smoke 2026-05-01'
    columns = @{
      well = 'well'
      area = 'area'
      lu = 'lu'
      sloy = 'sloy'
      well_pad = 'well_pad'
      brigade = 'brigade'
      gtm_type = 'gtm_type'
      planned_work = 'planned_work'
      start_date = 'start_date'
      end_date = 'end_date'
      duration_days = 'duration_days'
      increment = 'increment'
      liquid_increment = 'liquid_increment'
      gas_increment = 'gas_increment'
      gor_change = 'gor_change'
    }
  }
  infrastructure = @{
    sheet_name = 'Infrastructure'
    dataset_name = 'Synthetic Infrastructure smoke 2026-05-01'
    columns = @{
      area = 'area'
      lu = 'lu'
      sloy = 'sloy'
      well_pad = 'well_pad'
      object_name = 'object_name'
      object_type = 'object_type'
      commissioning_date = 'commissioning_date'
      capacity_oil = 'capacity_oil'
      capacity_gas = 'capacity_gas'
      capacity_liquid = 'capacity_liquid'
      capacity_water = 'capacity_water'
      connection_well = 'connection_well'
      parent_object = 'parent_object'
    }
  }
  external_krs_schedule = @{
    sheet_name = 'KRS'
    dataset_name = 'Synthetic imported KRS smoke 2026-05-01'
    columns = @{
      brigade = 'brigade'
      area = 'area'
      lu = 'lu'
      sloy = 'sloy'
      well_pad = 'well_pad'
      well = 'well'
      start_date = 'start_date'
      end_date = 'end_date'
      planned_work = 'planned_work'
      increment = 'increment'
      liquid_increment = 'liquid_increment'
      gas_increment = 'gas_increment'
      gor_change = 'gor_change'
    }
  }
}

$datasets = @{}
foreach ($sourceKind in @('wells', 'gtm', 'infrastructure', 'external_krs_schedule')) {
  $config = $sheetMappings[$sourceKind]
  $response = Invoke-ApiJson -Method Post -Uri "$BaseUrl/import/normalize" -Body @{
    file_id = $upload.file_id
    source_kind = $sourceKind
    sheet_name = $config.sheet_name
    dataset_name = $config.dataset_name
    columns = $config.columns
  }
  $datasets[$sourceKind] = $response
}

$manualInputs = Invoke-ApiJson -Method Post -Uri "$BaseUrl/manual-inputs/save" -Body @{
  name = 'Synthetic Module G ManualInputSet 2026-05-01'
  created_by = 'codex-smoke'
  payload = @{
    displacement_config = @(
      (New-DisplacementConfig -ConfigId 'disp-lu-a-a1' -LuId 'LU_A' -SloyId 'SLOY_A1' -Watercuts @(98, 90, 70, 40, 10)),
      (New-DisplacementConfig -ConfigId 'disp-lu-a-a2' -LuId 'LU_A' -SloyId 'SLOY_A2' -Watercuts @(99, 92, 72, 38, 8)),
      (New-DisplacementConfig -ConfigId 'disp-lu-b-b1' -LuId 'LU_B' -SloyId 'SLOY_B1' -Watercuts @(97, 88, 68, 35, 7))
    )
    decline_config = @(
      (New-DeclineConfig -ConfigId 'decl-lu-a-a1' -LuId 'LU_A' -SloyId 'SLOY_A1'),
      (New-DeclineConfig -ConfigId 'decl-lu-a-a2' -LuId 'LU_A' -SloyId 'SLOY_A2'),
      (New-DeclineConfig -ConfigId 'decl-lu-b-b1' -LuId 'LU_B' -SloyId 'SLOY_B1')
    )
    brigade_capacity_by_lu_config = @{
      items = @(
        @{ lu_id = 'LU_A'; month_date = '2026-05-01'; brigade_count = 2 },
        @{ lu_id = 'LU_A'; month_date = '2026-06-01'; brigade_count = 2 },
        @{ lu_id = 'LU_B'; month_date = '2026-05-01'; brigade_count = 2 },
        @{ lu_id = 'LU_B'; month_date = '2026-06-01'; brigade_count = 2 }
      )
      notes = 'Synthetic brigade capacity by LU'
    }
    failure_coefficient_config = @{
      items = @(
        @{ scope_type = 'LU'; lu_id = 'LU_A'; sloy_id = $null; coefficient = 0.08 },
        @{ scope_type = 'SLOY'; lu_id = 'LU_B'; sloy_id = 'SLOY_B1'; coefficient = 0.12 }
      )
      notes = 'Synthetic failure coefficients'
    }
    krs_resource_config = @{
      brigade_count = 4
      durations_by_gtm_type = @{
        well_service = 8
        fracturing = 10
        new_well = 12
        rir = 12
      }
      calendar_rules = @{
        work_mode = 'continuous'
      }
      notes = 'Synthetic KRS resource config'
    }
    economics_config = @{
      oil_price = 62
      gas_price = 18
      gas_handling_cost = 2
      discount_rate = 0.12
      netback_by_lu = @{
        LU_A = 48
        LU_B = 50
      }
      notes = 'Synthetic economics input'
    }
    optimizer_config = @{
      objective = 'oil_max'
      infra_policy = 'warn'
      heuristic_mode = 'balanced'
      notes = 'Synthetic optimizer config'
    }
    metadata = @{
      source = 'synthetic-smoke'
      created_for = 'module-g-manual-run'
    }
  }
}

$forecast = Invoke-ApiJson -Method Post -Uri "$BaseUrl/forecast/calculate" -Body @{
  name = 'Synthetic Module G Forecast Scenario 2026-05-01'
  wells = @{
    dataset_id = $datasets.wells.dataset_reference.dataset_id
    dataset_version_id = $datasets.wells.dataset_reference.dataset_version_id
  }
  gtm = @{
    dataset_id = $datasets.gtm.dataset_reference.dataset_id
    dataset_version_id = $datasets.gtm.dataset_reference.dataset_version_id
  }
  manual_input_set_id = $manualInputs.reference.manual_input_set_id
  forecast_start_date = '2026-05-01'
  source_type = 'uploaded_gtm'
  metadata = @{
    run_type = 'synthetic-smoke'
  }
}

$scenarioDetail = Invoke-ApiJson -Method Get -Uri "$BaseUrl/forecast/scenarios/$($forecast.scenario.scenario_id)"

$plannerOpen = Invoke-ApiJson -Method Post -Uri "$BaseUrl/schedule/open-imported" -Body @{
  dataset_id = $datasets.external_krs_schedule.dataset_reference.dataset_id
  dataset_version_id = $datasets.external_krs_schedule.dataset_reference.dataset_version_id
}

$summary = [ordered]@{
  workbook = @{
    path = $outputPath
    sheets = @($upload.sheets)
    file_id = $upload.file_id
  }
  datasets = [ordered]@{
    wells = @{
      reference = $datasets.wells.dataset_reference
      row_count = $datasets.wells.validation_report.row_count
    }
    gtm = @{
      reference = $datasets.gtm.dataset_reference
      row_count = $datasets.gtm.validation_report.row_count
    }
    infrastructure = @{
      reference = $datasets.infrastructure.dataset_reference
      row_count = $datasets.infrastructure.validation_report.row_count
      connection_count = @($datasets.infrastructure.normalized_payload.connections).Count
    }
    external_krs_schedule = @{
      reference = $datasets.external_krs_schedule.dataset_reference
      row_count = $datasets.external_krs_schedule.validation_report.row_count
      brigade_count = $datasets.external_krs_schedule.normalized_payload.schedule.brigade_count
    }
  }
  manual_input_set = @{
    reference = $manualInputs.reference
    displacement_count = @($manualInputs.payload.displacement_configs).Count
    decline_count = @($manualInputs.payload.decline_configs).Count
  }
  forecast = @{
    scenario = $forecast.scenario
    production_summary = $forecast.production_summary
    warning_count = @($forecast.warnings).Count
    chart_breakdown = Get-ProductionBreakdown -ScenarioDetail $scenarioDetail
    hierarchy = Get-HierarchySummary -ScenarioDetail $scenarioDetail
  }
  planner = @{
    dataset_reference = $plannerOpen.dataset_reference
    version_name = $plannerOpen.version_name
    item_count = @($plannerOpen.items).Count
    brigade_count = $plannerOpen.brigade_count
    min_date = $plannerOpen.min_date
    max_date = $plannerOpen.max_date
    first_items = @($plannerOpen.items | Select-Object -First 3)
  }
}

$summary | ConvertTo-Json -Depth 12
