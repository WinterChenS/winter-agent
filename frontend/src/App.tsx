import { useState, useCallback } from 'react';
import { Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { PrivateRoute } from './components/PrivateRoute';
import { Sidebar } from './components/Sidebar';
import { useSessions } from './hooks/useSessions';
import { ChatInterface } from './pages/ChatInterface';
import { LoginPage } from './pages/LoginPage';
import { AgentManagement } from './views/AgentManagement/AgentManagement';

function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const { sessions, createSession, removeSession } = useSessions();

  const handleSelectSession = useCallback((id: string) => {
    navigate(`/chat/${id}`);
    setMobileOpen(false);
  }, [navigate]);

  const handleNewChat = useCallback(() => {
    createSession();
    navigate('/');
    setMobileOpen(false);
  }, [createSession, navigate]);

  const handleDeleteSession = useCallback((id: string) => {
    removeSession(id);
    if (location.pathname === `/chat/${id}`) {
      navigate('/');
    }
  }, [removeSession, navigate, location.pathname]);

  // Get active session id from current URL
  const activeSessionId = location.pathname.startsWith('/chat/')
    ? location.pathname.replace('/chat/', '')
    : undefined;

  const closeMobile = () => setMobileOpen(false);

  return (
    <div className="flex h-screen bg-white dark:bg-gray-950">
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewChat}
        onDeleteSession={handleDeleteSession}
        isMobileOpen={mobileOpen}
        setMobileOpen={setMobileOpen}
        activeNav={location.pathname === '/agents' ? 'agents' : 'chat'}
        onNewChat={handleNewChat}
        onNavigate={(path) => { navigate(path); closeMobile(); }}
      />
      <main className="flex-1 flex flex-col min-w-0">
        <Routes>
          <Route path="/" element={<ChatInterface onHamburgerClick={() => setMobileOpen(true)} />} />
          <Route path="/chat/:id" element={<ChatInterface onHamburgerClick={() => setMobileOpen(true)} />} />
          <Route path="/agents" element={<AgentManagement />} />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/*" element={
          <PrivateRoute><AppLayout /></PrivateRoute>
        } />
      </Routes>
    </AuthProvider>
  );
}

export default App;
