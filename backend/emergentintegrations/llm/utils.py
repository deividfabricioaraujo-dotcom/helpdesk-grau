"""Utility functions for LLM integrations."""
import os
from typing import Optional


def get_app_identifier() -> Optional[str]:
    """
    Get the application identifier from environment variables.

    Tries APP_URL first (preview pods), then falls back to
    REACT_APP_BACKEND_URL (deployed apps).

    Returns:
        App URL if found, None otherwise
    """
    app_url = os.getenv('APP_URL')
    if not app_url:
        app_url = os.getenv('REACT_APP_BACKEND_URL')
    return app_url

def get_integration_proxy_url() -> Optional[str]:
    """
    Get the integration proxy URL from environment variables.

    Returns:
        Integration proxy URL if found, None otherwise
    """
    proxy_url = os.getenv('INTEGRATION_PROXY_URL')

    if not proxy_url:
        proxy_url = os.getenv('integration_proxy_url')

    if not proxy_url:
        proxy_url = "https://integrations.emergentagent.com"
        
    return proxy_url