const { validateCommand } = require('../schemas');

describe('Command Validation', () => {
  test('should validate a correct move command', () => {
    const cmd = { action: 'MOVE', target: '100 64 100' };
    const result = validateCommand(cmd);
    expect(result.success).toBe(true);
  });

  test('should fail if action is missing', () => {
    const cmd = { target: '100 64 100' };
    const result = validateCommand(cmd);
    expect(result.success).toBe(false);
  });

  test('should allow extra properties (passthrough)', () => {
    const cmd = { action: 'CHAT', message: 'Hello', extra: 'data' };
    const result = validateCommand(cmd);
    expect(result.success).toBe(true);
  });
});
