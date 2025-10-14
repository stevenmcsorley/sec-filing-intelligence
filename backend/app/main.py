import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, cast, Annotated

from fastapi import FastAPI, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from .auth.router import router as auth_router
from .config import get_settings
from .db import init_db
from .diff import DiffService
from .downloader import DownloadService
from .entities import EntityExtractionService
from .filings import router as filings_router
from .db import get_db_session
from .repositories import FilingRepository
from .ingestion import IngestionService
from .parsing import ParserService
from .summarization import SectionSummaryService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle: startup and shutdown events."""
    # Startup
    settings = get_settings()
    init_db(settings)
    ingestion_service = IngestionService(settings)
    await ingestion_service.start()
    download_service = DownloadService(settings)
    await download_service.start()
    parser_service = ParserService(settings)
    await parser_service.start()
    summary_service = SectionSummaryService(settings)
    await summary_service.start()
    entity_service = EntityExtractionService(settings)
    await entity_service.start()
    diff_service = DiffService(settings)
    await diff_service.start()
    state = cast(Any, app.state)
    state.ingestion_service = ingestion_service
    state.download_service = download_service
    state.parser_service = parser_service
    state.entity_service = entity_service
    state.summary_service = summary_service
    state.diff_service = diff_service
    yield
    # Shutdown


app = FastAPI(
    title="SEC Filing Intelligence API",
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for debugging
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(filings_router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Basic readiness probe used by compose, k8s, and CI smoke tests."""
    return {"status": "ok", "test": "this works"}

# Public endpoints (trying after router includes)
@app.get("/test-public")
def test_public() -> dict[str, str]:
    """Test public endpoint."""
    return {"message": "Public endpoint works!"}

@app.get("/public/filings/recent")
async def get_public_recent_filings(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=10)] = 3,
) -> dict[str, Any]:
    """Get recent filings for public homepage display (no auth required)."""
    repo = FilingRepository(db)
    
    # Get more filings to ensure we have filings from different companies
    filings = await repo.list_filings(
        limit=50,  # Get more filings to find distinct companies
        offset=0,
        # status="completed",  # Show recent filings regardless of status for homepage demo
    )

    # Group filings by company and get the most recent filing for each company
    company_filings = {}
    for filing in filings:
        company_key = filing.company_id if filing.company else filing.cik
        if (company_key not in company_filings or 
            filing.filed_at > company_filings[company_key].filed_at):
            company_filings[company_key] = filing
    
    # Take the most recent filings from different companies
    recent_company_filings = sorted(
        company_filings.values(),
        key=lambda f: f.filed_at,
        reverse=True
    )
    
    # Filter out placeholder companies
    filtered_filings = [
        f for f in recent_company_filings 
        if not (f.company and f.company.name in 
                ["Technology Company Inc.", "Investment Holdings LLC"])
    ][:limit]

    # Convert to API format that matches the authenticated filings API
    filing_list = []
    for filing in filtered_filings:
        # For Form 4, 144, and Schedule 13D/A filings, try to extract
        # issuer company information from analysis
        company_name = filing.company.name if filing.company else None
        extracted_ticker = filing.company.ticker if filing.company else filing.ticker
        
        # Create a simple analysis brief based on form type
        brief = ""
        if filing.form_type == "4":
            brief = "Insider trading disclosure filing"
        elif filing.form_type == "8-K":
            brief = "Current report of material events"
        elif filing.form_type == "10-K":
            brief = "Annual report with comprehensive financial information"
        elif filing.form_type == "10-Q":
            brief = "Quarterly report with financial results"
        filing_list.append({
            "id": filing.id,
            "cik": filing.cik,
            "ticker": extracted_ticker,
            "company_name": company_name,
            "form_type": filing.form_type,
            "filed_at": filing.filed_at,
            "accession_number": filing.accession_number,
            "status": filing.status,
            "downloaded_at": filing.downloaded_at,
            "section_count": len(filing.sections) if filing.sections else 0,
            "blob_count": len(filing.blobs) if filing.blobs else 0,
            "analysis": None,  # Skip analysis for list view to improve performance
        })

    return {
        "filings": filing_list,
        "total_count": len(filing_list),
        "limit": limit,
        "offset": 0,
        "debug": {
            "total_filings_retrieved": len(filings),
            "companies_grouped": len(company_filings),
            "filtered_count": len(filtered_filings)
        }
    }
