// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PromptEditor } from '../PromptEditor';

// CodeMirror uses DOM APIs that jsdom may not fully support (contenteditable)
// We test the React wrapper behavior, not CodeMirror internals

// Mock clipboard API
const writeTextMock = vi.fn();
Object.assign(navigator, {
  clipboard: {
    writeText: writeTextMock,
  },
});

// Mock CodeMirror modules
// Use a class so it can be used with `new`
vi.mock('codemirror', () => {
  class EditorViewMock {
    destroy = vi.fn();
    dispatch = vi.fn();
    state = {
      doc: {
        toString: vi.fn().mockReturnValue('test content'),
      },
    };
    static lineWrapping = Symbol('lineWrapping');
    static updateListener = { of: vi.fn().mockReturnValue([]) };
  }
  return {
    EditorView: EditorViewMock,
    basicSetup: [],
  };
});

vi.mock('@codemirror/state', () => ({
  EditorState: {
    create: vi.fn().mockReturnValue({}),
  },
}));

vi.mock('@codemirror/lang-markdown', () => ({
  markdown: vi.fn().mockReturnValue([]),
}));

describe('PromptEditor', () => {
  const defaultProps = {
    value: 'initial prompt',
    onChange: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    writeTextMock.mockReset();
  });

  it('renders editor container with prompt-editor-container class', () => {
    const { container } = render(<PromptEditor {...defaultProps} />);
    const editorContainer = container.querySelector('.prompt-editor-container');
    expect(editorContainer).toBeDefined();
  });

  it('renders copy button with correct aria-label', () => {
    render(<PromptEditor {...defaultProps} />);
    const copyButton = screen.getByLabelText('复制');
    expect(copyButton).toBeDefined();
  });

  it('renders fullscreen button with correct aria-label', () => {
    render(<PromptEditor {...defaultProps} />);
    const fullscreenButton = screen.getByLabelText('全屏');
    expect(fullscreenButton).toBeDefined();
  });

  it('toggles fullscreen class when fullscreen button is clicked', () => {
    const { container } = render(<PromptEditor {...defaultProps} />);
    const fullscreenButton = screen.getByLabelText('全屏');

    fireEvent.click(fullscreenButton);
    const containerAfterFirstClick = container.querySelector('.prompt-editor-container');
    expect(containerAfterFirstClick?.className).toContain('fixed inset-0 z-50');

    fireEvent.click(fullscreenButton);
    const containerAfterSecondClick = container.querySelector('.prompt-editor-container');
    expect(containerAfterSecondClick?.className).not.toContain('fixed inset-0 z-50');
  });

  it('calls clipboard.writeText when copy button is clicked', async () => {
    render(<PromptEditor {...defaultProps} />);
    const copyButton = screen.getByLabelText('复制');

    fireEvent.click(copyButton);

    expect(writeTextMock).toHaveBeenCalledWith('test content');
  });

  it('accepts and passes through custom minHeight', () => {
    const { container } = render(
      <PromptEditor {...defaultProps} minHeight="150px" />
    );
    const editorContainer = container.querySelector('.prompt-editor-container');
    expect(editorContainer).toBeDefined();
  });
});
