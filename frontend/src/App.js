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
  const [exportLoading, setExportLoading] = useState(false);

  const [progressLogs, setProgressLogs] = useState([]);
  const [showLogs, setShowLogs] = useState(false);

  // Stats for SDR dashboard
  const [stats, setStats] = useState({
    totalDirectories: 0,
    scrapedDirectories: 0,
    totalBusinesses: 0,
    businessesWithPhone: 0,
    businessesWithEmail: 0
  });

  // Fetch directories on component mount
  useEffect(() => {
    fetchDirectories();
    calculateStats();
  }, []);

  const fetchDirectories = async () => {
    try {
      const response = await axios.get(`${API}/directories`);
      setDirectories(response.data);
      calculateStats();
    } catch (error) {
      console.error('Error fetching directories:', error);
    }
  };

  const calculateStats = async () => {
    try {
      const dirResponse = await axios.get(`${API}/directories`);
      const directories = dirResponse.data;
      
      const bizResponse = await axios.get(`${API}/businesses`);
      const businesses = bizResponse.data;

      setStats({
        totalDirectories: directories.length,
        scrapedDirectories: directories.filter(d => d.scrape_status === 'scraped').length,
        totalBusinesses: businesses.length,
        businessesWithPhone: businesses.filter(b => b.phone).length,
        businessesWithEmail: businesses.filter(b => b.email).length
      });
    } catch (error) {
      console.error('Error calculating stats:', error);
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
    console.log('=== viewBusinesses called ===');
    console.log('Directory:', directory);
    console.log('Directory ID:', directory?.id);
    
    if (!directory || !directory.id) {
      console.error('No directory or directory ID provided');
      alert('❌ Error: Please select a valid directory first');
      return;
    }
    
    // Show loading state immediately
    setLoading(true);
    setActiveTab('businesses');
    setSelectedDirectory(directory);
    setBusinesses([]); // Clear existing businesses
    
    try {
      console.log('About to call API with ID:', directory.id);
      
      // Make API call directly
      const url = `${API}/businesses?directory_id=${directory.id}`;
      console.log('Making API call to:', url);
      
      const response = await axios.get(url);
      console.log('API response status:', response.status);
      console.log('API response data length:', response.data.length);
      
      // Update businesses state
      setBusinesses(response.data);
      console.log('Businesses state updated with', response.data.length, 'businesses');
      
      // Show success message
      if (response.data.length > 0) {
        alert(`✅ Success! Found ${response.data.length} businesses in ${directory.name}`);
      } else {
        alert(`ℹ️ No businesses found in ${directory.name}. This directory may need to be scraped first.`);
      }
      
    } catch (error) {
      console.error('Error in viewBusinesses:', error);
      alert(`❌ Error loading businesses: ${error.message}`);
    } finally {
      setLoading(false);
      console.log('viewBusinesses completed');
    }
  };

  const scrapeDirectory = async (directory) => {
    if (!directory || !directory.id) {
      alert('❌ Error: Please select a valid directory');
      return;
    }

    setLoading(true);
    setProgressLogs([]);
    setShowLogs(true);

    try {
      const response = await axios.post(`${API}/scrape-directory`, {
        directory_id: directory.id
      });

      if (response.data.success) {
        alert(`✅ Successfully scraped ${response.data.businesses_count} businesses from ${directory.name}!`);
        await fetchDirectories(); // Refresh directories to show updated status
        calculateStats(); // Update stats
      } else {
        alert(`❌ Scraping failed: ${response.data.message}`);
      }
    } catch (error) {
      console.error('Error scraping directory:', error);
      alert(`❌ Error: ${error.message}`);
    } finally {
      setLoading(false);
      setShowLogs(false);
    }
  };

  const exportBusinesses = async (directoryId = null, directoryName = null) => {
    setExportLoading(true);
    
    try {
      const url = directoryId 
        ? `${API}/export-businesses?directory_id=${directoryId}`
        : `${API}/export-businesses`;
      
      const response = await axios.get(url, {
        responseType: 'blob'
      });

      // Create download
      const blob = new Blob([response.data], { type: 'text/csv' });
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      
      const filename = directoryName 
        ? `${directoryName.replace(/[^a-zA-Z0-9]/g, '_')}_businesses.csv`
        : 'all_businesses.csv';
      
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(downloadUrl);

      const businessCount = directoryId ? businesses.length : stats.totalBusinesses;
      alert(`✅ Successfully exported ${businessCount} businesses to ${filename}!`);
      
    } catch (error) {
      console.error('Error exporting businesses:', error);
      alert(`❌ Export failed: ${error.message}`);
    } finally {
      setExportLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header with branding and stats */}
      <div className="bg-gradient-to-r from-blue-600 to-blue-800 text-white">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold">🏢 Business Directory Scraper</h1>
              <p className="text-blue-100 mt-1">Generate high-quality leads for The Guild Of Honour SDR team</p>
            </div>
            <div className="bg-white/10 rounded-lg p-4">
              <div className="grid grid-cols-2 gap-4 text-center">
                <div>
                  <div className="text-2xl font-bold">{stats.totalBusinesses.toLocaleString()}</div>
                  <div className="text-xs text-blue-100">Total Businesses</div>
                </div>
                <div>
                  <div className="text-2xl font-bold">{stats.scrapedDirectories}</div>
                  <div className="text-xs text-blue-100">Ready Directories</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* SDR Guide Section */}
      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="bg-blue-50 border-l-4 border-blue-400 p-4 mb-6">
          <div className="flex">
            <div className="flex-shrink-0">
              <div className="text-blue-400 text-xl">💡</div>
            </div>
            <div className="ml-3">
              <h3 className="text-lg font-medium text-blue-800">SDR Quick Start Guide</h3>
              <div className="mt-2 text-sm text-blue-700">
                <p className="mb-2"><strong>Step 1:</strong> Search for chambers in your target city using "Discover New Leads"</p>
                <p className="mb-2"><strong>Step 2:</strong> Scrape business data from discovered directories using "Manage Directories"</p>
                <p><strong>Step 3:</strong> View and export business contacts for outreach using "View Businesses"</p>
              </div>
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex space-x-1 bg-gray-100 p-1 rounded-lg mb-6">
          <button
            onClick={() => setActiveTab('discover')}
            className={`flex-1 py-3 px-4 text-sm font-medium rounded-md transition-colors flex items-center justify-center gap-2 ${
              activeTab === 'discover' 
                ? 'bg-white text-blue-600 shadow-sm' 
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <span className="text-lg">🔍</span>
            <div className="text-left">
              <div className="font-semibold">Discover New Leads</div>
              <div className="text-xs opacity-75">Find chambers in any city</div>
            </div>
          </button>
          <button
            onClick={() => setActiveTab('directories')}
            className={`flex-1 py-3 px-4 text-sm font-medium rounded-md transition-colors flex items-center justify-center gap-2 ${
              activeTab === 'directories' 
                ? 'bg-white text-blue-600 shadow-sm' 
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <span className="text-lg">📁</span>
            <div className="text-left">
              <div className="font-semibold">Manage Directories</div>
              <div className="text-xs opacity-75">Scrape business data</div>
            </div>
          </button>
          <button
            onClick={() => setActiveTab('businesses')}
            className={`flex-1 py-3 px-4 text-sm font-medium rounded-md transition-colors flex items-center justify-center gap-2 ${
              activeTab === 'businesses' 
                ? 'bg-white text-blue-600 shadow-sm' 
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <span className="text-lg">👥</span>
            <div className="text-left">
              <div className="font-semibold">View Businesses</div>
              <div className="text-xs opacity-75">Export contact lists</div>
            </div>
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
              <div className="flex items-center gap-3 mb-4">
                <span className="text-2xl">🎯</span>
                <div>
                  <h2 className="text-xl font-semibold text-gray-900">Discover New Lead Sources</h2>
                  <p className="text-sm text-gray-600">Find chambers of commerce and business directories in any city to generate leads</p>
                </div>
              </div>
              
              <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-6">
                <div className="flex">
                  <div className="flex-shrink-0">
                    <span className="text-yellow-400 text-lg">⚡</span>
                  </div>
                  <div className="ml-3">
                    <p className="text-sm text-yellow-700">
                      <strong>Pro Tip:</strong> The AI scraper automatically finds business directories from any chamber's main website. 
                      It works with all website types - WordPress, custom CMS, JavaScript-heavy sites, and more!
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex gap-4 items-end">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    🌍 Target City or Region
                  </label>
                  <input
                    type="text"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    className="w-full px-4 py-3 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-lg"
                    placeholder="Enter any city (e.g., Tampa Bay, Miami, Chicago, Dallas)"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    💡 Works with any US city - the AI will find all relevant chambers and business directories
                  </p>
                </div>
                <button
                  onClick={discoverDirectories}
                  disabled={loading}
                  className="px-8 py-3 bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-md hover:from-blue-700 hover:to-blue-800 disabled:bg-gray-400 disabled:cursor-not-allowed transition-all duration-200 font-semibold shadow-lg"
                >
                  {loading ? (
                    <div className="flex items-center gap-2">
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                      Discovering...
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      🔍 Find New Leads
                    </div>
                  )}
                </button>
              </div>
            </div>

            {searchResults.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-4">
                  <span className="text-lg">🎉</span>
                  <h3 className="text-lg font-medium text-gray-900">Discovery Results - Ready to Scrape!</h3>
                </div>
                <div className="grid gap-4">
                  {searchResults.map((directory) => (
                    <div key={directory.id} className="border border-gray-200 rounded-lg p-4 hover:border-blue-300 transition-colors">
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            <h4 className="font-medium text-gray-900">{directory.name}</h4>
                            <span className="inline-block bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded-full">
                              {directory.directory_type}
                            </span>
                          </div>
                          <p className="text-sm text-gray-500 mb-2">{directory.url}</p>
                          <p className="text-xs text-green-600">
                            ✅ Ready to scrape - AI will automatically find their business directory page
                          </p>
                        </div>
                        <button
                          onClick={() => scrapeDirectory(directory)}
                          disabled={loading}
                          className="px-6 py-2 bg-gradient-to-r from-green-600 to-green-700 text-white rounded-md hover:from-green-700 hover:to-green-800 disabled:bg-gray-400 transition-all duration-200 font-semibold shadow-md"
                        >
                          <div className="flex items-center gap-2">
                            🚀 Scrape Businesses
                          </div>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-4 p-4 bg-green-50 rounded-lg">
                  <p className="text-sm text-green-700">
                    <strong>Next Step:</strong> Click "Scrape Businesses" on any directory above to extract business contacts. 
                    The AI will automatically find their business directory page and extract phone numbers, emails, and websites!
                  </p>
                </div>
              </div>
            )}

            {searchResults.length === 0 && !loading && (
              <div className="text-center py-12">
                <div className="text-6xl mb-4">🎯</div>
                <h3 className="text-lg font-medium text-gray-900 mb-2">Ready to Find New Leads?</h3>
                <p className="text-gray-600 mb-4">
                  Enter a city name above and click "Find New Leads" to discover chambers of commerce and business directories.
                </p>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-3xl mx-auto text-sm">
                  <div className="bg-blue-50 p-4 rounded-lg">
                    <div className="text-blue-600 text-2xl mb-2">🌍</div>
                    <div className="font-medium text-blue-800">Universal Discovery</div>
                    <div className="text-blue-600">Works with any website technology</div>
                  </div>
                  <div className="bg-green-50 p-4 rounded-lg">
                    <div className="text-green-600 text-2xl mb-2">⚡</div>
                    <div className="font-medium text-green-800">AI-Powered</div>
                    <div className="text-green-600">Automatically finds business directories</div>
                  </div>
                  <div className="bg-purple-50 p-4 rounded-lg">
                    <div className="text-purple-600 text-2xl mb-2">📊</div>
                    <div className="font-medium text-purple-800">High Quality Data</div>
                    <div className="text-purple-600">Clean, verified business contacts</div>
                  </div>
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
                            onClick={(e) => {
                              e.preventDefault();
                              console.log('Button clicked, directory:', directory);
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