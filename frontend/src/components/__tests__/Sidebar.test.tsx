// @vitest-environment jsdom
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Sidebar } from '../Sidebar';
import { BrowserRouter } from 'react-router-dom';
import type { Conversation } from '../../types/chat';

const mockSessions: Conversation[] = [
  { id: '1', title: 'Chat about AI', createdAt: Date.now() },
  { id: '2', title: 'Research', createdAt: Date.now() - 86400000 * 2 }, // 2 days ago
  { id: '3', title: 'Old chat', createdAt: Date.now() - 86400000 * 3 }, // 3 days ago
];

const defaultProps = {
  sessions: mockSessions,
  activeSessionId: '1',
  onSelectSession: () => {},
  onNewSession: () => {},
  onDeleteSession: () => {},
  isMobileOpen: false,
  setMobileOpen: () => {},
};

function renderWithRouter(ui: React.ReactElement) {
  return render(<BrowserRouter>{ui}</BrowserRouter>);
}

describe('Sidebar', () => {
  it('renders AI Studio brand heading', () => {
    renderWithRouter(<Sidebar {...defaultProps} />);
    expect(screen.getByRole('heading', { name: 'AI Studio' })).toBeDefined();
  });

  it('renders New Chat button', () => {
    renderWithRouter(<Sidebar {...defaultProps} />);
    expect(screen.getByText('New Chat')).toBeDefined();
  });

  it('renders Agents menu item', () => {
    renderWithRouter(<Sidebar {...defaultProps} />);
    expect(screen.getByText('Agents')).toBeDefined();
  });

  it('renders Recent Chats section header', () => {
    renderWithRouter(<Sidebar {...defaultProps} />);
    expect(screen.getByText('Recent Chats')).toBeDefined();
  });

  it('renders locked menu items (Tools, Knowledge, MCP, Settings)', () => {
    renderWithRouter(<Sidebar {...defaultProps} />);
    expect(screen.getByText('Tools')).toBeDefined();
    expect(screen.getByText('Knowledge')).toBeDefined();
    expect(screen.getByText('MCP')).toBeDefined();
    expect(screen.getByText('Settings')).toBeDefined();
  });

  it('groups sessions into Today and older periods', () => {
    renderWithRouter(<Sidebar {...defaultProps} />);
    expect(screen.getByText('Today')).toBeDefined();
    expect(screen.getByText('Earlier')).toBeDefined();
  });

  it('renders session titles', () => {
    renderWithRouter(<Sidebar {...defaultProps} />);
    expect(screen.getByText('Chat about AI')).toBeDefined();
    expect(screen.getByText('Research')).toBeDefined();
    expect(screen.getByText('Old chat')).toBeDefined();
  });

  it('renders mobile overlay when isMobileOpen is true', () => {
    renderWithRouter(<Sidebar {...defaultProps} isMobileOpen={true} />);
    const overlay = document.querySelector('.fixed.inset-0');
    expect(overlay).toBeDefined();
  });
});
