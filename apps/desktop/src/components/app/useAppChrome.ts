import { useEffect, useState } from "react";

import type { AppRoute } from "../../lib/appRoutes";
import { normalizeLegacyHash, resolveRoute, routeToHash } from "../../lib/appRoutes";

type UseAppChromeResult = {
  route: AppRoute;
  setRoute: React.Dispatch<React.SetStateAction<AppRoute>>;
  theme: "dark" | "light";
  setTheme: React.Dispatch<React.SetStateAction<"dark" | "light">>;
  showAbout: boolean;
  setShowAbout: React.Dispatch<React.SetStateAction<boolean>>;
  showBrandMenu: boolean;
  setShowBrandMenu: React.Dispatch<React.SetStateAction<boolean>>;
  handleNavigate: (nextRoute: AppRoute) => void;
};

export function useAppChrome(): UseAppChromeResult {
  const [route, setRoute] = useState<AppRoute>(() => resolveRoute(normalizeLegacyHash(window.location.hash)));
  const [theme, setTheme] = useState<"dark" | "light">(() => loadThemePreference());
  const [showBrandMenu, setShowBrandMenu] = useState(false);
  const [showAbout, setShowAbout] = useState(false);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    const syncRoute = () => {
      const normalizedHash = normalizeLegacyHash(window.location.hash);
      if (normalizedHash !== window.location.hash) {
        window.location.hash = normalizedHash;
        return;
      }

      const nextRoute = resolveRoute(normalizedHash);
      setRoute(nextRoute);
    };

    if (!window.location.hash) {
      window.location.hash = routeToHash("chat");
    } else {
      syncRoute();
    }

    window.addEventListener("hashchange", syncRoute);
    return () => {
      window.removeEventListener("hashchange", syncRoute);
    };
  }, []);

  function handleNavigate(nextRoute: AppRoute) {
    const nextHash = routeToHash(nextRoute);
    if (window.location.hash !== nextHash) {
      window.location.hash = nextHash;
      return;
    }

    setRoute(nextRoute);
  }

  return {
    route,
    setRoute,
    theme,
    setTheme,
    showAbout,
    setShowAbout,
    showBrandMenu,
    setShowBrandMenu,
    handleNavigate,
  };
}

function loadThemePreference(): "dark" | "light" {
  if (typeof window === "undefined") {
    return "dark";
  }
  const saved = localStorage.getItem("theme");
  if (saved === "light" || saved === "dark") {
    return saved;
  }
  if (window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches) {
    return "light";
  }
  return "dark";
}
