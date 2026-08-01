import os
from typing import List, Dict, Any, Optional

from octotools.tools.base import BaseTool

from dotenv import load_dotenv
load_dotenv()


class Exa_Search_Tool(BaseTool):
    def __init__(self):
        super().__init__(
            tool_name="Exa_Search_Tool",
            tool_description="A tool that performs AI-powered web searches using Exa. Supports neural, fast, and auto search types with content retrieval (text, highlights, summary), category filtering, domain filtering, text filtering, and date range filtering.",
            tool_version="1.0.0",
            input_types={
                "query": "str - The search query to be used for the Exa search.",
                "num_results": "int - The number of search results to return (default: 10, max: 100).",
                "search_type": "str - The search algorithm to use: 'auto', 'neural', or 'fast' (default: 'auto').",
                "content_mode": "str - Content retrieval mode: 'text', 'highlights', 'summary', or None for no content (default: 'text').",
                "category": "str - Optional category filter: 'company', 'people', 'research paper', 'news', 'personal site', 'financial report' (default: None).",
                "include_domains": "list - Optional list of domains to restrict results to (default: None).",
                "exclude_domains": "list - Optional list of domains to exclude from results (default: None).",
                "include_text": "str - Optional text that must be present in results (default: None).",
                "exclude_text": "str - Optional text that must not be present in results (default: None).",
                "start_published_date": "str - Optional start date filter in ISO 8601 format, e.g. '2024-01-01T00:00:00.000Z' (default: None).",
                "end_published_date": "str - Optional end date filter in ISO 8601 format (default: None).",
            },
            output_type="list - A list of dictionaries containing search result information.",
            demo_commands=[
                {
                    "command": 'execution = tool.execute(query="Python programming")',
                    "description": "Perform an Exa search for 'Python programming' and return the default number of results with text content."
                },
                {
                    "command": 'execution = tool.execute(query="Machine learning tutorials", num_results=5, content_mode="highlights")',
                    "description": "Perform an Exa search for 'Machine learning tutorials' and return 5 results with highlights."
                },
                {
                    "command": 'execution = tool.execute(query="recent AI research", category="research paper", num_results=5)',
                    "description": "Search for recent AI research papers using category filtering."
                },
            ],
        )
        self.api_key = os.getenv("EXA_API_KEY")

    def execute(
        self,
        query: str,
        num_results: int = 10,
        search_type: str = "auto",
        content_mode: str = "text",
        category: Optional[str] = None,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        include_text: Optional[str] = None,
        exclude_text: Optional[str] = None,
        start_published_date: Optional[str] = None,
        end_published_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Executes an Exa search based on the provided query and parameters.

        Parameters:
            query (str): The search query.
            num_results (int): The number of search results to return (default: 10).
            search_type (str): The search algorithm: 'auto', 'neural', or 'fast' (default: 'auto').
            content_mode (str): Content retrieval mode: 'text', 'highlights', 'summary', or None (default: 'text').
            category (str): Optional category filter.
            include_domains (list): Optional list of domains to restrict results to.
            exclude_domains (list): Optional list of domains to exclude.
            include_text (str): Optional text that must be present in results.
            exclude_text (str): Optional text that must not be present in results.
            start_published_date (str): Optional start date filter in ISO 8601 format.
            end_published_date (str): Optional end date filter in ISO 8601 format.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries containing search result information.
        """
        if not self.api_key:
            return [{"error": "Exa API key is not set. Please set the EXA_API_KEY environment variable."}]

        try:
            from exa_py import Exa
        except ImportError:
            return [{"error": "exa-py is not installed. Please install it with: pip install exa-py"}]

        try:
            exa = Exa(self.api_key)
            exa.headers["x-exa-integration"] = "octotools"

            search_kwargs = {
                "query": query,
                "num_results": num_results,
                "type": search_type,
            }

            if category:
                search_kwargs["category"] = category
            if include_domains:
                search_kwargs["include_domains"] = include_domains
            if exclude_domains:
                search_kwargs["exclude_domains"] = exclude_domains
            if include_text:
                search_kwargs["include_text"] = [include_text]
            if exclude_text:
                search_kwargs["exclude_text"] = [exclude_text]
            if start_published_date:
                search_kwargs["start_published_date"] = start_published_date
            if end_published_date:
                search_kwargs["end_published_date"] = end_published_date

            if content_mode == "text":
                search_kwargs["text"] = True
            elif content_mode == "highlights":
                search_kwargs["highlights"] = True
            elif content_mode == "summary":
                search_kwargs["summary"] = True

            results = exa.search_and_contents(**search_kwargs)

            output = []
            for result in results.results:
                item = {
                    "title": result.title,
                    "url": result.url,
                }
                if hasattr(result, "text") and result.text:
                    item["text"] = result.text
                if hasattr(result, "highlights") and result.highlights:
                    item["highlights"] = result.highlights
                if hasattr(result, "summary") and result.summary:
                    item["summary"] = result.summary
                if hasattr(result, "published_date") and result.published_date:
                    item["published_date"] = result.published_date

                output.append(item)

            if not output:
                return [{"error": "No results found."}]

            return output

        except Exception as e:
            return [{"error": f"An error occurred: {str(e)}"}]

    def get_metadata(self):
        """
        Returns the metadata for the Exa_Search_Tool.

        Returns:
            dict: A dictionary containing the tool's metadata.
        """
        metadata = super().get_metadata()
        return metadata


if __name__ == "__main__":
    # Test command:
    """
    Run the following commands in the terminal to test the script:

    export EXA_API_KEY=your_api_key_here
    cd octotools/tools/exa_search
    python tool.py
    """

    # Example usage of the Exa_Search_Tool
    tool = Exa_Search_Tool()

    # Get tool metadata
    metadata = tool.get_metadata()
    print(metadata)

    # Execute the tool to perform an Exa search
    query = "nobel prize winners in chemistry 2024"
    try:
        execution = tool.execute(query=query, num_results=5)
        print("\nExecution Result:")
        print(f"Search query: {query}")
        print(f"Number of results: {len(execution)}")
        print("\nSearch Results:")
        if "error" in execution[0]:
            print(f"Error: {execution[0]['error']}")
        else:
            for i, item in enumerate(execution, 1):
                print(f"\n{i}. Title: {item['title']}")
                print(f"   URL: {item['url']}")
                if "text" in item:
                    print(f"   Text: {item['text'][:200]}...")
    except Exception as e:
        print(f"Execution failed: {e}")

    print("Done!")
