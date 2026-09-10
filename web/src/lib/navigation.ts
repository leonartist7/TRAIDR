import { useEffect, useState } from "react";

export type AppRoute = "/" | "/scanner";

export function routeFromHash(hash: string): AppRoute {
  return hash === "#/scanner" ? "/scanner" : "/";
}

export function useHashRoute(): AppRoute {
  const [route, setRoute] = useState<AppRoute>(() => routeFromHash(window.location.hash));

  useEffect(() => {
    const update = () => setRoute(routeFromHash(window.location.hash));
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);

  return route;
}
