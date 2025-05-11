import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Navbar, Nav, Container, Row, Col } from 'react-bootstrap';
import { FaUsers, FaKey, FaEnvelope, FaChartBar, FaSignOutAlt } from 'react-icons/fa';

const Layout = ({ children }) => {
  const location = useLocation();
  
  // Check if the current path matches the nav item path
  const isActive = (path) => {
    return location.pathname === path ? 'active' : '';
  };

  return (
    <div className="admin-layout">
      <Navbar bg="dark" variant="dark" expand="lg" className="mb-4">
        <Container fluid>
          <Navbar.Brand as={Link} to="/">Email Automation Admin</Navbar.Brand>
          <Navbar.Toggle aria-controls="basic-navbar-nav" />
          <Navbar.Collapse id="basic-navbar-nav">
            <Nav className="ms-auto">
              <Nav.Link href="#" onClick={() => console.log('Logout')}>
                <FaSignOutAlt /> Logout
              </Nav.Link>
            </Nav>
          </Navbar.Collapse>
        </Container>
      </Navbar>

      <Container fluid>
        <Row>
          <Col md={3} lg={2} className="sidebar">
            <Nav className="flex-column">
              <Nav.Link as={Link} to="/" className={isActive('/')}>
                <FaChartBar /> Dashboard
              </Nav.Link>
              <Nav.Link as={Link} to="/users" className={isActive('/users')}>
                <FaUsers /> User Management
              </Nav.Link>
              <Nav.Link as={Link} to="/licenses" className={isActive('/licenses')}>
                <FaKey /> License Management
              </Nav.Link>
              <Nav.Link as={Link} to="/email-config" className={isActive('/email-config')}>
                <FaEnvelope /> Email Configurations
              </Nav.Link>
            </Nav>
          </Col>
          <Col md={9} lg={10} className="main-content">
            {children}
          </Col>
        </Row>
      </Container>

      <footer className="bg-light py-3 mt-5">
        <Container>
          <p className="text-center text-muted mb-0">
            Email Automation Admin © {new Date().getFullYear()}
          </p>
        </Container>
      </footer>
    </div>
  );
};

export default Layout;
