# Mock Financial APIs
from typing import Dict


async def get_financial_news(company_name: str) -> dict:
    return {
        "company_name": company_name,
        "news": [{"headline": f"Mock news for {company_name}", "description": "Sample news", "date": "2025-05-25", "source": "Mock"}]
    }

async def get_quarterly_results(company_name: str, quarter: str) -> dict:
    return {
        "company_name": company_name,
        "quarter": quarter,
        "valuation_ratios": {"pe_ratio": 15.5, "pb_ratio": 2.3},
        "sales": 90000000
        # "files": {"balance_sheet": "https://dummyfinancialapi.com/files/balance_sheet.xlsx"}
    }

# Define invalid() function (add to src.chat.functions_list)
async def invalid() -> Dict:
    return {"error": "Query is not related to financial markets. Please ask about stocks, earnings, or financial news."}


FUNCTIONS = [
    {
        "name": "get_financial_news",
        "description": "Fetch financial news for a company",
        "parameters": {
            "type": "object",
            "properties": {"company_name": {"type": "string"}},
            "required": ["company_name"]
        }
    },
    {
        "name": "get_quarterly_results",
        "description": "Fetch quarterly financial results for a company",
        "parameters": {
            "type": "object",
            "properties": {
                "company_name": {"type": "string"},
                "quarter": {"type": "string", "description": "Quarter in YYYY-Q# format (e.g., 2024-Q4)"}
            },
            "required": ["company_name", "quarter"]
        }
    },
    {
        "name": "invalid",
        "description": "Call this function when the user query is not related to financial markets.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }
]

FUNCTION_MAP = {
    "get_financial_news": get_financial_news,
    "get_quarterly_results": get_quarterly_results,
    "invalid": invalid
}

