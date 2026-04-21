#!/usr/bin/env python3
"""
Test script to verify authentication implementation
Run this after starting the backend server
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_login():
    """Test login endpoint"""
    print("\n1. Testing Login Endpoint...")
    
    response = requests.post(
        f"{BASE_URL}/token",
        data={
            "username": "admin",
            "password": "highwire123"
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        token = data.get("access_token")
        print(f"✅ Login successful! Token: {token[:50]}...")
        return token
    else:
        print(f"❌ Login failed: {response.status_code} - {response.text}")
        return None


def test_protected_endpoint_without_token():
    """Test protected endpoint without token"""
    print("\n2. Testing Protected Endpoint WITHOUT Token...")
    
    response = requests.get(f"{BASE_URL}/api/graph/unread")
    
    if response.status_code == 401:
        print(f"✅ Correctly rejected: {response.json()}")
    else:
        print(f"❌ Should have been rejected but got: {response.status_code}")


def test_protected_endpoint_with_token(token):
    """Test protected endpoint with valid token"""
    print("\n3. Testing Protected Endpoint WITH Token...")
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    response = requests.get(
        f"{BASE_URL}/api/graph/unread",
        headers=headers
    )
    
    if response.status_code == 200:
        print(f"✅ Access granted! Response: {response.json()}")
    else:
        print(f"❌ Access denied: {response.status_code} - {response.text}")


def test_invalid_token():
    """Test protected endpoint with invalid token"""
    print("\n4. Testing Protected Endpoint with INVALID Token...")
    
    headers = {
        "Authorization": "Bearer invalid_token_12345"
    }
    
    response = requests.get(
        f"{BASE_URL}/api/graph/unread",
        headers=headers
    )
    
    if response.status_code == 401:
        print(f"✅ Correctly rejected invalid token: {response.json()}")
    else:
        print(f"❌ Should have rejected invalid token but got: {response.status_code}")


def main():
    print("=" * 60)
    print("Authentication Test Suite")
    print("=" * 60)
    print("\nMake sure the backend server is running on http://localhost:8000")
    print("Press Enter to continue or Ctrl+C to cancel...")
    input()
    
    try:
        # Test 1: Login
        token = test_login()
        
        if not token:
            print("\n❌ Cannot continue without valid token")
            return
        
        # Test 2: Access without token
        test_protected_endpoint_without_token()
        
        # Test 3: Access with valid token
        test_protected_endpoint_with_token(token)
        
        # Test 4: Access with invalid token
        test_invalid_token()
        
        print("\n" + "=" * 60)
        print("✅ All authentication tests completed!")
        print("=" * 60)
        
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Cannot connect to backend server")
        print("Make sure the server is running: uvicorn app.main:app --reload")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")


if __name__ == "__main__":
    main()
