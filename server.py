import os

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Notion")

NOTION_API_TOKEN = os.environ.get("NOTION_API_TOKEN")
NOTION_API_URL = "https://api.notion.com/v1"

headers = {
    "Authorization": f"Bearer {NOTION_API_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

if not NOTION_API_TOKEN:
    raise ValueError("Notion API credentials not configured")


@mcp.tool()
def notion_search(
    query: str,
    limit: int = 10,
    sort_order: str = "desc",
):
    """
    Search for articles in Notion

    Args:
        query: Search keyword
        limit: Maximum number of results (default: 10)
        sort_order: Sort order (asc, desc) (default: desc)

    Returns:
        List of matching Notion pages
    """

    # The Notion Search API only supports 'last_edited_time' for sort.timestamp
    direction = "ascending" if sort_order == "asc" else "descending"

    # Only last_edited_time is supported by Notion Search API for sorting
    sort = {"timestamp": "last_edited_time", "direction": direction}

    filter_obj = {"property": "object", "value": "page"}
    page_size = min(limit, 100)
    payload = {"query": query, "page_size": page_size}

    # Always include sort parameter
    payload["sort"] = sort
    payload["filter"] = filter_obj

    try:
        # Call the Notion search API
        with httpx.Client() as client:
            response = client.post(
                f"{NOTION_API_URL}/search", headers=headers, json=payload
            )

            response.raise_for_status()
            result = response.json()

            # Process the results
            pages = result.get("results", [])
            formatted_results = []

            for page in pages:
                # Process only page objects (redundant check but just to be safe)
                if page.get("object") != "page":
                    continue

                page_id = page.get("id")
                properties = page.get("properties", {})

                # Extract title
                title = ""
                title_property = properties.get("title", properties.get("Name", {}))
                if title_property and "title" in title_property:
                    title_parts = [
                        text.get("plain_text", "")
                        for text in title_property.get("title", [])
                    ]
                    title = "".join(title_parts)

                # Get page tags
                page_tags = []
                tags_property = properties.get("Tags", {})
                if tags_property and "multi_select" in tags_property:
                    page_tags = [
                        tag.get("name") for tag in tags_property.get("multi_select", [])
                    ]

                formatted_results.append(
                    {
                        "id": page_id,
                        "title": title,
                        "created_time": page.get("created_time"),
                        "last_edited_time": page.get("last_edited_time"),
                        "tags": page_tags,
                        "url": page.get("url"),
                    }
                )

            # Trim results if they exceed the limit
            if len(formatted_results) > limit:
                formatted_results = formatted_results[:limit]

            return formatted_results

    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP error: {e.response.status_code} - {e.response.text}"}
    except httpx.RequestError as e:
        return {"error": f"Request error: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


@mcp.tool()
def notion_get_article(article_id: str, format: str = "json"):
    """
    Retrieve article content from Notion

    Args:
        article_id: ID of the article to retrieve
        format: Output format (json, markdown, text) (default: json)

    Returns:
        Article content in the specified format
    """
    if not NOTION_API_TOKEN:
        return {"error": "Notion API credentials not configured"}

    try:
        with httpx.Client() as client:
            page_response = client.get(
                f"{NOTION_API_URL}/pages/{article_id}", headers=headers
            )
            page_response.raise_for_status()
            page_data = page_response.json()

            # Get page blocks (content)
            blocks_response = client.get(
                f"{NOTION_API_URL}/blocks/{article_id}/children?page_size=100",
                headers=headers,
            )
            blocks_response.raise_for_status()
            blocks_data = blocks_response.json()

            # Extract page properties
            properties = page_data.get("properties", {})

            # Extract title
            title = ""
            title_property = properties.get("title", properties.get("Name", {}))
            if title_property and "title" in title_property:
                title_parts = [
                    text.get("plain_text", "")
                    for text in title_property.get("title", [])
                ]
                title = "".join(title_parts)

            # Extract tags if available
            tags = []
            tags_property = properties.get("Tags", {})
            if tags_property and "multi_select" in tags_property:
                tags = [
                    tag.get("name") for tag in tags_property.get("multi_select", [])
                ]

            # Process blocks based on requested format
            content = _process_blocks(blocks_data.get("results", []), format)

            result = {
                "id": article_id,
                "title": title,
                "created_time": page_data.get("created_time"),
                "last_edited_time": page_data.get("last_edited_time"),
                "tags": tags,
                "url": page_data.get("url"),
                "content": content,
            }

            # If markdown format requested, convert result to markdown
            if format == "markdown":
                return _convert_to_markdown(result)
            elif format == "text":
                return _convert_to_text(result)
            else:
                return result

    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP error: {e.response.status_code} - {e.response.text}"}
    except httpx.RequestError as e:
        return {"error": f"Request error: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def _process_blocks(blocks, format="json"):
    """Process Notion blocks and extract content"""
    processed_blocks = []

    for block in blocks:
        block_type = block.get("type")
        block_id = block.get("id")

        if block_type in [
            "paragraph",
            "heading_1",
            "heading_2",
            "heading_3",
            "bulleted_list_item",
            "numbered_list_item",
            "quote",
            "code",
        ]:
            # Extract text content
            content = block.get(block_type, {}).get("rich_text", [])
            text = "".join([item.get("plain_text", "") for item in content])

            processed_blocks.append({"id": block_id, "type": block_type, "text": text})

    return processed_blocks


def _convert_to_markdown(result):
    """Convert the result to markdown format"""
    markdown = f"# {result['title']}\n\n"

    if result["tags"]:
        markdown += (
            "Tags: " + ", ".join([f"`{tag}`" for tag in result["tags"]]) + "\n\n"
        )

    for block in result["content"]:
        block_type = block["type"]
        text = block["text"]

        if block_type == "paragraph":
            markdown += f"{text}\n\n"
        elif block_type == "heading_1":
            markdown += f"# {text}\n\n"
        elif block_type == "heading_2":
            markdown += f"## {text}\n\n"
        elif block_type == "heading_3":
            markdown += f"### {text}\n\n"
        elif block_type == "bulleted_list_item":
            markdown += f"- {text}\n"
        elif block_type == "numbered_list_item":
            markdown += f"1. {text}\n"
        elif block_type == "quote":
            markdown += f"> {text}\n\n"
        elif block_type == "code":
            markdown += f"```\n{text}\n```\n\n"

    return markdown


def _convert_to_text(result):
    """Convert the result to plain text format"""
    text = f"{result['title']}\n\n"

    if result["tags"]:
        text += "Tags: " + ", ".join(result["tags"]) + "\n\n"

    for block in result["content"]:
        block_type = block["type"]
        content = block["text"]

        if block_type in ["paragraph", "quote"]:
            text += f"{content}\n\n"
        elif block_type in ["heading_1", "heading_2", "heading_3"]:
            text += f"{content.upper()}\n\n"
        elif block_type == "bulleted_list_item":
            text += f"* {content}\n"
        elif block_type == "numbered_list_item":
            text += f"- {content}\n"
        elif block_type == "code":
            text += f"{content}\n\n"

    return text
