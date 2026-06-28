// @vitest-environment jsdom
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { AgentCard } from '../AgentCard';
import { AgentStatus } from '../AgentStatus';

const mockAgent = {
  id: 'agent-1',
  name: 'researcher',
  display_name: '研究员',
  description: '负责搜索和研究',
  enabled: true,
  tags: ['search', 'research'],
  icon: '🔬',
  priority: 1,
};

describe('AgentCard', () => {
  it('renders agent display name and description', () => {
    render(<AgentCard agent={mockAgent} onEdit={vi.fn()} onDelete={vi.fn()} onToggle={vi.fn()} onClone={vi.fn()} />);
    expect(screen.getByText('研究员')).toBeDefined();
    expect(screen.getByText('负责搜索和研究')).toBeDefined();
  });

  it('renders tags', () => {
    render(<AgentCard agent={mockAgent} onEdit={vi.fn()} onDelete={vi.fn()} onToggle={vi.fn()} onClone={vi.fn()} />);
    expect(screen.getByText('search')).toBeDefined();
    expect(screen.getByText('research')).toBeDefined();
  });

  it('calls onEdit when edit button is clicked', () => {
    const onEdit = vi.fn();
    render(<AgentCard agent={mockAgent} onEdit={onEdit} onDelete={vi.fn()} onToggle={vi.fn()} onClone={vi.fn()} />);
    const editBtn = screen.getByLabelText('编辑');
    fireEvent.click(editBtn);
    expect(onEdit).toHaveBeenCalledWith('agent-1');
  });

  it('calls onDelete when delete button is clicked', () => {
    const onDelete = vi.fn();
    render(<AgentCard agent={mockAgent} onEdit={vi.fn()} onDelete={onDelete} onToggle={vi.fn()} onClone={vi.fn()} />);
    const deleteBtn = screen.getByLabelText('删除');
    fireEvent.click(deleteBtn);
    expect(onDelete).toHaveBeenCalledWith('agent-1');
  });

  it('calls onClone when clone button is clicked', () => {
    const onClone = vi.fn();
    render(<AgentCard agent={mockAgent} onEdit={vi.fn()} onDelete={vi.fn()} onToggle={vi.fn()} onClone={onClone} />);
    const cloneBtn = screen.getByLabelText('克隆');
    fireEvent.click(cloneBtn);
    expect(onClone).toHaveBeenCalledWith('agent-1');
  });

  it('calls onToggle when AgentStatus is clicked', () => {
    const onToggle = vi.fn();
    render(<AgentCard agent={mockAgent} onEdit={vi.fn()} onDelete={vi.fn()} onToggle={onToggle} onClone={vi.fn()} />);
    const statusBtn = screen.getByText('启用');
    fireEvent.click(statusBtn);
    expect(onToggle).toHaveBeenCalledWith('agent-1', false);
  });

  it('renders AgentStatus with enabled state', () => {
    render(<AgentCard agent={mockAgent} onEdit={vi.fn()} onDelete={vi.fn()} onToggle={vi.fn()} onClone={vi.fn()} />);
    expect(screen.getByText('启用')).toBeDefined();
  });

  it('renders disabled AgentStatus when agent is disabled', () => {
    const disabledAgent = { ...mockAgent, enabled: false };
    render(<AgentCard agent={disabledAgent} onEdit={vi.fn()} onDelete={vi.fn()} onToggle={vi.fn()} onClone={vi.fn()} />);
    expect(screen.getByText('禁用')).toBeDefined();
  });
});

describe('AgentStatus', () => {
  it('shows enabled badge when enabled is true', () => {
    render(<AgentStatus enabled={true} onToggle={vi.fn()} />);
    expect(screen.getByText('启用')).toBeDefined();
  });

  it('shows disabled badge when enabled is false', () => {
    render(<AgentStatus enabled={false} onToggle={vi.fn()} />);
    expect(screen.getByText('禁用')).toBeDefined();
  });

  it('calls onToggle when clicked', () => {
    const onToggle = vi.fn();
    render(<AgentStatus enabled={true} onToggle={onToggle} />);
    fireEvent.click(screen.getByRole('button'));
    expect(onToggle).toHaveBeenCalledOnce();
  });
});
