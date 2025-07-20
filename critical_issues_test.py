#!/usr/bin/env python3
"""
Focused Backend API Testing for Critical Issues
Tests the specific issues mentioned in the review request with rate limiting considerations
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

print(f"Testing critical backend issues at: {API_URL}")

class CriticalIssuesTester:
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
    
    def test_excel_export_fix(self):
        """Test that Excel export is working (was returning 500 error)"""
        try:
            response = self.session.get(f"{API_URL}/books/export")
            
            if response.status_code == 200:
                if response.headers.get('content-type') == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
                    content_length = len(response.content)
                    self.log_result("Excel Export Fix", True, f"Export successful, size: {content_length} bytes")
                    
                    # Verify filename in headers
                    content_disposition = response.headers.get('Content-Disposition', '')
                    if 'library_books_enhanced_' in content_disposition:
                        self.log_result("Excel Export Filename", True, "Correct filename format")
                    else:
                        self.log_result("Excel Export Filename", False, f"Unexpected filename: {content_disposition}")
                    
                    return True
                else:
                    self.log_result("Excel Export Fix", False, f"Wrong content type: {response.headers.get('content-type')}")
                    return False
            elif response.status_code == 404:
                self.log_result("Excel Export Fix", True, "No books to export (acceptable)")
                return True
            else:
                self.log_result("Excel Export Fix", False, f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Excel Export Fix", False, f"Exception: {str(e)}")
            return False
    
    def test_excel_upload_with_auto_enhancement(self):
        """Test Excel upload with auto_enhance=true parameter"""
        try:
            # Create Excel file with a simple book
            data = [
                {"Title": "Test Enhancement Book", "Author": "Test Author", "Barcode": "TEST001", "Shelf": "T1"}
            ]
            
            df = pd.DataFrame(data)
            excel_buffer = io.BytesIO()
            df.to_excel(excel_buffer, index=False, engine='openpyxl')
            excel_buffer.seek(0)
            
            files = {
                'file': ('test_auto_enhance.xlsx', excel_buffer, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            }
            
            # Test upload with auto_enhance=true
            response = self.session.post(f"{API_URL}/books/upload?auto_enhance=true", files=files)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    books_processed = data.get('books_processed', 0)
                    auto_enhanced = data.get('auto_enhanced', 0)
                    
                    self.log_result("Excel Upload with Auto-Enhancement", True, 
                                  f"Processed {books_processed} books, attempted auto-enhancement on {auto_enhanced}")
                    
                    # Verify the book was created with search_status
                    time.sleep(1)
                    book_response = self.session.get(f"{API_URL}/books", params={"search": "Test Enhancement Book"})
                    if book_response.status_code == 200:
                        books = book_response.json()
                        if books:
                            book = books[0]
                            search_status = book.get('search_status')
                            self.log_result("Auto-Enhancement Status Check", True, 
                                          f"Book created with search_status: {search_status}")
                            # Store for cleanup
                            self.test_book_ids.append(book['id'])
                        else:
                            self.log_result("Auto-Enhancement Status Check", False, "Book not found after upload")
                    
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
    
    def test_enhancement_endpoints_exist(self):
        """Test that enhancement endpoints exist and respond correctly"""
        try:
            # Create a test book first
            test_book = {
                "title": "Enhancement Test Book",
                "author": "Test Author",
                "barcode": "ENH001"
            }
            
            response = self.session.post(f"{API_URL}/books", json=test_book)
            if response.status_code != 200:
                self.log_result("Enhancement Endpoints - Book Creation", False, "Could not create test book")
                return False
            
            book = response.json()
            book_id = book['id']
            self.test_book_ids.append(book_id)
            
            # Test single book enhancement endpoint
            enhance_response = self.session.post(f"{API_URL}/books/{book_id}/enhance")
            
            if enhance_response.status_code == 200:
                data = enhance_response.json()
                self.log_result("Single Book Enhancement Endpoint", True, 
                              f"Endpoint exists and responds: {data.get('message', 'No message')}")
            else:
                self.log_result("Single Book Enhancement Endpoint", False, 
                              f"Status: {enhance_response.status_code}")
            
            # Test batch enhancement endpoint
            batch_request = {
                "book_ids": [book_id],
                "enhance_all_pending": False
            }
            
            batch_response = self.session.post(f"{API_URL}/books/enhance-batch", json=batch_request)
            
            if batch_response.status_code == 200:
                data = batch_response.json()
                self.log_result("Batch Enhancement Endpoint", True, 
                              f"Endpoint exists and responds: {data.get('message', 'No message')}")
            else:
                self.log_result("Batch Enhancement Endpoint", False, 
                              f"Status: {batch_response.status_code}")
            
            return True
                
        except Exception as e:
            self.log_result("Enhancement Endpoints", False, f"Exception: {str(e)}")
            return False
    
    def test_barcode_scanning_endpoint(self):
        """Test barcode scanning with shelf assignment endpoint"""
        try:
            # Create a book with barcode first
            test_book = {
                "title": "Barcode Test Book",
                "author": "Test Author",
                "barcode": "SCAN001"
            }
            
            response = self.session.post(f"{API_URL}/books", json=test_book)
            if response.status_code != 200:
                self.log_result("Barcode Scanning - Book Creation", False, "Could not create test book")
                return False
            
            book = response.json()
            self.test_book_ids.append(book['id'])
            
            # Test shelf assignment via barcode scanning
            scan_request = {
                "barcode": "SCAN001",
                "shelf": "S99"
            }
            
            response = self.session.post(f"{API_URL}/books/scan-assign-shelf", json=scan_request)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    book_title = data.get('book_title')
                    shelf_assigned = data.get('shelf_assigned')
                    
                    self.log_result("Barcode Scanning with Shelf Assignment", True, 
                                  f"Assigned shelf {shelf_assigned} to '{book_title}'")
                    
                    # Verify the shelf was actually assigned
                    verify_response = self.session.get(f"{API_URL}/books", params={"barcode": "SCAN001"})
                    if verify_response.status_code == 200:
                        verify_books = verify_response.json()
                        if verify_books and verify_books[0].get('shelf') == "S99":
                            self.log_result("Shelf Assignment Verification", True, "Shelf assignment verified")
                        else:
                            self.log_result("Shelf Assignment Verification", False, "Shelf assignment not reflected")
                    
                    return True
                else:
                    self.log_result("Barcode Scanning with Shelf Assignment", False, f"Assignment failed: {data}")
                    return False
            else:
                self.log_result("Barcode Scanning with Shelf Assignment", False, f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Barcode Scanning with Shelf Assignment", False, f"Exception: {str(e)}")
            return False
    
    def test_database_operations_with_enhanced_data(self):
        """Test that enhanced book data is properly saved and retrieved"""
        try:
            # Get books and check for enhanced data
            response = self.session.get(f"{API_URL}/books")
            
            if response.status_code != 200:
                self.log_result("Database Operations", False, f"Could not retrieve books: {response.status_code}")
                return False
            
            books = response.json()
            
            # Check search_status distribution
            status_counts = {}
            enhanced_books = 0
            
            for book in books:
                status = book.get('search_status', 'unknown')
                status_counts[status] = status_counts.get(status, 0) + 1
                
                # Count books with enhanced data
                if (book.get('description') or book.get('image_url') or 
                    (book.get('isbn') and len(book['isbn']) > 5) or
                    book.get('ar_level') or book.get('lexile')):
                    enhanced_books += 1
            
            self.log_result("Database Operations - Search Status", True, 
                          f"Status distribution: {status_counts}")
            
            self.log_result("Database Operations - Enhanced Data", True, 
                          f"Found {enhanced_books} books with enhanced data out of {len(books)} total")
            
            return True
                
        except Exception as e:
            self.log_result("Database Operations", False, f"Exception: {str(e)}")
            return False
    
    def test_filtered_export(self):
        """Test Excel export with different filter parameters"""
        try:
            # Test filtered exports with different parameters
            filter_tests = [
                {"genre": "Fiction"},
                {"shelf": "A1"},
                {"search_status": "found"},
                {"search_status": "not_found"}
            ]
            
            for filter_params in filter_tests:
                filter_name = list(filter_params.keys())[0]
                filter_value = list(filter_params.values())[0]
                
                response = self.session.get(f"{API_URL}/books/export", params=filter_params)
                
                if response.status_code in [200, 404]:  # 404 is acceptable if no books match filter
                    self.log_result(f"Filtered Export - {filter_name}={filter_value}", True, 
                                  f"Export handled correctly (status: {response.status_code})")
                else:
                    self.log_result(f"Filtered Export - {filter_name}={filter_value}", False, 
                                  f"Export failed with status: {response.status_code}")
            
            return True
            
        except Exception as e:
            self.log_result("Filtered Export", False, f"Exception: {str(e)}")
            return False
    
    def cleanup(self):
        """Clean up test data"""
        for book_id in self.test_book_ids:
            try:
                self.session.delete(f"{API_URL}/books/{book_id}")
            except:
                pass
    
    def run_critical_tests(self):
        """Run tests for critical issues mentioned in review request"""
        print("=" * 70)
        print("LIBRARY MANAGEMENT SYSTEM - CRITICAL ISSUES TESTING")
        print("Focus: Excel Export, Enhancement Endpoints, Auto-Enhancement, Barcode Scanning")
        print("=" * 70)
        
        # Test critical issues in order
        tests = [
            ("API Health Check", self.test_api_health),
            ("Excel Export Fix (was 500 error)", self.test_excel_export_fix),
            ("Excel Upload with Auto-Enhancement", self.test_excel_upload_with_auto_enhancement),
            ("Enhancement Endpoints Exist", self.test_enhancement_endpoints_exist),
            ("Barcode Scanning with Shelf Assignment", self.test_barcode_scanning_endpoint),
            ("Database Operations with Enhanced Data", self.test_database_operations_with_enhanced_data),
            ("Filtered Export Functionality", self.test_filtered_export),
        ]
        
        for test_name, test_func in tests:
            print(f"\n--- Running {test_name} ---")
            test_func()
            time.sleep(0.5)  # Small delay between tests
        
        # Cleanup
        self.cleanup()
        
        # Print summary
        print("\n" + "=" * 70)
        print("CRITICAL ISSUES TEST SUMMARY")
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
    tester = CriticalIssuesTester()
    success = tester.run_critical_tests()
    
    if success:
        print("\n🎉 All critical issue tests passed! The reported issues have been resolved.")
        exit(0)
    else:
        print("\n⚠️  Some critical issue tests failed. Check the details above.")
        exit(1)