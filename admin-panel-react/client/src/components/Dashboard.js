import React, { useState, useEffect } from 'react';
import { Container, Row, Col, Card } from 'react-bootstrap';
import { FaUsers, FaKey, FaEnvelope, FaExclamationTriangle } from 'react-icons/fa';
import axios from 'axios';

const Dashboard = () => {
  const [stats, setStats] = useState({
    totalUsers: 0,
    registeredUsers: 0,
    emailConfigs: 0,
    expiringSoon: 0
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        setLoading(true);
        const response = await axios.get('/api/stats');
        setStats(response.data);
        setError(null);
      } catch (err) {
        setError('Failed to load dashboard statistics');
        console.error('Error fetching stats:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, []);

  // Stat cards data
  const statCards = [
    {
      title: 'Total Licenses',
      value: stats.totalUsers,
      icon: <FaUsers className="icon text-primary" />,
      color: 'primary'
    },
    {
      title: 'Registered Devices',
      value: stats.registeredUsers,
      icon: <FaKey className="icon text-success" />,
      color: 'success'
    },
    {
      title: 'Email Configs',
      value: stats.emailConfigs,
      icon: <FaEnvelope className="icon text-info" />,
      color: 'info'
    },
    {
      title: 'Expiring Soon',
      value: stats.expiringSoon,
      icon: <FaExclamationTriangle className="icon text-warning" />,
      color: 'warning'
    }
  ];

  return (
    <Container>
      <div className="page-title">
        <h1>Dashboard</h1>
      </div>

      {loading ? (
        <p>Loading statistics...</p>
      ) : error ? (
        <div className="alert alert-danger" role="alert">
          {error}
        </div>
      ) : (
        <>
          <Row>
            {statCards.map((card, index) => (
              <Col key={index} md={6} lg={3} className="mb-4">
                <div className={`stats-card border-${card.color}`}>
                  {card.icon}
                  <div className="number">{card.value}</div>
                  <div className="label">{card.title}</div>
                </div>
              </Col>
            ))}
          </Row>

          <Row className="mt-4">
            <Col lg={6} className="mb-4">
              <Card>
                <Card.Header>Recent Licenses</Card.Header>
                <Card.Body>
                  <p className="text-muted">
                    Not implemented yet. This section will show recently added licenses.
                  </p>
                </Card.Body>
              </Card>
            </Col>
            <Col lg={6} className="mb-4">
              <Card>
                <Card.Header>License Expiry</Card.Header>
                <Card.Body>
                  <p className="text-muted">
                    Licenses expiring within the next 7 days: {stats.expiringSoon}
                  </p>
                </Card.Body>
              </Card>
            </Col>
          </Row>
        </>
      )}
    </Container>
  );
};

export default Dashboard;
