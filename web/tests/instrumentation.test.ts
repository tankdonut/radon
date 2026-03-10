import { describe, it, expect, vi } from 'vitest';

// Mock the modules used in instrumentation-node
vi.mock('child_process', () => ({
  spawn: vi.fn(() => ({
    stdout: { on: vi.fn() },
    stderr: { on: vi.fn() },
    on: vi.fn((event, cb) => {
      if (event === 'close') cb(0);
    }),
  })),
}));

vi.mock('fs/promises', () => ({
  stat: vi.fn(),
  writeFile: vi.fn(),
}));

vi.mock('path', () => ({
  join: vi.fn((...args) => args.join('/')),
}));

// We need to use dynamic import because the module itself uses dynamic imports
describe('instrumentation-node', () => {
  it('should export registerNode function', async () => {
    const { registerNode } = await import('../lib/instrumentation-node');
    expect(typeof registerNode).toBe('function');
  });

  it('should handle isCacheFresh correctly when cache is fresh', async () => {
    const { stat } = await import('fs/promises');
    // Mock stat to return a very recent mtimeMs
    (stat as any).mockResolvedValue({ mtimeMs: Date.now() });

    const { registerNode } = await import('../lib/instrumentation-node');
    
    // This will call isCacheFresh and it should return true
    // We can't directly call it because it's not exported, 
    // but we can verify that spawn is NOT called if cache is fresh.
    const { spawn } = await import('child_process');
    
    await registerNode();
    
    expect(spawn).not.toHaveBeenCalled();
  });

  it('should handle isCacheFresh correctly when cache is stale', async () => {
    const { stat } = await import('fs/promises');
    // Mock stat to return an old mtimeMs
    (stat as any).mockResolvedValue({ mtimeMs: Date.now() - 20 * 60 * 1000 });

    const { registerNode } = await import('../lib/instrumentation-node');
    const { spawn } = await import('child_process');
    
    await registerNode();
    
    // Spawn should be called 3 times (discover, flow analysis, scanner)
    expect(spawn).toHaveBeenCalledTimes(3);
  });

  it('should NOT overwrite cache if script output contains error field', async () => {
    const { spawn } = await import('child_process');
    const { writeFile, stat } = await import('fs/promises');
    
    // Mock stat to return stale
    (stat as any).mockResolvedValue({ mtimeMs: Date.now() - 20 * 60 * 1000 });

    // Mock spawn to return JSON with error
    const mockProc = {
      stdout: { on: vi.fn((event, cb) => {
        if (event === 'data') cb(Buffer.from('{"error": "something went wrong", "candidates": []}'));
      }) },
      stderr: { on: vi.fn() },
      on: vi.fn((event, cb) => {
        if (event === 'close') cb(0);
      }),
    };
    (spawn as any).mockReturnValue(mockProc);

    const { registerNode } = await import('../lib/instrumentation-node');
    await registerNode();

    // writeFile should NOT be called because of the error field
    expect(writeFile).not.toHaveBeenCalled();
  });
});
