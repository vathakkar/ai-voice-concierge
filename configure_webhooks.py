#!/usr/bin/env python3
"""
Script to configure Azure Communication Services webhooks
"""
import os
import requests
import json
from azure.identity import DefaultAzureCredential

# Set the connection string directly for testing
ACS_CONNECTION_STRING = "endpoint=https://phone-number-vansh.unitedstates.communication.azure.com/;accesskey=your_access_key_here"

def get_access_token():
    """Get access token for Azure Communication Services"""
    credential = DefaultAzureCredential()
    token = credential.get_token("https://communication.azure.com/.default")
    return token.token

def configure_webhooks():
    """Configure webhooks for ACS phone number"""
    
    # Extract resource details from connection string
    # Format: endpoint=https://resource.communication.azure.com/;accesskey=key
    connection_parts = ACS_CONNECTION_STRING.split(';')
    endpoint = None
    for part in connection_parts:
        if part.startswith('endpoint='):
            endpoint = part.split('=')[1]
            break
    
    if not endpoint:
        print("Could not extract endpoint from connection string")
        return
    
    # Extract resource name from endpoint
    # endpoint: https://phone-number-vansh.unitedstates.communication.azure.com/
    resource_name = endpoint.split('//')[1].split('.')[0]
    
    print(f"Resource name: {resource_name}")
    print(f"Endpoint: {endpoint}")
    
    # Get access token
    try:
        access_token = get_access_token()
        print("Successfully obtained access token")
    except Exception as e:
        print(f"Error getting access token: {e}")
        return
    
    # Webhook URLs for your deployed app
    webhook_base = "https://ai-voice-concierge.azurewebsites.net"
    webhook_urls = {
        "callConnected": f"{webhook_base}/webhook/call-connected",
        "mediaStream": f"{webhook_base}/webhook/media-stream", 
        "callEnded": f"{webhook_base}/webhook/call-ended"
    }
    
    print("\nWebhook URLs to configure:")
    for event, url in webhook_urls.items():
        print(f"{event}: {url}")
    
    print("\n=== MANUAL CONFIGURATION REQUIRED ===")
    print("Due to CLI limitations, you need to configure webhooks manually:")
    print("\n1. Go to Azure Portal: https://portal.azure.com")
    print("2. Navigate to: Communication Services > phone-number-vansh")
    print("3. Go to 'Phone numbers' section")
    print("4. Select your phone number")
    print("5. Configure webhooks with these URLs:")
    print("   - Call Connected: https://ai-voice-concierge.azurewebsites.net/webhook/call-connected")
    print("   - Media Stream: https://ai-voice-concierge.azurewebsites.net/webhook/media-stream")
    print("   - Call Ended: https://ai-voice-concierge.azurewebsites.net/webhook/call-ended")
    
    print("\n=== ALTERNATIVE: USE AZURE CLI ===")
    print("You can also try configuring via Azure CLI with these commands:")
    print("(Note: These may not work due to CLI extension limitations)")
    print("\n# Get phone numbers:")
    print("az communication phonenumber list")
    print("\n# Configure webhooks (if supported):")
    print("az communication phonenumber update --phone-number <your-phone-number> --webhook-url <webhook-url>")
    
    print("\n=== TEST YOUR WEBHOOKS ===")
    print("After configuring webhooks, test them by calling your ACS phone number.")
    print("The webhooks should trigger and you should see logs in your Azure Web App.")

if __name__ == "__main__":
    configure_webhooks() 