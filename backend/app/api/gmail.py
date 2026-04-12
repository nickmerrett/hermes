"""
Gmail OAuth API endpoints for connecting customer Gmail accounts.

Handles OAuth2 flow for Gmail API access (press release digest monitoring).
"""

import html
import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.models.database import Customer
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.config.settings import settings
from app.utils.encryption import get_encryption_service

router = APIRouter(prefix="/gmail", tags=["gmail"])
logger = logging.getLogger(__name__)

# Gmail API scopes
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',   # Read emails
    'https://www.googleapis.com/auth/gmail.modify'       # Mark as read, apply labels
]


def _get_oauth_flow() -> Flow:
    """Create OAuth2 flow for Gmail API."""
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=500,
            detail="Gmail OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
        )

    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uris": [settings.google_oauth_redirect_uri],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
    }

    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=settings.google_oauth_redirect_uri
    )

    return flow


@router.get("/oauth/start/{customer_id}")
async def start_gmail_oauth(
    customer_id: int,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user)
):
    """
    Start Gmail OAuth flow for a customer.

    Args:
        customer_id: Customer ID to connect Gmail for

    Returns:
        {
            "auth_url": "https://accounts.google.com/...",
            "customer_id": 123
        }
    """
    # Verify customer exists
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    try:
        flow = _get_oauth_flow()

        # Generate authorization URL
        auth_url, state = flow.authorization_url(
            access_type='offline',          # Request refresh token
            include_granted_scopes='true',  # Incremental authorization
            prompt='consent',               # Force consent screen to ensure refresh token
            state=str(customer_id)          # Pass customer_id in state parameter
        )

        logger.info(f"Started Gmail OAuth flow for customer {customer_id}")

        return {
            "auth_url": auth_url,
            "customer_id": customer_id
        }

    except Exception as e:
        logger.error(f"Error starting Gmail OAuth: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start OAuth flow: {str(e)}")


@router.get("/oauth/callback")
async def gmail_oauth_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="Customer ID passed in state parameter"),
    error: Optional[str] = Query(None, description="Error from OAuth provider"),
    db: Session = Depends(get_db)
):
    """
    Handle OAuth callback from Google.

    Exchanges authorization code for tokens and stores encrypted refresh token.

    Args:
        code: Authorization code from Google
        state: Customer ID
        error: Error message if authorization failed

    Returns:
        HTML page with success/error message
    """
    if error:
        logger.error(f"Gmail OAuth error: {error}")
        return HTMLResponse(
            content=f"""
            <html>
                <head><title>Gmail Connection Failed</title></head>
                <body>
                    <h1>Gmail Connection Failed</h1>
                    <p>Error: {html.escape(error)}</p>
                    <p><a href="javascript:window.close()">Close this window</a></p>
                </body>
            </html>
            """,
            status_code=400
        )

    try:
        customer_id = int(state)
        customer = db.query(Customer).filter(Customer.id == customer_id).first()

        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")

        # Exchange code for tokens
        flow = _get_oauth_flow()
        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Get user's email address
        service = build('gmail', 'v1', credentials=credentials)
        profile = service.users().getProfile(userId='me').execute()
        email_address = profile['emailAddress']

        logger.info(f"Gmail OAuth successful for {email_address} (customer {customer_id})")

        # Encrypt refresh token
        encryption_service = get_encryption_service()
        encrypted_token = encryption_service.encrypt(credentials.refresh_token)

        # Update customer config
        config = customer.config or {}
        config['gmail_enabled'] = True
        config['gmail_config'] = {
            'connected': True,
            'email_address': email_address,
            'refresh_token': encrypted_token,
            'token_expires_at': credentials.expiry.isoformat() if credentials.expiry else None,
            'connected_at': datetime.utcnow().isoformat(),
            'use_sender_whitelist': False,
            'sender_whitelist': [],
            'label_config': {
                'mark_as_read': True,
                'apply_label': ''
            }
        }

        customer.config = config
        db.commit()

        logger.info(f"Saved Gmail configuration for customer {customer_id}")

        # Success page
        return HTMLResponse(
            content=f"""
            <html>
                <head>
                    <title>Gmail Connected</title>
                    <style>
                        body {{
                            font-family: Arial, sans-serif;
                            max-width: 600px;
                            margin: 50px auto;
                            padding: 20px;
                            text-align: center;
                        }}
                        .success {{
                            color: #28a745;
                            font-size: 24px;
                            margin-bottom: 20px;
                        }}
                        .email {{
                            background: #f8f9fa;
                            padding: 10px;
                            border-radius: 5px;
                            margin: 20px 0;
                        }}
                        .button {{
                            background: #007bff;
                            color: white;
                            padding: 10px 20px;
                            border: none;
                            border-radius: 5px;
                            cursor: pointer;
                            text-decoration: none;
                            display: inline-block;
                        }}
                    </style>
                </head>
                <body>
                    <div class="success">✓ Gmail Connected Successfully!</div>
                    <p>Connected account:</p>
                    <div class="email">{email_address}</div>
                    <p>You can now close this window and return to Hermes.</p>
                    <button class="button" onclick="window.close()">Close Window</button>
                </body>
            </html>
            """
        )

    except ValueError as e:
        logger.error(f"Invalid customer ID in state: {state}")
        raise HTTPException(status_code=400, detail=f"Invalid customer ID: {str(e)}")

    except HttpError as e:
        logger.error(f"Gmail API error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Gmail API error: {str(e)}")

    except Exception as e:
        logger.error(f"Error in Gmail OAuth callback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to connect Gmail: {str(e)}")


@router.post("/disconnect/{customer_id}")
async def disconnect_gmail(
    customer_id: int,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user)
):
    """
    Disconnect Gmail for a customer.

    Removes Gmail configuration and encrypted tokens from customer config.

    Args:
        customer_id: Customer ID

    Returns:
        {"success": true, "message": "Gmail disconnected"}
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    try:
        # Remove Gmail config
        config = customer.config or {}

        if 'gmail_config' in config:
            del config['gmail_config']

        config['gmail_enabled'] = False
        customer.config = config
        db.commit()

        logger.info(f"Disconnected Gmail for customer {customer_id}")

        return {
            "success": True,
            "message": "Gmail disconnected successfully"
        }

    except Exception as e:
        logger.error(f"Error disconnecting Gmail: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to disconnect Gmail: {str(e)}")


@router.get("/status/{customer_id}")
async def get_gmail_status(
    customer_id: int,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user)
):
    """
    Check Gmail connection status for a customer.

    Args:
        customer_id: Customer ID

    Returns:
        {
            "connected": true,
            "email": "user@company.com",
            "connected_at": "2026-01-10T10:00:00",
            "enabled": true
        }
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    config = customer.config or {}
    gmail_config = config.get('gmail_config', {})
    gmail_enabled = config.get('gmail_enabled', False)

    connected = gmail_config.get('connected', False)
    email_address = gmail_config.get('email_address')
    connected_at = gmail_config.get('connected_at')

    return {
        "connected": connected,
        "email": email_address if connected else None,
        "connected_at": connected_at if connected else None,
        "enabled": gmail_enabled
    }
