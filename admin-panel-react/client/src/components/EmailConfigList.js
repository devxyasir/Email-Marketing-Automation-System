import React, { useState, useEffect } from 'react';
import { Container, Table, Button, Card } from 'react-bootstrap';
import { FaTrash, FaEye, FaEyeSlash } from 'react-icons/fa';
import axios from 'axios';

const EmailConfigList = () => {
  const [emailConfigs, setEmailConfigs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showPasswords, setShowPasswords] = useState({});

  // Fetch email configurations
  const fetchEmailConfigs = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/email-configs');
      setEmailConfigs(response.data);
      setError(null);
    } catch (err) {
      setError('Failed to load email configurations');
      console.error('Error fetching email configurations:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEmailConfigs();
  }, []);

  // Delete email configuration
  const handleDelete = async (id) => {
    if (window.confirm('Are you sure you want to delete this email configuration?')) {
      try {
        await axios.delete(`/api/email-configs/${id}`);
        // Refresh the list
        fetchEmailConfigs();
      } catch (err) {
        setError('Failed to delete email configuration');
        console.error('Error deleting email configuration:', err);
      }
    }
  };

  // Toggle password visibility
  const togglePasswordVisibility = (id) => {
    setShowPasswords(prev => ({
      ...prev,
      [id]: !prev[id]
    }));
  };

  // Format date
  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString();
  };

  return (
    <Container>
      <div className="page-title">
        <h1>Email Configurations</h1>
      </div>

      {loading ? (
        <p>Loading email configurations...</p>
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
                  <th>Hardware ID</th>
                  <th>Email</th>
                  <th>Password</th>
                  <th>SMTP Server</th>
                  <th>SMTP Port</th>
                  <th>Provider</th>
                  <th>Last Updated</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {emailConfigs.length === 0 ? (
                  <tr>
                    <td colSpan="8" className="text-center">
                      No email configurations found
                    </td>
                  </tr>
                ) : (
                  emailConfigs.map((config) => (
                    <tr key={config._id}>
                      <td>
                        {config.hardware_id 
                          ? `${config.hardware_id.substring(0, 8)}...`
                          : 'N/A'}
                      </td>
                      <td>{config.email}</td>
                      <td>
                        <div className="d-flex align-items-center">
                          {showPasswords[config._id] 
                            ? config.password_encrypted 
                              ? "********" // Don't show encrypted passwords
                              : config.password
                            : "********"}
                          <Button
                            variant="link"
                            size="sm"
                            className="p-0 ms-2"
                            onClick={() => togglePasswordVisibility(config._id)}
                            title={showPasswords[config._id] ? 'Hide Password' : 'Show Password'}
                          >
                            {showPasswords[config._id] ? <FaEyeSlash /> : <FaEye />}
                          </Button>
                        </div>
                      </td>
                      <td>{config.smtp_server}</td>
                      <td>{config.smtp_port}</td>
                      <td>{config.provider}</td>
                      <td>{formatDate(config.last_updated)}</td>
                      <td className="action-buttons">
                        <Button
                          variant="danger"
                          size="sm"
                          className="btn-icon"
                          onClick={() => handleDelete(config._id)}
                          title="Delete Configuration"
                        >
                          <FaTrash />
                        </Button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </Table>
          </Card.Body>
        </Card>
      )}
    </Container>
  );
};

export default EmailConfigList;
