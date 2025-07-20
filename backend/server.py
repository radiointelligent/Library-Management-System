from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, validator
from typing import List, Optional
import uuid
from datetime import datetime
import pandas as pd
import io
import json
import xlsxwriter
from urllib.parse import unquote


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

class BookUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    isbn: Optional[str] = None
    barcode: Optional[str] = None
    shelf: Optional[str] = None
    genre: Optional[str] = None

class ExcelUploadResponse(BaseModel):
    success: bool
    message: str
    books_processed: int
    errors: List[dict] = []
    duplicates_found: int = 0

class BookFilter(BaseModel):
    search: Optional[str] = None
    genre: Optional[str] = None
    shelf: Optional[str] = None
    author: Optional[str] = None


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
    return {"message": "Library Management System API"}

@api_router.post("/books/upload", response_model=ExcelUploadResponse)
async def upload_excel_file(file: UploadFile = File(...)):
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
                
                # Create book object
                book = Book(**book_data)
                
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
            message=f"Successfully processed {processed_books} books",
            books_processed=processed_books,
            errors=errors,
            duplicates_found=duplicates_found
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@api_router.get("/books", response_model=List[Book])
async def get_books(
    search: Optional[str] = Query(None, description="Search in title, author, or ISBN"),
    genre: Optional[str] = Query(None, description="Filter by genre"),
    shelf: Optional[str] = Query(None, description="Filter by shelf"),
    author: Optional[str] = Query(None, description="Filter by author"),
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
    
    return {
        "total_books": total_books,
        "total_genres": len(genres),
        "total_shelves": len(shelves),
        "total_authors": len(authors),
        "genres": sorted(genres),
        "shelves": sorted(shelves)
    }

@api_router.post("/books", response_model=Book)
async def create_book(book_data: BookCreate):
    """Create a new book manually"""
    
    # Check for duplicates
    is_duplicate = await check_duplicates(book_data.dict())
    if is_duplicate:
        raise HTTPException(status_code=400, detail="Duplicate book found")
    
    book = Book(**book_data.dict())
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
    author: Optional[str] = Query(None)
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
    
    # Get all matching books
    books = await db.books.find(filter_query).sort("title", 1).to_list(None)
    
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
    filename = f"library_books_{timestamp}.xlsx"
    
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