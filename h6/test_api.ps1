Write-Host "=== Testing RNA Secondary Structure Prediction API ==="
Write-Host ""

Write-Host "1. Health Check:"
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8080/health" -Method Get
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Error: $_"
}
Write-Host ""

Write-Host "2. Predict RNA Structure (AUGCAUCGUAUGCAUCG):"
try {
    $body = @{ sequence = "AUGCAUCGUAUGCAUCG" } | ConvertTo-Json
    $response = Invoke-RestMethod -Uri "http://localhost:8080/api/v1/predict" -Method Post -Body $body -ContentType "application/json"
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Error: $_"
}
Write-Host ""

Write-Host "3. Get RNA Families:"
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8080/api/v1/families" -Method Get
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Error: $_"
}
Write-Host ""

Write-Host "4. Test miRNA sequence (22 nucleotides):"
try {
    $body = @{ sequence = "UAGCUUAGCUUAGCUUAGCUUA" } | ConvertTo-Json
    $response = Invoke-RestMethod -Uri "http://localhost:8080/api/v1/predict" -Method Post -Body $body -ContentType "application/json"
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Error: $_"
}
Write-Host ""

Write-Host "5. Test invalid sequence:"
try {
    $body = @{ sequence = "AUGCTXYZ" } | ConvertTo-Json
    $response = Invoke-RestMethod -Uri "http://localhost:8080/api/v1/predict" -Method Post -Body $body -ContentType "application/json"
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Error: $($_.Exception.Message)"
}
Write-Host ""

Write-Host "6. Test short sequence:"
try {
    $body = @{ sequence = "AUG" } | ConvertTo-Json
    $response = Invoke-RestMethod -Uri "http://localhost:8080/api/v1/predict" -Method Post -Body $body -ContentType "application/json"
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Error: $($_.Exception.Message)"
}
Write-Host ""

Write-Host "7. Clear Cache:"
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8080/api/v1/cache" -Method Delete
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Error: $_"
}
Write-Host ""

Write-Host "8. Get Cache Stats:"
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8080/api/v1/cache/stats" -Method Get
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Error: $_"
}
Write-Host ""

Write-Host "9. Predict RNA Structure with SHAPE data:"
try {
    $body = @{
        sequence = "AUGCAUCGUAUGCAUCG"
        shape_data = @(
            @{ position = 0; reactivity = 0.1 },
            @{ position = 1; reactivity = 0.3 },
            @{ position = 2; reactivity = 0.8 },
            @{ position = 3; reactivity = 0.2 },
            @{ position = 4; reactivity = 0.5 },
            @{ position = 10; reactivity = 0.9 },
            @{ position = 15; reactivity = 0.4 }
        )
        shape_slope = 2.6
        shape_intercept = -0.8
    } | ConvertTo-Json -Depth 10
    $response = Invoke-RestMethod -Uri "http://localhost:8080/api/v1/predict/shape" -Method Post -Body $body -ContentType "application/json"
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Error: $_"
}
Write-Host ""

Write-Host "10. Sample Suboptimal (Metastable) Structures:"
try {
    $body = @{
        sequence = "AUGCAUCGUAUGCAUCG"
        num_samples = 500
        temperature = 37.0
        max_energy_diff = 5.0
    } | ConvertTo-Json
    $response = Invoke-RestMethod -Uri "http://localhost:8080/api/v1/sample" -Method Post -Body $body -ContentType "application/json"
    Write-Host "Sequence: $($response.sequence)"
    Write-Host "MFE Structure: $($response.mfe_structure)"
    Write-Host "MFE Energy: $($response.mfe_energy) kcal/mol"
    Write-Host "Total Samples: $($response.num_samples)"
    Write-Host "Unique Structures: $($response.unique_structures)"
    Write-Host "Ensemble Defect: $($response.ensemble_defect)"
    Write-Host ""
    Write-Host "Top 5 Structures:"
    for ($i = 0; $i -lt [Math]::Min(5, $response.structures.Count); $i++) {
        $s = $response.structures[$i]
        Write-Host "  [$($i+1)] $($s.structure) (E=$($s.energy) kcal/mol, freq=$($s.frequency))"
    }
} catch {
    Write-Host "Error: $_"
}
Write-Host ""

Write-Host "11. Predict Common Structure from MSA:"
try {
    $body = @{
        sequences = @(
            "AUGCAUCGUAUGCAUCG",
            "AUGCAUCGUAUGCGUCG",
            "AUGCAACGUAUGCAUCG",
            "AUGCAUCGUACGCAUCG",
            "AUGCAUCGUAUGCAUCG"
        )
        consensus_cutoff = 0.6
        use_covariation = $true
    } | ConvertTo-Json
    $response = Invoke-RestMethod -Uri "http://localhost:8080/api/v1/msa/common" -Method Post -Body $body -ContentType "application/json"
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Error: $_"
}
Write-Host ""

Write-Host "=== Tests Complete ==="
