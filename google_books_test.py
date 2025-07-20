#!/usr/bin/env python3
"""
Google Books API Integration Testing with REAL Book Titles
Tests the Google Books API search functionality with famous book titles to identify why it's not finding actual book data.
"""

import requests
import json
import io
import pandas as pd
import os
from pathlib import Path
import time
import uuid
import asyncio
import httpx

# Get backend URL from frontend .env file
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

print(f"Testing Google Books API integration at: {API_URL}")

# Real famous books for testing
REAL_BOOKS = [
    {"title": "Harry Potter and the Philosopher's Stone", "author": "J.K. Rowling"},
    {"title": "The Great Gatsby", "author": "F. Scott Fitzgerald"},
    {"title": "To Kill a Mockingbird", "author": "Harper Lee"},
    {"title": "1984", "author": "George Orwell"},
    {"title": "Pride and Prejudice", "author": "Jane Austen"},
    {"title": "The Catcher in the Rye", "author": "J.D. Salinger"},
    {"title": "Lord of the Rings", "author": "J.R.R. Tolkien"},
    {"title": "The Hobbit", "author": "J.R.R. Tolkien"},
    {"title": "Dune", "author": "Frank Herbert"},
    {"title": "Fahrenheit 451", "author": "Ray Bradbury"}
]

class GoogleBooksAPITester:
    def __init__(self):
        self.session = requests.Session()
        self.test_book_ids = []
        self.test_results = {
            'passed': 0,
            'failed': 0,
            'errors': []
        }
    
    def log_result(self, test_name, success, message=""):
        if success:
            self.test_results['passed'] += 1
            print(f"✅ {test_name}: PASSED {message}")
        else:
            self.test_results['failed'] += 1
            self.test_results['errors'].append(f"{test_name}: {message}")
            print(f"❌ {test_name}: FAILED {message}")
    
    async def test_direct_google_books_api(self):
        """Test direct Google Books API calls to verify connectivity"""
        print("\n=== TESTING DIRECT GOOGLE BOOKS API ===")
        
        try:
            for book in REAL_BOOKS[:3]:  # Test first 3 books
                query = f"{book['title']} {book['author']}"
                url = "https://www.googleapis.com/books/v1/volumes"
                params = {
                    "q": query,
                    "maxResults": 5,
                    "fields": "items(id,volumeInfo(title,authors,industryIdentifiers,categories,description,imageLinks,pageCount,maturityRating,language,publishedDate))"
                }
                
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(url, params=params)
                    
                    if response.status_code == 200:
                        data = response.json()
                        items = data.get("items", [])
                        
                        if items:
                            volume_info = items[0].get("volumeInfo", {})
                            found_title = volume_info.get("title", "")
                            found_authors = volume_info.get("authors", [])
                            
                            self.log_result(
                                f"Direct Google Books API - {book['title']}", 
                                True, 
                                f"Found: '{found_title}' by {found_authors}"
                            )
                            
                            # Print detailed info
                            print(f"    📖 Title: {found_title}")
                            print(f"    👤 Authors: {found_authors}")
                            print(f"    📚 Categories: {volume_info.get('categories', [])}")
                            print(f"    📄 Page Count: {volume_info.get('pageCount', 'N/A')}")
                            print(f"    🖼️  Has Image: {'Yes' if volume_info.get('imageLinks') else 'No'}")
                            print(f"    📝 Has Description: {'Yes' if volume_info.get('description') else 'No'}")
                            
                        else:
                            self.log_result(
                                f"Direct Google Books API - {book['title']}", 
                                False, 
                                "No results found"
                            )
                    else:
                        self.log_result(
                            f"Direct Google Books API - {book['title']}", 
                            False, 
                            f"HTTP {response.status_code}: {response.text}"
                        )
                
                await asyncio.sleep(1)  # Rate limiting
                
        except Exception as e:
            self.log_result("Direct Google Books API", False, f"Exception: {str(e)}")
    
    def test_create_real_books_manually(self):
        """Create real books manually to test enhancement"""
        print("\n=== CREATING REAL BOOKS FOR TESTING ===")
        
        created_books = []
        
        for i, book in enumerate(REAL_BOOKS[:5]):  # Create first 5 books
            try:
                book_data = {
                    "title": book["title"],
                    "author": book["author"],
                    "barcode": f"REAL{i+1:03d}",
                    "shelf": f"TEST{i+1}"
                }
                
                response = self.session.post(f"{API_URL}/books", json=book_data)
                
                if response.status_code == 200:
                    data = response.json()
                    book_id = data.get('id')
                    if book_id:
                        self.test_book_ids.append(book_id)
                        created_books.append({"id": book_id, "title": book["title"], "author": book["author"]})
                        self.log_result(
                            f"Create Real Book - {book['title']}", 
                            True, 
                            f"Created with ID: {book_id}"
                        )
                    else:
                        self.log_result(f"Create Real Book - {book['title']}", False, "No ID returned")
                else:
                    self.log_result(
                        f"Create Real Book - {book['title']}", 
                        False, 
                        f"HTTP {response.status_code}: {response.text}"
                    )
                    
            except Exception as e:
                self.log_result(f"Create Real Book - {book['title']}", False, f"Exception: {str(e)}")
        
        return created_books
    
    def test_single_book_enhancement(self, created_books):
        """Test single book enhancement with real books"""
        print("\n=== TESTING SINGLE BOOK ENHANCEMENT ===")
        
        for book in created_books[:3]:  # Test first 3 created books
            try:
                book_id = book["id"]
                
                # Test enhancement endpoint
                response = self.session.post(f"{API_URL}/books/{book_id}/enhance")
                
                if response.status_code == 200:
                    data = response.json()
                    success = data.get('success', False)
                    enhanced_fields = data.get('enhanced_fields', [])
                    message = data.get('message', '')
                    
                    self.log_result(
                        f"Single Enhancement - {book['title']}", 
                        True, 
                        f"Success: {success}, Enhanced: {enhanced_fields}, Message: {message}"
                    )
                    
                    # Get the enhanced book to see what was found
                    get_response = self.session.get(f"{API_URL}/books", params={"search": book["title"]})
                    if get_response.status_code == 200:
                        books = get_response.json()
                        enhanced_book = next((b for b in books if b.get('id') == book_id), None)
                        
                        if enhanced_book:
                            print(f"    📖 Enhanced Book Details:")
                            print(f"        Title: {enhanced_book.get('title')}")
                            print(f"        Author: {enhanced_book.get('author')}")
                            print(f"        ISBN: {enhanced_book.get('isbn', 'Not found')}")
                            print(f"        Genre: {enhanced_book.get('genre', 'Not found')}")
                            print(f"        AR Level: {enhanced_book.get('ar_level', 'Not found')}")
                            print(f"        Lexile: {enhanced_book.get('lexile', 'Not found')}")
                            print(f"        Description: {'Found' if enhanced_book.get('description') else 'Not found'}")
                            print(f"        Image URL: {'Found' if enhanced_book.get('image_url') else 'Not found'}")
                            print(f"        Search Status: {enhanced_book.get('search_status', 'Unknown')}")
                            print(f"        Page Count: {enhanced_book.get('page_count', 'Not found')}")
                            print(f"        Categories: {enhanced_book.get('categories', [])}")
                
                else:
                    self.log_result(
                        f"Single Enhancement - {book['title']}", 
                        False, 
                        f"HTTP {response.status_code}: {response.text}"
                    )
                    
                time.sleep(2)  # Rate limiting
                
            except Exception as e:
                self.log_result(f"Single Enhancement - {book['title']}", False, f"Exception: {str(e)}")
    
    def test_batch_enhancement(self, created_books):
        """Test batch enhancement functionality"""
        print("\n=== TESTING BATCH ENHANCEMENT ===")
        
        try:
            # Test with specific book IDs
            book_ids = [book["id"] for book in created_books[3:]]  # Use remaining books
            
            if book_ids:
                request_data = {
                    "book_ids": book_ids,
                    "enhance_all_pending": False
                }
                
                response = self.session.post(f"{API_URL}/books/enhance-batch", json=request_data)
                
                if response.status_code == 200:
                    data = response.json()
                    enhanced_count = data.get('enhanced_count', 0)
                    total_processed = data.get('total_processed', 0)
                    errors = data.get('errors', [])
                    
                    self.log_result(
                        "Batch Enhancement (Specific IDs)", 
                        True, 
                        f"Enhanced {enhanced_count}/{total_processed} books, {len(errors)} errors"
                    )
                    
                    if errors:
                        print("    ⚠️  Errors encountered:")
                        for error in errors:
                            print(f"        - {error.get('title', 'Unknown')}: {error.get('error', 'Unknown error')}")
                
                else:
                    self.log_result(
                        "Batch Enhancement (Specific IDs)", 
                        False, 
                        f"HTTP {response.status_code}: {response.text}"
                    )
            
            # Test enhance all pending
            request_data = {
                "enhance_all_pending": True
            }
            
            response = self.session.post(f"{API_URL}/books/enhance-batch", json=request_data)
            
            if response.status_code == 200:
                data = response.json()
                enhanced_count = data.get('enhanced_count', 0)
                total_processed = data.get('total_processed', 0)
                
                self.log_result(
                    "Batch Enhancement (All Pending)", 
                    True, 
                    f"Enhanced {enhanced_count}/{total_processed} pending books"
                )
            else:
                self.log_result(
                    "Batch Enhancement (All Pending)", 
                    False, 
                    f"HTTP {response.status_code}: {response.text}"
                )
                
        except Exception as e:
            self.log_result("Batch Enhancement", False, f"Exception: {str(e)}")
    
    def test_excel_upload_with_auto_enhance(self):
        """Test Excel upload with auto_enhance=true using real book titles"""
        print("\n=== TESTING EXCEL UPLOAD WITH AUTO-ENHANCEMENT ===")
        
        try:
            # Create Excel with real book titles (minimal data - just barcode and title)
            excel_data = [
                {"Title": "The Lord of the Rings", "Author": "J.R.R. Tolkien", "Barcode": "AUTO001"},
                {"Title": "Animal Farm", "Author": "George Orwell", "Barcode": "AUTO002"},
                {"Title": "Brave New World", "Author": "Aldous Huxley", "Barcode": "AUTO003"},
            ]
            
            df = pd.DataFrame(excel_data)
            excel_buffer = io.BytesIO()
            df.to_excel(excel_buffer, index=False, engine='openpyxl')
            excel_buffer.seek(0)
            
            files = {
                'file': ('real_books_auto_enhance.xlsx', excel_buffer, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            }
            
            # Upload with auto_enhance=true
            response = self.session.post(f"{API_URL}/books/upload?auto_enhance=true", files=files)
            
            if response.status_code == 200:
                data = response.json()
                books_processed = data.get('books_processed', 0)
                auto_enhanced = data.get('auto_enhanced', 0)
                errors = data.get('errors', [])
                
                self.log_result(
                    "Excel Upload with Auto-Enhancement", 
                    True, 
                    f"Processed {books_processed} books, auto-enhanced {auto_enhanced}, {len(errors)} errors"
                )
                
                # Check if books were actually enhanced by retrieving them
                time.sleep(3)  # Wait for enhancement to complete
                
                for book_data in excel_data:
                    search_response = self.session.get(f"{API_URL}/books", params={"search": book_data["Title"]})
                    if search_response.status_code == 200:
                        books = search_response.json()
                        found_book = next((b for b in books if book_data["Title"].lower() in b.get('title', '').lower()), None)
                        
                        if found_book:
                            print(f"    📖 {book_data['Title']}:")
                            print(f"        Search Status: {found_book.get('search_status', 'Unknown')}")
                            print(f"        ISBN: {'Found' if found_book.get('isbn') else 'Not found'}")
                            print(f"        Genre: {found_book.get('genre', 'Not found')}")
                            print(f"        Description: {'Found' if found_book.get('description') else 'Not found'}")
                            print(f"        Image: {'Found' if found_book.get('image_url') else 'Not found'}")
                            
                            # Store ID for cleanup
                            if found_book.get('id'):
                                self.test_book_ids.append(found_book['id'])
            
            else:
                self.log_result(
                    "Excel Upload with Auto-Enhancement", 
                    False, 
                    f"HTTP {response.status_code}: {response.text}"
                )
                
        except Exception as e:
            self.log_result("Excel Upload with Auto-Enhancement", False, f"Exception: {str(e)}")
    
    def test_barcode_scanning_with_shelf_assignment(self):
        """Test barcode scanning with shelf assignment"""
        print("\n=== TESTING BARCODE SCANNING WITH SHELF ASSIGNMENT ===")
        
        try:
            # First create a book with a barcode
            book_data = {
                "title": "The Chronicles of Narnia",
                "author": "C.S. Lewis",
                "barcode": "SCAN001"
            }
            
            create_response = self.session.post(f"{API_URL}/books", json=book_data)
            
            if create_response.status_code == 200:
                created_book = create_response.json()
                book_id = created_book.get('id')
                if book_id:
                    self.test_book_ids.append(book_id)
                
                # Now test barcode scanning with shelf assignment
                scan_data = {
                    "barcode": "SCAN001",
                    "shelf": "SCAN-SHELF-1"
                }
                
                response = self.session.post(f"{API_URL}/books/scan-assign-shelf", json=scan_data)
                
                if response.status_code == 200:
                    data = response.json()
                    success = data.get('success', False)
                    book_title = data.get('book_title', '')
                    shelf_assigned = data.get('shelf_assigned', '')
                    auto_enhanced = data.get('auto_enhanced', False)
                    
                    self.log_result(
                        "Barcode Scanning with Shelf Assignment", 
                        success, 
                        f"Book: '{book_title}', Shelf: {shelf_assigned}, Auto-enhanced: {auto_enhanced}"
                    )
                    
                    # Verify the book was updated
                    get_response = self.session.get(f"{API_URL}/books", params={"barcode": "SCAN001"})
                    if get_response.status_code == 200:
                        books = get_response.json()
                        if books:
                            updated_book = books[0]
                            print(f"    📖 Updated Book:")
                            print(f"        Title: {updated_book.get('title')}")
                            print(f"        Shelf: {updated_book.get('shelf')}")
                            print(f"        Search Status: {updated_book.get('search_status')}")
                            print(f"        Enhanced: {'Yes' if updated_book.get('description') or updated_book.get('isbn') else 'No'}")
                
                else:
                    self.log_result(
                        "Barcode Scanning with Shelf Assignment", 
                        False, 
                        f"HTTP {response.status_code}: {response.text}"
                    )
            else:
                self.log_result(
                    "Barcode Scanning with Shelf Assignment", 
                    False, 
                    f"Failed to create test book: HTTP {create_response.status_code}"
                )
                
        except Exception as e:
            self.log_result("Barcode Scanning with Shelf Assignment", False, f"Exception: {str(e)}")
    
    def test_enhanced_database_operations(self):
        """Test enhanced database operations and data integrity"""
        print("\n=== TESTING ENHANCED DATABASE OPERATIONS ===")
        
        try:
            # Get all books and analyze enhancement status
            response = self.session.get(f"{API_URL}/books", params={"show_all": True})
            
            if response.status_code == 200:
                books = response.json()
                total_books = len(books)
                
                if total_books > 0:
                    # Analyze enhancement status
                    status_counts = {}
                    enhanced_books = 0
                    
                    for book in books:
                        status = book.get('search_status', 'unknown')
                        status_counts[status] = status_counts.get(status, 0) + 1
                        
                        # Count books with enhanced data
                        if (book.get('description') or book.get('isbn') or 
                            book.get('image_url') or book.get('ar_level') or book.get('lexile')):
                            enhanced_books += 1
                    
                    enhancement_rate = (enhanced_books / total_books) * 100 if total_books > 0 else 0
                    
                    self.log_result(
                        "Enhanced Database Operations", 
                        True, 
                        f"Total: {total_books}, Enhanced: {enhanced_books} ({enhancement_rate:.1f}%)"
                    )
                    
                    print(f"    📊 Search Status Distribution:")
                    for status, count in status_counts.items():
                        print(f"        {status}: {count}")
                    
                    print(f"    📈 Enhancement Statistics:")
                    print(f"        Books with ISBN: {sum(1 for b in books if b.get('isbn'))}")
                    print(f"        Books with Description: {sum(1 for b in books if b.get('description'))}")
                    print(f"        Books with Image URL: {sum(1 for b in books if b.get('image_url'))}")
                    print(f"        Books with AR Level: {sum(1 for b in books if b.get('ar_level'))}")
                    print(f"        Books with Lexile: {sum(1 for b in books if b.get('lexile'))}")
                    
                else:
                    self.log_result("Enhanced Database Operations", True, "No books in database")
            
            else:
                self.log_result(
                    "Enhanced Database Operations", 
                    False, 
                    f"HTTP {response.status_code}: {response.text}"
                )
                
        except Exception as e:
            self.log_result("Enhanced Database Operations", False, f"Exception: {str(e)}")
    
    def cleanup(self):
        """Clean up test data"""
        print("\n=== CLEANING UP TEST DATA ===")
        
        for book_id in self.test_book_ids:
            try:
                response = self.session.delete(f"{API_URL}/books/{book_id}")
                if response.status_code == 200:
                    print(f"    🗑️  Deleted book {book_id}")
            except:
                pass
    
    async def run_all_tests(self):
        """Run all Google Books API integration tests"""
        print("=" * 80)
        print("GOOGLE BOOKS API INTEGRATION TESTING WITH REAL BOOK TITLES")
        print("=" * 80)
        
        # Test direct Google Books API first
        await self.test_direct_google_books_api()
        
        # Create real books for testing
        created_books = self.test_create_real_books_manually()
        
        # Test single book enhancement
        if created_books:
            self.test_single_book_enhancement(created_books)
        
        # Test batch enhancement
        if created_books:
            self.test_batch_enhancement(created_books)
        
        # Test Excel upload with auto-enhancement
        self.test_excel_upload_with_auto_enhance()
        
        # Test barcode scanning with shelf assignment
        self.test_barcode_scanning_with_shelf_assignment()
        
        # Test enhanced database operations
        self.test_enhanced_database_operations()
        
        # Cleanup
        self.cleanup()
        
        # Print summary
        print("\n" + "=" * 80)
        print("GOOGLE BOOKS API INTEGRATION TEST SUMMARY")
        print("=" * 80)
        print(f"✅ Passed: {self.test_results['passed']}")
        print(f"❌ Failed: {self.test_results['failed']}")
        
        if self.test_results['errors']:
            print("\nFAILED TESTS:")
            for error in self.test_results['errors']:
                print(f"  - {error}")
        
        success_rate = (self.test_results['passed'] / (self.test_results['passed'] + self.test_results['failed'])) * 100 if (self.test_results['passed'] + self.test_results['failed']) > 0 else 0
        print(f"\nSuccess Rate: {success_rate:.1f}%")
        
        return self.test_results['failed'] == 0

async def main():
    tester = GoogleBooksAPITester()
    success = await tester.run_all_tests()
    
    if success:
        print("\n🎉 All Google Books API integration tests passed!")
        return 0
    else:
        print("\n⚠️  Some Google Books API integration tests failed. Check the details above.")
        return 1

if __name__ == "__main__":
    exit(asyncio.run(main()))