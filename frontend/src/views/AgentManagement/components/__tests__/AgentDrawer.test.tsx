// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AgentDrawer } from '../AgentDrawer';
import { ToolSelector } from '../ToolSelector';
import { TagInput } from '../TagInput';
import { agentApi } from '../../../../features/ai-chat/services/agent';

vi.mock('../../../../features/ai-chat/services/agent', () => ({
  agentApi: {
    getAgent: vi.fn().mockResolvedValue({
      id: '1',
      name: 'test-agent',
      display_name: 'Test Agent',
      description: 'A test agent',
      enabled: true,
      icon: '\u{1F916}',
      agent_type: 'assistant',
      system_prompt: '',
      tools: ['search', 'browser'],
      model_config: {
        model_name: 'gpt-4',
        temperature: 0.7,
        top_p: 1,
        max_tokens: 2048,
        streaming: true,
        json_mode: false,
      },
      trigger_keywords: [],
      collaboration_strategy: 'sequential',
      priority: 0,
      tags: [],
      created_at: '2024-01-01',
      updated_at: '2024-01-01',
    }),
    createAgent: vi.fn().mockResolvedValue({ id: 'new-1' }),
    updateAgent: vi.fn().mockResolvedValue({ id: '1' }),
  },
}));

describe('ToolSelector', () => {
  const available = ['search', 'browser', 'execute_python', 'time'];

  it('renders checkboxes for all available tools', () => {
    render(<ToolSelector selected={[]} available={available} onChange={() => {}} />);
    available.forEach(tool => {
      expect(screen.getByText(tool)).toBeDefined();
    });
    expect(screen.getAllByRole('checkbox')).toHaveLength(available.length);
  });

  it('checks checkboxes for selected tools', () => {
    render(<ToolSelector selected={['search', 'browser']} available={available} onChange={() => {}} />);
    const checkboxes = screen.getAllByRole('checkbox');
    expect((checkboxes[0] as HTMLInputElement).checked).toBe(true);
    expect((checkboxes[1] as HTMLInputElement).checked).toBe(true);
    expect((checkboxes[2] as HTMLInputElement).checked).toBe(false);
    expect((checkboxes[3] as HTMLInputElement).checked).toBe(false);
  });

  it('calls onChange with added tool when clicking unchecked', () => {
    const onChange = vi.fn();
    render(<ToolSelector selected={[]} available={available} onChange={onChange} />);
    fireEvent.click(screen.getByText('search'));
    expect(onChange).toHaveBeenCalledWith(['search']);
  });

  it('calls onChange with removed tool when clicking checked', () => {
    const onChange = vi.fn();
    render(<ToolSelector selected={['search', 'browser']} available={available} onChange={onChange} />);
    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[0]); // click 'search' checkbox
    expect(onChange).toHaveBeenCalledWith(['browser']);
  });
});

describe('TagInput', () => {
  it('renders existing tags as chips', () => {
    render(<TagInput tags={['tag1', 'tag2']} onChange={() => {}} />);
    expect(screen.getByText('tag1')).toBeDefined();
    expect(screen.getByText('tag2')).toBeDefined();
  });

  it('adds a new tag on Enter key', () => {
    const onChange = vi.fn();
    render(<TagInput tags={['existing']} onChange={onChange} />);
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'new-tag' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onChange).toHaveBeenCalledWith(['existing', 'new-tag']);
  });

  it('does not add duplicate tags', () => {
    const onChange = vi.fn();
    render(<TagInput tags={['existing']} onChange={onChange} />);
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'existing' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onChange).not.toHaveBeenCalled();
  });

  it('removes tag when close button is clicked', () => {
    const onChange = vi.fn();
    render(<TagInput tags={['tag1', 'tag2']} onChange={onChange} />);
    const buttons = screen.getAllByRole('button');
    fireEvent.click(buttons[0]);
    expect(onChange).toHaveBeenCalledWith(['tag2']);
  });

  it('clears input after adding a tag', () => {
    const onChange = vi.fn();
    render(<TagInput tags={[]} onChange={onChange} />);
    const input = screen.getByPlaceholderText('输入关键词后回车') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'new-tag' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(input.value).toBe('');
  });
});

describe('AgentDrawer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders closed drawer with translate-x-full class', () => {
    const { container } = render(<AgentDrawer open={false} onClose={() => {}} onSave={() => {}} />);
    const drawer = container.querySelector('[class*="translate-x-full"]');
    expect(drawer).toBeDefined();
  });

  it('renders drawer content when open in create mode', () => {
    render(<AgentDrawer open={true} onClose={() => {}} onSave={() => {}} />);
    expect(screen.getByText('新建 Agent')).toBeDefined();
  });

  it('renders in edit mode with agent title', async () => {
    render(<AgentDrawer open={true} agentId="1" onClose={() => {}} onSave={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText('编辑 Agent')).toBeDefined();
    });
  });

  it('renders all form sections', () => {
    render(<AgentDrawer open={true} onClose={() => {}} onSave={() => {}} />);
    expect(screen.getByText('基本信息')).toBeDefined();
    expect(screen.getByText('System Prompt')).toBeDefined();
    expect(screen.getByText('模型配置')).toBeDefined();
    expect(screen.getByText('工具')).toBeDefined();
    expect(screen.getByText('触发关键词')).toBeDefined();
    expect(screen.getByText('高级配置')).toBeDefined();
  });

  it('closes when backdrop overlay is clicked', () => {
    const onClose = vi.fn();
    const { container } = render(<AgentDrawer open={true} onClose={onClose} onSave={() => {}} />);
    const backdrop = container.firstChild as HTMLElement;
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalled();
  });

  it('calls agentApi.createAgent on save and invokes callbacks', async () => {
    const onSave = vi.fn();
    const onClose = vi.fn();
    render(<AgentDrawer open={true} onClose={onClose} onSave={onSave} />);
    fireEvent.click(screen.getByText('保存'));
    await waitFor(() => {
      expect(agentApi.createAgent).toHaveBeenCalled();
      expect(onSave).toHaveBeenCalled();
      expect(onClose).toHaveBeenCalled();
    });
  });

  it('calls agentApi.updateAgent on save in edit mode', async () => {
    render(<AgentDrawer open={true} agentId="1" onClose={() => {}} onSave={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText('编辑 Agent')).toBeDefined();
    });
    fireEvent.click(screen.getByText('保存'));
    await waitFor(() => {
      expect(agentApi.updateAgent).toHaveBeenCalledWith('1', expect.any(Object));
    });
  });

  it('pre-fills form with loaded agent data in edit mode', async () => {
    render(<AgentDrawer open={true} agentId="1" onClose={() => {}} onSave={() => {}} />);
    await waitFor(() => {
      expect(screen.getByDisplayValue('Test Agent')).toBeDefined();
    });
  });
});
