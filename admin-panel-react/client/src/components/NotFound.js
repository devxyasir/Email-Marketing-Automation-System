import React from 'react';
import { Container, Alert, Button } from 'react-bootstrap';
import { Link } from 'react-router-dom';

const NotFound = () => {
  return (
    <Container className="text-center py-5">
      <Alert variant="warning">
        <h1>404</h1>
        <h2>Page Not Found</h2>
        <p>The page you are looking for does not exist or has been moved.</p>
        <Link to="/">
          <Button variant="primary">Go to Dashboard</Button>
        </Link>
      </Alert>
    </Container>
  );
};

export default NotFound;
