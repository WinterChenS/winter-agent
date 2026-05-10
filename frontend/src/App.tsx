import { Route, Routes } from 'react-router-dom';

import { ChatInterface } from './pages/ChatInterface';

function App() {
  return (
    <Routes>
      <Route path="/" element={<ChatInterface />} />
      <Route path="/chat/:id" element={<ChatInterface />} />
    </Routes>
  );
}

export default App;
