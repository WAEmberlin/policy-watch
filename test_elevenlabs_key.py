"""
Quick test script to verify your ElevenLabs API key works.
Run this to test your API key before using it in the workflow.
"""
import os
import requests

def test_api_key():
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    
    if not api_key:
        print("ERROR: ELEVENLABS_API_KEY environment variable not set")
        print("\nTo set it:")
        print("  Windows PowerShell: $env:ELEVENLABS_API_KEY='your_key_here'")
        print("  Windows CMD: set ELEVENLABS_API_KEY=your_key_here")
        print("  Linux/Mac: export ELEVENLABS_API_KEY='your_key_here'")
        return False
    
    # Clean the key
    api_key = api_key.strip()
    print(f"Testing API key (length: {len(api_key)} characters)...")
    print(f"Key starts with: {api_key[:4]}...")
    
    # Test with a simple request
    url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }
    
    data = {
        "text": "Hello, this is a test.",
        "model_id": "eleven_flash_v2_5",  # Free tier model - Eleven Flash v2.5
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }
    
    try:
        print("\nMaking test API call...")
        response = requests.post(url, json=data, headers=headers, timeout=30)
        
        if response.status_code == 200:
            print("✅ SUCCESS! API key is valid and working.")
            print(f"   Received {len(response.content)} bytes of audio data")
            return True
        elif response.status_code == 401:
            print("❌ ERROR: 401 Unauthorized")
            print("   The API key is being rejected by ElevenLabs.")
            print("\nPossible causes:")
            print("   1. API key is incorrect or expired")
            print("   2. API key doesn't have text-to-speech permissions")
            print("   3. Account has been suspended or disabled")
            try:
                error_detail = response.json()
                if "detail" in error_detail:
                    print(f"\n   API says: {error_detail.get('detail', {}).get('message', 'Unknown')}")
            except:
                pass
            return False
        elif response.status_code == 429:
            print("❌ ERROR: 429 Rate Limit")
            print("   You've exceeded your monthly character limit.")
            return False
        else:
            print(f"❌ ERROR: Unexpected status code {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR: Request failed - {e}")
        return False
    except Exception as e:
        print(f"❌ ERROR: Unexpected error - {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("ElevenLabs API Key Test")
    print("=" * 60)
    test_api_key()
    print("=" * 60)

