#!/usr/bin/env python3
"""
Focused Google Books API Debugging Test
Tests with very famous books to identify specific issues
"""

import requests
import json
import asyncio
import httpx
from pathlib import Path

# Get backend URL
def get_backend_url():
    frontend_env_path = Path("/app/frontend/.env")
    if frontend_env_path.exists():
        with open(frontend_env_path, 'r') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    return line.split('=', 1)[1].strip()
    return "http://localhost:8001"

BASE_URL = get_backend_url()
API_URL = f"{BASE_URL}/api"

async def test_google_books_direct():
    """Test Google Books API directly with different strategies"""
    print("🔍 TESTING GOOGLE BOOKS API DIRECTLY")
    print("=" * 50)
    
    # Test with very simple, famous book
    test_queries = [
        "Harry Potter",
        "The Great Gatsby",
        "intitle:Harry Potter",
        "inauthor:Rowling Harry Potter",
        "isbn:9780439708180"  # Harry Potter ISBN
    ]
    
    for query in test_queries:
        print(f"\n📚 Testing query: '{query}'")
        
        try:
            url = "https://www.googleapis.com/books/v1/volumes"
            params = {
                "q": query,
                "maxResults": 3,
                "fields": "items(id,volumeInfo(title,authors,industryIdentifiers,description,imageLinks))"
            }
            
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, params=params)
                
                print(f"   Status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get("items", [])
                    print(f"   Results found: {len(items)}")
                    
                    if items:
                        for i, item in enumerate(items[:2]):
                            volume_info = item.get("volumeInfo", {})
                            print(f"   Result {i+1}:")
                            print(f"     Title: {volume_info.get('title', 'N/A')}")
                            print(f"     Authors: {volume_info.get('authors', [])}")
                            print(f"     Has Description: {'Yes' if volume_info.get('description') else 'No'}")
                            print(f"     Has Image: {'Yes' if volume_info.get('imageLinks') else 'No'}")
                else:
                    error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                    print(f"   Error: {error_data}")
                
                await asyncio.sleep(2)  # Rate limiting
                
        except Exception as e:
            print(f"   Exception: {str(e)}")

def test_create_simple_book():
    """Create a very simple, famous book for testing"""
    print("\n🔍 CREATING SIMPLE TEST BOOK")
    print("=" * 50)
    
    # Use a very famous book that should definitely be found
    book_data = {
        "title": "Harry Potter and the Sorcerer's Stone",
        "author": "J.K. Rowling",
        "barcode": "TEST_HP_001"
    }
    
    try:
        response = requests.post(f"{API_URL}/books", json=book_data)
        
        if response.status_code == 200:
            data = response.json()
            book_id = data.get('id')
            print(f"✅ Created book: {book_id}")
            print(f"   Title: {data.get('title')}")
            print(f"   Author: {data.get('author')}")
            print(f"   Search Status: {data.get('search_status')}")
            return book_id
        else:
            print(f"❌ Failed to create book: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Exception creating book: {str(e)}")
        return None

def test_enhance_book(book_id):
    """Test enhancing the created book"""
    print(f"\n🔍 TESTING BOOK ENHANCEMENT")
    print("=" * 50)
    
    try:
        # Get book before enhancement
        get_response = requests.get(f"{API_URL}/books", params={"search": "Harry Potter"})
        if get_response.status_code == 200:
            books = get_response.json()
            original_book = next((b for b in books if b.get('id') == book_id), None)
            
            if original_book:
                print("📖 Book BEFORE enhancement:")
                print(f"   Title: {original_book.get('title')}")
                print(f"   Author: {original_book.get('author')}")
                print(f"   Search Status: {original_book.get('search_status')}")
                print(f"   ISBN: {original_book.get('isbn', 'Not found')}")
                print(f"   Description: {'Found' if original_book.get('description') else 'Not found'}")
                print(f"   Image URL: {'Found' if original_book.get('image_url') else 'Not found'}")
                print(f"   Genre: {original_book.get('genre', 'Not found')}")
        
        # Try enhancement
        print(f"\n🚀 Attempting enhancement...")
        enhance_response = requests.post(f"{API_URL}/books/{book_id}/enhance")
        
        print(f"Enhancement Response Status: {enhance_response.status_code}")
        
        if enhance_response.status_code == 200:
            data = enhance_response.json()
            print(f"   Success: {data.get('success')}")
            print(f"   Message: {data.get('message')}")
            print(f"   Enhanced Fields: {data.get('enhanced_fields', [])}")
        else:
            print(f"   Error Response: {enhance_response.text}")
        
        # Get book after enhancement
        print(f"\n📖 Book AFTER enhancement:")
        get_response = requests.get(f"{API_URL}/books", params={"search": "Harry Potter"})
        if get_response.status_code == 200:
            books = get_response.json()
            enhanced_book = next((b for b in books if b.get('id') == book_id), None)
            
            if enhanced_book:
                print(f"   Title: {enhanced_book.get('title')}")
                print(f"   Author: {enhanced_book.get('author')}")
                print(f"   Search Status: {enhanced_book.get('search_status')}")
                print(f"   ISBN: {enhanced_book.get('isbn', 'Not found')}")
                print(f"   Description: {'Found' if enhanced_book.get('description') else 'Not found'}")
                print(f"   Image URL: {'Found' if enhanced_book.get('image_url') else 'Not found'}")
                print(f"   Genre: {enhanced_book.get('genre', 'Not found')}")
                print(f"   AR Level: {enhanced_book.get('ar_level', 'Not found')}")
                print(f"   Lexile: {enhanced_book.get('lexile', 'Not found')}")
                print(f"   Page Count: {enhanced_book.get('page_count', 'Not found')}")
                print(f"   Categories: {enhanced_book.get('categories', [])}")
                
                return enhanced_book
        
    except Exception as e:
        print(f"❌ Exception during enhancement: {str(e)}")
    
    return None

def cleanup_test_book(book_id):
    """Clean up the test book"""
    if book_id:
        try:
            response = requests.delete(f"{API_URL}/books/{book_id}")
            if response.status_code == 200:
                print(f"\n🗑️  Cleaned up test book: {book_id}")
        except:
            pass

async def main():
    print("🔍 GOOGLE BOOKS API DEBUGGING TEST")
    print("=" * 60)
    
    # Test 1: Direct Google Books API
    await test_google_books_direct()
    
    # Test 2: Create and enhance a simple book
    book_id = test_create_simple_book()
    
    if book_id:
        enhanced_book = test_enhance_book(book_id)
        cleanup_test_book(book_id)
    
    print("\n" + "=" * 60)
    print("🔍 DEBUGGING SUMMARY")
    print("=" * 60)
    print("Key findings will be shown above.")
    print("Check for API rate limits, geographic restrictions, or search query issues.")

if __name__ == "__main__":
    asyncio.run(main())