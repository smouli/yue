#!/usr/bin/env python3
"""
Simple health check script for Vertex AI deployment
This provides more detailed error information than curl
"""
import requests
import sys
import json
import time

def check_health():
    try:
        # Try to connect to the health endpoint
        response = requests.get('http://localhost:8080/health', timeout=30)
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"✅ Health check passed: {data.get('status', 'unknown')}")
                return True
            except json.JSONDecodeError:
                print(f"✅ Health check passed (non-JSON response): {response.text[:100]}")
                return True
        else:
            print(f"❌ Health check failed: HTTP {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Health check failed: Cannot connect to server (not started yet?)")
        return False
    except requests.exceptions.Timeout:
        print("❌ Health check failed: Request timeout (server too slow?)")
        return False
    except Exception as e:
        print(f"❌ Health check failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = check_health()
    sys.exit(0 if success else 1) 