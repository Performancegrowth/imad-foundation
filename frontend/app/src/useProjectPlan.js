import { useEffect, useState } from 'react';
import { useProjectId } from './useProjectId';
import { api } from './api';

export function useProjectPlan() {
  const projectId = useProjectId();
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!projectId) { setLoading(false); return; }
    let cancelled = false;
    (async () => {
      try {
        // 1) Metadata list first (GET /plans/{id}) — cheap, and it provides the
        //    saved-plan slug that GET /plans/{id}/{name} requires.
        const list = await api.listPlans(projectId);
        if (cancelled) return;
        if (!Array.isArray(list) || list.length === 0) {
          setPlan(null);
          setLoading(false);
          return;
        }
        const firstMeta = list[0];
        const name = firstMeta.name || firstMeta.label;
        if (!name) { setPlan(null); setError(null); setLoading(false); return; }
        // Attach the metadata slug (`name`) onto the full geometry so callers
        // that pass `plan.name` as `plan_name` (Boq/Carbon/Analyze Saved) still
        // resolve the correct saved file — PlanData itself only carries `label`.
        setError(null);
        try {
          const fullPlan = await api.getPlan(projectId, name);
          if (!cancelled) setPlan({ ...fullPlan, name });
        } catch (geoErr) {
          if (!cancelled) setPlan(firstMeta);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e?.message || 'Failed to load plan');
          setPlan(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [projectId]);

  return { plan, loading, error, projectId };
}