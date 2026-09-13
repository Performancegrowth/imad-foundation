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
    api.listPlans(projectId)
      .then(list => {
        // listPlans returns an array of {name, label, ...}; pick the first/most recent
        const first = Array.isArray(list) && list.length ? list[0] : list;
        setPlan(first || null);
        setError(null);
      })
      .catch(e => setError(e.response?.data?.detail || e.message || 'Could not load plan'))
      .finally(() => setLoading(false));
  }, [projectId]);

  return { plan, loading, error, projectId };
}
