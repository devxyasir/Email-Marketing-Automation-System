import React, { useState, useEffect } from 'react';
import { Container, Form, Button, Card } from 'react-bootstrap';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';

const UserForm = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const isEditMode = !!id;

  // Form state
  const [formData, setFormData] = useState({
    licenseCode: '',
    expiryDays: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Fetch user data if in edit mode
  useEffect(() => {
    const fetchUser = async () => {
      if (isEditMode) {
        try {
          setLoading(true);
          const response = await axios.get(`/api/users/${id}`);
          const userData = response.data;
          
          // Format data for form
          setFormData({
            licenseCode: userData.License_Code || '',
            expiryDays: '' // We don't set existing expiry days, to avoid accidental extension
          });
          
          setError(null);
        } catch (err) {
          setError('Failed to load user data');
          console.error('Error fetching user:', err);
        } finally {
          setLoading(false);
        }
      }
    };

    fetchUser();
  }, [id, isEditMode]);

  // Handle form input changes
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData({
      ...formData,
      [name]: value
    });
  };

  // Handle form submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    try {
      setLoading(true);
      
      if (isEditMode) {
        // Update existing user
        await axios.put(`/api/users/${id}`, formData);
      } else {
        // Create new user
        await axios.post('/api/users', formData);
      }
      
      // Redirect back to user list
      navigate('/users');
    } catch (err) {
      setError(`Failed to ${isEditMode ? 'update' : 'create'} user`);
      console.error('Error saving user:', err);
      setLoading(false);
    }
  };

  return (
    <Container>
      <div className="page-title">
        <h1>{isEditMode ? 'Edit License' : 'Add New License'}</h1>
      </div>

      <Card>
        <Card.Body>
          {error && (
            <div className="alert alert-danger" role="alert">
              {error}
            </div>
          )}

          <Form onSubmit={handleSubmit}>
            <Form.Group className="mb-3">
              <Form.Label>License Code</Form.Label>
              <Form.Control
                type="text"
                name="licenseCode"
                value={formData.licenseCode}
                onChange={handleChange}
                required
                disabled={loading}
              />
              <Form.Text className="text-muted">
                This is the unique license code that will be used to activate the software.
              </Form.Text>
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>Expiry (Days)</Form.Label>
              <Form.Control
                type="number"
                name="expiryDays"
                value={formData.expiryDays}
                onChange={handleChange}
                min="0"
                disabled={loading}
              />
              <Form.Text className="text-muted">
                Number of days until the license expires. Leave empty for unlimited duration.
              </Form.Text>
            </Form.Group>

            <div className="d-flex justify-content-end gap-2">
              <Button
                variant="secondary"
                onClick={() => navigate('/users')}
                disabled={loading}
              >
                Cancel
              </Button>
              <Button variant="primary" type="submit" disabled={loading}>
                {loading
                  ? isEditMode
                    ? 'Updating...'
                    : 'Creating...'
                  : isEditMode
                  ? 'Update License'
                  : 'Create License'}
              </Button>
            </div>
          </Form>
        </Card.Body>
      </Card>
    </Container>
  );
};

export default UserForm;
