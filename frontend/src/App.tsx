import { Route, Routes } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { PrivateRoute } from './components/PrivateRoute';
import { ChatInterface } from './pages/ChatInterface';
import { LoginPage } from './pages/LoginPage';
import { AdminAgents } from './pages/AdminAgents';
import { ChatContainer } from './features/ai-chat';

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
        <Route path="/admin/agents" element={
          <PrivateRoute><AdminAgents /></PrivateRoute>
        } />
        <Route path="/chat-v2/:id" element={
          <PrivateRoute><ChatContainer /></PrivateRoute>
        } />
        <Route path="/chat-v2" element={
          <PrivateRoute><ChatContainer /></PrivateRoute>
        } />
      </Routes>
    </AuthProvider>
  );
}

export default App;
