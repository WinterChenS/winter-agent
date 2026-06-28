// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { useChatStore } from '../../store/chatStore';
import { AgentStatusIndicator } from '../AgentStatusIndicator';

// Helper to set store state directly
function setStoreState(partial: Partial<ReturnType<typeof useChatStore.getState>>) {
  useChatStore.setState(partial);
}

describe('AgentStatusIndicator', () => {
  beforeEach(() => {
    // Reset to idle state before each test
    useChatStore.setState({
      agentStatus: 'idle',
      activeAgent: null,
      activeAgentDisplay: null,
    });
  });

  it('renders nothing when agentStatus is idle', () => {
    const { container } = render(<AgentStatusIndicator />);
    expect(container.innerHTML).toBe('');
  });

  it('shows "Thinking..." when agentStatus is thinking', () => {
    useChatStore.setState({
      agentStatus: 'thinking',
      activeAgent: 'assistant-1',
      activeAgentDisplay: 'AI Assistant',
    });
    render(<AgentStatusIndicator />);
    expect(screen.getByText('AI Assistant')).toBeTruthy();
    expect(screen.getByText('Thinking...')).toBeTruthy();
  });

  it('shows "Calling tool..." when agentStatus is calling_tool', () => {
    useChatStore.setState({
      agentStatus: 'calling_tool',
      activeAgent: 'research-agent',
      activeAgentDisplay: 'Research Agent',
    });
    render(<AgentStatusIndicator />);
    expect(screen.getByText('Research Agent')).toBeTruthy();
    expect(screen.getByText('Calling tool...')).toBeTruthy();
  });

  it('shows "Generating..." when agentStatus is generating', () => {
    useChatStore.setState({
      agentStatus: 'generating',
      activeAgent: 'writer-agent',
      activeAgentDisplay: 'Writer Agent',
    });
    render(<AgentStatusIndicator />);
    expect(screen.getByText('Writer Agent')).toBeTruthy();
    expect(screen.getByText('Generating...')).toBeTruthy();
  });

  it('falls back to activeAgent when activeAgentDisplay is null', () => {
    useChatStore.setState({
      agentStatus: 'thinking',
      activeAgent: 'fallback-agent',
      activeAgentDisplay: null,
    });
    render(<AgentStatusIndicator />);
    expect(screen.getByText('fallback-agent')).toBeTruthy();
  });

  it('shows agent icon element when agentStatus is not idle', () => {
    useChatStore.setState({
      agentStatus: 'thinking',
      activeAgent: 'test-agent',
      activeAgentDisplay: 'Test Agent',
    });
    render(<AgentStatusIndicator />);
    // Should render an icon-like element (a small dot or SVG)
    const container = document.querySelector('.agent-status-indicator');
    expect(container).toBeTruthy();
    // Should have an icon element inside
    expect(container?.querySelector('.agent-status-icon')).toBeTruthy();
  });
});
