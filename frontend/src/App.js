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

  const deleteAllData = async () => {
    // Double confirmation for safety
    const firstConfirm = window.confirm(
      '⚠️ WARNING: This will delete ALL directories and business data permanently!\n\n' +
      'Are you absolutely sure you want to delete everything?\n\n' +
      'This action cannot be undone!'
    );
    
    if (!firstConfirm) return;
    
    const secondConfirm = window.confirm(
      '🚨 FINAL CONFIRMATION\n\n' +
      `You are about to delete:\n` +
      `• ${stats.totalDirectories} directories\n` +
      `• ${stats.totalBusinesses} business contacts\n\n` +
      'Type "DELETE" in the next prompt to confirm...'
    );
    
    if (!secondConfirm) return;
    
    const finalConfirm = window.prompt(
      'Type "DELETE" (in capital letters) to confirm deletion:'
    );
    
    if (finalConfirm !== 'DELETE') {
      alert('❌ Deletion cancelled - text did not match "DELETE"');
      return;
    }
    
    setLoading(true);
    
    try {
      const response = await axios.delete(`${API}/delete-all-data`);
      
      if (response.data.success) {
        alert(`✅ Successfully deleted all data!\n\n${response.data.message}`);
        
        // Reset all state
        setDirectories([]);
        setBusinesses([]);
        setSelectedDirectory(null);
        setSearchResults([]);
        setStats({
          totalDirectories: 0,
          scrapedDirectories: 0,
          totalBusinesses: 0,
          businessesWithPhone: 0,
          businessesWithEmail: 0
        });
        
        // Go back to discover tab
        setActiveTab('discover');
      }
      
    } catch (error) {
      console.error('Error deleting all data:', error);
      alert(`❌ Error deleting data: ${error.message}`);
    } finally {
      setLoading(false);
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
            <div className="flex items-center gap-4">
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
              
              {/* Delete All Data Button */}
              {(stats.totalDirectories > 0 || stats.totalBusinesses > 0) && (
                <button
                  onClick={deleteAllData}
                  disabled={loading}
                  className="px-4 py-2 bg-red-600/20 border border-red-400/30 text-red-100 rounded-md hover:bg-red-600/30 disabled:bg-gray-600/20 disabled:text-gray-400 transition-all duration-200 text-sm font-medium"
                  title="Delete all directories and business data"
                >
                  <div className="flex items-center gap-2">
                    🗑️ Clear All Data
                  </div>
                </button>
              )}
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
            <div className="flex items-center gap-3 mb-6">
              <span className="text-2xl">📁</span>
              <div>
                <h2 className="text-xl font-semibold text-gray-900">Directory Management Center</h2>
                <p className="text-sm text-gray-600">Scrape business data from discovered directories and manage your lead sources</p>
              </div>
            </div>

            {/* Status Summary */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
              <div className="bg-blue-50 p-4 rounded-lg text-center">
                <div className="text-2xl font-bold text-blue-600">{stats.totalDirectories}</div>
                <div className="text-sm text-blue-600">Total Directories</div>
              </div>
              <div className="bg-green-50 p-4 rounded-lg text-center">
                <div className="text-2xl font-bold text-green-600">{stats.scrapedDirectories}</div>
                <div className="text-sm text-green-600">Scraped & Ready</div>
              </div>
              <div className="bg-purple-50 p-4 rounded-lg text-center">
                <div className="text-2xl font-bold text-purple-600">{stats.totalBusinesses.toLocaleString()}</div>
                <div className="text-sm text-purple-600">Total Businesses</div>
              </div>
              <div className="bg-orange-50 p-4 rounded-lg text-center">
                <div className="text-2xl font-bold text-orange-600">{stats.businessesWithPhone.toLocaleString()}</div>
                <div className="text-sm text-orange-600">With Phone Numbers</div>
              </div>
            </div>

            {/* Action Guide */}
            <div className="bg-green-50 border-l-4 border-green-400 p-4 mb-6">
              <div className="flex">
                <div className="flex-shrink-0">
                  <span className="text-green-400 text-lg">🎯</span>
                </div>
                <div className="ml-3">
                  <h4 className="text-green-800 font-medium">How to Extract Business Data</h4>
                  <div className="text-sm text-green-700 mt-1">
                    <p className="mb-1"><strong>Green "Scrape" buttons:</strong> Click to extract business data from that directory</p>
                    <p className="mb-1"><strong>Blue "View Businesses" buttons:</strong> See extracted business contacts</p>
                    <p><strong>Gray "Export CSV" buttons:</strong> Download contact list for your CRM/outreach tools</p>
                  </div>
                </div>
              </div>
            </div>

            {directories.length === 0 ? (
              <div className="text-center py-12">
                <div className="text-6xl mb-4">📂</div>
                <h3 className="text-lg font-medium text-gray-900 mb-2">No Directories Yet</h3>
                <p className="text-gray-600 mb-4">
                  Start by discovering directories in the "Discover New Leads" tab above.
                </p>
                <button
                  onClick={() => setActiveTab('discover')}
                  className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
                >
                  🔍 Discover New Leads
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                {directories.map((directory) => (
                  <div key={directory.id} className="border border-gray-200 rounded-lg p-5 hover:border-blue-300 transition-colors">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <h4 className="font-semibold text-gray-900 text-lg">{directory.name}</h4>
                          <span className={`text-xs px-3 py-1 rounded-full font-medium ${
                            directory.scrape_status === 'scraped' 
                              ? 'bg-green-100 text-green-800' 
                              : directory.scrape_status === 'failed'
                              ? 'bg-red-100 text-red-800'
                              : 'bg-yellow-100 text-yellow-800'
                          }`}>
                            {directory.scrape_status === 'scraped' ? '✅ Ready' : 
                             directory.scrape_status === 'failed' ? '❌ Failed' : '⏳ Pending'}
                          </span>
                        </div>
                        <p className="text-sm text-gray-500 mb-2">🌐 {directory.url}</p>
                        <div className="flex items-center gap-4 text-sm">
                          <span className="inline-block bg-blue-100 text-blue-800 px-2 py-1 rounded-full">
                            📂 {directory.directory_type}
                          </span>
                          <span className="text-gray-600">
                            📍 {directory.location}
                          </span>
                          {directory.business_count > 0 && (
                            <span className="text-green-600 font-medium">
                              👥 {directory.business_count} businesses extracted
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex flex-col gap-2 ml-4">
                        {directory.scrape_status === 'scraped' ? (
                          <>
                            <button
                              onClick={(e) => {
                                e.preventDefault();
                                console.log('Button clicked, directory:', directory);
                                viewBusinesses(directory);
                              }}
                              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors font-medium shadow-md"
                            >
                              <div className="flex items-center gap-2">
                                👁️ View {directory.business_count || 0} Businesses
                              </div>
                            </button>
                            <button
                              onClick={() => exportBusinesses(directory.id, directory.name)}
                              disabled={exportLoading}
                              className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-400 transition-colors font-medium shadow-md"
                            >
                              {exportLoading ? (
                                <div className="flex items-center gap-2">
                                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                                  Exporting...
                                </div>
                              ) : (
                                <div className="flex items-center gap-2">
                                  📥 Export CSV
                                </div>
                              )}
                            </button>
                          </>
                        ) : (
                          <button
                            onClick={() => scrapeDirectory(directory)}
                            disabled={loading}
                            className="px-6 py-2 bg-gradient-to-r from-green-600 to-green-700 text-white rounded-md hover:from-green-700 hover:to-green-800 disabled:bg-gray-400 transition-all duration-200 font-semibold shadow-md"
                          >
                            {loading ? (
                              <div className="flex items-center gap-2">
                                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                                Scraping...
                              </div>
                            ) : (
                              <div className="flex items-center gap-2">
                                🚀 Scrape Businesses
                              </div>
                            )}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
                
                {directories.filter(d => d.scrape_status === 'scraped').length > 0 && (
                  <div className="mt-6 p-4 bg-blue-50 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-blue-600">💼</span>
                      <h4 className="font-medium text-blue-800">Bulk Export Option</h4>
                    </div>
                    <div className="flex items-center justify-between">
                      <p className="text-sm text-blue-700">
                        Export all businesses from all scraped directories as one master CSV file
                      </p>
                      <button
                        onClick={() => exportBusinesses()}
                        disabled={exportLoading}
                        className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 transition-colors font-medium"
                      >
                        {exportLoading ? 'Exporting...' : '📊 Export All Businesses'}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {activeTab === 'businesses' && (
          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex items-center gap-3 mb-6">
              <span className="text-2xl">👥</span>
              <div>
                <h2 className="text-xl font-semibold text-gray-900">Business Contact Database</h2>
                <p className="text-sm text-gray-600">View and export business contacts for your outreach campaigns</p>
              </div>
            </div>

            {/* Contact Statistics */}
            {businesses.length > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                <div className="bg-blue-50 p-4 rounded-lg text-center">
                  <div className="text-2xl font-bold text-blue-600">{businesses.length}</div>
                  <div className="text-sm text-blue-600">Total Contacts</div>
                </div>
                <div className="bg-green-50 p-4 rounded-lg text-center">
                  <div className="text-2xl font-bold text-green-600">
                    {businesses.filter(b => b.phone).length}
                  </div>
                  <div className="text-sm text-green-600">With Phone Numbers</div>
                </div>
                <div className="bg-purple-50 p-4 rounded-lg text-center">
                  <div className="text-2xl font-bold text-purple-600">
                    {businesses.filter(b => b.email).length}
                  </div>
                  <div className="text-sm text-purple-600">With Email Addresses</div>
                </div>
                <div className="bg-orange-50 p-4 rounded-lg text-center">
                  <div className="text-2xl font-bold text-orange-600">
                    {businesses.filter(b => b.website).length}
                  </div>
                  <div className="text-sm text-orange-600">With Websites</div>
                </div>
              </div>
            )}

            {/* Directory Selection and Export */}
            <div className="flex items-center justify-between mb-6 p-4 bg-gray-50 rounded-lg">
              <div className="flex items-center gap-3">
                {selectedDirectory ? (
                  <>
                    <span className="text-green-600">✅</span>
                    <div>
                      <div className="font-medium text-gray-900">Viewing: {selectedDirectory.name}</div>
                      <div className="text-sm text-gray-600">
                        {businesses.length} business contacts • Click "View Businesses" from any directory in "Manage Directories" to change source
                      </div>
                    </div>
                  </>
                ) : (
                  <>
                    <span className="text-yellow-600">⚠️</span>
                    <div>
                      <div className="font-medium text-gray-900">No Directory Selected</div>
                      <div className="text-sm text-gray-600">
                        Go to "Manage Directories" and click "View Businesses" on any scraped directory
                      </div>
                    </div>
                  </>
                )}
              </div>
              {selectedDirectory && businesses.length > 0 && (
                <div className="flex gap-2">
                  <button
                    onClick={() => exportBusinesses(selectedDirectory.id, selectedDirectory.name)}
                    disabled={exportLoading}
                    className="px-6 py-2 bg-gradient-to-r from-green-600 to-green-700 text-white rounded-md hover:from-green-700 hover:to-green-800 disabled:bg-gray-400 transition-all duration-200 font-semibold shadow-md"
                  >
                    {exportLoading ? (
                      <div className="flex items-center gap-2">
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                        Exporting...
                      </div>
                    ) : (
                      <div className="flex items-center gap-2">
                        📥 Export {businesses.length} Contacts
                      </div>
                    )}
                  </button>
                  <button
                    onClick={() => exportBusinesses()}
                    disabled={exportLoading}
                    className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
                  >
                    📊 Export All ({stats.totalBusinesses})
                  </button>
                </div>
              )}
            </div>

            {/* Business Contacts Table */}
            {businesses.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        <div className="flex items-center gap-1">
                          🏢 Business Name
                        </div>
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        <div className="flex items-center gap-1">
                          📞 Phone Number
                        </div>
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        <div className="flex items-center gap-1">
                          📧 Email Address
                        </div>
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        <div className="flex items-center gap-1">
                          🌐 Website
                        </div>
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        <div className="flex items-center gap-1">
                          📍 Address
                        </div>
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        <div className="flex items-center gap-1">
                          🎯 SDR Actions
                        </div>
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {businesses.map((business, index) => (
                      <tr key={business.id || index} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center">
                            <div>
                              <div className="text-sm font-medium text-gray-900">
                                {business.business_name || 'N/A'}
                              </div>
                              {business.contact_person && (
                                <div className="text-sm text-gray-500">
                                  Contact: {business.contact_person}
                                </div>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            {business.phone ? (
                              <>
                                <span className="text-green-600">📞</span>
                                <a
                                  href={`tel:${business.phone}`}
                                  className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                                >
                                  {business.phone}
                                </a>
                              </>
                            ) : (
                              <span className="text-gray-400 text-sm">No phone</span>
                            )}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            {business.email ? (
                              <>
                                <span className="text-green-600">📧</span>
                                <a
                                  href={`mailto:${business.email}`}
                                  className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                                >
                                  {business.email}
                                </a>
                              </>
                            ) : (
                              <span className="text-gray-400 text-sm">No email</span>
                            )}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            {business.website ? (
                              <>
                                <span className="text-green-600">🌐</span>
                                <a
                                  href={business.website}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-sm text-blue-600 hover:text-blue-800 font-medium truncate max-w-32"
                                >
                                  {business.website.replace(/^https?:\/\//, '').split('/')[0]}
                                </a>
                              </>
                            ) : (
                              <span className="text-gray-400 text-sm">No website</span>
                            )}
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <div className="text-sm text-gray-900 max-w-48">
                            {business.address || <span className="text-gray-400">No address</span>}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex gap-1">
                            {business.phone && (
                              <a
                                href={`tel:${business.phone}`}
                                className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs hover:bg-green-200 transition-colors"
                                title="Call this business"
                              >
                                📞 Call
                              </a>
                            )}
                            {business.email && (
                              <a
                                href={`mailto:${business.email}?subject=Partnership Opportunity with The Guild Of Honour`}
                                className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs hover:bg-blue-200 transition-colors"
                                title="Email this business"
                              >
                                📧 Email
                              </a>
                            )}
                            {business.website && (
                              <a
                                href={business.website}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs hover:bg-purple-200 transition-colors"
                                title="Visit business website"
                              >
                                🌐 Visit
                              </a>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-12">
                {selectedDirectory ? (
                  <>
                    <div className="text-6xl mb-4">📭</div>
                    <h3 className="text-lg font-medium text-gray-900 mb-2">No Businesses Found</h3>
                    <p className="text-gray-600 mb-4">
                      The directory "{selectedDirectory.name}" hasn't been scraped yet or contains no business listings.
                    </p>
                    <button
                      onClick={() => scrapeDirectory(selectedDirectory)}
                      className="px-6 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
                    >
                      🚀 Scrape This Directory
                    </button>
                  </>
                ) : (
                  <>
                    <div className="text-6xl mb-4">👥</div>
                    <h3 className="text-lg font-medium text-gray-900 mb-2">Select a Directory to View Businesses</h3>
                    <p className="text-gray-600 mb-4">
                      Go to "Manage Directories" and click "View Businesses" on any scraped directory to see business contacts here.
                    </p>
                    <button
                      onClick={() => setActiveTab('directories')}
                      className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
                    >
                      📁 Go to Manage Directories
                    </button>
                  </>
                )}
              </div>
            )}

            {businesses.length > 0 && (
              <div className="mt-6 p-4 bg-yellow-50 border-l-4 border-yellow-400">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-yellow-600">💡</span>
                  <h4 className="font-medium text-yellow-800">SDR Pro Tips</h4>
                </div>
                <div className="text-sm text-yellow-700 space-y-1">
                  <p>• <strong>Quick Actions:</strong> Use the "Call", "Email", and "Visit" buttons in each row for immediate outreach</p>
                  <p>• <strong>Email Template:</strong> The email links include "Guild Of Honour" in the subject line automatically</p>
                  <p>• <strong>CSV Export:</strong> Perfect for importing into your CRM (HubSpot, Salesforce, etc.)</p>
                  <p>• <strong>Data Quality:</strong> All contacts have been verified and filtered for accuracy</p>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default App;