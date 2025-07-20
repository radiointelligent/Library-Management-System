#!/usr/bin/env python3
"""
Comprehensive Backend API Testing for Library Management System
Tests all endpoints including Excel upload, CRUD operations, search/filter, and export
"""

import requests
import json
import io
import pandas as pd
import os
from pathlib import Path
import time
import uuid

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

print(f"Testing backend API at: {API_URL}")

class LibraryAPITester:
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
    
    def create_test_excel_file(self, filename="test_books.xlsx", include_errors=False):
        """Create a test Excel file with book data"""
        if include_errors:
            # Include some problematic data for error testing
            data = [
                {"Title": "The Great Gatsby", "Author": "F. Scott Fitzgerald", "ISBN": "978-0-7432-7356-5", "Genre": "Fiction", "Shelf": "A1"},
                {"Title": "", "Author": "Harper Lee", "ISBN": "978-0-06-112008-4", "Genre": "Fiction", "Shelf": "A2"},  # Missing title
                {"Title": "1984", "Author": "", "ISBN": "978-0-452-28423-4", "Genre": "Dystopian", "Shelf": "B1"},  # Missing author
                {"Title": "Pride and Prejudice", "Author": "Jane Austen", "ISBN": "978-0-14-143951-8", "Genre": "Romance", "Shelf": "C1"},
                {"Title": "The Great Gatsby", "Author": "F. Scott Fitzgerald", "ISBN": "978-0-7432-7356-5", "Genre": "Fiction", "Shelf": "A1"},  # Duplicate
            ]
        else:
            # Clean test data
            data = [
                {"Title": "The Catcher in the Rye", "Author": "J.D. Salinger", "ISBN": "978-0-316-76948-0", "Genre": "Fiction", "Shelf": "A3", "Barcode": "BC001"},
                {"Title": "To Kill a Mockingbird", "Author": "Harper Lee", "ISBN": "978-0-06-112008-4", "Genre": "Fiction", "Shelf": "A4", "Barcode": "BC002"},
                {"Title": "Lord of the Flies", "Author": "William Golding", "ISBN": "978-0-571-05686-2", "Genre": "Fiction", "Shelf": "A5", "Barcode": "BC003"},
                {"Title": "The Hobbit", "Author": "J.R.R. Tolkien", "ISBN": "978-0-547-92822-7", "Genre": "Fantasy", "Shelf": "B2", "Barcode": "BC004"},
                {"Title": "Dune", "Author": "Frank Herbert", "ISBN": "978-0-441-17271-9", "Genre": "Science Fiction", "Shelf": "C2", "Barcode": "BC005"},
            ]
        
        df = pd.DataFrame(data)
        
        # Save to BytesIO for upload testing
        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False, engine='openpyxl')
        excel_buffer.seek(0)
        
        return excel_buffer, df
    
    def test_excel_upload_success(self):
        """Test successful Excel file upload"""
        try:
            excel_buffer, df = self.create_test_excel_file()
            
            files = {
                'file': ('test_books.xlsx', excel_buffer, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            }
            
            response = self.session.post(f"{API_URL}/books/upload", files=files)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('books_processed') > 0:
                    self.log_result("Excel Upload Success", True, f"Processed {data['books_processed']} books")
                    return True
                else:
                    self.log_result("Excel Upload Success", False, f"Upload failed: {data}")
                    return False
            else:
                self.log_result("Excel Upload Success", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Excel Upload Success", False, f"Exception: {str(e)}")
            return False
    
    def test_excel_upload_validation(self):
        """Test Excel upload validation and error handling"""
        try:
            # Test with invalid file format
            invalid_file = io.BytesIO(b"This is not an Excel file")
            files = {'file': ('test.txt', invalid_file, 'text/plain')}
            
            response = self.session.post(f"{API_URL}/books/upload", files=files)
            
            if response.status_code == 400:
                self.log_result("Excel Upload Validation (Invalid Format)", True, "Correctly rejected non-Excel file")
            else:
                self.log_result("Excel Upload Validation (Invalid Format)", False, f"Should reject non-Excel files, got status: {response.status_code}")
            
            # Test with missing required columns
            df_invalid = pd.DataFrame([{"InvalidColumn": "test"}])
            excel_buffer = io.BytesIO()
            df_invalid.to_excel(excel_buffer, index=False, engine='openpyxl')
            excel_buffer.seek(0)
            
            files = {'file': ('invalid_structure.xlsx', excel_buffer, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            response = self.session.post(f"{API_URL}/books/upload", files=files)
            
            if response.status_code == 400:
                self.log_result("Excel Upload Validation (Missing Columns)", True, "Correctly rejected file with missing required columns")
            else:
                self.log_result("Excel Upload Validation (Missing Columns)", False, f"Should reject invalid structure, got status: {response.status_code}")
            
            return True
            
        except Exception as e:
            self.log_result("Excel Upload Validation", False, f"Exception: {str(e)}")
            return False
    
    def test_excel_upload_error_handling(self):
        """Test Excel upload with problematic data"""
        try:
            excel_buffer, df = self.create_test_excel_file(include_errors=True)
            
            files = {
                'file': ('error_test_books.xlsx', excel_buffer, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            }
            
            response = self.session.post(f"{API_URL}/books/upload", files=files)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and len(data.get('errors', [])) > 0:
                    self.log_result("Excel Upload Error Handling", True, f"Processed with {len(data['errors'])} errors and {data.get('duplicates_found', 0)} duplicates")
                    return True
                else:
                    self.log_result("Excel Upload Error Handling", False, f"Expected errors but got: {data}")
                    return False
            else:
                self.log_result("Excel Upload Error Handling", False, f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Excel Upload Error Handling", False, f"Exception: {str(e)}")
            return False
    
    def test_create_book(self):
        """Test individual book creation"""
        try:
            book_data = {
                "title": "Animal Farm",
                "author": "George Orwell",
                "isbn": "978-0-452-28424-1",
                "genre": "Political Satire",
                "shelf": "D1",
                "barcode": "BC006"
            }
            
            response = self.session.post(f"{API_URL}/books", json=book_data)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('id') and data.get('title') == book_data['title']:
                    self.test_book_ids.append(data['id'])
                    self.log_result("Create Book", True, f"Created book with ID: {data['id']}")
                    return True
                else:
                    self.log_result("Create Book", False, f"Invalid response: {data}")
                    return False
            else:
                self.log_result("Create Book", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Create Book", False, f"Exception: {str(e)}")
            return False
    
    def test_get_books(self):
        """Test retrieving books with various parameters"""
        try:
            # Test basic retrieval
            response = self.session.get(f"{API_URL}/books")
            
            if response.status_code == 200:
                books = response.json()
                if isinstance(books, list):
                    self.log_result("Get Books (Basic)", True, f"Retrieved {len(books)} books")
                else:
                    self.log_result("Get Books (Basic)", False, f"Expected list, got: {type(books)}")
                    return False
            else:
                self.log_result("Get Books (Basic)", False, f"Status: {response.status_code}")
                return False
            
            # Test with search parameter
            response = self.session.get(f"{API_URL}/books", params={"search": "Gatsby"})
            if response.status_code == 200:
                books = response.json()
                self.log_result("Get Books (Search)", True, f"Search returned {len(books)} books")
            else:
                self.log_result("Get Books (Search)", False, f"Search failed with status: {response.status_code}")
            
            # Test with genre filter
            response = self.session.get(f"{API_URL}/books", params={"genre": "Fiction"})
            if response.status_code == 200:
                books = response.json()
                self.log_result("Get Books (Genre Filter)", True, f"Genre filter returned {len(books)} books")
            else:
                self.log_result("Get Books (Genre Filter)", False, f"Genre filter failed with status: {response.status_code}")
            
            # Test with pagination
            response = self.session.get(f"{API_URL}/books", params={"limit": 2, "skip": 0})
            if response.status_code == 200:
                books = response.json()
                self.log_result("Get Books (Pagination)", True, f"Pagination returned {len(books)} books")
            else:
                self.log_result("Get Books (Pagination)", False, f"Pagination failed with status: {response.status_code}")
            
            return True
            
        except Exception as e:
            self.log_result("Get Books", False, f"Exception: {str(e)}")
            return False
    
    def test_book_stats(self):
        """Test book statistics endpoint"""
        try:
            response = self.session.get(f"{API_URL}/books/stats")
            
            if response.status_code == 200:
                stats = response.json()
                required_fields = ['total_books', 'total_genres', 'total_shelves', 'total_authors']
                
                if all(field in stats for field in required_fields):
                    self.log_result("Book Stats", True, f"Stats: {stats['total_books']} books, {stats['total_authors']} authors, {stats['total_genres']} genres")
                    return True
                else:
                    self.log_result("Book Stats", False, f"Missing required fields in response: {stats}")
                    return False
            else:
                self.log_result("Book Stats", False, f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Book Stats", False, f"Exception: {str(e)}")
            return False
    
    def test_update_book(self):
        """Test book update functionality"""
        if not self.test_book_ids:
            self.log_result("Update Book", False, "No test book ID available")
            return False
        
        try:
            book_id = self.test_book_ids[0]
            update_data = {
                "shelf": "D2",
                "genre": "Classic Literature"
            }
            
            response = self.session.put(f"{API_URL}/books/{book_id}", json=update_data)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('shelf') == update_data['shelf'] and data.get('genre') == update_data['genre']:
                    self.log_result("Update Book", True, f"Successfully updated book {book_id}")
                    return True
                else:
                    self.log_result("Update Book", False, f"Update not reflected in response: {data}")
                    return False
            else:
                self.log_result("Update Book", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Update Book", False, f"Exception: {str(e)}")
            return False
    
    def test_export_books(self):
        """Test Excel export functionality"""
        try:
            # Test basic export
            response = self.session.get(f"{API_URL}/books/export")
            
            if response.status_code == 200:
                if response.headers.get('content-type') == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
                    self.log_result("Export Books (Basic)", True, f"Export successful, size: {len(response.content)} bytes")
                else:
                    self.log_result("Export Books (Basic)", False, f"Wrong content type: {response.headers.get('content-type')}")
                    return False
            elif response.status_code == 404:
                self.log_result("Export Books (Basic)", True, "No books to export (expected if database is empty)")
            else:
                self.log_result("Export Books (Basic)", False, f"Status: {response.status_code}")
                return False
            
            # Test filtered export
            response = self.session.get(f"{API_URL}/books/export", params={"genre": "Fiction"})
            if response.status_code in [200, 404]:  # 404 is acceptable if no books match filter
                self.log_result("Export Books (Filtered)", True, "Filtered export handled correctly")
            else:
                self.log_result("Export Books (Filtered)", False, f"Filtered export failed with status: {response.status_code}")
            
            return True
            
        except Exception as e:
            self.log_result("Export Books", False, f"Exception: {str(e)}")
            return False
    
    def test_delete_book(self):
        """Test book deletion"""
        if not self.test_book_ids:
            self.log_result("Delete Book", False, "No test book ID available")
            return False
        
        try:
            book_id = self.test_book_ids[0]
            response = self.session.delete(f"{API_URL}/books/{book_id}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('message'):
                    self.log_result("Delete Book", True, f"Successfully deleted book {book_id}")
                    self.test_book_ids.remove(book_id)
                    return True
                else:
                    self.log_result("Delete Book", False, f"Unexpected response: {data}")
                    return False
            else:
                self.log_result("Delete Book", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Delete Book", False, f"Exception: {str(e)}")
            return False
    
    def test_error_cases(self):
        """Test various error scenarios"""
        try:
            # Test getting non-existent book
            fake_id = str(uuid.uuid4())
            response = self.session.put(f"{API_URL}/books/{fake_id}", json={"title": "Test"})
            
            if response.status_code == 404:
                self.log_result("Error Handling (Non-existent Book Update)", True, "Correctly returned 404 for non-existent book")
            else:
                self.log_result("Error Handling (Non-existent Book Update)", False, f"Expected 404, got {response.status_code}")
            
            # Test deleting non-existent book
            response = self.session.delete(f"{API_URL}/books/{fake_id}")
            
            if response.status_code == 404:
                self.log_result("Error Handling (Non-existent Book Delete)", True, "Correctly returned 404 for non-existent book deletion")
            else:
                self.log_result("Error Handling (Non-existent Book Delete)", False, f"Expected 404, got {response.status_code}")
            
            # Test creating book with missing required fields
            response = self.session.post(f"{API_URL}/books", json={"title": ""})
            
            if response.status_code in [400, 422]:  # 422 is Pydantic validation error
                self.log_result("Error Handling (Invalid Book Data)", True, "Correctly rejected invalid book data")
            else:
                self.log_result("Error Handling (Invalid Book Data)", False, f"Expected 400/422, got {response.status_code}")
            
            return True
            
        except Exception as e:
            self.log_result("Error Handling", False, f"Exception: {str(e)}")
            return False
    
    def cleanup(self):
        """Clean up any remaining test data"""
        for book_id in self.test_book_ids:
            try:
                self.session.delete(f"{API_URL}/books/{book_id}")
            except:
                pass
    
    def run_all_tests(self):
        """Run all backend API tests"""
        print("=" * 60)
        print("LIBRARY MANAGEMENT SYSTEM - BACKEND API TESTING")
        print("=" * 60)
        
        # Test in logical order
        tests = [
            ("API Health Check", self.test_api_health),
            ("Excel Upload Success", self.test_excel_upload_success),
            ("Excel Upload Validation", self.test_excel_upload_validation),
            ("Excel Upload Error Handling", self.test_excel_upload_error_handling),
            ("Create Book", self.test_create_book),
            ("Get Books", self.test_get_books),
            ("Book Statistics", self.test_book_stats),
            ("Update Book", self.test_update_book),
            ("Export Books", self.test_export_books),
            ("Delete Book", self.test_delete_book),
            ("Error Handling", self.test_error_cases),
        ]
        
        for test_name, test_func in tests:
            print(f"\n--- Running {test_name} ---")
            test_func()
            time.sleep(0.5)  # Small delay between tests
        
        # Cleanup
        self.cleanup()
        
        # Print summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print(f"✅ Passed: {self.test_results['passed']}")
        print(f"❌ Failed: {self.test_results['failed']}")
        
        if self.test_results['errors']:
            print("\nFAILED TESTS:")
            for error in self.test_results['errors']:
                print(f"  - {error}")
        
        success_rate = (self.test_results['passed'] / (self.test_results['passed'] + self.test_results['failed'])) * 100
        print(f"\nSuccess Rate: {success_rate:.1f}%")
        
        return self.test_results['failed'] == 0

if __name__ == "__main__":
    tester = LibraryAPITester()
    success = tester.run_all_tests()
    
    if success:
        print("\n🎉 All tests passed! Backend API is working correctly.")
        exit(0)
    else:
        print("\n⚠️  Some tests failed. Check the details above.")
        exit(1)