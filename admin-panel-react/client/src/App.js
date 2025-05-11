import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import 'bootstrap/dist/css/bootstrap.min.css';
import './App.css';

// Components
import Layout from './components/Layout';
import Dashboard from './components/Dashboard';
import UserList from './components/UserList';
import UserForm from './components/UserForm';
import LicenseList from './components/LicenseList';
import EmailConfigList from './components/EmailConfigList';
import NotFound from './components/NotFound';

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/users" element={<UserList />} />
          <Route path="/users/add" element={<UserForm />} />
          <Route path="/users/edit/:id" element={<UserForm />} />
          <Route path="/licenses" element={<LicenseList />} />
          <Route path="/email-config" element={<EmailConfigList />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Layout>
    </Router>
  );
}

export default App;
