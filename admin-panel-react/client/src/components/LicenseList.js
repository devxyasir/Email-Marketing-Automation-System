import React, { useState, useEffect } from 'react';
import { Container, Table, Button, Badge, Card } from 'react-bootstrap';
import { FaTrash, FaSync } from 'react-icons/fa';
import axios from 'axios';

const LicenseList = () => {
  const [licenses, setLicenses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch licenses data
  const fetchLicenses = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/users');
      setLicenses(response.data);
      setError(null);
    } catch (err) {
      setError('Failed to load licenses');
      console.error('Error fetching licenses:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLicenses();
  }, []);

  // Delete license
  const handleDelete = async (id) => {
    if (window.confirm('Are you sure you want to delete this license?')) {
      try {
        await axios.delete(`/api/users/${id}`);
        // Refresh the licenses list
        fetchLicenses();
      } catch (err) {
        setError('Failed to delete license');
        console.error('Error deleting license:', err);
      }
    }
  };

  // Reset a license (remove system ID binding)
  const handleReset = async (id) => {
    if (window.confirm('Are you sure you want to reset this license? This will remove it from the current system.')) {
      try {
        await axios.put(`/api/users/${id}`, {
          active: false,
          registered_system_id: null
        });
        // Refresh the licenses list
        fetchLicenses();
      } catch (err) {
        setError('Failed to reset license');
        console.error('Error resetting license:', err);
      }
    }
  };

  // Format date
  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString();
  };

  // Calculate status
  const getLicenseStatus = (license) => {
    if (!license.Active) {
      return { status: 'Inactive', variant: 'secondary' };
    }
    
    if (license.expiryDate) {
      const now = new Date();
      const expiry = new Date(license.expiryDate);
      
      if (now > expiry) {
        return { status: 'Expired', variant: 'danger' };
      }
      
      // Check if expiring within 7 days
      const sevenDays = 7 * 24 * 60 * 60 * 1000;
      if (expiry - now < sevenDays) {
        return { status: 'Expiring Soon', variant: 'warning' };
      }
    }
    
    return { status: 'Active', variant: 'success' };
  };

  return (
    <Container>
      <div className="page-title">
        <h1>License Management</h1>
      </div>

      {loading ? (
        <p>Loading licenses...</p>
      ) : error ? (
        <div className="alert alert-danger" role="alert">
          {error}
        </div>
      ) : (
        <Card>
          <Card.Body>
            <Table responsive hover>
              <thead>
                <tr>
                  <th>License Code</th>
                  <th>Status</th>
                  <th>System ID</th>
                  <th>Time Frame</th>
                  <th>Expires</th>
                  <th>Activated</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {licenses.length === 0 ? (
                  <tr>
                    <td colSpan="7" className="text-center">
                      No licenses found
                    </td>
                  </tr>
                ) : (
                  licenses.map((license) => {
                    const status = getLicenseStatus(license);
                    return (
                      <tr key={license._id}>
                        <td>{license.License_Code}</td>
                        <td>
                          <Badge bg={status.variant}>
                            {status.status}
                          </Badge>
                        </td>
                        <td>
                          {license.registered_system_id 
                            ? license.registered_system_id.substring(0, 8) + '...'
                            : 'Not Registered'}
                        </td>
                        <td>{license.timeFrame || 'Unlimited'}</td>
                        <td>{formatDate(license.expiryDate)}</td>
                        <td>{formatDate(license.activationDate)}</td>
                        <td className="action-buttons">
                          {license.registered_system_id && (
                            <Button
                              variant="warning"
                              size="sm"
                              className="btn-icon"
                              onClick={() => handleReset(license._id)}
                              title="Reset License"
                            >
                              <FaSync />
                            </Button>
                          )}
                          <Button
                            variant="danger"
                            size="sm"
                            className="btn-icon"
                            onClick={() => handleDelete(license._id)}
                            title="Delete License"
                          >
                            <FaTrash />
                          </Button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </Table>
          </Card.Body>
        </Card>
      )}
    </Container>
  );
};

export default LicenseList;
