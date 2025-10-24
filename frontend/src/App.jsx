import { useEffect, useMemo, useRef, useState } from 'react';
import './App.css';

const TOOL_OPTIONS = [
  { id: 'certificate_search', label: 'Certificate search' },
  { id: 'waybackurls', label: 'WaybackURLs' },
  { id: 'gau', label: 'Gau' },
  { id: 'waymore', label: 'Waymore' },
  { id: 'subfinder', label: 'Subfinder' },
  { id: 'chaos', label: 'Chaos' },
  { id: 'github', label: 'GitHub' },
  { id: 'gitlab', label: 'GitLab' },
  { id: 'sourcegraph', label: 'Sourcegraph' },
  { id: 'gatherurls', label: 'GatherURLs' },
  { id: 'static_bruteforce', label: 'Static brute-force' },
  { id: 'dynamic_bruteforce', label: 'Dynamic brute-force' },
];

const TOOL_ID_MAP = {
  certificate_search: 'crtsh',
  waybackurls: 'waybackurls',
  gau: 'gau',
  waymore: 'waymore',
  subfinder: 'subfinder',
  chaos: 'chaos',
  github: 'github-subdomains',
  gitlab: 'gitlab-subdomains',
  sourcegraph: 'source_scan',
  gatherurls: 'urlfinder',
};

const API_BASE_URL = (import.meta.env?.VITE_API_BASE_URL ?? '').replace(/\/$/, '');

const buildApiUrl = (path) => {
  if (!path.startsWith('/')) {
    throw new Error(`API paths must start with a leading slash. Received: ${path}`);
  }

  return `${API_BASE_URL}${path}`;
};

const parseJobId = (payload) => {
  if (!payload) return null;
  if (typeof payload === 'string') return payload;
  if (typeof payload === 'object') {
    return payload.jobId ?? payload.id ?? null;
  }
  return null;
};

function App() {
  const [targetDomain, setTargetDomain] = useState('');
  const [selectedTools, setSelectedTools] = useState(() => TOOL_OPTIONS.map((tool) => tool.id));
  const [isRunning, setIsRunning] = useState(false);
  const [logs, setLogs] = useState([]);
  const [artifacts, setArtifacts] = useState([]);
  const [jobId, setJobId] = useState(null);
  const [error, setError] = useState(null);
  const [statusMessage, setStatusMessage] = useState('');

  const eventSourceRef = useRef(null);
  const artifactTimerRef = useRef(null);

  const hasArtifacts = useMemo(() => artifacts.length > 0, [artifacts]);

  const cleanupSubscriptions = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (artifactTimerRef.current !== null) {
      window.clearInterval(artifactTimerRef.current);
      artifactTimerRef.current = null;
    }
  };

  useEffect(() => {
    return () => {
      cleanupSubscriptions();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleToolToggle = (toolId) => {
    setSelectedTools((prev) => {
      if (prev.includes(toolId)) {
        return prev.filter((id) => id !== toolId);
      }
      return [...prev, toolId];
    });
  };

  const fetchArtifacts = async (id) => {
    if (!id) return;

    try {
      const response = await fetch(buildApiUrl(`/api/jobs/${encodeURIComponent(id)}/artifacts`));
      if (!response.ok) {
        throw new Error('Failed to load artifacts');
      }

      const payload = await response.json();
      if (!Array.isArray(payload)) return;

      setArtifacts(
        payload.map((artifact) => ({
          name: artifact.name ?? artifact.file ?? 'Download',
          url:
            artifact.url ??
            artifact.href ??
            buildApiUrl(`/api/jobs/${encodeURIComponent(id)}/artifacts/${encodeURIComponent(artifact.name ?? artifact.file ?? '')}`),
        }))
      );
      setStatusMessage((prev) => (prev && prev.startsWith('Unable to refresh') ? '' : prev));
    } catch (err) {
      console.error(err);
      setStatusMessage('Unable to refresh artifacts. Retrying…');
    }
  };

  const subscribeToLogs = (id) => {
    if (!id) return;

    cleanupSubscriptions();

    const source = new EventSource(buildApiUrl(`/api/jobs/${encodeURIComponent(id)}/logs`));
    eventSourceRef.current = source;

    source.onmessage = (event) => {
      setLogs((prev) => [...prev, event.data]);
    };

    const handleCompletion = () => {
      setStatusMessage('Recon run finished. You can download the artifacts below.');
      setIsRunning(false);
      cleanupSubscriptions();
      fetchArtifacts(id);
    };

    source.addEventListener('complete', handleCompletion);
    source.addEventListener('done', handleCompletion);

    source.addEventListener('artifact', () => {
      fetchArtifacts(id);
    });

    source.onerror = (event) => {
      console.error('EventSource error', event);
      setError('Lost connection to the log stream. Retrying may be necessary.');
      setIsRunning(false);
      cleanupSubscriptions();
    };

    artifactTimerRef.current = window.setInterval(() => {
      fetchArtifacts(id);
    }, 5000);
  };

  const handleStart = async (event) => {
    event.preventDefault();

    const trimmedTarget = targetDomain.trim();
    if (!trimmedTarget) {
      setError('Please enter a target domain.');
      return;
    }

    if (selectedTools.length === 0) {
      setError('Select at least one tool to run.');
      return;
    }

    const remappedToolIds = Array.from(
      new Set(
        selectedTools
          .map((toolId) => TOOL_ID_MAP[toolId])
          .filter((toolId) => typeof toolId === 'string' && toolId.length > 0)
      )
    );

    setError(null);
    setStatusMessage('Preparing recon job…');
    setIsRunning(true);
    setLogs([]);
    setArtifacts([]);

    try {
      const payload = {
        targets: [trimmedTarget],
        tools: remappedToolIds,
        static_bruteforce: {
          enabled: selectedTools.includes('static_bruteforce'),
        },
        dynamic_bruteforce: {
          enabled: selectedTools.includes('dynamic_bruteforce'),
        },
      };

      const response = await fetch(buildApiUrl('/jobs'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error('Failed to start recon job');
      }

      const data = await response.json();
      const id = parseJobId(data);
      if (!id) {
        throw new Error('The backend did not return a job identifier.');
      }

      setJobId(id);
      setStatusMessage('Recon run in progress…');
      subscribeToLogs(id);
      fetchArtifacts(id);
    } catch (err) {
      console.error(err);
      setError(err.message || 'Something went wrong while starting the recon job.');
      setIsRunning(false);
      cleanupSubscriptions();
    }
  };

  const formattedLogs = useMemo(() => (logs.length ? logs.join('\n') : 'Logs will appear here once the job starts.'), [logs]);

  return (
    <div className="app">
      <header className="app__header">
        <h1>WatchMySix Orchestrator</h1>
        <p>Launch reconnaissance jobs, follow the live output, and download generated subdomain lists.</p>
      </header>

      <main className="app__grid">
        <section className="card form-card">
          <h2>New run</h2>
          <form onSubmit={handleStart} className="scan-form">
            <label className="scan-form__label" htmlFor="target-domain">
              Target domain
            </label>
            <input
              id="target-domain"
              name="target-domain"
              type="text"
              placeholder="example.com"
              value={targetDomain}
              onChange={(event) => setTargetDomain(event.target.value)}
              disabled={isRunning}
              autoComplete="off"
              required
            />

            <fieldset className="scan-form__fieldset" disabled={isRunning}>
              <legend>Tools</legend>
              <div className="tool-grid">
                {TOOL_OPTIONS.map((tool) => (
                  <label key={tool.id} className="tool-option">
                    <input
                      type="checkbox"
                      name="tools"
                      value={tool.id}
                      checked={selectedTools.includes(tool.id)}
                      onChange={() => handleToolToggle(tool.id)}
                    />
                    <span>{tool.label}</span>
                  </label>
                ))}
              </div>
            </fieldset>

            <button type="submit" className="primary-button" disabled={isRunning}>
              {isRunning ? (
                <span className="loading">
                  <span className="loading__spinner" aria-hidden="true" />
                  Starting…
                </span>
              ) : (
                'Start reconnaissance'
              )}
            </button>
            {statusMessage && <p className="status-message">{statusMessage}</p>}
            {error && <p className="error-message" role="alert">{error}</p>}
          </form>
        </section>

        <section className="card logs-card">
          <div className="card__header">
            <h2>Execution log</h2>
            {isRunning && <span className="badge badge--running">Live</span>}
          </div>
          <pre className="logs" aria-live="polite">
            {formattedLogs}
          </pre>
        </section>

        <section className="card artifacts-card">
          <h2>Artifacts</h2>
          {isRunning && <p className="muted">Artifacts refresh automatically while the job is running.</p>}
          {!hasArtifacts && <p className="muted">Artifacts will appear here as soon as they are generated.</p>}
          {hasArtifacts && (
            <ul className="artifact-list">
              {artifacts.map((artifact) => (
                <li key={artifact.name}>
                  <a href={artifact.url} download>
                    {artifact.name}
                  </a>
                </li>
              ))}
            </ul>
          )}
          {jobId && (
            <p className="muted">Job ID: <code>{jobId}</code></p>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;
