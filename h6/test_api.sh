#!/bin/bash

echo "=== Testing RNA Secondary Structure Prediction API ==="
echo ""

echo "1. Health Check:"
curl -s http://localhost:8080/health | python3 -m json.tool
echo ""

echo "2. Predict RNA Structure (AUGCAUCGUAUGCAUCG):"
curl -s -X POST http://localhost:8080/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{"sequence": "AUGCAUCGUAUGCAUCG"}' | python3 -m json.tool
echo ""

echo "3. Get RNA Families:"
curl -s http://localhost:8080/api/v1/families | python3 -m json.tool
echo ""

echo "4. Test miRNA sequence (22 nucleotides):"
curl -s -X POST http://localhost:8080/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{"sequence": "UAGCUUAGCUUAGCUUAGCUUA"}' | python3 -m json.tool
echo ""

echo "5. Test invalid sequence:"
curl -s -X POST http://localhost:8080/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{"sequence": "AUGCTXYZ"}' | python3 -m json.tool
echo ""

echo "6. Test short sequence:"
curl -s -X POST http://localhost:8080/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{"sequence": "AUG"}' | python3 -m json.tool
echo ""

echo "7. Clear Cache:"
curl -s -X DELETE http://localhost:8080/api/v1/cache | python3 -m json.tool
echo ""

echo "8. Get Cache Stats:"
curl -s http://localhost:8080/api/v1/cache/stats | python3 -m json.tool
echo ""

echo "9. Predict RNA Structure with SHAPE data:"
curl -s -X POST http://localhost:8080/api/v1/predict/shape \
  -H "Content-Type: application/json" \
  -d '{
    "sequence": "AUGCAUCGUAUGCAUCG",
    "shape_data": [
        {"position": 0, "reactivity": 0.1},
        {"position": 1, "reactivity": 0.3},
        {"position": 2, "reactivity": 0.8},
        {"position": 3, "reactivity": 0.2},
        {"position": 4, "reactivity": 0.5},
        {"position": 10, "reactivity": 0.9},
        {"position": 15, "reactivity": 0.4}
    ],
    "shape_slope": 2.6,
    "shape_intercept": -0.8
}' | python3 -m json.tool
echo ""

echo "10. Sample Suboptimal (Metastable) Structures:"
RESPONSE=$(curl -s -X POST http://localhost:8080/api/v1/sample \
  -H "Content-Type: application/json" \
  -d '{"sequence": "AUGCAUCGUAUGCAUCG", "num_samples": 500, "temperature": 37.0, "max_energy_diff": 5.0}')
echo "$RESPONSE" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f'Sequence: {data[\"sequence\"]}')
print(f'MFE Structure: {data[\"mfe_structure\"]}')
print(f'MFE Energy: {data[\"mfe_energy\"]} kcal/mol')
print(f'Total Samples: {data[\"num_samples\"]}')
print(f'Unique Structures: {data[\"unique_structures\"]}')
print(f'Ensemble Defect: {data[\"ensemble_defect\"]}')
print()
print('Top 5 Structures:')
for i, s in enumerate(data['structures'][:5]):
    print(f'  [{i+1}] {s[\"structure\"]} (E={s[\"energy\"]} kcal/mol, freq={s[\"frequency\"]})')
"
echo ""

echo "11. Predict Common Structure from MSA:"
curl -s -X POST http://localhost:8080/api/v1/msa/common \
  -H "Content-Type: application/json" \
  -d '{
    "sequences": [
        "AUGCAUCGUAUGCAUCG",
        "AUGCAUCGUAUGCGUCG",
        "AUGCAACGUAUGCAUCG",
        "AUGCAUCGUACGCAUCG",
        "AUGCAUCGUAUGCAUCG"
    ],
    "consensus_cutoff": 0.6,
    "use_covariation": true
}' | python3 -m json.tool
echo ""

echo "=== Tests Complete ==="
