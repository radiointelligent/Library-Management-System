import React, { useState, useEffect, useCallback, useRef } from "react";
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
  const [selectedSearchStatus, setSelectedSearchStatus] = useState("");
  const [uploadStatus, setUploadStatus] = useState(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [currentView, setCurrentView] = useState("upload"); // upload, catalog, scanner
  const [currentBook, setCurrentBook] = useState(null);
  const [isViewerOpen, setIsViewerOpen] = useState(false);
  const [enhancementStatus, setEnhancementStatus] = useState(null);
  const [batchProgress, setBatchProgress] = useState(null);
  
  // Scanner mode state
  const [scannerMode, setScannerMode] = useState(false);
  const [selectedShelfForScanner, setSelectedShelfForScanner] = useState("");
  const [barcodeInput, setBarcodeInput] = useState("");
  const [scanHistory, setScanHistory] = useState([]);
  const [scanStats, setScanStats] = useState({ success: 0, error: 0 });
  const [autoEnhanceOnUpload, setAutoEnhanceOnUpload] = useState(false);
  const [selectedBooks, setSelectedBooks] = useState([]);
  const [bulkShelf, setBulkShelf] = useState("");
  
  const barcodeInputRef = useRef(null);

  // Sound for scan feedback
  const playSuccessSound = () => {
    const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmMeBC+D0O/Vfj0KIXbQ6t2CNA0YZrrt6yEREAg=');
    audio.volume = 0.3;
    audio.play().catch(() => {});
  };

  const playErrorSound = () => {
    const audio = new Audio('data:audio/wav;base64,UklGRhIEAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YeoDAACGhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmMeBC+D0O/Vfj0KIXbQ6t2CNA0YZrrt6yEREAg=');
    audio.volume = 0.5;
    audio.play().catch(() => {});
  };

  // Fetch books with filters
  const fetchBooks = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      
      if (searchTerm) params.append('search', searchTerm);
      if (selectedGenre) params.append('genre', selectedGenre);
      if (selectedShelf) params.append('shelf', selectedShelf);
      if (selectedAuthor) params.append('author', selectedAuthor);
      if (selectedSearchStatus) params.append('search_status', selectedSearchStatus);
      
      const response = await axios.get(`${API}/books?${params.toString()}`);
      setBooks(response.data);
    } catch (error) {
      console.error("Error fetching books:", error);
      setBooks([]);
    } finally {
      setLoading(false);
    }
  }, [searchTerm, selectedGenre, selectedShelf, selectedAuthor, selectedSearchStatus]);

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

  // Focus barcode input when scanner mode is activated
  useEffect(() => {
    if (scannerMode && barcodeInputRef.current) {
      barcodeInputRef.current.focus();
    }
  }, [scannerMode, selectedShelfForScanner]);

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
    
    const url = autoEnhanceOnUpload 
      ? `${API}/books/upload?auto_enhance=true`
      : `${API}/books/upload`;
    
    try {
      const response = await axios.post(url, formData, {
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

  // Barcode scanning functions
  const handleBarcodeScanning = async (barcode) => {
    if (!selectedShelfForScanner || !barcode.trim()) {
      return;
    }

    try {
      const response = await axios.post(`${API}/books/scan-assign-shelf`, {
        barcode: barcode.trim(),
        shelf: selectedShelfForScanner
      });

      if (response.data.success) {
        playSuccessSound();
        setScanHistory(prev => [{
          id: Date.now(),
          barcode: barcode.trim(),
          title: response.data.book_title,
          author: response.data.book_author,
          shelf: response.data.shelf_assigned,
          auto_enhanced: response.data.auto_enhanced,
          timestamp: new Date(),
          success: true
        }, ...prev.slice(0, 49)]); // Keep only last 50 scans

        setScanStats(prev => ({ ...prev, success: prev.success + 1 }));
        
        // Show brief success message
        setEnhancementStatus({
          type: 'success',
          message: `✅ ${response.data.book_title} → Shelf ${response.data.shelf_assigned}` + 
                   (response.data.auto_enhanced ? ' (Enhanced!)' : '')
        });
        
        setTimeout(() => setEnhancementStatus(null), 3000);

      } else {
        throw new Error('Assignment failed');
      }

    } catch (error) {
      playErrorSound();
      setScanHistory(prev => [{
        id: Date.now(),
        barcode: barcode.trim(),
        title: 'Unknown Book',
        author: '',
        shelf: selectedShelfForScanner,
        timestamp: new Date(),
        success: false,
        error: error.response?.data?.detail || 'Book not found'
      }, ...prev.slice(0, 49)]);

      setScanStats(prev => ({ ...prev, error: prev.error + 1 }));
      
      setEnhancementStatus({
        type: 'error',
        message: `❌ Barcode ${barcode.trim()}: ${error.response?.data?.detail || 'Book not found'}`
      });
      
      setTimeout(() => setEnhancementStatus(null), 5000);
    }
  };

  const handleBarcodeSubmit = (e) => {
    e.preventDefault();
    if (barcodeInput.trim()) {
      handleBarcodeScanning(barcodeInput);
      setBarcodeInput('');
      
      // Refocus input for continuous scanning
      setTimeout(() => {
        if (barcodeInputRef.current) {
          barcodeInputRef.current.focus();
        }
      }, 100);
    }
  };

  const startScannerMode = () => {
    if (!selectedShelfForScanner) {
      alert('Please select a shelf first');
      return;
    }
    setScannerMode(true);
    setScanHistory([]);
    setScanStats({ success: 0, error: 0 });
  };

  const stopScannerMode = () => {
    setScannerMode(false);
    setBarcodeInput('');
    fetchBooks(); // Refresh books after scanning session
    fetchStats(); // Refresh stats
  };

  // Bulk shelf assignment
  const handleBulkShelfAssignment = async () => {
    if (selectedBooks.length === 0) {
      alert('Please select books first');
      return;
    }
    
    if (!bulkShelf) {
      alert('Please select a shelf');
      return;
    }

    try {
      const response = await axios.post(`${API}/books/batch-shelf-assignment`, selectedBooks, {
        params: { shelf: bulkShelf }
      });

      if (response.data.success) {
        alert(`Successfully assigned shelf ${bulkShelf} to ${response.data.updated_count} books`);
        setSelectedBooks([]);
        setBulkShelf('');
        fetchBooks();
        fetchStats();
      }

    } catch (error) {
      console.error("Bulk assignment error:", error);
      alert(error.response?.data?.detail || "Bulk assignment failed");
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

  // Book enhancement functions
  const enhanceSingleBook = async (bookId) => {
    try {
      setEnhancementStatus({ type: 'loading', message: 'Searching Google Books...' });
      
      const response = await axios.post(`${API}/books/${bookId}/enhance`);
      
      if (response.data.success) {
        setEnhancementStatus({
          type: 'success',
          message: `Book enhanced successfully! Updated: ${response.data.enhanced_fields.join(', ')}`
        });
        fetchBooks();
        fetchStats();
      } else {
        setEnhancementStatus({
          type: 'warning',
          message: response.data.message
        });
      }
      
      setTimeout(() => setEnhancementStatus(null), 5000);
      
    } catch (error) {
      console.error("Enhancement error:", error);
      setEnhancementStatus({
        type: 'error',
        message: error.response?.data?.detail || "Enhancement failed"
      });
      setTimeout(() => setEnhancementStatus(null), 5000);
    }
  };

  const enhanceAllPendingBooks = async () => {
    try {
      const pendingBooks = books.filter(book => book.search_status === 'pending');
      if (pendingBooks.length === 0) {
        alert('No pending books to enhance');
        return;
      }

      const confirm = window.confirm(
        `Enhance ${pendingBooks.length} pending books? This may take several minutes.`
      );
      
      if (!confirm) return;

      setBatchProgress({ current: 0, total: pendingBooks.length });
      
      const response = await axios.post(`${API}/books/enhance-batch`, {
        enhance_all_pending: true
      });

      setBatchProgress(null);
      
      if (response.data.success) {
        alert(`Batch enhancement completed! Enhanced ${response.data.enhanced_count} of ${response.data.total_processed} books.`);
        fetchBooks();
        fetchStats();
      }
      
    } catch (error) {
      setBatchProgress(null);
      console.error("Batch enhancement error:", error);
      alert(error.response?.data?.detail || "Batch enhancement failed");
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
      if (selectedSearchStatus) params.append('search_status', selectedSearchStatus);
      
      const response = await axios.get(`${API}/books/export?${params.toString()}`, {
        responseType: 'blob',
      });
      
      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      
      // Extract filename from headers or use default
      const contentDisposition = response.headers['content-disposition'];
      let filename = 'library_books_enhanced.xlsx';
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
    setSelectedSearchStatus("");
  };

  const openBookViewer = (book) => {
    setCurrentBook(book);
    setIsViewerOpen(true);
  };

  const closeBookViewer = () => {
    setCurrentBook(null);
    setIsViewerOpen(false);
  };

  const getStatusBadgeClass = (status) => {
    switch (status) {
      case 'found':
        return 'bg-green-100 text-green-800';
      case 'not_found':
        return 'bg-red-100 text-red-800';
      case 'searching':
        return 'bg-yellow-100 text-yellow-800';
      case 'pending':
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'found':
        return 'Found';
      case 'not_found':
        return 'Not Found';
      case 'searching':
        return 'Searching...';
      case 'pending':
      default:
        return 'Pending';
    }
  };

  const getGenreText = (genre) => {
    const genreMap = {
      'fic': 'Fiction',
      'nf': 'Non-Fiction',
      'bio': 'Biography',
      'sci': 'Science',
      'his': 'History',
      'mys': 'Mystery',
      'rom': 'Romance',
      'fan': 'Fantasy',
      'adv': 'Adventure'
    };
    return genreMap[genre] || genre || '—';
  };

  // Generate shelf options (1-120)
  const shelfOptions = Array.from({ length: 120 }, (_, i) => i + 1);

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
                  📚 Library Management System
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
                📁 Upload Books
              </button>
              <button
                onClick={() => setCurrentView('catalog')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  currentView === 'catalog'
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
                }`}
              >
                📖 Book Catalog
              </button>
              <button
                onClick={() => setCurrentView('scanner')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  currentView === 'scanner'
                    ? 'bg-green-100 text-green-700'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
                }`}
              >
                📱 Barcode Scanner
              </button>
            </nav>
          </div>
        </div>
      </header>

      {/* Stats Bar */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
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
              <div className="text-2xl font-bold text-orange-600">{stats.total_shelves || 0}/120</div>
              <div className="text-sm text-gray-500">Shelves Used</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-500">{stats.search_status?.found || 0}</div>
              <div className="text-sm text-gray-500">🔍 Enhanced</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-yellow-500">{stats.search_status?.pending || 0}</div>
              <div className="text-sm text-gray-500">⏳ Pending</div>
            </div>
          </div>
        </div>
      </div>

      {/* Enhancement Status */}
      {enhancementStatus && (
        <div className={`mx-auto max-w-7xl px-4 py-2`}>
          <div className={`p-3 rounded-lg flex items-center ${
            enhancementStatus.type === 'success' ? 'bg-green-100 text-green-800' :
            enhancementStatus.type === 'error' ? 'bg-red-100 text-red-800' :
            enhancementStatus.type === 'warning' ? 'bg-yellow-100 text-yellow-800' :
            'bg-blue-100 text-blue-800'
          }`}>
            {enhancementStatus.type === 'loading' && (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-current mr-2"></div>
            )}
            <span>{enhancementStatus.message}</span>
          </div>
        </div>
      )}

      {/* Batch Progress */}
      {batchProgress && (
        <div className="mx-auto max-w-7xl px-4 py-2">
          <div className="bg-blue-100 p-4 rounded-lg">
            <div className="flex justify-between items-center mb-2">
              <span className="text-blue-800">Enhancing books...</span>
              <span className="text-blue-800">{batchProgress.current}/{batchProgress.total}</span>
            </div>
            <div className="w-full bg-blue-200 rounded-full h-2">
              <div 
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{width: `${(batchProgress.current / batchProgress.total) * 100}%`}}
              ></div>
            </div>
          </div>
        </div>
      )}

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        
        {/* Upload View */}
        {currentView === 'upload' && (
          <div className="space-y-8">
            {/* Upload Section */}
            <div className="bg-white rounded-xl shadow-lg p-8">
              <div className="text-center mb-8">
                <h2 className="text-3xl font-bold text-gray-900 mb-4">📚 Upload Your Library Catalog</h2>
                <p className="text-lg text-gray-600 max-w-2xl mx-auto">
                  Upload your Excel file containing book data. We support .xlsx and .xls formats with columns for Title, Author, ISBN, Barcode, Shelf, and Genre.
                </p>
                <p className="text-sm text-blue-600 mt-2">
                  🔍 <strong>NEW:</strong> Books will be automatically enhanced with information from Google Books API!
                </p>
              </div>

              {/* Auto-enhance option */}
              <div className="mb-6 p-4 bg-green-50 rounded-lg border border-green-200">
                <label className="flex items-center space-x-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={autoEnhanceOnUpload}
                    onChange={(e) => setAutoEnhanceOnUpload(e.target.checked)}
                    className="w-4 h-4 text-green-600 bg-gray-100 border-gray-300 rounded focus:ring-green-500"
                  />
                  <div>
                    <div className="font-medium text-green-800">🚀 Auto-enhance during upload</div>
                    <div className="text-sm text-green-600">
                      Automatically search Google Books and enhance each book during upload (slower but complete)
                    </div>
                  </div>
                </label>
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
                      <span className="text-blue-600">
                        {autoEnhanceOnUpload ? 'Processing and enhancing...' : 'Processing file...'}
                      </span>
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
                          {uploadStatus.auto_enhanced > 0 && (
                            <span className="text-green-600 font-medium">
                              <br />🚀 Auto-enhanced {uploadStatus.auto_enhanced} books with Google Books data!
                            </span>
                          )}
                          <br />📍 Books are ready for Google Books enhancement in the catalog view.
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
                <h3 className="text-lg font-medium text-blue-900 mb-3">📋 Required Excel Format</h3>
                <div className="text-blue-800 space-y-2">
                  <p><span className="font-medium">Required columns:</span> Title, Author</p>
                  <p><span className="font-medium">Optional columns:</span> ISBN, Barcode, Shelf, Genre</p>
                  <p className="text-sm text-blue-600">Column names are case-insensitive. The system will automatically detect and validate your file structure.</p>
                  <p className="text-sm text-green-600 mt-3">
                    🚀 <strong>Auto-Enhancement:</strong> After upload, use the "🔍 Enhance All Pending" button to automatically fill in missing information like authors, ISBNs, descriptions, and genres from Google Books!
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Scanner View */}
        {currentView === 'scanner' && (
          <div className="space-y-8">
            <div className="bg-white rounded-xl shadow-lg p-8">
              <div className="text-center mb-8">
                <h2 className="text-3xl font-bold text-gray-900 mb-4">📱 Barcode Scanner & Shelf Assignment</h2>
                <p className="text-lg text-gray-600">
                  Select a shelf number, then scan barcodes to assign books instantly. Books will be automatically enhanced with Google Books data.
                </p>
              </div>

              {/* Scanner Setup */}
              {!scannerMode ? (
                <div className="max-w-md mx-auto space-y-6">
                  <div>
                    <label className="block text-lg font-medium text-gray-700 mb-3">Select Shelf (1-120)</label>
                    <select
                      value={selectedShelfForScanner}
                      onChange={(e) => setSelectedShelfForScanner(e.target.value)}
                      className="w-full p-4 text-lg border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    >
                      <option value="">Choose Shelf...</option>
                      {shelfOptions.map(shelf => (
                        <option key={shelf} value={shelf}>
                          Shelf {shelf} ({stats.shelf_distribution?.[shelf] || 0} books)
                        </option>
                      ))}
                    </select>
                  </div>

                  <button
                    onClick={startScannerMode}
                    disabled={!selectedShelfForScanner}
                    className="w-full py-4 px-6 bg-green-600 text-white text-lg font-semibold rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    🚀 Start Scanning Mode
                  </button>
                </div>
              ) : (
                /* Scanner Active Mode */
                <div className="space-y-6">
                  {/* Scanner Header */}
                  <div className="bg-green-50 border border-green-200 rounded-lg p-6">
                    <div className="flex justify-between items-center mb-4">
                      <div>
                        <h3 className="text-xl font-bold text-green-800">📱 Scanner Active</h3>
                        <p className="text-green-600">Assigning to Shelf {selectedShelfForScanner}</p>
                      </div>
                      <button
                        onClick={stopScannerMode}
                        className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
                      >
                        ⏹️ Stop Scanning
                      </button>
                    </div>

                    {/* Scan Stats */}
                    <div className="grid grid-cols-2 gap-4">
                      <div className="text-center p-4 bg-white rounded-lg">
                        <div className="text-2xl font-bold text-green-600">{scanStats.success}</div>
                        <div className="text-sm text-gray-600">Successful</div>
                      </div>
                      <div className="text-center p-4 bg-white rounded-lg">
                        <div className="text-2xl font-bold text-red-600">{scanStats.error}</div>
                        <div className="text-sm text-gray-600">Errors</div>
                      </div>
                    </div>
                  </div>

                  {/* Barcode Input */}
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
                    <form onSubmit={handleBarcodeSubmit} className="space-y-4">
                      <label className="block text-lg font-medium text-blue-800 mb-3">
                        📋 Scan or Enter Barcode
                      </label>
                      <input
                        ref={barcodeInputRef}
                        type="text"
                        value={barcodeInput}
                        onChange={(e) => setBarcodeInput(e.target.value)}
                        placeholder="Scan barcode here..."
                        className="w-full p-4 text-lg border border-blue-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        autoFocus
                      />
                      <button
                        type="submit"
                        disabled={!barcodeInput.trim()}
                        className="w-full py-3 px-6 bg-blue-600 text-white text-lg font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        ✅ Assign to Shelf {selectedShelfForScanner}
                      </button>
                    </form>
                  </div>

                  {/* Scan History */}
                  {scanHistory.length > 0 && (
                    <div className="bg-gray-50 rounded-lg p-6">
                      <h4 className="text-lg font-bold text-gray-800 mb-4">📋 Recent Scans</h4>
                      <div className="space-y-2 max-h-96 overflow-y-auto">
                        {scanHistory.slice(0, 10).map((scan) => (
                          <div
                            key={scan.id}
                            className={`p-3 rounded-lg border ${
                              scan.success
                                ? 'bg-green-50 border-green-200 text-green-800'
                                : 'bg-red-50 border-red-200 text-red-800'
                            }`}
                          >
                            <div className="flex justify-between items-start">
                              <div>
                                <div className="font-medium">
                                  {scan.success ? '✅' : '❌'} {scan.title}
                                  {scan.auto_enhanced && ' 🚀'}
                                </div>
                                <div className="text-sm opacity-75">
                                  {scan.author} • Barcode: {scan.barcode} • Shelf: {scan.shelf}
                                </div>
                                {scan.error && (
                                  <div className="text-sm font-medium">Error: {scan.error}</div>
                                )}
                              </div>
                              <div className="text-xs opacity-60">
                                {scan.timestamp.toLocaleTimeString()}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Catalog View */}
        {currentView === 'catalog' && (
          <div className="space-y-6">
            {/* Enhancement Controls */}
            <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl p-6 border border-blue-200">
              <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
                <div>
                  <h3 className="text-lg font-semibold text-blue-900 mb-2">🔍 Google Books Enhancement</h3>
                  <p className="text-blue-700 text-sm">
                    Automatically find authors, ISBNs, descriptions, cover images, and genres for your books.
                    <br />
                    <strong>Pending books:</strong> {stats.search_status?.pending || 0} • <strong>Enhanced:</strong> {stats.search_status?.found || 0}
                  </p>
                </div>
                <div className="flex gap-3">
                  <button
                    onClick={enhanceAllPendingBooks}
                    disabled={loading || (stats.search_status?.pending || 0) === 0}
                    className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2 font-medium"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                    🔍 Enhance All Pending ({stats.search_status?.pending || 0})
                  </button>
                </div>
              </div>
            </div>

            {/* Bulk Actions */}
            {selectedBooks.length > 0 && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-6">
                <div className="flex justify-between items-center">
                  <div>
                    <h3 className="text-lg font-semibold text-yellow-800">
                      📦 Bulk Actions ({selectedBooks.length} books selected)
                    </h3>
                  </div>
                  <div className="flex gap-3">
                    <select
                      value={bulkShelf}
                      onChange={(e) => setBulkShelf(e.target.value)}
                      className="px-3 py-2 border border-yellow-300 rounded-lg focus:ring-2 focus:ring-yellow-500"
                    >
                      <option value="">Select Shelf...</option>
                      {shelfOptions.map(shelf => (
                        <option key={shelf} value={shelf}>Shelf {shelf}</option>
                      ))}
                    </select>
                    <button
                      onClick={handleBulkShelfAssignment}
                      disabled={!bulkShelf}
                      className="px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 disabled:opacity-50 transition-colors"
                    >
                      Assign Shelf
                    </button>
                    <button
                      onClick={() => setSelectedBooks([])}
                      className="px-4 py-2 text-gray-600 hover:text-gray-800 rounded-lg transition-colors"
                    >
                      Clear Selection
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Search and Filter Section */}
            <div className="bg-white rounded-xl shadow-lg p-6">
              <div className="grid grid-cols-1 lg:grid-cols-6 gap-4 items-end">
                {/* Search */}
                <div className="lg:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-2">Search</label>
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
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Genre</label>
                  <select
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    value={selectedGenre}
                    onChange={(e) => setSelectedGenre(e.target.value)}
                  >
                    <option value="">All Genres</option>
                    {stats.genres?.map((genre) => (
                      <option key={genre} value={genre}>{getGenreText(genre)}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Shelf</label>
                  <select
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    value={selectedShelf}
                    onChange={(e) => setSelectedShelf(e.target.value)}
                  >
                    <option value="">All Shelves</option>
                    {shelfOptions.map(shelf => (
                      <option key={shelf} value={shelf}>Shelf {shelf}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Status</label>
                  <select
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    value={selectedSearchStatus}
                    onChange={(e) => setSelectedSearchStatus(e.target.value)}
                  >
                    <option value="">All Status</option>
                    <option value="pending">⏳ Pending</option>
                    <option value="found">✅ Found</option>
                    <option value="not_found">❌ Not Found</option>
                    <option value="searching">🔍 Searching</option>
                  </select>
                </div>

                <div className="flex gap-2">
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
                    Export
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
                        <th className="px-6 py-3 text-left">
                          <input
                            type="checkbox"
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelectedBooks(books.map(book => book.id));
                              } else {
                                setSelectedBooks([]);
                              }
                            }}
                            checked={selectedBooks.length === books.length && books.length > 0}
                            className="w-4 h-4 text-blue-600"
                          />
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Title</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Author</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ISBN</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Genre</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Shelf</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {books.map((book) => (
                        <tr key={book.id} className="hover:bg-gray-50 transition-colors">
                          <td className="px-6 py-4">
                            <input
                              type="checkbox"
                              checked={selectedBooks.includes(book.id)}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setSelectedBooks([...selectedBooks, book.id]);
                                } else {
                                  setSelectedBooks(selectedBooks.filter(id => id !== book.id));
                                }
                              }}
                              className="w-4 h-4 text-blue-600"
                            />
                          </td>
                          <td className="px-6 py-4">
                            <div 
                              className="text-sm font-medium text-blue-600 hover:text-blue-800 cursor-pointer"
                              onClick={() => openBookViewer(book)}
                            >
                              {book.title}
                            </div>
                            {book.barcode && (
                              <div className="text-xs text-gray-500">{book.barcode}</div>
                            )}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="text-sm text-gray-900">{book.author || '—'}</div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="text-sm text-gray-900">{book.isbn || '—'}</div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                              book.genre ? 'bg-purple-100 text-purple-800' : 'bg-gray-100 text-gray-800'
                            }`}>
                              {getGenreText(book.genre)}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="text-sm text-gray-900">{book.shelf ? `Shelf ${book.shelf}` : '—'}</div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusBadgeClass(book.search_status)}`}>
                              {getStatusText(book.search_status)}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                            <button
                              onClick={() => openBookViewer(book)}
                              className="text-blue-600 hover:text-blue-900 transition-colors"
                              title="View Details"
                            >
                              👁️ View
                            </button>
                            {book.search_status === 'pending' && (
                              <button
                                onClick={() => enhanceSingleBook(book.id)}
                                className="text-green-600 hover:text-green-900 transition-colors"
                                title="Enhance with Google Books"
                              >
                                🔍 Enhance
                              </button>
                            )}
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

      {/* Book Viewer Modal */}
      {isViewerOpen && currentBook && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl max-w-4xl w-full max-h-[90vh] overflow-auto">
            <div className="p-6">
              <div className="flex justify-between items-start mb-6">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900 mb-2">{currentBook.title}</h2>
                  <p className="text-gray-600">{currentBook.author}</p>
                  <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full mt-2 ${getStatusBadgeClass(currentBook.search_status)}`}>
                    {getStatusText(currentBook.search_status)}
                  </span>
                </div>
                <button
                  onClick={closeBookViewer}
                  className="text-gray-400 hover:text-gray-600 text-2xl"
                >
                  ✕
                </button>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Book Cover */}
                <div className="text-center">
                  {currentBook.image_url ? (
                    <img
                      src={currentBook.image_url}
                      alt={`Cover of ${currentBook.title}`}
                      className="w-full max-w-64 h-auto rounded-lg shadow-md mx-auto"
                      onError={(e) => {
                        e.target.style.display = 'none';
                        e.target.nextSibling.style.display = 'flex';
                      }}
                    />
                  ) : (
                    <div className="w-full max-w-64 h-80 bg-gray-200 rounded-lg shadow-md mx-auto flex items-center justify-center">
                      <span className="text-gray-500">No Cover</span>
                    </div>
                  )}
                  <div className="mt-4 text-sm text-gray-600">
                    {currentBook.page_count && <p>Pages: {currentBook.page_count}</p>}
                    {currentBook.categories && currentBook.categories.length > 0 && (
                      <p>Categories: {currentBook.categories.slice(0, 3).join(', ')}</p>
                    )}
                  </div>
                </div>

                {/* Book Details */}
                <div className="lg:col-span-2 space-y-6">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700">ISBN</label>
                      <p className="mt-1 text-sm text-gray-900">{currentBook.isbn || '—'}</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700">Barcode</label>
                      <p className="mt-1 text-sm text-gray-900">{currentBook.barcode || '—'}</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700">Genre</label>
                      <p className="mt-1 text-sm text-gray-900">{getGenreText(currentBook.genre)}</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700">Shelf</label>
                      <p className="mt-1 text-sm text-gray-900">{currentBook.shelf ? `Shelf ${currentBook.shelf}` : '—'}</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700">AR Level</label>
                      <p className="mt-1 text-sm text-gray-900">{currentBook.ar_level || '—'}</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700">Lexile</label>
                      <p className="mt-1 text-sm text-gray-900">{currentBook.lexile || '—'}</p>
                    </div>
                  </div>

                  {/* Description */}
                  {currentBook.description && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">Description</label>
                      <div className="bg-gray-50 rounded-lg p-4 max-h-40 overflow-y-auto">
                        <p className="text-sm text-gray-700 leading-relaxed">{currentBook.description}</p>
                      </div>
                    </div>
                  )}

                  {/* Russian Description */}
                  {currentBook.description_ru && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">Описание (русский)</label>
                      <div className="bg-gray-50 rounded-lg p-4 max-h-40 overflow-y-auto">
                        <p className="text-sm text-gray-700 leading-relaxed">{currentBook.description_ru}</p>
                      </div>
                    </div>
                  )}

                  {/* Enhancement Button */}
                  {currentBook.search_status === 'pending' && (
                    <div className="pt-4 border-t">
                      <button
                        onClick={() => {
                          enhanceSingleBook(currentBook.id);
                          closeBookViewer();
                        }}
                        className="w-full py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center justify-center gap-2"
                      >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                        </svg>
                        🔍 Enhance with Google Books
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;