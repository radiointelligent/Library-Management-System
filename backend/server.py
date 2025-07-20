from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
import pandas as pd
import io
import json
import xlsxwriter
from urllib.parse import unquote
import httpx
import asyncio


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class Book(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    author: str
    isbn: Optional[str] = None
    barcode: Optional[str] = None
    shelf: Optional[str] = None
    genre: Optional[str] = None
    ar_level: Optional[str] = None
    lexile: Optional[str] = None
    image_url: Optional[str] = None
    description: Optional[str] = None
    description_ru: Optional[str] = None
    page_count: Optional[int] = None
    categories: Optional[List[str]] = None
    maturity_rating: Optional[str] = None
    search_status: str = "pending"  # pending, found, not_found, searching
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('title', 'author')
    def validate_required_fields(cls, v):
        if not v or not v.strip():
            raise ValueError('Title and Author are required fields')
        return v.strip()

class BookCreate(BaseModel):
    title: str
    author: str
    isbn: Optional[str] = None
    barcode: Optional[str] = None
    shelf: Optional[str] = None
    genre: Optional[str] = None
    ar_level: Optional[str] = None
    lexile: Optional[str] = None

class BookUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    isbn: Optional[str] = None
    barcode: Optional[str] = None
    shelf: Optional[str] = None
    genre: Optional[str] = None
    ar_level: Optional[str] = None
    lexile: Optional[str] = None

class ExcelUploadResponse(BaseModel):
    success: bool
    message: str
    books_processed: int
    errors: List[dict] = []
    duplicates_found: int = 0
    auto_enhanced: int = 0

class BookFilter(BaseModel):
    search: Optional[str] = None
    genre: Optional[str] = None
    shelf: Optional[str] = None
    author: Optional[str] = None

class BookEnhancementRequest(BaseModel):
    book_id: str

class BookEnhancementResponse(BaseModel):
    success: bool
    message: str
    enhanced_fields: List[str] = []

class BatchEnhancementRequest(BaseModel):
    book_ids: Optional[List[str]] = None
    enhance_all_pending: bool = False

class BatchShelfAssignmentRequest(BaseModel):
    barcode: str
    shelf: str

class BatchShelfAssignmentResponse(BaseModel):
    success: bool
    message: str
    book_title: Optional[str] = None
    book_author: Optional[str] = None
    shelf_assigned: str
    auto_enhanced: bool = False


# Google Books API Integration
async def search_google_books(title: str, author: str = None, max_results: int = 5) -> List[Dict]:
    """Search Google Books API for book information"""
    try:
        search_terms = [title]
        if author and author.strip() and author != "Неизвестен":
            search_terms.append(author)
        
        query = " ".join(search_terms)
        url = f"https://www.googleapis.com/books/v1/volumes"
        params = {
            "q": query,
            "maxResults": max_results,
            "fields": "items(id,volumeInfo(title,authors,industryIdentifiers,categories,description,imageLinks,pageCount,maturityRating,language,publishedDate))"
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            
        data = response.json()
        
        if "items" not in data:
            return []
            
        return data["items"]
        
    except Exception as e:
        logging.error(f"Error searching Google Books API: {str(e)}")
        return []

def calculate_similarity(str1: str, str2: str) -> float:
    """Calculate similarity between two strings"""
    if not str1 or not str2:
        return 0.0
    
    str1_lower = str1.lower()
    str2_lower = str2.lower()
    
    # Exact match
    if str1_lower == str2_lower:
        return 1.0
    
    # Contains match
    if str1_lower in str2_lower or str2_lower in str1_lower:
        shorter = min(len(str1_lower), len(str2_lower))
        longer = max(len(str1_lower), len(str2_lower))
        return min(shorter / longer + 0.3, 1.0)
    
    # Word overlap
    words1 = str1_lower.split()
    words2 = str2_lower.split()
    
    if not words1 or not words2:
        return 0.0
    
    common_words = 0
    for word in words1:
        if len(word) > 2 and word in words2:
            common_words += 1
    
    return common_words / max(len(words1), len(words2))

def detect_genre(volume_info: Dict) -> str:
    """Detect genre from Google Books volume info"""
    categories = volume_info.get("categories", [])
    description = (volume_info.get("description", "")).lower()
    title = (volume_info.get("title", "")).lower()
    
    # Check categories first
    for category in categories:
        category_lower = category.lower()
        
        if "fiction" in category_lower and "non-fiction" not in category_lower:
            if "romance" in category_lower:
                return "rom"
            if "mystery" in category_lower or "thriller" in category_lower:
                return "mys"
            if "fantasy" in category_lower or "magic" in category_lower:
                return "fan"
            if "adventure" in category_lower:
                return "adv"
            return "fic"
        
        if "non-fiction" in category_lower or "nonfiction" in category_lower:
            return "nf"
        if "biography" in category_lower or "memoir" in category_lower:
            return "bio"
        if "science" in category_lower or "technology" in category_lower:
            return "sci"
        if "history" in category_lower or "historical" in category_lower:
            return "his"
        if "romance" in category_lower:
            return "rom"
        if "mystery" in category_lower or "detective" in category_lower:
            return "mys"
        if "fantasy" in category_lower or "fairy" in category_lower:
            return "fan"
        if "adventure" in category_lower or "action" in category_lower:
            return "adv"
    
    # Check description and title
    combined_text = f"{description} {title}"
    
    if "biography" in combined_text or "memoir" in combined_text or "life of" in combined_text:
        return "bio"
    if "mystery" in combined_text or "detective" in combined_text or "murder" in combined_text:
        return "mys"
    if "romance" in combined_text or "love story" in combined_text:
        return "rom"
    if "fantasy" in combined_text or "magic" in combined_text or "wizard" in combined_text:
        return "fan"
    if "adventure" in combined_text or "journey" in combined_text or "quest" in combined_text:
        return "adv"
    if "science" in combined_text or "technology" in combined_text or "research" in combined_text:
        return "sci"
    if "history" in combined_text or "historical" in combined_text or "ancient" in combined_text:
        return "his"
    if "true story" in combined_text or "real" in combined_text or "fact" in combined_text:
        return "nf"
    
    return "fic"

def generate_ar_level(volume_info: Dict) -> str:
    """Generate AR Level based on book characteristics"""
    page_count = volume_info.get("pageCount", 0)
    maturity_rating = (volume_info.get("maturityRating", "")).lower()
    categories = volume_info.get("categories", [])
    
    # Check if it's a children's book
    is_childrens = any("juvenile" in cat.lower() or "children" in cat.lower() for cat in categories)
    
    if is_childrens:
        if page_count < 50:
            return "1.0-2.5"
        elif page_count < 100:
            return "2.0-3.5"
        else:
            return "3.0-5.0"
    
    # Adult books
    if page_count < 100:
        return "3.0-5.0"
    elif page_count < 200:
        return "4.0-6.5"
    elif page_count < 300:
        return "5.0-8.0"
    elif page_count < 500:
        return "6.0-9.0"
    else:
        return "7.0-12.0"

def generate_lexile(volume_info: Dict) -> str:
    """Generate Lexile level based on book characteristics"""
    page_count = volume_info.get("pageCount", 0)
    categories = volume_info.get("categories", [])
    
    is_childrens = any("juvenile" in cat.lower() or "children" in cat.lower() for cat in categories)
    
    if is_childrens:
        if page_count < 50:
            return "200L-400L"
        elif page_count < 100:
            return "300L-600L"
        else:
            return "500L-800L"
    
    # Adult books
    if page_count < 100:
        return "400L-700L"
    elif page_count < 200:
        return "600L-900L"
    elif page_count < 300:
        return "700L-1000L"
    elif page_count < 500:
        return "800L-1200L"
    else:
        return "900L-1400L"

def find_best_match(google_books_results: List[Dict], target_title: str, target_author: str = None) -> Optional[Dict]:
    """Find the best matching book from Google Books results"""
    if not google_books_results:
        return None
    
    best_match = None
    best_score = 0.0
    
    for item in google_books_results:
        volume_info = item.get("volumeInfo", {})
        score = 0.0
        
        # Title similarity (weighted heavily)
        book_title = volume_info.get("title", "")
        if book_title:
            title_similarity = calculate_similarity(book_title, target_title)
            score += title_similarity * 3
        
        # Author similarity
        book_authors = volume_info.get("authors", [])
        if book_authors and target_author and target_author != "Неизвестен":
            author_similarity = max(
                calculate_similarity(author, target_author) 
                for author in book_authors
            )
            if author_similarity > 0.7:
                score += 2
        
        # Language preference (English books)
        language = volume_info.get("language", "")
        if language == "en":
            score += 0.5
        
        # Has description
        if volume_info.get("description"):
            score += 0.3
        
        # Has image
        if volume_info.get("imageLinks"):
            score += 0.2
        
        if score > best_score:
            best_score = score
            best_match = item
    
    # Only return if score is reasonable
    return best_match if best_score > 1.0 else None

async def enhance_book_with_google_books(book: Book) -> Book:
    """Enhance a single book with Google Books data"""
    try:
        # Search for the book
        google_results = await search_google_books(book.title, book.author)
        
        if not google_results:
            book.search_status = "not_found"
            return book
        
        # Find best match
        best_match = find_best_match(google_results, book.title, book.author)
        
        if not best_match:
            book.search_status = "not_found"
            return book
        
        volume_info = best_match.get("volumeInfo", {})
        
        # Update book information only if current fields are empty
        enhanced_fields = []
        
        # Update author if unknown
        authors = volume_info.get("authors", [])
        if authors and (not book.author or book.author == "Неизвестен" or book.author.strip() == ""):
            book.author = authors[0]
            enhanced_fields.append("author")
        
        # Update ISBN
        if not book.isbn:
            industry_identifiers = volume_info.get("industryIdentifiers", [])
            for identifier in industry_identifiers:
                if "ISBN" in identifier.get("type", ""):
                    book.isbn = identifier.get("identifier", "")
                    enhanced_fields.append("isbn")
                    break
        
        # Update description
        if not book.description:
            description = volume_info.get("description", "")
            if description:
                book.description = description
                enhanced_fields.append("description")
        
        # Update image URL
        if not book.image_url:
            image_links = volume_info.get("imageLinks", {})
            if image_links:
                book.image_url = (
                    image_links.get("thumbnail") or 
                    image_links.get("smallThumbnail") or 
                    image_links.get("medium") or 
                    image_links.get("large") or ""
                )
                if book.image_url:
                    enhanced_fields.append("image_url")
        
        # Update genre
        if not book.genre:
            book.genre = detect_genre(volume_info)
            enhanced_fields.append("genre")
        
        # Update AR level
        if not book.ar_level:
            book.ar_level = generate_ar_level(volume_info)
            enhanced_fields.append("ar_level")
        
        # Update Lexile
        if not book.lexile:
            book.lexile = generate_lexile(volume_info)
            enhanced_fields.append("lexile")
        
        # Store additional metadata
        book.page_count = volume_info.get("pageCount")
        book.categories = volume_info.get("categories", [])
        book.maturity_rating = volume_info.get("maturityRating")
        
        book.search_status = "found"
        book.updated_at = datetime.utcnow()
        
        logging.info(f"Enhanced book '{book.title}' with fields: {enhanced_fields}")
        
        return book
        
    except Exception as e:
        logging.error(f"Error enhancing book '{book.title}': {str(e)}")
        book.search_status = "not_found"
        return book


# Excel Processing Functions
def validate_excel_structure(df):
    """Validate that the Excel file has required columns"""
    required_columns = ['title', 'author']
    optional_columns = ['isbn', 'barcode', 'shelf', 'genre']
    
    # Convert column names to lowercase for case-insensitive matching
    df.columns = df.columns.str.lower().str.strip()
    
    missing_columns = []
    for col in required_columns:
        if col not in df.columns:
            missing_columns.append(col)
    
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")
    
    return df

def clean_book_data(row):
    """Clean and validate individual book data"""
    book_data = {}
    
    # Required fields
    book_data['title'] = str(row.get('title', '')).strip()
    book_data['author'] = str(row.get('author', '')).strip()
    
    # Optional fields
    book_data['isbn'] = str(row.get('isbn', '')).strip() if pd.notna(row.get('isbn')) else None
    book_data['barcode'] = str(row.get('barcode', '')).strip() if pd.notna(row.get('barcode')) else None
    book_data['shelf'] = str(row.get('shelf', '')).strip() if pd.notna(row.get('shelf')) else None
    book_data['genre'] = str(row.get('genre', '')).strip() if pd.notna(row.get('genre')) else None
    
    # Remove empty strings and replace with None
    for key, value in book_data.items():
        if value == '' or value == 'nan':
            book_data[key] = None
    
    return book_data

async def check_duplicates(book_data):
    """Check for duplicate books based on ISBN, barcode, or title+author combination"""
    filters = []
    
    if book_data.get('isbn'):
        filters.append({"isbn": book_data['isbn']})
    
    if book_data.get('barcode'):
        filters.append({"barcode": book_data['barcode']})
    
    # Check for title+author combination
    filters.append({
        "title": {"$regex": f"^{book_data['title']}$", "$options": "i"},
        "author": {"$regex": f"^{book_data['author']}$", "$options": "i"}
    })
    
    if filters:
        existing_book = await db.books.find_one({"$or": filters})
        return existing_book is not None
    
    return False


# API Routes
@api_router.get("/")
async def root():
    return {"message": "Library Management System API with Google Books Integration and Barcode Scanning"}

@api_router.post("/books/upload", response_model=ExcelUploadResponse)
async def upload_excel_file(
    file: UploadFile = File(...),
    auto_enhance: bool = Query(False, description="Automatically enhance books after upload")
):
    """Upload and process Excel file with book data"""
    
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only Excel files (.xlsx, .xls) are supported")
    
    try:
        # Read the uploaded file
        content = await file.read()
        
        # Try to read Excel file
        try:
            if file.filename.lower().endswith('.xlsx'):
                df = pd.read_excel(io.BytesIO(content), engine='openpyxl')
            else:
                df = pd.read_excel(io.BytesIO(content), engine='xlrd')
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error reading Excel file: {str(e)}")
        
        # Validate Excel structure
        try:
            df = validate_excel_structure(df)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        # Process each row
        processed_books = 0
        errors = []
        duplicates_found = 0
        auto_enhanced_count = 0
        
        for index, row in df.iterrows():
            try:
                # Clean the data
                book_data = clean_book_data(row)
                
                # Skip rows with empty title or author
                if not book_data['title'] or not book_data['author']:
                    errors.append({
                        "row": index + 2,  # +2 because pandas is 0-indexed and Excel starts from row 1 with headers
                        "error": "Missing required fields: title and/or author"
                    })
                    continue
                
                # Check for duplicates
                is_duplicate = await check_duplicates(book_data)
                if is_duplicate:
                    duplicates_found += 1
                    errors.append({
                        "row": index + 2,
                        "error": f"Duplicate book found: {book_data['title']} by {book_data['author']}"
                    })
                    continue
                
                # Create book object with search_status = pending
                book_data['search_status'] = 'pending'
                book = Book(**book_data)
                
                # Auto-enhance if requested
                if auto_enhance:
                    book.search_status = 'searching'
                    enhanced_book = await enhance_book_with_google_books(book)
                    if enhanced_book.search_status == 'found':
                        auto_enhanced_count += 1
                    book = enhanced_book
                    # Small delay to respect API limits
                    await asyncio.sleep(0.5)
                
                # Insert into database
                await db.books.insert_one(book.dict())
                processed_books += 1
                
            except Exception as e:
                errors.append({
                    "row": index + 2,
                    "error": str(e)
                })
        
        return ExcelUploadResponse(
            success=True,
            message=f"Successfully processed {processed_books} books" + (f", auto-enhanced {auto_enhanced_count}" if auto_enhance else ""),
            books_processed=processed_books,
            errors=errors,
            duplicates_found=duplicates_found,
            auto_enhanced=auto_enhanced_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@api_router.post("/books/scan-assign-shelf", response_model=BatchShelfAssignmentResponse)
async def scan_assign_shelf(request: BatchShelfAssignmentRequest):
    """Scan barcode and assign shelf in one operation"""
    try:
        # Find book by barcode
        book_data = await db.books.find_one({"barcode": request.barcode})
        
        if not book_data:
            raise HTTPException(status_code=404, detail="Book with this barcode not found")
        
        book = Book(**book_data)
        
        # Assign shelf
        book.shelf = request.shelf
        book.updated_at = datetime.utcnow()
        
        # Auto-enhance if book is still pending
        auto_enhanced = False
        if book.search_status == 'pending':
            book.search_status = 'searching'
            enhanced_book = await enhance_book_with_google_books(book)
            if enhanced_book.search_status == 'found':
                auto_enhanced = True
            book = enhanced_book
        
        # Update in database
        await db.books.update_one(
            {"id": book.id}, 
            {"$set": book.dict()}
        )
        
        return BatchShelfAssignmentResponse(
            success=True,
            message="Shelf assigned successfully",
            book_title=book.title,
            book_author=book.author,
            shelf_assigned=request.shelf,
            auto_enhanced=auto_enhanced
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error assigning shelf: {str(e)}")

@api_router.get("/books/shelves")
async def get_available_shelves():
    """Get all available shelf numbers (1-120)"""
    shelves = [{"value": str(i), "label": f"Shelf {i}"} for i in range(1, 121)]
    
    # Get shelf usage statistics
    shelf_stats = {}
    for i in range(1, 121):
        count = await db.books.count_documents({"shelf": str(i)})
        shelf_stats[str(i)] = count
    
    return {
        "shelves": shelves,
        "usage": shelf_stats,
        "total_shelves": 120
    }

@api_router.post("/books/batch-shelf-assignment")
async def batch_assign_shelves(book_ids: List[str], shelf: str):
    """Assign shelf to multiple books"""
    try:
        if not shelf or not shelf.strip():
            raise HTTPException(status_code=400, detail="Shelf number is required")
        
        shelf_num = int(shelf)
        if shelf_num < 1 or shelf_num > 120:
            raise HTTPException(status_code=400, detail="Shelf number must be between 1 and 120")
        
        # Update all specified books
        result = await db.books.update_many(
            {"id": {"$in": book_ids}},
            {"$set": {"shelf": shelf, "updated_at": datetime.utcnow()}}
        )
        
        return {
            "success": True,
            "message": f"Assigned shelf {shelf} to {result.modified_count} books",
            "updated_count": result.modified_count
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid shelf number")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in batch assignment: {str(e)}")

@api_router.post("/books/{book_id}/enhance", response_model=BookEnhancementResponse)
async def enhance_single_book(book_id: str):
    """Enhance a single book with Google Books data"""
    try:
        # Find the book
        book_data = await db.books.find_one({"id": book_id})
        if not book_data:
            raise HTTPException(status_code=404, detail="Book not found")
        
        book = Book(**book_data)
        
        # Set status to searching
        await db.books.update_one(
            {"id": book_id}, 
            {"$set": {"search_status": "searching", "updated_at": datetime.utcnow()}}
        )
        
        # Enhance the book
        enhanced_book = await enhance_book_with_google_books(book)
        
        # Update in database
        await db.books.update_one(
            {"id": book_id}, 
            {"$set": enhanced_book.dict()}
        )
        
        enhanced_fields = []
        original_book = Book(**book_data)
        
        # Determine which fields were enhanced
        if enhanced_book.author != original_book.author:
            enhanced_fields.append("author")
        if enhanced_book.isbn != original_book.isbn:
            enhanced_fields.append("isbn")
        if enhanced_book.description != original_book.description:
            enhanced_fields.append("description")
        if enhanced_book.image_url != original_book.image_url:
            enhanced_fields.append("image_url")
        if enhanced_book.genre != original_book.genre:
            enhanced_fields.append("genre")
        
        return BookEnhancementResponse(
            success=enhanced_book.search_status == "found",
            message="Book enhanced successfully" if enhanced_book.search_status == "found" else "No additional information found",
            enhanced_fields=enhanced_fields
        )
        
    except HTTPException:
        raise
    except Exception as e:
        # Reset status to pending on error
        await db.books.update_one(
            {"id": book_id}, 
            {"$set": {"search_status": "pending", "updated_at": datetime.utcnow()}}
        )
        raise HTTPException(status_code=500, detail=f"Error enhancing book: {str(e)}")

@api_router.post("/books/enhance-batch")
async def enhance_books_batch(request: BatchEnhancementRequest):
    """Enhance multiple books with Google Books data"""
    try:
        # Determine which books to enhance
        if request.enhance_all_pending:
            # Enhance all books with pending status
            books_cursor = db.books.find({"search_status": "pending"})
            books_data = await books_cursor.to_list(length=None)
        else:
            # Enhance specific books
            if not request.book_ids:
                raise HTTPException(status_code=400, detail="No books specified for enhancement")
            
            books_data = []
            for book_id in request.book_ids:
                book_data = await db.books.find_one({"id": book_id})
                if book_data:
                    books_data.append(book_data)
        
        if not books_data:
            return {"success": True, "message": "No books to enhance", "enhanced_count": 0, "errors": []}
        
        enhanced_count = 0
        errors = []
        
        # Process books with delay to respect API limits
        for book_data in books_data:
            try:
                book = Book(**book_data)
                
                # Set status to searching
                await db.books.update_one(
                    {"id": book.id}, 
                    {"$set": {"search_status": "searching", "updated_at": datetime.utcnow()}}
                )
                
                # Enhance the book
                enhanced_book = await enhance_book_with_google_books(book)
                
                # Update in database
                await db.books.update_one(
                    {"id": book.id}, 
                    {"$set": enhanced_book.dict()}
                )
                
                if enhanced_book.search_status == "found":
                    enhanced_count += 1
                
                # Small delay to respect API limits
                await asyncio.sleep(1.0)
                
            except Exception as e:
                logging.error(f"Error enhancing book {book_data.get('title', 'Unknown')}: {str(e)}")
                errors.append({
                    "book_id": book_data.get("id"),
                    "title": book_data.get("title"),
                    "error": str(e)
                })
                
                # Reset status to pending on error
                await db.books.update_one(
                    {"id": book_data.get("id")}, 
                    {"$set": {"search_status": "pending", "updated_at": datetime.utcnow()}}
                )
        
        return {
            "success": True,
            "message": f"Batch enhancement completed. Enhanced {enhanced_count} of {len(books_data)} books.",
            "enhanced_count": enhanced_count,
            "total_processed": len(books_data),
            "errors": errors
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in batch enhancement: {str(e)}")

@api_router.get("/books", response_model=List[Book])
async def get_books(
    search: Optional[str] = Query(None, description="Search in title, author, or ISBN"),
    genre: Optional[str] = Query(None, description="Filter by genre"),
    shelf: Optional[str] = Query(None, description="Filter by shelf"),
    author: Optional[str] = Query(None, description="Filter by author"),
    search_status: Optional[str] = Query(None, description="Filter by search status"),
    barcode: Optional[str] = Query(None, description="Search by barcode"),
    limit: int = Query(100, le=500, description="Maximum number of books to return"),
    skip: int = Query(0, ge=0, description="Number of books to skip")
):
    """Get books with optional filtering and search"""
    
    # Build filter query
    filter_query = {}
    
    if search:
        # Search in title, author, and ISBN
        search_regex = {"$regex": search, "$options": "i"}
        filter_query["$or"] = [
            {"title": search_regex},
            {"author": search_regex},
            {"isbn": search_regex}
        ]
    
    if genre:
        filter_query["genre"] = {"$regex": f"^{genre}$", "$options": "i"}
    
    if shelf:
        filter_query["shelf"] = {"$regex": f"^{shelf}$", "$options": "i"}
    
    if author:
        filter_query["author"] = {"$regex": author, "$options": "i"}
    
    if search_status:
        filter_query["search_status"] = search_status
    
    if barcode:
        filter_query["barcode"] = {"$regex": barcode, "$options": "i"}
    
    # Query database
    cursor = db.books.find(filter_query).skip(skip).limit(limit).sort("title", 1)
    books = await cursor.to_list(length=limit)
    
    return [Book(**book) for book in books]

@api_router.get("/books/stats")
async def get_book_stats():
    """Get statistics about the book collection"""
    
    total_books = await db.books.count_documents({})
    
    # Get unique genres
    genres = await db.books.distinct("genre", {"genre": {"$ne": None}})
    
    # Get unique shelves
    shelves = await db.books.distinct("shelf", {"shelf": {"$ne": None}})
    
    # Get unique authors
    authors = await db.books.distinct("author")
    
    # Get search status counts
    pending_count = await db.books.count_documents({"search_status": "pending"})
    found_count = await db.books.count_documents({"search_status": "found"})
    not_found_count = await db.books.count_documents({"search_status": "not_found"})
    searching_count = await db.books.count_documents({"search_status": "searching"})
    
    # Get shelf distribution
    shelf_distribution = {}
    for shelf in range(1, 121):
        count = await db.books.count_documents({"shelf": str(shelf)})
        if count > 0:
            shelf_distribution[str(shelf)] = count
    
    return {
        "total_books": total_books,
        "total_genres": len(genres),
        "total_shelves": len([s for s in shelves if s]),
        "total_authors": len(authors),
        "genres": sorted(genres),
        "shelves": sorted([int(s) for s in shelves if s.isdigit()]),
        "shelf_distribution": shelf_distribution,
        "search_status": {
            "pending": pending_count,
            "found": found_count,
            "not_found": not_found_count,
            "searching": searching_count
        }
    }

@api_router.post("/books", response_model=Book)
async def create_book(book_data: BookCreate):
    """Create a new book manually"""
    
    # Check for duplicates
    is_duplicate = await check_duplicates(book_data.dict())
    if is_duplicate:
        raise HTTPException(status_code=400, detail="Duplicate book found")
    
    book_dict = book_data.dict()
    book_dict['search_status'] = 'pending'
    book = Book(**book_dict)
    await db.books.insert_one(book.dict())
    
    return book

@api_router.put("/books/{book_id}", response_model=Book)
async def update_book(book_id: str, book_data: BookUpdate):
    """Update an existing book"""
    
    # Check if book exists
    existing_book = await db.books.find_one({"id": book_id})
    if not existing_book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    # Prepare update data
    update_data = {k: v for k, v in book_data.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()
    
    # Update book
    await db.books.update_one({"id": book_id}, {"$set": update_data})
    
    # Return updated book
    updated_book = await db.books.find_one({"id": book_id})
    return Book(**updated_book)

@api_router.delete("/books/{book_id}")
async def delete_book(book_id: str):
    """Delete a book"""
    
    result = await db.books.delete_one({"id": book_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Book not found")
    
    return {"message": "Book deleted successfully"}

@api_router.get("/books/export")
async def export_books_to_excel(
    search: Optional[str] = Query(None),
    genre: Optional[str] = Query(None),
    shelf: Optional[str] = Query(None),
    author: Optional[str] = Query(None),
    search_status: Optional[str] = Query(None)
):
    """Export books to Excel file"""
    
    # Build filter query (same as get_books)
    filter_query = {}
    
    if search:
        search_regex = {"$regex": search, "$options": "i"}
        filter_query["$or"] = [
            {"title": search_regex},
            {"author": search_regex},
            {"isbn": search_regex}
        ]
    
    if genre:
        filter_query["genre"] = {"$regex": f"^{genre}$", "$options": "i"}
    
    if shelf:
        filter_query["shelf"] = {"$regex": f"^{shelf}$", "$options": "i"}
    
    if author:
        filter_query["author"] = {"$regex": author, "$options": "i"}
    
    if search_status:
        filter_query["search_status"] = search_status
    
    # Get all matching books
    books = await db.books.find(filter_query).sort("shelf", 1).to_list(None)
    
    if not books:
        raise HTTPException(status_code=404, detail="No books found to export")
    
    # Create Excel file in memory
    output = io.BytesIO()
    
    # Prepare data for Excel
    book_data = []
    for book in books:
        book_data.append({
            'Title': book.get('title', ''),
            'Author': book.get('author', ''),
            'ISBN': book.get('isbn', ''),
            'Barcode': book.get('barcode', ''),
            'Shelf': book.get('shelf', ''),
            'Genre': book.get('genre', ''),
            'AR Level': book.get('ar_level', ''),
            'Lexile': book.get('lexile', ''),
            'Search Status': book.get('search_status', ''),
            'Description': book.get('description', ''),
            'Description RU': book.get('description_ru', ''),
            'Image URL': book.get('image_url', ''),
            'Page Count': book.get('page_count', ''),
            'Categories': ', '.join(book.get('categories', [])),
            'Created At': book.get('created_at', '').strftime('%Y-%m-%d %H:%M:%S') if book.get('created_at') else '',
        })
    
    # Create DataFrame and write to Excel
    df = pd.DataFrame(book_data)
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Books', index=False)
        
        # Get the workbook and worksheet objects
        workbook = writer.book
        worksheet = writer.sheets['Books']
        
        # Add some formatting
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#D7E4BC',
            'border': 1
        })
        
        # Write the column headers with formatting
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        # Adjust column widths
        for i, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).str.len().max(), len(col)) + 2
            worksheet.set_column(i, i, min(max_len, 50))
    
    output.seek(0)
    
    # Create filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"library_books_enhanced_{timestamp}.xlsx"
    
    # Return the Excel file
    return StreamingResponse(
        io.BytesIO(output.read()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()