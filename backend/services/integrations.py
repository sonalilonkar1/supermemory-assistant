"""Integration services using Supermemory Connectors API"""
import os
import requests
import json
import uuid
from typing import List, Dict, Optional
from datetime import datetime, timezone
from services.supermemory_client import get_supermemory_headers, SUPERMEMORY_API_URL

# Supported connector providers (per current Supermemory API)
# Note: Gmail/LinkedIn are not yet supported by the upstream API and will 400.
SUPPORTED_PROVIDERS = ['notion', 'google-drive', 'onedrive', 'github', 'web-crawler']

def get_connector_auth_url(user_id: str, provider: str, redirect_url: str) -> Dict:
    """
    Initiate connector connection using Supermemory API
    Returns auth URL for OAuth-based connectors or connection ID for non-OAuth
    """
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider}")
    
    url = f'{SUPERMEMORY_API_URL}/connections/{provider}'
    
    # Prepare metadata based on provider
    metadata = {}
    if provider == 'web-crawler':
        # Web crawler needs startUrl
        metadata['startUrl'] = redirect_url  # Use redirect_url as startUrl for web crawler
    else:
        # OAuth-based connectors need redirectUrl
        metadata['redirectUrl'] = redirect_url
    
    payload = {
        'metadata': metadata
    }
    
    try:
        response = requests.post(
            url,
            headers=get_supermemory_headers(),
            json=payload
        )
        response.raise_for_status()
        result = response.json()
        
        # OAuth connectors return authLink, non-OAuth return connection directly
        if 'authLink' in result:
            return {
                'authUrl': result['authLink'],
                'connectionId': result.get('connectionId'),
                'requiresOAuth': True
            }
        elif 'connectionId' in result:
            return {
                'connectionId': result['connectionId'],
                'requiresOAuth': False
            }
        else:
            return {
                'connectionId': result.get('id'),
                'requiresOAuth': False
            }
    except requests.exceptions.HTTPError as e:
        error_msg = e.response.text if e.response else str(e)
        status_code = e.response.status_code if e.response else 500
        
        # Handle specific error cases
        if status_code == 403:
            raise ValueError(f"This connector requires a Supermemory Pro plan or is not available for your account. Please check your subscription or try another connector.")
        elif status_code == 400:
            raise ValueError(f"Invalid request for {provider}. This connector may not be supported yet.")
        elif status_code == 404:
            raise ValueError(f"Connector '{provider}' is not available. Please check if it's supported.")
        else:
            print(f"Error initiating {provider} connection: {status_code} - {error_msg}")
            raise ValueError(f"Failed to connect {provider}: {error_msg}")

def get_connection_status(connection_id: str) -> Dict:
    """Get status of a Supermemory connection"""
    url = f'{SUPERMEMORY_API_URL}/connections/{connection_id}'
    
    try:
        response = requests.get(
            url,
            headers=get_supermemory_headers()
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"Error getting connection status: {e.response.status_code} - {e.response.text}")
        return {'status': 'error', 'error': str(e)}

def sync_connection(connection_id: str) -> Dict:
    """Trigger manual sync for a connector"""
    url = f'{SUPERMEMORY_API_URL}/connections/{connection_id}/sync'
    
    try:
        response = requests.post(
            url,
            headers=get_supermemory_headers()
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"Error syncing connection: {e.response.status_code} - {e.response.text}")
        return {'success': False, 'error': str(e)}

def disconnect_connection(connection_id: str) -> bool:
    """Disconnect a Supermemory connector"""
    url = f'{SUPERMEMORY_API_URL}/connections/{connection_id}'
    
    try:
        response = requests.delete(
            url,
            headers=get_supermemory_headers()
        )
        response.raise_for_status()
        return True
    except requests.exceptions.HTTPError as e:
        print(f"Error disconnecting: {e.response.status_code} - {e.response.text}")
        return False

def list_user_connections(user_id: str) -> List[Dict]:
    """List all connections for a user (using container tags)"""
    # Note: Supermemory API may not have a direct "list user connections" endpoint
    # This would need to be tracked in our database via Connector model
    # For now, return empty list - actual connections are stored in Connector model
    return []

def process_connection_callback(provider: str, connection_id: str, user_id: str) -> Dict:
    """
    Process callback after OAuth completion
    Updates connection status and triggers initial sync
    """
    # Check connection status
    status = get_connection_status(connection_id)
    
    if status.get('status') == 'connected':
        # Trigger initial sync
        sync_result = sync_connection(connection_id)
        return {
            'success': True,
            'connectionId': connection_id,
            'status': 'connected',
            'syncTriggered': sync_result.get('success', False)
        }
    else:
        return {
            'success': False,
            'connectionId': connection_id,
            'status': status.get('status', 'unknown'),
            'error': status.get('error')
        }
