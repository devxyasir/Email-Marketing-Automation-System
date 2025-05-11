import React, { useState, useEffect } from 'react';
import { Container, Table, Button, Badge, Card } from 'react-bootstrap';
import { Link } from 'react-router-dom';
import { FaEdit, FaTrash, FaPlus } from 'react-icons/fa';
import axios from 'axios';

const UserList = () => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch users data
  const fetchUsers = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/users');
      setUsers(response.data);
      setError(null);
    } catch (err) {
      setError('Failed to load users');
      console.error('Error fetching users:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  // Delete user
  const handleDelete = async (id) => {
    if (window.confirm('Are you sure you want to delete this license?')) {
      try {
        await axios.delete(`/api/users/${id}`);
        // Refresh the users list
        fetchUsers();
      } catch (err) {
        setError('Failed to delete license');
        console.error('Error deleting license:', err);
      }
    }
  };

  // Format date
  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString();
  };

  return (
    <Container>
      <div className="page-title">
        <h1>License Management</h1>
        <Link to="/users/add">
          <Button variant="primary">
            <FaPlus /> Add New License
          </Button>
        </Link>
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
                  <th>System ID</th>
                  <th>Time Frame</th>
                  <th>Expires</th>
                  <th>Activated</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.length === 0 ? (
                  <tr>
                    <td colSpan="6" className="text-center">
                      No licenses found
                    </td>
                  </tr>
                ) : (
                  users.map((user) => (
                    <tr key={user._id}>
                      <td>{user.License_Code}</td>
                      <td>
                        {user.registered_system_id 
                          ? user.registered_system_id.substring(0, 8) + '...'
                          : <Badge bg="secondary">Not Registered</Badge>}
                      </td>
                      <td>{user.timeFrame || 'Unlimited'}</td>
                      <td>{formatDate(user.expiryDate)}</td>
                      <td>{formatDate(user.activationDate)}</td>
                      <td className="action-buttons">
                        <Link to={`/users/edit/${user._id}`}>
                          <Button variant="info" size="sm" className="btn-icon">
                            <FaEdit />
                          </Button>
                        </Link>
                        <Button
                          variant="danger"
                          size="sm"
                          className="btn-icon"
                          onClick={() => handleDelete(user._id)}
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

export default UserList;
