import React, { useState, useEffect, useCallback } from "react";
import "./App.css";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [books, setBooks] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedGenre, setSelectedGenre] = useState("");
  const [selectedShelf, setSelectedShelf] = useState("");
  const [selectedAuthor, setSelectedAuthor] = useState("");
  const [uploadStatus, setUploadStatus] = useState(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [currentView, setCurrentView] = useState("upload"); // upload, catalog

  // Fetch books with filters
  const fetchBooks = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      
      if (searchTerm) params.append('search', searchTerm);
      if (selectedGenre) params.append('genre', selectedGenre);
      if (selectedShelf) params.append('shelf', selectedShelf);
      if (selectedAuthor) params.append('author', selectedAuthor);
      
      const response = await axios.get(`${API}/books?${params.toString()}`);
      setBooks(response.data);
    } catch (error) {
      console.error("Error fetching books:", error);
      setBooks([]);
    } finally {
      setLoading(false);
    }
  }, [searchTerm, selectedGenre, selectedShelf, selectedAuthor]);

  // Fetch stats
  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API}/books/stats`);
      setStats(response.data);
    } catch (error) {
      console.error("Error fetching stats:", error);
    }
  };

  useEffect(() => {
    fetchStats();
    if (currentView === 'catalog') {
      fetchBooks();
    }
  }, [currentView, fetchBooks]);

  // File upload handlers
  const handleFileUpload = async (file) => {
    if (!file) return;
    
    if (!file.name.toLowerCase().endsWith('.xlsx') && !file.name.toLowerCase().endsWith('.xls')) {
      setUploadStatus({
        success: false,
        message: "Please upload only Excel files (.xlsx or .xls)"
      });
      return;
    }
    
    setLoading(true);
    setUploadStatus(null);
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const response = await axios.post(`${API}/books/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      
      setUploadStatus(response.data);
      fetchStats(); // Refresh stats after upload
      
      // Auto-switch to catalog view if upload was successful
      if (response.data.success && response.data.books_processed > 0) {
        setTimeout(() => {
          setCurrentView('catalog');
        }, 2000);
      }
      
    } catch (error) {
      console.error("Upload error:", error);
      setUploadStatus({
        success: false,
        message: error.response?.data?.detail || "Upload failed. Please try again."
      });
    } finally {
      setLoading(false);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileUpload(files[0]);
    }
  };

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      handleFileUpload(file);
    }
  };

  // Export functionality
  const handleExport = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      
      if (searchTerm) params.append('search', searchTerm);
      if (selectedGenre) params.append('genre', selectedGenre);
      if (selectedShelf) params.append('shelf', selectedShelf);
      if (selectedAuthor) params.append('author', selectedAuthor);
      
      const response = await axios.get(`${API}/books/export?${params.toString()}`, {
        responseType: 'blob',
      });
      
      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      
      // Extract filename from headers or use default
      const contentDisposition = response.headers['content-disposition'];
      let filename = 'library_books.xlsx';
      if (contentDisposition) {
        const matches = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (matches && matches[1]) {
          filename = matches[1].replace(/['"]/g, '');
        }
      }
      
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
    } catch (error) {
      console.error("Export error:", error);
      alert("Export failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const clearFilters = () => {
    setSearchTerm("");
    setSelectedGenre("");
    setSelectedShelf("");
    setSelectedAuthor("");
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-indigo-50">
      {/* Header */}
      <header className="bg-white shadow-lg border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <h1 className="text-2xl font-bold text-gray-900 flex items-center">
                  <svg className="w-8 h-8 text-blue-600 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.746 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253z" />
                  </svg>
                  Library Management System
                </h1>
              </div>
            </div>
            
            {/* Navigation */}
            <nav className="flex space-x-4">
              <button
                onClick={() => setCurrentView('upload')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  currentView === 'upload'
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
                }`}
              >
                Upload Books
              </button>
              <button
                onClick={() => setCurrentView('catalog')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  currentView === 'catalog'
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
                }`}
              >
                Book Catalog
              </button>
            </nav>
          </div>
        </div>
      </header>

      {/* Stats Bar */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">{stats.total_books || 0}</div>
              <div className="text-sm text-gray-500">Total Books</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">{stats.total_authors || 0}</div>
              <div className="text-sm text-gray-500">Authors</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-purple-600">{stats.total_genres || 0}</div>
              <div className="text-sm text-gray-500">Genres</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-orange-600">{stats.total_shelves || 0}</div>
              <div className="text-sm text-gray-500">Shelves</div>
            </div>
          </div>
        </div>
      </div>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        
        {/* Upload View */}
        {currentView === 'upload' && (
          <div className="space-y-8">
            {/* Upload Section */}
            <div className="bg-white rounded-xl shadow-lg p-8">
              <div className="text-center mb-8">
                <h2 className="text-3xl font-bold text-gray-900 mb-4">Upload Your Library Catalog</h2>
                <p className="text-lg text-gray-600 max-w-2xl mx-auto">
                  Upload your Excel file containing book data. We support .xlsx and .xls formats with columns for Title, Author, ISBN, Barcode, Shelf, and Genre.
                </p>
              </div>

              {/* Drag and Drop Area */}
              <div
                className={`border-2 border-dashed rounded-xl p-12 text-center transition-all duration-300 ${
                  isDragOver
                    ? 'border-blue-400 bg-blue-50'
                    : 'border-gray-300 hover:border-gray-400'
                }`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
              >
                <div className="space-y-4">
                  <svg className="w-16 h-16 text-gray-400 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                  
                  <div>
                    <p className="text-xl text-gray-600 mb-2">
                      Drag and drop your Excel file here, or{' '}
                      <label className="text-blue-600 hover:text-blue-700 cursor-pointer font-medium">
                        browse to upload
                        <input
                          type="file"
                          className="hidden"
                          accept=".xlsx,.xls"
                          onChange={handleFileSelect}
                          disabled={loading}
                        />
                      </label>
                    </p>
                    <p className="text-sm text-gray-500">Supports .xlsx and .xls files up to 10MB</p>
                  </div>
                  
                  {loading && (
                    <div className="flex items-center justify-center space-x-2">
                      <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
                      <span className="text-blue-600">Processing file...</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Upload Status */}
              {uploadStatus && (
                <div className={`mt-6 p-4 rounded-lg ${uploadStatus.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
                  <div className={`flex items-start ${uploadStatus.success ? 'text-green-800' : 'text-red-800'}`}>
                    <svg className={`w-5 h-5 mt-0.5 mr-2 ${uploadStatus.success ? 'text-green-500' : 'text-red-500'}`} fill="currentColor" viewBox="0 0 20 20">
                      {uploadStatus.success ? (
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                      ) : (
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                      )}
                    </svg>
                    <div className="flex-1">
                      <p className="font-medium">{uploadStatus.message}</p>
                      {uploadStatus.books_processed > 0 && (
                        <p className="text-sm mt-1">
                          Successfully imported {uploadStatus.books_processed} books.
                        </p>
                      )}
                      {uploadStatus.duplicates_found > 0 && (
                        <p className="text-sm mt-1">
                          Found {uploadStatus.duplicates_found} duplicate entries (skipped).
                        </p>
                      )}
                      {uploadStatus.errors && uploadStatus.errors.length > 0 && (
                        <div className="mt-3">
                          <p className="text-sm font-medium">Issues found:</p>
                          <ul className="text-sm mt-1 space-y-1 max-h-32 overflow-y-auto">
                            {uploadStatus.errors.slice(0, 10).map((error, index) => (
                              <li key={index}>Row {error.row}: {error.error}</li>
                            ))}
                            {uploadStatus.errors.length > 10 && (
                              <li>...and {uploadStatus.errors.length - 10} more issues</li>
                            )}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Required Format Info */}
              <div className="mt-8 bg-blue-50 rounded-lg p-6">
                <h3 className="text-lg font-medium text-blue-900 mb-3">Required Excel Format</h3>
                <div className="text-blue-800 space-y-2">
                  <p><span className="font-medium">Required columns:</span> Title, Author</p>
                  <p><span className="font-medium">Optional columns:</span> ISBN, Barcode, Shelf, Genre</p>
                  <p className="text-sm text-blue-600">Column names are case-insensitive. The system will automatically detect and validate your file structure.</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Catalog View */}
        {currentView === 'catalog' && (
          <div className="space-y-6">
            {/* Search and Filter Section */}
            <div className="bg-white rounded-xl shadow-lg p-6">
              <div className="flex flex-col lg:flex-row gap-4 items-center">
                {/* Search */}
                <div className="flex-1 w-full lg:w-auto">
                  <div className="relative">
                    <svg className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                    <input
                      type="text"
                      placeholder="Search books, authors, or ISBN..."
                      className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                    />
                  </div>
                </div>

                {/* Filters */}
                <div className="flex gap-3 w-full lg:w-auto">
                  <select
                    className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    value={selectedGenre}
                    onChange={(e) => setSelectedGenre(e.target.value)}
                  >
                    <option value="">All Genres</option>
                    {stats.genres?.map((genre) => (
                      <option key={genre} value={genre}>{genre}</option>
                    ))}
                  </select>

                  <select
                    className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    value={selectedShelf}
                    onChange={(e) => setSelectedShelf(e.target.value)}
                  >
                    <option value="">All Shelves</option>
                    {stats.shelves?.map((shelf) => (
                      <option key={shelf} value={shelf}>{shelf}</option>
                    ))}
                  </select>

                  <button
                    onClick={clearFilters}
                    className="px-4 py-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors"
                  >
                    Clear
                  </button>

                  <button
                    onClick={handleExport}
                    disabled={loading || books.length === 0}
                    className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    Export Excel
                  </button>
                </div>
              </div>
            </div>

            {/* Books Table */}
            <div className="bg-white rounded-xl shadow-lg overflow-hidden">
              {loading ? (
                <div className="flex items-center justify-center p-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                  <span className="ml-3 text-gray-600">Loading books...</span>
                </div>
              ) : books.length === 0 ? (
                <div className="text-center p-8">
                  <svg className="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.746 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253z" />
                  </svg>
                  <p className="text-xl text-gray-500 mb-2">No books found</p>
                  <p className="text-gray-400">
                    {stats.total_books === 0 
                      ? "Upload an Excel file to get started"
                      : "Try adjusting your search or filter criteria"
                    }
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Title</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Author</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ISBN</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Barcode</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Shelf</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Genre</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {books.map((book) => (
                        <tr key={book.id} className="hover:bg-gray-50 transition-colors">
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="text-sm font-medium text-gray-900">{book.title}</div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="text-sm text-gray-900">{book.author}</div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="text-sm text-gray-900">{book.isbn || '-'}</div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="text-sm text-gray-900">{book.barcode || '-'}</div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="text-sm text-gray-900">{book.shelf || '-'}</div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="text-sm text-gray-900">{book.genre || '-'}</div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
            
            {books.length > 0 && (
              <div className="text-center text-sm text-gray-500">
                Showing {books.length} books
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

export default App;