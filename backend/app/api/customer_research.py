"""
Customer research API endpoints

Provides endpoints for automated customer config generation
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
import logging

from app.services.customer_research import get_research_service

logger = logging.getLogger(__name__)
router = APIRouter()


class ResearchRequest(BaseModel):
    """Request to research a company"""
    company_name: str


class ResearchResponse(BaseModel):
    """Research results for a company"""
    company_name: str
    domain: Optional[str]
    description: Optional[str]
    stock_symbol: Optional[str]
    industry: Optional[str]
    executives: List[Dict[str, str]]
    competitors: List[str]
    keywords: List[str]
    priority_keywords: List[str]
    data_sources: Dict[str, Any]


class GenerateConfigRequest(BaseModel):
    """Request to generate YAML config"""
    research_data: Dict[str, Any]


class GenerateConfigResponse(BaseModel):
    """Generated YAML configuration"""
    yaml_config: str


@router.post("/research", response_model=ResearchResponse)
async def research_company(request: ResearchRequest):
    """
    Research a company and return structured data

    This endpoint uses AI and web search to discover:
    - Company information (domain, description, stock symbol)
    - Executive team and LinkedIn profiles
    - Competitors
    - Keywords and data sources

    Args:
        request: Company name to research

    Returns:
        Structured research data
    """
    try:
        logger.info(f"Researching company: {request.company_name}")

        research_service = get_research_service()
        result = await research_service.research_company(request.company_name)

        return ResearchResponse(**result)

    except Exception as e:
        logger.error(f"Error researching company: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to research company: {str(e)}"
        )


@router.post("/generate-config", response_model=GenerateConfigResponse)
async def generate_config(request: GenerateConfigRequest):
    """
    Generate YAML configuration from research data

    Takes research results and generates a complete YAML block
    ready to paste into customers.yaml

    Args:
        request: Research data from /research endpoint

    Returns:
        YAML configuration string
    """
    try:
        logger.info(f"Generating config for: {request.research_data.get('company_name')}")

        research_service = get_research_service()
        yaml_config = research_service.generate_yaml_config(request.research_data)

        return GenerateConfigResponse(yaml_config=yaml_config)

    except Exception as e:
        logger.error(f"Error generating config: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate config: {str(e)}"
        )


@router.post("/research-and-generate")
async def research_and_generate(request: ResearchRequest):
    """
    One-stop endpoint: research company and generate YAML config

    Combines /research and /generate-config into a single call

    Args:
        request: Company name to research

    Returns:
        Both research data and generated YAML config
    """
    try:
        logger.info(f"Researching and generating config for: {request.company_name}")

        research_service = get_research_service()

        # Research company
        research_data = await research_service.research_company(request.company_name)

        # Generate YAML
        yaml_config = research_service.generate_yaml_config(research_data)

        return {
            "research_data": research_data,
            "yaml_config": yaml_config
        }

    except Exception as e:
        logger.error(f"Error in research-and-generate: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to research and generate config: {str(e)}"
        )
