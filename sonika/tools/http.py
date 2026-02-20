import httpx
from typing import Optional, Dict, Any, Type
from pydantic import BaseModel, Field
from .base import BaseTool

class HttpRequestInput(BaseModel):
    url: str = Field(description="The full URL including protocol (http/https)")
    method: str = Field(default="GET", description="HTTP method (GET, POST, PUT, DELETE, PATCH)")
    headers: Optional[Dict[str, str]] = Field(default=None, description="Request headers")
    body: Optional[Dict[str, Any]] = Field(default=None, description="JSON body for the request")
    timeout: Optional[int] = Field(default=30, description="Request timeout in seconds")

class HttpRequestTool(BaseTool):
    name: str = "http_request"
    description: str = """
    Make an HTTP request to any URL. Returns status code, headers, and body.
    """
    args_schema: Type[BaseModel] = HttpRequestInput
    risk_level: int = 1

    def _run(
        self, 
        url: str, 
        method: str = "GET", 
        headers: Optional[Dict[str, str]] = None,
        body: Optional[Dict[str, Any]] = None,
        timeout: int = 30
    ) -> str:
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.request(
                    method=method.upper(),
                    url=url,
                    headers=headers,
                    json=body
                )
                
                # Formato de respuesta para el LLM
                result = f"Status Code: {response.status_code}\n"
                result += "Headers: " + str(dict(response.headers)) + "\n"
                result += "Body:\n"
                
                try:
                    # Intentar formatear JSON bonito
                    import json
                    json_body = response.json()
                    result += json.dumps(json_body, indent=2)
                except:
                    # Fallback a texto plano
                    result += response.text[:2000] # Limitar tamaño
                    if len(response.text) > 2000:
                        result += "\n... (truncated)"
                        
                return result

        except httpx.TimeoutException:
            return f"ERROR: Request timed out after {timeout} seconds"
        except Exception as e:
            return f"ERROR: HTTP Request failed: {str(e)}"
