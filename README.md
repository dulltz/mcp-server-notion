# mcp-server-notion

## Overview

mcp-server-notion is an MCP server that uses the Notion API to search for articles on Notion and retrieve their contents. This service utilizes Notion as a content source, allowing you to easily access necessary article information programmatically.

## Features

- Search for articles within Notion databases
- Retrieve full article content or partial content

## Prerequisites

- Python 3.13 or higher
- Notion API integration setup and permissions
- Notion integration token

### Configuration

```env
NOTION_API_TOKEN=your_notion_integration_token
```

### Tools

#### `notion_search`

- `query`: Search keyword
- `limit`: Maximum number of results

#### `notion_get_article`

- `article_id`: ID of the article to retrieve
- `format`: Output format (json, markdown, text)
