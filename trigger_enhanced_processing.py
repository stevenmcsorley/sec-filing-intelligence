#!/usr/bin/env python3
"""
Trigger Enhanced Processing for Existing Filings
Creates chunk tasks for all filings without analysis to trigger the enhanced processing pipeline
"""

import asyncio
import sys
import os
from datetime import datetime, UTC
from typing import List
import json

# Add the backend directory to the Python path
sys.path.insert(0, '/app')

from app.db import get_db_session
from app.config import Settings
from app.models.filing import Filing, FilingSection
from app.orchestration.planner import EnhancedChunkPlanner, EnhancedChunkTask
from app.orchestration.queue import ChunkQueue
from sqlalchemy import select
from redis.asyncio import Redis

async def trigger_enhanced_processing():
    """Trigger enhanced processing for all filings without analysis."""
    print("🚀 Triggering Enhanced Processing for Existing Filings")
    print("=" * 60)
    
    settings = Settings()
    redis_client = Redis.from_url(settings.redis_url)
    
    # Initialize enhanced chunk planner
    planner = EnhancedChunkPlanner()
    
    # Initialize chunk queue
    chunk_queue = ChunkQueue(redis_client)
    
    # Get all filings without analysis
    async with get_db_session(settings) as session:
        # Get filings without analysis
        filings_stmt = select(Filing).where(
            ~Filing.id.in_(
                select(FilingSection.filing_id).where(FilingSection.filing_id.isnot(None))
            )
        ).limit(50)  # Process in batches of 50
        
        filings_result = await session.execute(filings_stmt)
        filings = filings_result.scalars().all()
        
        print(f"📋 Found {len(filings)} filings to process")
        
        if not filings:
            print("ℹ️  No filings found without analysis")
            return
        
        # Process each filing
        total_tasks_created = 0
        
        for filing in filings:
            print(f"\n🔄 Processing filing: {filing.accession_number} ({filing.form_type})")
            
            try:
                # Get filing sections
                sections_stmt = select(FilingSection).where(FilingSection.filing_id == filing.id)
                sections_result = await session.execute(sections_stmt)
                sections = sections_result.scalars().all()
                
                if not sections:
                    print(f"   ⚠️  No sections found for filing {filing.accession_number}")
                    continue
                
                print(f"   📄 Found {len(sections)} sections")
                
                # Convert sections to planner format
                planner_sections = []
                for section in sections:
                    planner_sections.append({
                        'title': section.title,
                        'content': section.content,
                        'ordinal': section.ordinal
                    })
                
                # Generate enhanced chunk tasks
                enhanced_tasks = await planner.plan_with_analysis(
                    filing.accession_number,
                    planner_sections,
                    filing,
                    sections
                )
                
                print(f"   🧩 Generated {len(enhanced_tasks)} chunk tasks")
                
                # Add tasks to queue
                for task in enhanced_tasks:
                    await chunk_queue.push(task)
                    total_tasks_created += 1
                
                print(f"   ✅ Added {len(enhanced_tasks)} tasks to processing queue")
                
            except Exception as e:
                print(f"   ❌ Error processing filing {filing.accession_number}: {e}")
                continue
        
        print(f"\n🎉 Successfully created {total_tasks_created} processing tasks")
        print(f"📊 Tasks are now in the queue and will be processed by workers")
        
        # Show queue status
        queue_length = await chunk_queue.length()
        print(f"📈 Current queue length: {queue_length}")

async def main():
    """Main entry point."""
    print("🔧 Enhanced Filing Processing Trigger")
    print("This will create processing tasks for filings without analysis")
    print()
    
    await trigger_enhanced_processing()

if __name__ == "__main__":
    asyncio.run(main())
