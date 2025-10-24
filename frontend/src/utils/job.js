export const parseJobId = (payload) => {
  if (!payload) return null;

  if (typeof payload === 'string' || typeof payload === 'number') {
    const value = String(payload).trim();
    return value.length > 0 ? value : null;
  }

  if (typeof payload === 'object') {
    const candidates = [payload.jobId, payload.job_id, payload.id];

    for (const candidate of candidates) {
      if (candidate === undefined || candidate === null) {
        continue;
      }

      if (typeof candidate === 'string') {
        const trimmed = candidate.trim();
        if (trimmed.length > 0) {
          return trimmed;
        }
      }

      if (typeof candidate === 'number') {
        return String(candidate);
      }
    }
  }

  return null;
};

export default parseJobId;
