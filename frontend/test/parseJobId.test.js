import test from 'node:test';
import assert from 'node:assert/strict';
import { parseJobId } from '../src/utils/job.js';

test('parses job_id property from backend response', () => {
  assert.equal(parseJobId({ job_id: 'abc-123' }), 'abc-123');
});

test('falls back to jobId property when present', () => {
  assert.equal(parseJobId({ jobId: 'def-456' }), 'def-456');
});

test('falls back to id property when present', () => {
  assert.equal(parseJobId({ id: 'ghi-789' }), 'ghi-789');
});

test('handles numeric identifiers by converting to strings', () => {
  assert.equal(parseJobId({ job_id: 42 }), '42');
});

test('returns null when identifier is missing', () => {
  assert.equal(parseJobId({}), null);
});
