// @vitest-environment jsdom
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ToolCallPanel } from '../components/ToolCallPanel';

function makeToolCall(id: string, status: 'pending' | 'running' | 'done' | 'failed', name = 'search') {
  return { id, name, arguments: {}, status, result: undefined };
}

describe('ToolCallPanel', () => {
  it('renders null when toolCalls is empty', () => {
    const { container } = render(<ToolCallPanel toolCalls={[]} />);
    expect(container.innerHTML).toBe('');
  });

  it('renders null when toolCalls is undefined', () => {
    const { container } = render(<ToolCallPanel toolCalls={undefined as any} />);
    expect(container.innerHTML).toBe('');
  });

  it('shows aggregate header with tool count for multiple tools', () => {
    render(<ToolCallPanel toolCalls={[
      makeToolCall('tc-1', 'done'),
      makeToolCall('tc-2', 'done'),
    ]} />);
    expect(screen.getByText(/2 tools/i)).toBeTruthy();
  });

  it('shows green checkmark when all tools are done', () => {
    render(<ToolCallPanel toolCalls={[
      makeToolCall('tc-1', 'done'),
      makeToolCall('tc-2', 'done'),
    ]} />);
    const checkmarks = screen.getAllByText('✓');
    expect(checkmarks.length).toBeGreaterThan(0);
  });

  it('shows tool name for each tool', () => {
    render(<ToolCallPanel toolCalls={[
      makeToolCall('tc-1', 'done', 'search'),
      makeToolCall('tc-2', 'done', 'browser'),
    ]} />);
    expect(screen.getByText('search')).toBeTruthy();
    expect(screen.getByText('browser')).toBeTruthy();
  });
});
