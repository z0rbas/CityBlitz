import React, { useState, useEffect } from "react";
import "./App.css";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const App = () => {
  const [activeTab, setActiveTab] = useState('discover');
  const [location, setLocation] = useState('Tampa Bay');
  const [directories, setDirectories] = useState([]);
  const [businesses, setBusinesses] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedDirectory, setSelectedDirectory] = useState(null);
  const [searchResults, setSearchResults] = useState([]);

  const [progressLogs, setProgressLogs] = useState([]);
  const [showLogs, setShowLogs] = useState(false);

  // Fetch directories on component mount
  useEffect(() => {
    fetchDirectories();
  }, []);

  const fetchDirectories = async () => {
    try {
      const response = await axios.get(`${API}/directories`);
      setDirectories(response.data);
    } catch (error) {
      console.error('Error fetching directories:', error);
    }
  };

  const fetchBusinesses = async (directoryId = null) => {
    console.log('fetchBusinesses called with directoryId:', directoryId);
    try {
      const url = directoryId ? `${API}/businesses?directory_id=${directoryId}` : `${API}/businesses`;
      console.log('Making API call to:', url);
      const response = await axios.get(url);
      console.log('API response:', response.data);
      setBusinesses(response.data);
    } catch (error) {
      console.error('Error fetching businesses:', error);
    }
  };

  const discoverDirectories = async () => {
    setLoading(true);
    setProgressLogs([]);
    setShowLogs(true);
    
    try {
      const response = await axios.post(`${API}/discover-directories`, {
        location: location,
        directory_types: ["chamber of commerce", "business directory", "better business bureau"],
        max_results: 20
      });
      
      setSearchResults(response.data.directories);
      setProgressLogs(response.data.progress_log || []);
      await fetchDirectories();
    } catch (error) {
      console.error('Error discovering directories:', error);
      alert('Error discovering directories. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const scrapeDirectory = async (directoryId) => {
    setLoading(true);
    setProgressLogs([]);
    setShowLogs(true);
    
    try {
      const response = await axios.post(`${API}/scrape-directory`, {
        directory_id: directoryId
      });
      
      setProgressLogs(response.data.progress_log || []);
      alert(`Successfully scraped ${response.data.businesses_found} businesses!`);
      await fetchDirectories();
      if (selectedDirectory?.id === directoryId) {
        await fetchBusinesses(directoryId);
      }
    } catch (error) {
      console.error('Error scraping directory:', error);
      alert('Error scraping directory. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const exportToCsv = async (directoryId) => {
    try {
      const response = await axios.get(`${API}/export-csv/${directoryId}`);
      
      // Create and download CSV file
      const element = document.createElement('a');
      const file = new Blob([response.data.csv_content], { type: 'text/csv' });
      element.href = URL.createObjectURL(file);
      element.download = response.data.filename;
      document.body.appendChild(element);
      element.click();
      document.body.removeChild(element);
    } catch (error) {
      console.error('Error exporting CSV:', error);
      alert('Error exporting CSV. Please try again.');
    }
  };

  const viewBusinesses = async (directory) => {
    // Alert to test if function is being called
    alert(`viewBusinesses called with directory: ${directory?.name || 'No name'}`);
    
    console.log('=== viewBusinesses called ===');
    console.log('Directory:', directory);
    console.log('Directory ID:', directory?.id);
    
    if (!directory || !directory.id) {
      console.error('No directory or directory ID provided');
      alert('Error: No directory selected');
      return;
    }
    
    // Set states synchronously first
    setActiveTab('businesses');
    setSelectedDirectory(directory);
    setLoading(true);
    setBusinesses([]); // Clear existing businesses
    
    try {
      console.log('About to call API with ID:', directory.id);
      
      // Make API call directly
      const url = `${API}/businesses?directory_id=${directory.id}`;
      console.log('Making API call to:', url);
      
      const response = await axios.get(url);
      console.log('API response status:', response.status);
      console.log('API response data length:', response.data.length);
      console.log('Sample business:', response.data[0] || 'No businesses');
      
      // Update businesses state
      setBusinesses(response.data);
      console.log('Businesses state updated with', response.data.length, 'businesses');
      
    } catch (error) {
      console.error('Error in viewBusinesses:', error);
      console.error('Error response:', error.response?.data);
      alert(`Error loading businesses: ${error.message}`);
    } finally {
      setLoading(false);
      console.log('viewBusinesses completed');
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Chamber Directory Scraper</h1>
              <p className="text-gray-600 mt-1">Discover and scrape business directories automatically</p>
            </div>
            <div className="flex items-center space-x-4">
              <div className="bg-blue-50 px-4 py-2 rounded-lg">
                <span className="text-sm font-medium text-blue-800">Directories: {directories.length}</span>
              </div>
              <div className="bg-green-50 px-4 py-2 rounded-lg">
                <span className="text-sm font-medium text-green-800">Businesses: {businesses.length}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="flex space-x-1 bg-gray-100 p-1 rounded-lg mb-6">
          <button
            onClick={() => setActiveTab('discover')}
            className={`flex-1 py-2 px-4 text-sm font-medium rounded-md transition-colors ${
              activeTab === 'discover' 
                ? 'bg-white text-blue-600 shadow-sm' 
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            🔍 Discover Directories
          </button>
          <button
            onClick={() => setActiveTab('directories')}
            className={`flex-1 py-2 px-4 text-sm font-medium rounded-md transition-colors ${
              activeTab === 'directories' 
                ? 'bg-white text-blue-600 shadow-sm' 
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            📁 Manage Directories
          </button>
          <button
            onClick={() => setActiveTab('businesses')}
            className={`flex-1 py-2 px-4 text-sm font-medium rounded-md transition-colors ${
              activeTab === 'businesses' 
                ? 'bg-white text-blue-600 shadow-sm' 
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            👥 View Businesses
          </button>
        </div>

        {/* Progress Logs */}
        {showLogs && progressLogs.length > 0 && (
          <div className="bg-gray-900 text-green-400 p-4 rounded-lg mb-6 font-mono text-sm">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-white font-semibold">🔍 Processing Log</h3>
              <button
                onClick={() => setShowLogs(false)}
                className="text-gray-400 hover:text-white"
              >
                ✕
              </button>
            </div>
            <div className="max-h-40 overflow-y-auto">
              {progressLogs.map((log, index) => (
                <div key={index} className="mb-1">
                  {log}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Content */}
        {activeTab === 'discover' && (
          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="mb-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">Discover New Directories</h2>
              <div className="flex gap-4 items-end">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-gray-700 mb-2">Location</label>
                  <input
                    type="text"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Enter location (e.g., Tampa Bay, Miami, Orlando)"
                  />
                </div>
                <button
                  onClick={discoverDirectories}
                  disabled={loading}
                  className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                >
                  {loading ? 'Discovering...' : 'Discover Directories'}
                </button>
              </div>
            </div>

            {searchResults.length > 0 && (
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-4">Recent Discovery Results</h3>
                <div className="grid gap-4">
                  {searchResults.map((directory) => (
                    <div key={directory.id} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <h4 className="font-medium text-gray-900">{directory.name}</h4>
                          <p className="text-sm text-gray-500">{directory.url}</p>
                          <span className="inline-block bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded-full mt-2">
                            {directory.directory_type}
                          </span>
                        </div>
                        <button
                          onClick={() => scrapeDirectory(directory.id)}
                          className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
                        >
                          Scrape Now
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'directories' && (
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Discovered Directories</h2>
            <div className="grid gap-4">
              {directories.map((directory) => (
                <div key={directory.id} className="border border-gray-200 rounded-lg p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <h4 className="font-medium text-gray-900">{directory.name}</h4>
                      <p className="text-sm text-gray-500">{directory.url}</p>
                      <div className="flex items-center space-x-4 mt-2">
                        <span className="inline-block bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded-full">
                          {directory.directory_type}
                        </span>
                        <span className="text-sm text-gray-500">
                          📍 {directory.location}
                        </span>
                        <span className={`text-xs px-2 py-1 rounded-full ${
                          directory.scrape_status === 'scraped' 
                            ? 'bg-green-100 text-green-800' 
                            : directory.scrape_status === 'failed'
                            ? 'bg-red-100 text-red-800'
                            : 'bg-yellow-100 text-yellow-800'
                        }`}>
                          {directory.scrape_status}
                        </span>
                        {directory.business_count > 0 && (
                          <span className="text-sm text-gray-500">
                            👥 {directory.business_count} businesses
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex space-x-2">
                      {directory.scrape_status === 'scraped' && (
                        <>
                          <button
                            onClick={() => {
                              alert('Button clicked!');
                              viewBusinesses(directory);
                            }}
                            className="px-3 py-1 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors text-sm"
                          >
                            View Businesses
                          </button>
                          <button
                            onClick={() => exportToCsv(directory.id)}
                            className="px-3 py-1 bg-gray-600 text-white rounded-md hover:bg-gray-700 transition-colors text-sm"
                          >
                            Export CSV
                          </button>
                        </>
                      )}
                      {directory.scrape_status !== 'scraped' && (
                        <button
                          onClick={() => scrapeDirectory(directory.id)}
                          disabled={loading}
                          className="px-3 py-1 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-400 transition-colors text-sm"
                        >
                          {loading ? 'Scraping...' : 'Scrape'}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'businesses' && (
          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-gray-900">
                Business Contacts
                {selectedDirectory && (
                  <span className="text-sm font-normal text-gray-500 ml-2">
                    from {selectedDirectory.name}
                  </span>
                )}
              </h2>
              {selectedDirectory && (
                <button
                  onClick={() => exportToCsv(selectedDirectory.id)}
                  className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
                >
                  Export to CSV
                </button>
              )}
            </div>

            <div className="overflow-x-auto">
              {/* Debug information */}
              <div className="mb-4 p-2 bg-gray-100 rounded text-sm">
                <strong>Debug Info:</strong> 
                <br />Businesses array length: {businesses.length}
                <br />Selected directory: {selectedDirectory?.name || 'None'}
                <br />Selected directory ID: {selectedDirectory?.id || 'None'}
                <br />Loading state: {loading ? 'True' : 'False'}
                {businesses.length > 0 && (
                  <>
                    <br />Sample business: {businesses[0]?.business_name || 'No name'}
                    <br />Sample phone: {businesses[0]?.phone || 'No phone'}
                  </>
                )}
              </div>
              
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Business Name
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Contact Person
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Phone
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Email
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Website
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Socials
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {businesses.length === 0 ? (
                    <tr>
                      <td colSpan="6" className="px-6 py-4 text-center text-gray-500">
                        {loading ? 'Loading businesses...' : 'No businesses found. Click "View Businesses" on a scraped directory.'}
                      </td>
                    </tr>
                  ) : (
                    businesses.map((business) => (
                      <tr key={business.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm font-medium text-gray-900">{business.business_name}</div>
                          {business.address && (
                            <div className="text-sm text-gray-500">{business.address}</div>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {business.contact_person || '-'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {business.phone ? (
                            <a href={`tel:${business.phone}`} className="text-blue-600 hover:text-blue-900">
                              {business.phone}
                            </a>
                          ) : '-'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {business.email ? (
                            <a href={`mailto:${business.email}`} className="text-blue-600 hover:text-blue-900">
                              {business.email}
                            </a>
                          ) : '-'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {business.website ? (
                            <a href={business.website} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-900">
                              Visit
                            </a>
                          ) : '-'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {business.socials ? (
                            <div className="max-w-xs truncate" title={business.socials}>
                              {business.socials}
                            </div>
                          ) : '-'}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default App;