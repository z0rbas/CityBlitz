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
    try {
      const url = directoryId ? `${API}/businesses?directory_id=${directoryId}` : `${API}/businesses`;
      const response = await axios.get(url);
      setBusinesses(response.data);
    } catch (error) {
      console.error('Error fetching businesses:', error);
    }
  };

  const discoverDirectories = async () => {
    setLoading(true);
    try {
      const response = await axios.post(`${API}/discover-directories`, {
        location: location,
        directory_types: ["chamber of commerce", "business directory", "better business bureau"],
        max_results: 20
      });
      
      setSearchResults(response.data.directories);
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
    try {
      const response = await axios.post(`${API}/scrape-directory`, {
        directory_id: directoryId
      });
      
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
    setSelectedDirectory(directory);
    await fetchBusinesses(directory.id);
    setActiveTab('businesses');
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
                            onClick={() => viewBusinesses(directory)}
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
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Business Name
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Contact
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
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {businesses.map((business) => (
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
                        {business.phone || '-'}
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
                    </tr>
                  ))}
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