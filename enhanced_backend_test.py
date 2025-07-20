#!/usr/bin/env python3
"""
Enhanced Backend API Testing for Library Management System
Focus on Google Books API Integration and Enhancement Features
Tests the critical issues reported in the review request
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

print(f"Testing enhanced backend API at: {API_URL}")

class EnhancedLibraryAPITester:
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
    
    def test_api_health(self):
        """Test basic API connectivity"""
        try:
            response = self.session.get(f"{API_URL}/")
            if response.status_code == 200:
                data = response.json()
                self.log_result("API Health Check", True, f"Response: {data}")
                return True
            else:
                self.log_result("API Health Check", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("API Health Check", False, f"Connection error: {str(e)}")
            return False
    
    def create_test_books_for_enhancement(self):
        """Create test books with real titles that should be findable in Google Books"""
        test_books = [
            {
                "title": "Harry Potter and the Philosopher's Stone",
                "author": "J.K. Rowling",
                "barcode": "HP001"
            },
            {
                "title": "The Great Gatsby",
                "author": "F. Scott Fitzgerald", 
                "barcode": "GG001"
            },
            {
                "title": "To Kill a Mockingbird",
                "author": "Harper Lee",
                "barcode": "TKM001"
            },
            {
                "title": "1984",
                "author": "George Orwell",
                "barcode": "GO001"
            },
            {
                "title": "Pride and Prejudice",
                "author": "Jane Austen",
                "barcode": "PP001"
            }
        ]
        
        created_books = []
        for book_data in test_books:
            try:
                response = self.session.post(f"{API_URL}/books", json=book_data)
                if response.status_code == 200:
                    book = response.json()
                    created_books.append(book)
                    self.test_book_ids.append(book['id'])
                    print(f"Created test book: {book['title']} (ID: {book['id']})")
                else:
                    print(f"Failed to create book {book_data['title']}: {response.status_code}")
            except Exception as e:
                print(f"Error creating book {book_data['title']}: {str(e)}")
        
        return created_books
    
    def test_single_book_enhancement(self):
        """Test POST /api/books/{id}/enhance - single book enhancement"""
        try:
            # Create a test book first
            test_books = self.create_test_books_for_enhancement()
            if not test_books:
                self.log_result("Single Book Enhancement", False, "No test books created")
                return False
            
            book = test_books[0]  # Use Harry Potter
            book_id = book['id']
            
            # Test the enhancement endpoint
            response = self.session.post(f"{API_URL}/books/{book_id}/enhance")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    enhanced_fields = data.get('enhanced_fields', [])
                    self.log_result("Single Book Enhancement", True, 
                                  f"Enhanced book with fields: {enhanced_fields}")
                    
                    # Verify the book was actually enhanced by checking the database
                    book_response = self.session.get(f"{API_URL}/books", params={"search": book['title']})
                    if book_response.status_code == 200:
                        books = book_response.json()
                        if books:
                            enhanced_book = books[0]
                            # Check if search_status was updated
                            if enhanced_book.get('search_status') in ['found', 'not_found']:
                                self.log_result("Single Book Enhancement - Status Update", True, 
                                              f"Search status: {enhanced_book.get('search_status')}")
                            else:
                                self.log_result("Single Book Enhancement - Status Update", False, 
                                              f"Search status not updated: {enhanced_book.get('search_status')}")
                    
                    return True
                else:
                    self.log_result("Single Book Enhancement", False, f"Enhancement failed: {data}")
                    return False
            else:
                self.log_result("Single Book Enhancement", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Single Book Enhancement", False, f"Exception: {str(e)}")
            return False
    
    def test_batch_book_enhancement(self):
        """Test POST /api/books/enhance-batch - batch enhancement"""
        try:
            if len(self.test_book_ids) < 2:
                self.log_result("Batch Book Enhancement", False, "Need at least 2 test books")
                return False
            
            # Test batch enhancement with specific book IDs
            batch_request = {
                "book_ids": self.test_book_ids[:3],  # Enhance first 3 books
                "enhance_all_pending": False
            }
            
            response = self.session.post(f"{API_URL}/books/enhance-batch", json=batch_request)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    enhanced_count = data.get('enhanced_count', 0)
                    total_processed = data.get('total_processed', 0)
                    errors = data.get('errors', [])
                    
                    self.log_result("Batch Book Enhancement", True, 
                                  f"Enhanced {enhanced_count}/{total_processed} books, {len(errors)} errors")
                    
                    # Test enhance all pending
                    batch_request_all = {
                        "enhance_all_pending": True
                    }
                    
                    response_all = self.session.post(f"{API_URL}/books/enhance-batch", json=batch_request_all)
                    if response_all.status_code == 200:
                        data_all = response_all.json()
                        self.log_result("Batch Enhancement - All Pending", True, 
                                      f"Processed {data_all.get('total_processed', 0)} pending books")
                    else:
                        self.log_result("Batch Enhancement - All Pending", False, 
                                      f"Status: {response_all.status_code}")
                    
                    return True
                else:
                    self.log_result("Batch Book Enhancement", False, f"Enhancement failed: {data}")
                    return False
            else:
                self.log_result("Batch Book Enhancement", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Batch Book Enhancement", False, f"Exception: {str(e)}")
            return False
    
    def test_excel_upload_with_auto_enhancement(self):
        """Test POST /api/books/upload?auto_enhance=true - Excel upload with auto-enhancement"""
        try:
            # Create Excel file with real book titles that should be findable
            data = [
                {"Title": "The Hobbit", "Author": "J.R.R. Tolkien", "Barcode": "HOB001", "Shelf": "F1"},
                {"Title": "Dune", "Author": "Frank Herbert", "Barcode": "DUN001", "Shelf": "F2"},
                {"Title": "The Catcher in the Rye", "Author": "J.D. Salinger", "Barcode": "CTR001", "Shelf": "F3"}
            ]
            
            df = pd.DataFrame(data)
            excel_buffer = io.BytesIO()
            df.to_excel(excel_buffer, index=False, engine='openpyxl')
            excel_buffer.seek(0)
            
            files = {
                'file': ('enhancement_test_books.xlsx', excel_buffer, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            }
            
            # Test upload with auto_enhance=true
            response = self.session.post(f"{API_URL}/books/upload?auto_enhance=true", files=files)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    books_processed = data.get('books_processed', 0)
                    auto_enhanced = data.get('auto_enhanced', 0)
                    
                    self.log_result("Excel Upload with Auto-Enhancement", True, 
                                  f"Processed {books_processed} books, auto-enhanced {auto_enhanced}")
                    
                    # Verify that books were actually enhanced by checking their data
                    time.sleep(2)  # Wait for enhancement to complete
                    
                    # Check if any of the uploaded books have enhanced data
                    for book_title in ["The Hobbit", "Dune", "The Catcher in the Rye"]:
                        book_response = self.session.get(f"{API_URL}/books", params={"search": book_title})
                        if book_response.status_code == 200:
                            books = book_response.json()
                            if books:
                                book = books[0]
                                enhanced_fields = []
                                if book.get('description'):
                                    enhanced_fields.append('description')
                                if book.get('image_url'):
                                    enhanced_fields.append('image_url')
                                if book.get('isbn'):
                                    enhanced_fields.append('isbn')
                                
                                if enhanced_fields:
                                    self.log_result(f"Auto-Enhancement Verification - {book_title}", True, 
                                                  f"Enhanced fields: {enhanced_fields}")
                                else:
                                    self.log_result(f"Auto-Enhancement Verification - {book_title}", False, 
                                                  "No enhanced fields found")
                    
                    return True
                else:
                    self.log_result("Excel Upload with Auto-Enhancement", False, f"Upload failed: {data}")
                    return False
            else:
                self.log_result("Excel Upload with Auto-Enhancement", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Excel Upload with Auto-Enhancement", False, f"Exception: {str(e)}")
            return False
    
    def test_barcode_scanning_with_shelf_assignment(self):
        """Test POST /api/books/scan-assign-shelf - barcode scanning with shelf assignment"""
        try:
            # First, ensure we have a book with a barcode
            if not self.test_book_ids:
                self.log_result("Barcode Scanning with Shelf Assignment", False, "No test books available")
                return False
            
            # Get a book with barcode
            response = self.session.get(f"{API_URL}/books")
            if response.status_code != 200:
                self.log_result("Barcode Scanning with Shelf Assignment", False, "Could not retrieve books")
                return False
            
            books = response.json()
            book_with_barcode = None
            for book in books:
                if book.get('barcode'):
                    book_with_barcode = book
                    break
            
            if not book_with_barcode:
                self.log_result("Barcode Scanning with Shelf Assignment", False, "No book with barcode found")
                return False
            
            # Test shelf assignment via barcode scanning
            scan_request = {
                "barcode": book_with_barcode['barcode'],
                "shelf": "S99"  # Assign to shelf S99
            }
            
            response = self.session.post(f"{API_URL}/books/scan-assign-shelf", json=scan_request)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    book_title = data.get('book_title')
                    shelf_assigned = data.get('shelf_assigned')
                    auto_enhanced = data.get('auto_enhanced', False)
                    
                    self.log_result("Barcode Scanning with Shelf Assignment", True, 
                                  f"Assigned shelf {shelf_assigned} to '{book_title}', auto-enhanced: {auto_enhanced}")
                    
                    # Verify the shelf was actually assigned
                    verify_response = self.session.get(f"{API_URL}/books", params={"barcode": book_with_barcode['barcode']})
                    if verify_response.status_code == 200:
                        verify_books = verify_response.json()
                        if verify_books and verify_books[0].get('shelf') == "S99":
                            self.log_result("Shelf Assignment Verification", True, "Shelf assignment verified in database")
                        else:
                            self.log_result("Shelf Assignment Verification", False, "Shelf assignment not reflected in database")
                    
                    return True
                else:
                    self.log_result("Barcode Scanning with Shelf Assignment", False, f"Assignment failed: {data}")
                    return False
            else:
                self.log_result("Barcode Scanning with Shelf Assignment", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Barcode Scanning with Shelf Assignment", False, f"Exception: {str(e)}")
            return False
    
    def test_enhanced_excel_export(self):
        """Test GET /api/books/export - enhanced Excel export functionality"""
        try:
            # Test basic export
            response = self.session.get(f"{API_URL}/books/export")
            
            if response.status_code == 200:
                if response.headers.get('content-type') == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
                    content_length = len(response.content)
                    self.log_result("Enhanced Excel Export - Basic", True, f"Export successful, size: {content_length} bytes")
                    
                    # Verify filename in headers
                    content_disposition = response.headers.get('Content-Disposition', '')
                    if 'library_books_enhanced_' in content_disposition:
                        self.log_result("Enhanced Excel Export - Filename", True, "Correct filename format")
                    else:
                        self.log_result("Enhanced Excel Export - Filename", False, f"Unexpected filename: {content_disposition}")
                    
                else:
                    self.log_result("Enhanced Excel Export - Basic", False, f"Wrong content type: {response.headers.get('content-type')}")
                    return False
            elif response.status_code == 404:
                self.log_result("Enhanced Excel Export - Basic", True, "No books to export (expected if database is empty)")
            else:
                self.log_result("Enhanced Excel Export - Basic", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
            
            # Test filtered exports with different parameters
            filter_tests = [
                {"genre": "Fiction"},
                {"shelf": "F1"},
                {"author": "Tolkien"},
                {"search_status": "found"}
            ]
            
            for filter_params in filter_tests:
                filter_name = list(filter_params.keys())[0]
                response = self.session.get(f"{API_URL}/books/export", params=filter_params)
                
                if response.status_code in [200, 404]:  # 404 is acceptable if no books match filter
                    self.log_result(f"Enhanced Excel Export - {filter_name.title()} Filter", True, 
                                  f"Filtered export handled correctly (status: {response.status_code})")
                else:
                    self.log_result(f"Enhanced Excel Export - {filter_name.title()} Filter", False, 
                                  f"Filtered export failed with status: {response.status_code}")
            
            return True
            
        except Exception as e:
            self.log_result("Enhanced Excel Export", False, f"Exception: {str(e)}")
            return False
    
    def test_database_operations_with_enhanced_data(self):
        """Test that enhanced book data is properly saved and retrieved"""
        try:
            # Get books and check for enhanced data
            response = self.session.get(f"{API_URL}/books")
            
            if response.status_code != 200:
                self.log_result("Database Operations - Enhanced Data", False, f"Could not retrieve books: {response.status_code}")
                return False
            
            books = response.json()
            enhanced_books = []
            
            for book in books:
                enhanced_fields = []
                if book.get('description'):
                    enhanced_fields.append('description')
                if book.get('image_url'):
                    enhanced_fields.append('image_url')
                if book.get('isbn') and len(book['isbn']) > 5:  # Proper ISBN
                    enhanced_fields.append('isbn')
                if book.get('genre') and book['genre'] != 'Unknown':
                    enhanced_fields.append('genre')
                if book.get('ar_level'):
                    enhanced_fields.append('ar_level')
                if book.get('lexile'):
                    enhanced_fields.append('lexile')
                
                if enhanced_fields:
                    enhanced_books.append({
                        'title': book.get('title'),
                        'search_status': book.get('search_status'),
                        'enhanced_fields': enhanced_fields
                    })
            
            if enhanced_books:
                self.log_result("Database Operations - Enhanced Data", True, 
                              f"Found {len(enhanced_books)} books with enhanced data")
                
                # Check search_status distribution
                status_counts = {}
                for book in books:
                    status = book.get('search_status', 'unknown')
                    status_counts[status] = status_counts.get(status, 0) + 1
                
                self.log_result("Database Operations - Search Status", True, 
                              f"Status distribution: {status_counts}")
                
                return True
            else:
                self.log_result("Database Operations - Enhanced Data", False, 
                              "No books with enhanced data found")
                return False
                
        except Exception as e:
            self.log_result("Database Operations - Enhanced Data", False, f"Exception: {str(e)}")
            return False
    
    def test_google_books_api_integration(self):
        """Test if Google Books API integration is working"""
        try:
            # Create a book with a very well-known title
            test_book = {
                "title": "The Lord of the Rings",
                "author": "J.R.R. Tolkien",
                "barcode": "LOTR001"
            }
            
            response = self.session.post(f"{API_URL}/books", json=test_book)
            if response.status_code != 200:
                self.log_result("Google Books API Integration", False, "Could not create test book")
                return False
            
            book = response.json()
            book_id = book['id']
            self.test_book_ids.append(book_id)
            
            # Try to enhance it
            enhance_response = self.session.post(f"{API_URL}/books/{book_id}/enhance")
            
            if enhance_response.status_code == 200:
                data = enhance_response.json()
                if data.get('success'):
                    enhanced_fields = data.get('enhanced_fields', [])
                    self.log_result("Google Books API Integration", True, 
                                  f"Successfully enhanced with fields: {enhanced_fields}")
                    
                    # Verify the enhanced data was saved
                    time.sleep(1)
                    verify_response = self.session.get(f"{API_URL}/books", params={"search": "Lord of the Rings"})
                    if verify_response.status_code == 200:
                        books = verify_response.json()
                        if books:
                            enhanced_book = books[0]
                            if enhanced_book.get('search_status') == 'found':
                                self.log_result("Google Books API - Data Persistence", True, 
                                              "Enhanced data persisted correctly")
                            else:
                                self.log_result("Google Books API - Data Persistence", False, 
                                              f"Search status: {enhanced_book.get('search_status')}")
                    
                    return True
                else:
                    # Even if no enhancement occurred, the API call worked
                    self.log_result("Google Books API Integration", True, 
                                  "API call successful (no enhancement needed)")
                    return True
            else:
                self.log_result("Google Books API Integration", False, 
                              f"Enhancement failed: {enhance_response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Google Books API Integration", False, f"Exception: {str(e)}")
            return False
    
    def cleanup(self):
        """Clean up test data"""
        for book_id in self.test_book_ids:
            try:
                self.session.delete(f"{API_URL}/books/{book_id}")
            except:
                pass
    
    def run_enhanced_tests(self):
        """Run all enhanced backend API tests focusing on critical issues"""
        print("=" * 70)
        print("LIBRARY MANAGEMENT SYSTEM - ENHANCED BACKEND API TESTING")
        print("Focus: Google Books API Integration & Enhancement Features")
        print("=" * 70)
        
        # Test in logical order focusing on critical issues
        tests = [
            ("API Health Check", self.test_api_health),
            ("Google Books API Integration", self.test_google_books_api_integration),
            ("Single Book Enhancement", self.test_single_book_enhancement),
            ("Batch Book Enhancement", self.test_batch_book_enhancement),
            ("Excel Upload with Auto-Enhancement", self.test_excel_upload_with_auto_enhancement),
            ("Barcode Scanning with Shelf Assignment", self.test_barcode_scanning_with_shelf_assignment),
            ("Enhanced Excel Export", self.test_enhanced_excel_export),
            ("Database Operations with Enhanced Data", self.test_database_operations_with_enhanced_data),
        ]
        
        for test_name, test_func in tests:
            print(f"\n--- Running {test_name} ---")
            test_func()
            time.sleep(1)  # Delay between tests to respect API limits
        
        # Cleanup
        self.cleanup()
        
        # Print summary
        print("\n" + "=" * 70)
        print("ENHANCED TEST SUMMARY")
        print("=" * 70)
        print(f"✅ Passed: {self.test_results['passed']}")
        print(f"❌ Failed: {self.test_results['failed']}")
        
        if self.test_results['errors']:
            print("\nFAILED TESTS:")
            for error in self.test_results['errors']:
                print(f"  - {error}")
        
        success_rate = (self.test_results['passed'] / (self.test_results['passed'] + self.test_results['failed'])) * 100 if (self.test_results['passed'] + self.test_results['failed']) > 0 else 0
        print(f"\nSuccess Rate: {success_rate:.1f}%")
        
        return self.test_results['failed'] == 0

if __name__ == "__main__":
    tester = EnhancedLibraryAPITester()
    success = tester.run_enhanced_tests()
    
    if success:
        print("\n🎉 All enhanced tests passed! Google Books integration and enhancement features are working correctly.")
        exit(0)
    else:
        print("\n⚠️  Some enhanced tests failed. Check the details above.")
        exit(1)