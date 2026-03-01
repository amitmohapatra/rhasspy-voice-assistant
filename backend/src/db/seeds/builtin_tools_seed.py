"""Seed data for built-in tools.

Run this ONCE during initial setup to populate the database.
After that, all management is via API/UI - no code changes needed.

Usage:
    python -m src.db.seeds.builtin_tools_seed

Or call from migration/startup:
    from src.db.seeds.builtin_tools_seed import seed_builtin_tools
    await seed_builtin_tools(db_session)
"""

from src.models.capability import CapabilityType
from src.models.builtin_tool import ToolCategory


# ==================== Seed Data ====================
# This is ONLY used for initial database population.
# After seeding, all management is via API/UI.

BUILTIN_TOOLS_SEED_DATA = {
    # Provider name -> List of tools
    "openai": [
        {
            "name": "file_search",
            "display_name": "File Search",
            "description": "Search through uploaded files using semantic search. Automatically indexes PDFs, documents, and text files.",
            "icon": "file-search",
            "category": ToolCategory.RETRIEVAL,
            "capability_type": CapabilityType.FILE_SEARCH,
            "config_schema": {
                "type": "object",
                "properties": {
                    "max_num_results": {"type": "integer", "default": 20, "minimum": 1, "maximum": 50},
                }
            },
            "default_config": {"max_num_results": 20},
            "api_config": {"tool_type": "file_search"},
            "excluded_model_patterns": ["o1*", "o3*", "o4*"],
            "docs_url": "https://platform.openai.com/docs/assistants/tools/file-search",
            "sort_order": 1,
        },
        {
            "name": "code_interpreter",
            "display_name": "Code Interpreter",
            "description": "Execute Python code in a sandboxed environment. Great for data analysis, math, and file processing.",
            "icon": "code",
            "category": ToolCategory.EXECUTION,
            "capability_type": CapabilityType.CODE_INTERPRETER,
            "config_schema": {"type": "object", "properties": {}},
            "default_config": {},
            "api_config": {"tool_type": "code_interpreter"},
            "excluded_model_patterns": ["o1*", "o3*", "o4*"],
            "docs_url": "https://platform.openai.com/docs/assistants/tools/code-interpreter",
            "sort_order": 2,
        },
        {
            "name": "web_search",
            "display_name": "Web Search",
            "description": "Search the internet for real-time information. Access current news, weather, and live data.",
            "icon": "globe",
            "category": ToolCategory.RETRIEVAL,
            "capability_type": CapabilityType.WEB_SEARCH,
            "config_schema": {"type": "object", "properties": {"search_context_size": {"type": "string", "enum": ["low", "medium", "high"]}}},
            "default_config": {"search_context_size": "medium"},
            "api_config": {"tool_type": "web_search"},
            "supported_model_patterns": ["gpt-4*", "gpt-5*"],
            "docs_url": "https://platform.openai.com/docs/guides/tools-web-search",
            "sort_order": 3,
        },
        {
            "name": "image_generation",
            "display_name": "DALL·E Image Generation",
            "description": "Generate images from text descriptions using DALL·E 3.",
            "icon": "image",
            "category": ToolCategory.GENERATION,
            "capability_type": CapabilityType.IMAGE_GENERATION,
            "config_schema": {"type": "object", "properties": {"size": {"type": "string"}, "quality": {"type": "string"}}},
            "default_config": {"size": "1024x1024", "quality": "standard"},
            "api_config": {"model": "dall-e-3"},
            "sort_order": 4,
        },
        {
            "name": "computer_use",
            "display_name": "Computer Use",
            "description": "Control a computer through screenshots and mouse/keyboard actions. Preview feature for GPT-5 and GPT-4o models.",
            "icon": "monitor",
            "category": ToolCategory.AUTOMATION,
            "capability_type": CapabilityType.COMPUTER_USE,
            "config_schema": {"type": "object", "properties": {"display_width": {"type": "integer"}, "display_height": {"type": "integer"}}},
            "default_config": {"display_width": 1024, "display_height": 768},
            "api_config": {"tool_type": "computer_use_preview"},
            "is_preview": True,
            "supported_model_patterns": ["gpt-5*", "gpt-4o*"],
            "docs_url": "https://platform.openai.com/docs/guides/tools-computer-use",
            "sort_order": 5,
        },
    ],

    "anthropic": [
        {
            "name": "computer_use",
            "display_name": "Computer Use",
            "description": "Control a computer through screenshots and mouse/keyboard actions.",
            "icon": "monitor",
            "category": ToolCategory.AUTOMATION,
            "capability_type": CapabilityType.COMPUTER_USE,
            "config_schema": {"type": "object", "properties": {"display_width": {"type": "integer"}, "display_height": {"type": "integer"}}},
            "default_config": {"display_width": 1024, "display_height": 768},
            "api_config": {"tool_type": "computer_20250124"},
            "is_beta": True,
            "supported_model_patterns": ["claude-3-5-sonnet*", "claude-*-4*", "claude-*-4.6*"],
            "docs_url": "https://docs.anthropic.com/en/docs/build-with-claude/computer-use",
            "sort_order": 1,
        },
        {
            "name": "web_search",
            "display_name": "Web Search",
            "description": "Search the internet for real-time information using Claude's built-in web search tool.",
            "icon": "globe",
            "category": ToolCategory.RETRIEVAL,
            "capability_type": CapabilityType.WEB_SEARCH,
            "config_schema": {"type": "object", "properties": {"max_results": {"type": "integer", "default": 5}}},
            "default_config": {"max_results": 5},
            "api_config": {"tool_type": "web_search_20250305"},
            "supported_model_patterns": ["claude-*-4*"],
            "docs_url": "https://docs.anthropic.com/en/docs/build-with-claude/tool-use/web-search",
            "sort_order": 2,
        },
        {
            "name": "text_editor",
            "display_name": "Text Editor",
            "description": "View, create, and edit files with Claude's built-in text editor tool for code editing tasks.",
            "icon": "code",
            "category": ToolCategory.EXECUTION,
            "capability_type": CapabilityType.CODE_INTERPRETER,
            "config_schema": {},
            "default_config": {},
            "api_config": {"tool_type": "text_editor_20250124"},
            "supported_model_patterns": ["claude-*-4*"],
            "docs_url": "https://docs.anthropic.com/en/docs/build-with-claude/tool-use/text-editor",
            "sort_order": 3,
        },
        {
            "name": "artifacts",
            "display_name": "Artifacts",
            "description": "Create rich, interactive artifacts like code, documents, and visualizations.",
            "icon": "box",
            "category": ToolCategory.OUTPUT,
            "capability_type": CapabilityType.ARTIFACTS,
            "config_schema": {},
            "default_config": {},
            "api_config": {},
            "sort_order": 4,
        },
        {
            "name": "mcp",
            "display_name": "MCP Tools",
            "description": "Connect to external tools via Model Context Protocol (MCP) servers.",
            "icon": "plug",
            "category": ToolCategory.INTEGRATION,
            "capability_type": CapabilityType.MCP,
            "config_schema": {"type": "object", "properties": {"servers": {"type": "array"}}},
            "default_config": {},
            "api_config": {},
            "is_beta": True,
            "docs_url": "https://modelcontextprotocol.io/",
            "sort_order": 5,
        },
    ],

    "google": [
        {
            "name": "google_search",
            "display_name": "Google Search",
            "description": "Search the web using Google Search for real-time information.",
            "icon": "globe",
            "category": ToolCategory.RETRIEVAL,
            "capability_type": CapabilityType.WEB_SEARCH,
            "config_schema": {"type": "object", "properties": {"dynamic_threshold": {"type": "number"}}},
            "default_config": {},
            "api_config": {"tool_type": "google_search_retrieval"},
            "docs_url": "https://ai.google.dev/gemini-api/docs/grounding",
            "sort_order": 1,
        },
        {
            "name": "code_execution",
            "display_name": "Code Execution",
            "description": "Execute Python code within Gemini for calculations and data processing.",
            "icon": "code",
            "category": ToolCategory.EXECUTION,
            "capability_type": CapabilityType.CODE_INTERPRETER,
            "config_schema": {},
            "default_config": {},
            "api_config": {"tool_type": "code_execution"},
            "sort_order": 2,
        },
        {
            "name": "url_context",
            "display_name": "URL Context",
            "description": "Fetch and process content from URLs for grounding responses with web page data.",
            "icon": "globe",
            "category": ToolCategory.RETRIEVAL,
            "capability_type": CapabilityType.WEB_SEARCH,
            "config_schema": {},
            "default_config": {},
            "api_config": {"tool_type": "url_context"},
            "docs_url": "https://ai.google.dev/gemini-api/docs/url-context",
            "sort_order": 3,
        },
    ],

    "mistral": [
        {
            "name": "web_search",
            "display_name": "Web Search",
            "description": "Search the internet using Mistral's integrated web search.",
            "icon": "globe",
            "category": ToolCategory.RETRIEVAL,
            "capability_type": CapabilityType.WEB_SEARCH,
            "config_schema": {},
            "default_config": {},
            "api_config": {},
            "sort_order": 1,
        },
        {
            "name": "code_interpreter",
            "display_name": "Code Interpreter",
            "description": "Execute code in a sandboxed environment.",
            "icon": "code",
            "category": ToolCategory.EXECUTION,
            "capability_type": CapabilityType.CODE_INTERPRETER,
            "config_schema": {},
            "default_config": {},
            "api_config": {},
            "sort_order": 2,
        },
    ],

    "cohere": [
        {
            "name": "web_search",
            "display_name": "Web Search",
            "description": "Search the internet with Cohere's connector system.",
            "icon": "globe",
            "category": ToolCategory.RETRIEVAL,
            "capability_type": CapabilityType.WEB_SEARCH,
            "config_schema": {"type": "object", "properties": {"connector_id": {"type": "string"}}},
            "default_config": {"connector_id": "web-search"},
            "api_config": {"connector_id": "web-search"},
            "sort_order": 1,
        },
        {
            "name": "rag_search",
            "display_name": "RAG Search",
            "description": "Search through documents using Cohere's RAG system.",
            "icon": "file-search",
            "category": ToolCategory.RETRIEVAL,
            "capability_type": CapabilityType.FILE_SEARCH,
            "config_schema": {},
            "default_config": {},
            "api_config": {},
            "sort_order": 2,
        },
    ],

    "perplexity": [
        {
            "name": "online_search",
            "display_name": "Online Search",
            "description": "Real-time web search with citations. Native to all Perplexity models.",
            "icon": "globe",
            "category": ToolCategory.RETRIEVAL,
            "capability_type": CapabilityType.WEB_SEARCH,
            "config_schema": {"type": "object", "properties": {"search_recency_filter": {"type": "string", "enum": ["day", "week", "month", "year"]}}},
            "default_config": {},
            "api_config": {},
            "is_always_on": True,
            "sort_order": 1,
        },
    ],

    "groq": [
        {
            "name": "function_calling",
            "display_name": "Function Calling",
            "description": "Call custom functions with ultra-fast inference.",
            "icon": "function",
            "category": ToolCategory.TOOLS,
            "capability_type": CapabilityType.FUNCTION_CALLING,
            "config_schema": {},
            "default_config": {},
            "api_config": {},
            "sort_order": 1,
        },
    ],

    "together": [
        {
            "name": "function_calling",
            "display_name": "Function Calling",
            "description": "Call custom functions with Together AI models.",
            "icon": "function",
            "category": ToolCategory.TOOLS,
            "capability_type": CapabilityType.FUNCTION_CALLING,
            "config_schema": {},
            "default_config": {},
            "api_config": {},
            "sort_order": 1,
        },
    ],

    "fireworks": [
        {
            "name": "function_calling",
            "display_name": "Function Calling",
            "description": "Call custom functions with Fireworks AI inference.",
            "icon": "function",
            "category": ToolCategory.TOOLS,
            "capability_type": CapabilityType.FUNCTION_CALLING,
            "config_schema": {},
            "default_config": {},
            "api_config": {},
            "sort_order": 1,
        },
        {
            "name": "json_mode",
            "display_name": "JSON Mode",
            "description": "Generate structured JSON output with grammar-based decoding.",
            "icon": "braces",
            "category": ToolCategory.OUTPUT,
            "capability_type": CapabilityType.STRUCTURED_OUTPUT,
            "config_schema": {"type": "object", "properties": {"json_schema": {"type": "object"}}},
            "default_config": {},
            "api_config": {},
            "sort_order": 2,
        },
    ],

    "deepseek": [
        {
            "name": "function_calling",
            "display_name": "Function Calling",
            "description": "Call custom functions with DeepSeek models.",
            "icon": "function",
            "category": ToolCategory.TOOLS,
            "capability_type": CapabilityType.FUNCTION_CALLING,
            "config_schema": {},
            "default_config": {},
            "api_config": {},
            "sort_order": 1,
        },
        {
            "name": "deep_thinking",
            "display_name": "Deep Thinking",
            "description": "Extended reasoning mode for complex problems (DeepSeek R1).",
            "icon": "brain",
            "category": ToolCategory.REASONING,
            "capability_type": CapabilityType.EXTENDED_THINKING,
            "config_schema": {},
            "default_config": {},
            "api_config": {},
            "supported_model_patterns": ["deepseek-r1*", "deepseek-reasoner*"],
            "sort_order": 2,
        },
    ],

    "xai": [
        {
            "name": "web_search",
            "display_name": "Web Search",
            "description": "Real-time web search with X/Twitter integration.",
            "icon": "globe",
            "category": ToolCategory.RETRIEVAL,
            "capability_type": CapabilityType.WEB_SEARCH,
            "config_schema": {},
            "default_config": {},
            "api_config": {},
            "sort_order": 1,
        },
        {
            "name": "function_calling",
            "display_name": "Function Calling",
            "description": "Call custom functions with Grok models.",
            "icon": "function",
            "category": ToolCategory.TOOLS,
            "capability_type": CapabilityType.FUNCTION_CALLING,
            "config_schema": {},
            "default_config": {},
            "api_config": {},
            "sort_order": 2,
        },
    ],

    "azure_openai": [
        {
            "name": "file_search",
            "display_name": "File Search",
            "description": "Search through files with Azure AI Search integration.",
            "icon": "file-search",
            "category": ToolCategory.RETRIEVAL,
            "capability_type": CapabilityType.FILE_SEARCH,
            "config_schema": {},
            "default_config": {},
            "api_config": {"tool_type": "file_search"},
            "sort_order": 1,
        },
        {
            "name": "code_interpreter",
            "display_name": "Code Interpreter",
            "description": "Execute Python code in Azure's sandboxed environment.",
            "icon": "code",
            "category": ToolCategory.EXECUTION,
            "capability_type": CapabilityType.CODE_INTERPRETER,
            "config_schema": {},
            "default_config": {},
            "api_config": {"tool_type": "code_interpreter"},
            "sort_order": 2,
        },
    ],

    "bedrock": [
        {
            "name": "tool_use",
            "display_name": "Tool Use",
            "description": "Call custom tools with Bedrock Converse API.",
            "icon": "function",
            "category": ToolCategory.TOOLS,
            "capability_type": CapabilityType.FUNCTION_CALLING,
            "config_schema": {},
            "default_config": {},
            "api_config": {},
            "sort_order": 1,
        },
        {
            "name": "knowledge_base",
            "display_name": "Knowledge Base",
            "description": "Search through Amazon Bedrock Knowledge Bases.",
            "icon": "file-search",
            "category": ToolCategory.RETRIEVAL,
            "capability_type": CapabilityType.FILE_SEARCH,
            "config_schema": {"type": "object", "properties": {"knowledge_base_id": {"type": "string"}}},
            "default_config": {},
            "api_config": {},
            "sort_order": 2,
        },
    ],

    "ollama": [
        {
            "name": "function_calling",
            "display_name": "Function Calling",
            "description": "Call custom functions with local Ollama models (model-dependent).",
            "icon": "function",
            "category": ToolCategory.TOOLS,
            "capability_type": CapabilityType.FUNCTION_CALLING,
            "config_schema": {},
            "default_config": {},
            "api_config": {},
            "sort_order": 1,
        },
    ],
}


async def seed_builtin_tools(db_session) -> dict:
    """Seed built-in tools into the database.

    This should be called once during initial setup.
    After seeding, all management is via API/UI.

    Returns:
        Summary of seeding operation
    """
    from sqlalchemy import select
    from src.models.ai_model import AIProvider
    from src.models.builtin_tool import BuiltinTool

    created = []
    skipped = []
    errors = []

    for provider_name, tools in BUILTIN_TOOLS_SEED_DATA.items():
        # Find provider
        result = await db_session.execute(
            select(AIProvider).where(AIProvider.name == provider_name)
        )
        provider = result.scalar_one_or_none()

        if not provider:
            errors.append(f"Provider '{provider_name}' not found in database")
            continue

        for tool_data in tools:
            # Check if tool already exists
            result = await db_session.execute(
                select(BuiltinTool).where(
                    BuiltinTool.provider_id == provider.id,
                    BuiltinTool.name == tool_data["name"],
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                skipped.append(f"{provider_name}/{tool_data['name']}")
                continue

            try:
                tool = BuiltinTool(
                    provider_id=provider.id,
                    name=tool_data["name"],
                    display_name=tool_data["display_name"],
                    description=tool_data.get("description"),
                    icon=tool_data.get("icon"),
                    category=tool_data.get("category", ToolCategory.TOOLS),
                    capability_type=tool_data["capability_type"],
                    config_schema=tool_data.get("config_schema", {}),
                    default_config=tool_data.get("default_config", {}),
                    api_config=tool_data.get("api_config", {}),
                    is_preview=tool_data.get("is_preview", False),
                    is_beta=tool_data.get("is_beta", False),
                    is_always_on=tool_data.get("is_always_on", False),
                    supported_model_patterns=tool_data.get("supported_model_patterns", []),
                    excluded_model_patterns=tool_data.get("excluded_model_patterns", []),
                    docs_url=tool_data.get("docs_url"),
                    sort_order=tool_data.get("sort_order", 0),
                )
                db_session.add(tool)
                created.append(f"{provider_name}/{tool_data['name']}")
            except Exception as e:
                errors.append(f"{provider_name}/{tool_data['name']}: {str(e)}")

    await db_session.commit()

    return {
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "summary": {
            "total_created": len(created),
            "total_skipped": len(skipped),
            "total_errors": len(errors),
        }
    }


# CLI entry point
if __name__ == "__main__":
    import asyncio
    from src.db.session import AsyncSessionLocal

    async def main():
        async with AsyncSessionLocal() as session:
            result = await seed_builtin_tools(session)
            print("Seeding complete!")
            print(f"Created: {result['summary']['total_created']}")
            print(f"Skipped: {result['summary']['total_skipped']}")
            print(f"Errors: {result['summary']['total_errors']}")

            if result['errors']:
                print("\nErrors:")
                for error in result['errors']:
                    print(f"  - {error}")

    asyncio.run(main())
