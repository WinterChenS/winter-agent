import { Route, Routes } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { PrivateRoute } from './components/PrivateRoute';
import { ChatInterface } from './pages/ChatInterface';
import { LoginPage } from './pages/LoginPage';
import { AgentManagement } from './views/AgentManagement/AgentManagement';

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={
          <PrivateRoute><ChatInterface /></PrivateRoute>
        } />
        <Route path="/chat/:id" element={
          <PrivateRoute><ChatInterface /></PrivateRoute>
        } />
        <Route path="/agents" element={
          <PrivateRoute><AgentManagement /></PrivateRoute>
        } />
      </Routes>
    </AuthProvider>
  );
}

export default App;
