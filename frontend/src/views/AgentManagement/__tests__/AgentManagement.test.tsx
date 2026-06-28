// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { AgentManagement } from '../AgentManagement';
import { useAgent } from '../../../features/ai-chat/hooks/useAgent';
import { BrowserRouter } from 'react-router-dom';

vi.mock('../../../features/ai-chat/hooks/useAgent', () => ({
  useAgent: vi.fn(),
}));

const mockAgents = [
  { id: '1', name: 'researcher', display_name: '研究员', description: 'Research agent', enabled: true, tags: ['search'], priority: 2, created_at: '2024-01-01' },
  { id: '2', name: 'coder', display_name: '程序员', description: 'Code agent', enabled: false, tags: ['code'], priority: 1, created_at: '2024-02-01' },
  { id: '3', name: 'helper', display_name: '助手', description: 'Helper agent', enabled: true, tags: ['help'], priority: 3, created_at: '2024-03-01' },
];

function renderWithRouter(ui: React.ReactElement) {
  return render(<BrowserRouter>{ui}</BrowserRouter>);
}

describe('AgentManagement', () => {
  beforeEach(() => {
    vi.mocked(useAgent).mockReturnValue({
      agents: mockAgents,
      loading: false,
      error: null,
      fetchAgents: vi.fn(),
      createAgent: vi.fn(),
      updateAgent: vi.fn(),
      deleteAgent: vi.fn(),
      toggleAgent: vi.fn(),
      cloneAgent: vi.fn(),
    });
  });

  it('renders page title and create button', () => {
    renderWithRouter(<AgentManagement />);
    expect(screen.getByText('Agent 管理')).toBeDefined();
    expect(screen.getByText('+ 新建 Agent')).toBeDefined();
  });

  it('renders agent cards for each agent', () => {
    renderWithRouter(<AgentManagement />);
    expect(screen.getByText('研究员')).toBeDefined();
    expect(screen.getByText('程序员')).toBeDefined();
    expect(screen.getByText('助手')).toBeDefined();
  });

  it('shows search input and filters agents by name/display_name', () => {
    renderWithRouter(<AgentManagement />);
    const searchInput = screen.getByPlaceholderText('搜索 Agent...');
    expect(searchInput).toBeDefined();

    fireEvent.change(searchInput, { target: { value: '研究' } });
    expect(screen.getByText('研究员')).toBeDefined();
    expect(screen.queryByText('程序员')).toBeNull();
  });

  it('shows loading state when loading', () => {
    vi.mocked(useAgent).mockReturnValue({
      agents: [],
      loading: true,
      error: null,
      fetchAgents: vi.fn(),
      createAgent: vi.fn(),
      updateAgent: vi.fn(),
      deleteAgent: vi.fn(),
      toggleAgent: vi.fn(),
      cloneAgent: vi.fn(),
    });

    renderWithRouter(<AgentManagement />);
    expect(screen.getByText('加载中...')).toBeDefined();
  });

  it('shows error state with retry button', () => {
    vi.mocked(useAgent).mockReturnValue({
      agents: [],
      loading: false,
      error: 'Failed to fetch',
      fetchAgents: vi.fn(),
      createAgent: vi.fn(),
      updateAgent: vi.fn(),
      deleteAgent: vi.fn(),
      toggleAgent: vi.fn(),
      cloneAgent: vi.fn(),
    });

    renderWithRouter(<AgentManagement />);
    expect(screen.getByText(/加载失败/)).toBeDefined();
    expect(screen.getByText('重试')).toBeDefined();
  });

  it('shows empty state when no agents', () => {
    vi.mocked(useAgent).mockReturnValue({
      agents: [],
      loading: false,
      error: null,
      fetchAgents: vi.fn(),
      createAgent: vi.fn(),
      updateAgent: vi.fn(),
      deleteAgent: vi.fn(),
      toggleAgent: vi.fn(),
      cloneAgent: vi.fn(),
    });

    renderWithRouter(<AgentManagement />);
    expect(screen.getByText(/暂无 Agent/)).toBeDefined();
  });

  it('sorts agents by name ascending and descending', () => {
    renderWithRouter(<AgentManagement />);

    // Default sort: name ascending
    const sortSelect = screen.getByRole('combobox');
    let cards = screen.getAllByText(/研究员|程序员|助手/);
    const firstAsc = cards[0].textContent;
    const lastAsc = cards[cards.length - 1].textContent;

    // Switch to name descending
    fireEvent.change(sortSelect, { target: { value: 'name-desc' } });

    cards = screen.getAllByText(/研究员|程序员|助手/);
    const firstDesc = cards[0].textContent;
    const lastDesc = cards[cards.length - 1].textContent;

    // Order should be reversed
    expect(firstAsc).toBe(lastDesc);
    expect(lastAsc).toBe(firstDesc);
  });

  it('paginates agents when page size is exceeded', () => {
    // Create more agents to exceed page size
    const manyAgents = Array.from({ length: 15 }, (_, i) => ({
      id: String(i + 1),
      name: `agent-${i + 1}`,
      display_name: `Agent ${i + 1}`,
      description: '',
      enabled: true,
      priority: 0,
      created_at: '2024-01-01',
    }));

    vi.mocked(useAgent).mockReturnValue({
      agents: manyAgents,
      loading: false,
      error: null,
      fetchAgents: vi.fn(),
      createAgent: vi.fn(),
      updateAgent: vi.fn(),
      deleteAgent: vi.fn(),
      toggleAgent: vi.fn(),
      cloneAgent: vi.fn(),
    });

    renderWithRouter(<AgentManagement />);

    // Should show 12 agents on first page
    const page1Cards = screen.getAllByText(/Agent \d+/);
    expect(page1Cards).toHaveLength(12);

    // Click next page
    const nextButton = screen.getByText('下一页');
    fireEvent.click(nextButton);

    // Should show remaining agents
    const page2Cards = screen.getAllByText(/Agent \d+/);
    expect(page2Cards).toHaveLength(3);
  });

  it('dispatches custom event on create button click', () => {
    const dispatchSpy = vi.spyOn(window, 'dispatchEvent');
    renderWithRouter(<AgentManagement />);

    const createButton = screen.getByText('+ 新建 Agent');
    fireEvent.click(createButton);

    expect(dispatchSpy).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'agent:create' })
    );
  });
});
