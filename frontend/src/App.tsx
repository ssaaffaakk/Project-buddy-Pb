import { useEffect, useState } from "react";
import {
  fetchProjects, fetchRecommendations,
  Page, Project, Recommendation,
} from "./api";

const STATUSES = ["open", "closed", "completed"] as const;

function ProjectCard({ project, fit }: { project: Project; fit?: number }) {
  return (
    <article className="spa-card">
      {fit !== undefined && <span className="spa-fit">{Math.round(fit)}% fit</span>}
      <h3>
        <a href={`/project/${project.id}`}>{project.title}</a>
      </h3>
      <p className="spa-desc">{project.description.slice(0, 140)}</p>
      <div className="spa-tags">
        {project.tags.slice(0, 4).map((tag) => (
          <span key={tag} className="spa-tag">{tag}</span>
        ))}
      </div>
      <footer>
        <span>
          {project.member_count}/{project.team_size} members
          {project.spots_left > 0 && ` · ${project.spots_left} spot(s) left`}
        </span>
        {project.status === "open" && (
          <a className="spa-apply" href={`/projects/${project.id}/apply`}>Apply</a>
        )}
      </footer>
    </article>
  );
}

export default function App() {
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [status, setStatus] = useState<string>("open");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<Project> | null>(null);
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // debounce the search box so we don't hammer the API per keystroke
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebounced(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchProjects({ q: debounced, status, page, per_page: 9 })
      .then((result) => {
        if (!cancelled) {
          setData(result);
          setError(null);
        }
      })
      .catch((e: Error) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [debounced, status, page]);

  useEffect(() => {
    fetchRecommendations()
      .then((r) => setRecs(r.items.slice(0, 3)))
      .catch(() => setRecs([]));
  }, []);

  return (
    <div className="spa-wrap">
      <header className="spa-header">
        <div>
          <h1>Projects Explorer</h1>
          <p className="spa-sub">
            React + TypeScript · live from <code>/api/v1</code>
          </p>
        </div>
      </header>

      {recs.length > 0 && (
        <section>
          <h2 className="spa-section-title">Recommended for you</h2>
          <div className="spa-grid">
            {recs.map(({ project, fit_percent }) => (
              <ProjectCard key={project.id} project={project} fit={fit_percent} />
            ))}
          </div>
        </section>
      )}

      <section>
        <div className="spa-controls">
          <input
            type="search"
            placeholder="Search title or description…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select
            value={status}
            onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          >
            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>

        {error && <p className="spa-error">Couldn&apos;t load projects: {error}</p>}
        {loading && !data && <p className="spa-muted">Loading…</p>}

        {data && (
          <>
            <div className="spa-grid">
              {data.items.map((project) => (
                <ProjectCard key={project.id} project={project} />
              ))}
              {data.items.length === 0 && (
                <p className="spa-muted">No projects match.</p>
              )}
            </div>
            <nav className="spa-pager">
              <button disabled={page <= 1} onClick={() => setPage(page - 1)}>
                ← Prev
              </button>
              <span>
                page {data.page} / {Math.max(data.pages, 1)} · {data.total} projects
              </span>
              <button disabled={page >= data.pages} onClick={() => setPage(page + 1)}>
                Next →
              </button>
            </nav>
          </>
        )}
      </section>
    </div>
  );
}
