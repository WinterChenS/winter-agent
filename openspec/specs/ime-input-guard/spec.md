# ime-input-guard Specification

## Purpose
TBD - created by archiving change optimize-chat-ui-rendering. Update Purpose after archive.
## Requirements
### Requirement: IME Composition State Lock
系统 SHALL 在 InputBox 组件中监听 `compositionstart` 和 `compositionend` 事件，维护 `isComposing` 状态锁。当 IME 处于组合输入状态时，Enter 键不触发消息发送。

#### Scenario: IME composition prevents send
- **WHEN** 用户使用中文/日文/韩文输入法输入文字
- **AND** IME 组合窗口处于激活状态（compositionstart 已触发，compositionend 未触发）
- **AND** 用户按下 Enter 键确认候选字
- **THEN** 系统不触发消息发送
- **AND** Enter 事件由 IME 处理（选字确认）

#### Scenario: Enter sends when not composing
- **WHEN** 用户输入英文或已完成中文输入
- **AND** IME 组合窗口未激活（isComposing === false）
- **AND** 用户按下 Enter 键（非 Shift+Enter）
- **THEN** 系统触发消息发送

#### Scenario: Shift+Enter inserts newline during composition
- **WHEN** IME 处于组合输入状态
- **AND** 用户按下 Shift+Enter
- **THEN** 系统在输入框中插入换行符（不发送消息）

### Requirement: IME State Isolation
系统 SHALL 使用 `useRef` 存储 `isComposing` 状态，避免 composition 状态变化触发不必要的组件 re-render。

#### Scenario: Composition state changes don't cause re-render
- **WHEN** IME composition 状态在 true/false 之间切换
- **THEN** InputBox 组件不发生 re-render
- **AND** 输入框的光标位置和候选窗口不受影响

### Requirement: Cross-Browser IME Compatibility
系统 SHALL 确保 IME 守卫逻辑在主流浏览器（Chrome、Firefox、Safari、Edge）上行为一致。

#### Scenario: Chrome IME behavior
- **WHEN** 在 Chrome 中使用拼音输入法
- **AND** `compositionstart` 和 `compositionend` 事件按规范触发
- **THEN** Enter 键在 composition 期间不发送消息

#### Scenario: Safari IME behavior
- **WHEN** 在 Safari 中使用中文输入法
- **AND** Safari 的 `keydown` 事件在 composition 期间 `keyCode` 为 229
- **THEN** 系统通过 `isComposing` ref 正确阻止发送

