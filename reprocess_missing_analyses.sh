#!/bin/bash
# reprocess_missing_analyses.sh
# Reprocess filings that currently have no analysis

echo "🔄 Starting reprocessing of filings without analysis..."

# Get list of filings without analysis
docker compose -f ops/compose/docker-compose.yml exec postgres psql -U filings -d filings -c "
SELECT f.accession_number 
FROM filings f
LEFT JOIN filing_analyses fa ON f.id = fa.filing_id
WHERE fa.id IS NULL
ORDER BY f.filed_at DESC
LIMIT 50;" > missing_filings.txt

echo "📋 Found filings without analysis. Processing first 50..."

# Process each filing (this would need to be implemented)
echo "⚠️  Note: This requires implementing a reprocessing script that:"
echo "   1. Reads the missing filings list"
echo "2. Triggers the enhanced analysis pipeline"
echo "3. Uses the new rule-based analysis for low-priority filings"
echo "4. Skips Groq for boilerplate filings"

echo "✅ Script framework ready - implementation needed"
